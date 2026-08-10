"""Capture for a non-subject period (TT-2) — the block's own surface.

A block is a `Session` on the timetable (`D-112`). Its roll, its per-student
logs, its memories and its class log are all `SessionService`'s, and this module
does not reimplement any of them — it opens the meeting and delegates, so the
evening hostel screen and the 15:30 homework period write to exactly the same
rows.

What is genuinely new is the homework class: **class → subject → the homework
that is live tonight → the books**. Its verdicts go to `homework_results`, the
canonical store behind `core/homework_verdict.py`, the parent portal and every
insight — never to a second column that would then disagree with the morning.

Authorization is `TimetableService.may_take_block`: the block's staff, its
owner, or an admin. The warden running homework class teaches none of these
subjects, which is exactly why `ClassroomService._can_touch_homework` grew a
block arm rather than this module writing rows itself.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from app.core import day_shape
from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    ClassSubject,
    HomeworkAssignment,
    HomeworkCheck,
    SchoolClass,
    SessionMeeting,
    Subject,
)
from app.models import Session as SessionModel
from app.schemas.blocks import BlockAssignment, BlockHomeworkOut, SubjectOption
from app.schemas.classroom import HomeworkCheckIn, HomeworkSheetOut
from app.schemas.sessions import MeetingOut
from app.services.classroom import ClassroomService
from app.services.sessions import SessionService, open_tonight
from app.services.timetable import TimetableService


class BlockService:
    def __init__(self, db: OrmSession):
        self.db = db
        self.sessions = SessionService(db)
        self.classroom = ClassroomService(db)
        self.timetable = TimetableService(db)

    # ── the meeting ──────────────────────────────────────────────────────────
    def open(self, m: CurrentMember, session_id: uuid.UUID,
             on_date: date | None = None) -> MeetingOut:
        """Get-or-create today's meeting for this block, and return its card."""
        self.timetable.assert_may_take_block(m, session_id)
        return self.sessions.open_meeting(m, session_id, on_date)

    def guard(self, m: CurrentMember, meeting_id: uuid.UUID) -> SessionModel:
        """Assert the caller may run this meeting's block; return the block.

        Public because the thin endpoints call it before delegating to
        `SessionService` (law 6 — endpoints do plumbing), and a private name
        reached from a router is just a private name that lies.
        """
        return self._meeting(m, meeting_id)[1]

    def _meeting(self, m: CurrentMember,
                 meeting_id: uuid.UUID) -> tuple[SessionMeeting, SessionModel]:
        meeting = self.db.scalar(select(SessionMeeting).where(
            SessionMeeting.id == meeting_id, SessionMeeting.org_id == m.org_id))
        if meeting is None:
            raise NotFoundError("Meeting")
        block = self.db.scalar(select(SessionModel).where(
            SessionModel.id == meeting.session_id, SessionModel.org_id == m.org_id))
        if block is None:
            raise NotFoundError("Block")
        self.timetable.assert_may_take_block(m, block.id)
        return meeting, block

    # ── the homework class (TT-2 §3) ─────────────────────────────────────────
    def _assert_homework_block(self, block: SessionModel) -> None:
        if not day_shape.capture_for(block.kind).homework_check:
            raise ValidationError(
                f"A {day_shape.label_for(block.kind).lower()} block does not check homework.",
                code="no_homework_check")

    def _block_class_ids(self, m: CurrentMember, block: SessionModel) -> set[uuid.UUID]:
        """Which classes this block covers.

        Deliberately the classes it is *linked to* — through the grid or through
        `session_classes` — plus the classes of any hand-added students. NOT the
        classes that happen to have a child on tonight's roster: a class whose
        students have not been enrolled yet would then silently drop out of the
        tabs, and the warden would be told the class "is not in this block"
        while looking at it on the timetable. Empty is a state, not an absence.
        """
        from app.models import SessionClass, TimetableSlot  # noqa: PLC0415
        ids = {
            cid for (cid,) in self.db.execute(
                select(SessionClass.class_id).where(
                    SessionClass.session_id == block.id)).all()
        }
        ids |= {
            cid for (cid,) in self.db.execute(
                select(TimetableSlot.class_id.distinct()).where(
                    TimetableSlot.org_id == m.org_id,
                    TimetableSlot.session_id == block.id,
                    TimetableSlot.effective_to.is_(None))).all()
        }
        ids |= {st.class_id for st, explicit in self.sessions.roster(m.org_id, block)
                if explicit and st.class_id}
        return ids

    def homework(self, m: CurrentMember, meeting_id: uuid.UUID,
                 class_id: uuid.UUID | None = None,
                 class_subject_id: uuid.UUID | None = None) -> BlockHomeworkOut:
        """The subject tabs for one class, and what is live tonight under them."""
        meeting, block = self._meeting(m, meeting_id)
        self._assert_homework_block(block)

        allowed = self._block_class_ids(m, block)
        if class_id is not None and class_id not in allowed:
            raise ValidationError("That class is not in this block tonight.",
                                  code="class_not_in_block")
        if class_id is None:
            if class_subject_id is None:
                return BlockHomeworkOut(meeting_id=meeting.id, date=meeting.date)
            owner = self.db.scalar(select(ClassSubject.class_id).where(
                ClassSubject.id == class_subject_id, ClassSubject.org_id == m.org_id))
            if owner is None or owner not in allowed:
                raise ValidationError("That subject is not in this block tonight.",
                                      code="subject_not_in_block")
            class_id = owner

        cs_rows = self.db.execute(
            select(ClassSubject.id, Subject.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id)
            .order_by(Subject.name)
        ).all()
        cs_ids = [cs_id for cs_id, _n in cs_rows]
        if class_subject_id is not None and class_subject_id not in cs_ids:
            raise ValidationError("That subject is not taught in this class.",
                                  code="subject_not_in_class")

        live: list[HomeworkAssignment] = list(self.db.scalars(
            select(HomeworkAssignment).where(
                HomeworkAssignment.org_id == m.org_id,
                HomeworkAssignment.class_subject_id.in_(cs_ids),
                open_tonight(meeting.date))
            .order_by(HomeworkAssignment.date.desc()))) if cs_ids else []

        checked_ids = set(self.db.scalars(
            select(HomeworkCheck.assignment_id).where(
                HomeworkCheck.assignment_id.in_([a.id for a in live])))) if live else set()
        name_of = dict(cs_rows)
        per_cs: dict[uuid.UUID, int] = {}
        for a in live:
            per_cs[a.class_subject_id] = per_cs.get(a.class_subject_id, 0) + 1

        return BlockHomeworkOut(
            meeting_id=meeting.id, date=meeting.date, class_id=class_id,
            class_subject_id=class_subject_id,
            subjects=[SubjectOption(class_subject_id=cs_id, subject_name=name,
                                    open_count=per_cs.get(cs_id, 0))
                      for cs_id, name in cs_rows],
            assignments=[
                BlockAssignment(
                    assignment_id=a.id, subject_name=name_of.get(a.class_subject_id, ""),
                    text=a.text, assigned_on=a.date, due_date=a.due_date,
                    checked=a.id in checked_ids, student_id=a.student_id)
                for a in live
                if class_subject_id is None or a.class_subject_id == class_subject_id
            ])

    def _assert_assignment_in_block(self, m: CurrentMember, block: SessionModel,
                                    assignment_id: uuid.UUID) -> None:
        """The assignment must belong to a class this block actually holds.

        Without it, `block_id` would be a skeleton key: any staff member of any
        homework block could check any assignment in the school just by naming
        one.
        """
        owner = self.db.scalar(
            select(ClassSubject.class_id)
            .join(HomeworkAssignment,
                  HomeworkAssignment.class_subject_id == ClassSubject.id)
            .where(HomeworkAssignment.id == assignment_id,
                   HomeworkAssignment.org_id == m.org_id))
        if owner is None:
            raise NotFoundError("Homework")
        if owner not in self._block_class_ids(m, block):
            raise ValidationError("That homework is not for a class in this block.",
                                  code="homework_not_in_block")

    def sheet(self, m: CurrentMember, meeting_id: uuid.UUID,
              assignment_id: uuid.UUID) -> HomeworkSheetOut:
        _meeting, block = self._meeting(m, meeting_id)
        self._assert_homework_block(block)
        self._assert_assignment_in_block(m, block, assignment_id)
        return self.classroom.homework_sheet(m, assignment_id, block_id=block.id)

    def check(self, m: CurrentMember, meeting_id: uuid.UUID, assignment_id: uuid.UUID,
              body: HomeworkCheckIn) -> HomeworkSheetOut:
        """Record the verdicts. Saving IS the act of checking (TT-2 §3).

        Until it is saved the assignment has no `homework_checks` row, so every
        child reads `not_checked` — worth nothing and outside the denominator.
        That is what "default not done" has to mean if the screen is not to cost
        one tap per child to reach the ordinary case (P1v2).
        """
        _meeting, block = self._meeting(m, meeting_id)
        self._assert_homework_block(block)
        self._assert_assignment_in_block(m, block, assignment_id)
        return self.classroom.check_homework(m, assignment_id, body, block_id=block.id)

    # ── labels ───────────────────────────────────────────────────────────────
    def class_label(self, class_id: uuid.UUID) -> str:
        klass = self.db.get(SchoolClass, class_id)
        return f"{klass.name}{klass.section or ''}" if klass else "?"
