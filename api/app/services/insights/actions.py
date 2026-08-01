"""The action rail (DASH3 §5) — every button on every red row.

Two rules, and they are the whole design:

  1. **An action calls the existing service. It never re-implements a write.**
     Reminding a guardian is `notify_guardians`; assigning a follow-up is
     `TaskService.create`; extending a due date is `TaskService.edit`. The rail
     is a shortcut through the app, not a second way into the database — so
     every guard, notification and event those services already carry rides
     along for free.

  2. **Every action appends a `followup_actions` row.** That log is what makes
     the rail idempotent-in-practice: each red row reads its own history for
     today and renders "already reminded" instead of firing a second time. Three
     people looking at the same absent student in the same morning is the normal
     case, not the edge case, and without this the parent gets three messages.

Guardian messages are plain text and **never carry band information** (P4). The
only thing the rail can say about a student is that they were absent.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    Board,
    BoardMember,
    FollowupAction,
    Guardian,
    Membership,
    SchoolClass,
    Student,
    TaskInstance,
    User,
)
from app.schemas.insights import ActionIn, ActionOut, FollowupRow
from app.schemas.task import TaskCreateRequest, TaskUpdateRequest
from app.services.notify_guardian import notify_guardians
from app.services.school_clock import today_in
from app.services.substitution import SubstitutionService
from app.services.task import TaskService

FOLLOWUPS_BOARD_NAME = "Follow-ups"


def ensure_followups_board(db: Session, m: CurrentMember) -> Board:
    """The one board every rail-created task lands on (DASH3 PR-0).

    Public with `task_scope='assigned'`: each teacher sees only the rows assigned
    to them, the admin sees all. Deliberately NOT a private per-teacher board —
    law 5 says admins do not see private boards they aren't members of, so the
    admin would be firing tasks into a board they could never then track.
    """
    board = db.scalar(
        select(Board).where(Board.org_id == m.org_id, Board.name == FOLLOWUPS_BOARD_NAME,
                            Board.archived_at.is_(None)))
    if board is not None:
        return board
    board = Board(
        org_id=m.org_id, name=FOLLOWUPS_BOARD_NAME, visibility="public",
        task_scope="assigned", category="tasks",
        created_by=m.user_id, owner_id=m.user_id)
    db.add(board)
    db.flush()
    db.add(BoardMember(board_id=board.id, user_id=m.user_id))
    db.flush()
    return board


class ActionService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_in(m.org.timezone)

    # ── the audit trail ──────────────────────────────────────────────────────
    def _append(self, m: CurrentMember, kind: str, subject_type: str,
                subject_id: uuid.UUID | None, *, target_member_id: uuid.UUID | None = None,
                detail: dict | None = None) -> None:
        self.db.add(FollowupAction(
            org_id=m.org_id, kind=kind, subject_type=subject_type, subject_id=subject_id,
            actor_member_id=m.membership.id, target_member_id=target_member_id,
            detail=detail, created_at=datetime.now(UTC)))
        self.db.flush()

    def done_today(self, org_id: uuid.UUID, subject_type: str, on: date,
                   tz: str) -> dict[tuple[str, uuid.UUID | None], datetime]:
        """(kind, subject_id) → when, for everything fired on `on`.

        One query for a whole red list, so a 30-row board does not do 30 lookups
        to answer "have we already done this today".
        """
        from zoneinfo import ZoneInfo  # noqa: PLC0415

        start = datetime.combine(on, datetime.min.time(), tzinfo=ZoneInfo(tz))
        rows = self.db.execute(
            select(FollowupAction.kind, FollowupAction.subject_id, FollowupAction.created_at)
            .where(FollowupAction.org_id == org_id,
                   FollowupAction.subject_type == subject_type,
                   FollowupAction.created_at >= start,
                   FollowupAction.created_at < start + timedelta(days=1))
        ).all()
        return {(kind, sid): when for kind, sid, when in rows}

    def history(self, m: CurrentMember, subject_type: str | None = None,
                subject_id: uuid.UUID | None = None, limit: int = 50) -> list[FollowupRow]:
        q = select(FollowupAction).where(FollowupAction.org_id == m.org_id)
        if subject_type:
            q = q.where(FollowupAction.subject_type == subject_type)
        if subject_id:
            q = q.where(FollowupAction.subject_id == subject_id)
        rows = list(self.db.scalars(
            q.order_by(FollowupAction.created_at.desc()).limit(min(limit, 200))))
        member_ids = {r.actor_member_id for r in rows} | {r.target_member_id for r in rows}
        member_ids.discard(None)
        names = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name).join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(member_ids))).all()
        } if member_ids else {}
        return [
            FollowupRow(
                id=r.id, kind=r.kind, subject_type=r.subject_type, subject_id=r.subject_id,
                actor_name=names.get(r.actor_member_id),
                target_name=names.get(r.target_member_id),
                detail=r.detail, created_at=r.created_at)
            for r in rows
        ]

    # ── the verbs ────────────────────────────────────────────────────────────
    def run(self, m: CurrentMember, kind: str, body: ActionIn) -> ActionOut:
        handler = {
            "guardian_reminded": self._remind_guardian,
            "followup_assigned": self._assign_followup,
            "substitute_assigned": self._assign_substitute,
            "task_reassigned": self._reassign_task,
            "task_extended": self._extend_task,
            "nudged": self._nudge,
        }.get(kind)
        if handler is None:
            raise ValidationError(f"Unknown action '{kind}'.", code="unknown_action")
        return handler(m, body)

    def _student(self, m: CurrentMember, student_id: uuid.UUID | None) -> Student:
        if student_id is None:
            raise ValidationError("This action needs a student.")
        s = self.db.scalar(
            select(Student).where(Student.id == student_id, Student.org_id == m.org_id))
        if s is None:
            raise NotFoundError("Student")
        return s

    def _remind_guardian(self, m: CurrentMember, body: ActionIn) -> ActionOut:
        student = self._student(m, body.student_id)
        today = self._today(m)
        already = self.done_today(m.org_id, "student", today, m.org.timezone)
        if ("guardian_reminded", student.id) in already:
            return ActionOut(
                kind="guardian_reminded", ok=True, already_done=True,
                subject_type="student", subject_id=student.id,
                message=f"{student.full_name}'s guardians were already reminded today.")

        guardians = list(self.db.scalars(
            select(Guardian).where(Guardian.org_id == m.org_id,
                                   Guardian.student_id == student.id)))
        if not guardians:
            raise ValidationError(f"{student.full_name} has no guardian on file.",
                                  code="no_guardian")
        # Plain text, and nothing about tiers or bands — ever (P4).
        text = (body.message or "").strip() or (
            f"{m.org.name}: {student.full_name} has been absent from school. "
            "Please let the class teacher know if everything is alright.")
        sent = notify_guardians([(g.phone, g.notify_opt_out) for g in guardians], text)
        self._append(m, "guardian_reminded", "student", student.id,
                     detail={"sent": sent, "message": text})
        return ActionOut(
            kind="guardian_reminded", ok=True, subject_type="student", subject_id=student.id,
            message=(f"Reminded {sent} guardian{'s' if sent != 1 else ''}."
                     if sent else "No guardian could be reached — check phone numbers."))

    def _assign_followup(self, m: CurrentMember, body: ActionIn) -> ActionOut:
        """Create a task on the Follow-ups board, assigned to a real person.

        Defaults to the class teacher of the student the row is about, because
        that is who would make the call anyway — but an explicit member wins.
        """
        title = (body.title or "").strip()
        subject_id = body.student_id or body.member_id
        subject_type = "student" if body.student_id else "member"
        assignee_user_id: uuid.UUID | None = None
        target_member_id: uuid.UUID | None = body.member_id

        if body.user_id is not None:
            assignee_user_id = body.user_id
        elif body.member_id is not None:
            assignee_user_id = self.db.scalar(
                select(Membership.user_id).where(Membership.id == body.member_id,
                                                 Membership.org_id == m.org_id))
        elif body.student_id is not None:
            student = self._student(m, body.student_id)
            if not title:
                title = f"Call {student.full_name}'s parent"
            teacher_member_id = self.db.scalar(
                select(SchoolClass.class_teacher_member_id)
                .where(SchoolClass.id == student.class_id)) if student.class_id else None
            if teacher_member_id:
                target_member_id = teacher_member_id
                assignee_user_id = self.db.scalar(
                    select(Membership.user_id).where(Membership.id == teacher_member_id))
        if not title:
            raise ValidationError("A follow-up needs a title.")

        today = self._today(m)
        already = self.done_today(m.org_id, subject_type, today, m.org.timezone)
        if subject_id is not None and ("followup_assigned", subject_id) in already:
            return ActionOut(
                kind="followup_assigned", ok=True, already_done=True,
                subject_type=subject_type, subject_id=subject_id,
                message="A follow-up was already assigned for this today.")

        board = ensure_followups_board(self.db, m)
        task = TaskService(self.db).create(m, TaskCreateRequest(
            board_id=board.id, title=title[:255], description=body.note,
            assignee_id=assignee_user_id,
            due_at=body.due_at or datetime.combine(
                today + timedelta(days=1), datetime.min.time(), tzinfo=UTC)))
        self._append(m, "followup_assigned", subject_type, subject_id,
                     target_member_id=target_member_id,
                     detail={"task_id": str(task.id), "title": title, "board": board.name})
        return ActionOut(
            kind="followup_assigned", ok=True, subject_type=subject_type, subject_id=subject_id,
            task_id=task.id,
            message=f"Follow-up created on {board.name}"
                    + (" and assigned." if assignee_user_id else " (unassigned)."))

    def _assign_substitute(self, m: CurrentMember, body: ActionIn) -> ActionOut:
        if body.substitution is None:
            raise ValidationError("This action needs the period to cover.")
        out = SubstitutionService(self.db).create(m, body.substitution)
        self._append(m, "substitute_assigned", "member", body.substitution.absent_member_id,
                     target_member_id=out.substitute_member_id,
                     detail={"substitution_id": str(out.id), "date": str(out.date),
                             "period_no": out.period_no, "class_label": out.class_label})
        return ActionOut(
            kind="substitute_assigned", ok=True, subject_type="member",
            subject_id=body.substitution.absent_member_id, substitution=out,
            message=f"{out.substitute_name or 'Substitute'} is covering "
                    f"{out.class_label} period {out.period_no}.")

    def _task(self, m: CurrentMember, task_id: uuid.UUID | None) -> TaskInstance:
        if task_id is None:
            raise ValidationError("This action needs a task.")
        t = self.db.scalar(
            select(TaskInstance).where(TaskInstance.id == task_id,
                                       TaskInstance.org_id == m.org_id))
        if t is None:
            raise NotFoundError("Task")
        return t

    def _reassign_task(self, m: CurrentMember, body: ActionIn) -> ActionOut:
        task = self._task(m, body.task_id)
        user_id = body.user_id
        if user_id is None and body.member_id is not None:
            user_id = self.db.scalar(
                select(Membership.user_id).where(Membership.id == body.member_id,
                                                 Membership.org_id == m.org_id))
        if user_id is None:
            raise ValidationError("Pick who the task should move to.")
        TaskService(self.db).reassign(m, task.id, user_id)
        self._append(m, "task_reassigned", "task", task.id,
                     detail={"to_user_id": str(user_id), "title": task.title})
        return ActionOut(kind="task_reassigned", ok=True, subject_type="task",
                         subject_id=task.id, task_id=task.id, message="Task reassigned.")

    def _extend_task(self, m: CurrentMember, body: ActionIn) -> ActionOut:
        task = self._task(m, body.task_id)
        due = body.due_at or (
            (task.due_at or datetime.now(UTC)) + timedelta(days=1))
        TaskService(self.db).edit(m, task.id, TaskUpdateRequest(due_at=due))
        self._append(m, "task_extended", "task", task.id,
                     detail={"due_at": due.isoformat(), "title": task.title})
        return ActionOut(kind="task_extended", ok=True, subject_type="task",
                         subject_id=task.id, task_id=task.id,
                         message=f"Due date moved to {due:%d %b}.")

    def _nudge(self, m: CurrentMember, body: ActionIn) -> ActionOut:
        """A gentle "still waiting on you 🙂" — never "you failed".

        Reuses `NudgeService`, which already dedupes within 4 hours, so the rail
        cannot be used to pester even by an admin refreshing the board.
        """
        from app.services.nudge import NudgeService  # noqa: PLC0415

        user_id = body.user_id
        if user_id is None and body.member_id is not None:
            user_id = self.db.scalar(
                select(Membership.user_id).where(Membership.id == body.member_id,
                                                 Membership.org_id == m.org_id))
        if user_id is None:
            raise ValidationError("Pick who to nudge.")
        res = NudgeService(self.db).nudge(m, user_id)
        self._append(m, "nudged", "member", body.member_id, target_member_id=body.member_id,
                     detail={"sent": res.sent, "overdue_count": res.overdue_count,
                             "reason": res.reason})
        message = ("Nudge sent." if res.sent
                   else "Nothing overdue to nudge about."
                   if res.reason == "nothing_overdue"
                   else "Already nudged recently — try again later.")
        return ActionOut(kind="nudged", ok=res.sent, subject_type="member",
                         subject_id=body.member_id, message=message,
                         already_done=not res.sent and res.reason != "nothing_overdue")
