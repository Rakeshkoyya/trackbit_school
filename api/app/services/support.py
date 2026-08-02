"""The owner's two screens (V1-9, `D-87`) — *"who am I responsible for"* and
*"what's happened with Kabir, and what do I do next?"*

**`S-164` is the whole design.** This is the only screen in the product that
asks a teacher to type about one child, by hand, repeatedly — so it is also the
one most likely to be abandoned by week three. The answer is that the page
**opens already written**: the child's week is read from capture five other
teachers already did —

    attendance_exceptions   he wasn't there
    lesson_observations     "needs work, Reading aloud" (Anil, Tue P2)
    check_results           the C-band check he missed
    homework_results        Ex 4.2 not done
    session_student_logs    "finished two pages without help" (evening study)

— and she is asked only for the one thing nobody else knows: what she actually
did with him. Four fields, once a week (`S-165`/`D-87`). Value before data (P3).

Two lines that are load-bearing:

* **She proposes readiness; a test moves the band** (`D-76`). The owner is the
  person who knows he is ready, and also the person with an interest in him
  being ready.
* **No completion score, no streak, no comparison with other owners** (`S-170`).
  A teacher whose support log can cost her an appraisal writes a support log
  that flatters her, and the children handed to the best teacher are by
  construction the hardest ones.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.bands import SOURCE_LABEL, TIERS
from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AssessmentCycle,
    AssessmentScore,
    AttendanceException,
    CheckResult,
    ClassPeriod,
    DailyCheck,
    HomeworkAssignment,
    HomeworkResult,
    Intervention,
    LessonObservation,
    Membership,
    SchoolClass,
    SessionMeeting,
    SessionStudentLog,
    Student,
    StudentBand,
    Subject,
    SupportCheckpoint,
    User,
)
from app.schemas.bands import (
    BandDescriptorOut,
    CheckpointIn,
    CheckpointOut,
    SupportChild,
    SupportDayRow,
    SupportList,
    SupportStudentRow,
)
from app.services.bands import BandService
from app.services.school_clock import today_in

_WEEK_ROWS = 25


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _label(k: SchoolClass | None) -> str | None:
    if k is None:
        return None
    return f"{k.name}-{k.section}" if k.section else k.name


class SupportService:
    def __init__(self, db: Session):
        self.db = db

    # ── /support — her list (D-71 / D-77) ────────────────────────────────────
    def my_students(self, m: CurrentMember,
                    member_id: uuid.UUID | None = None) -> SupportList:
        """Her children, grouped by subject — ownership is per subject, so a
        child who is C in Hindi and C in Maths sits on two teachers' lists and
        neither is guessing whose he is (`D-77`)."""
        today = today_in(m.org.timezone)
        week = _monday(today)
        owner = member_id or m.membership.id
        if member_id and member_id != m.membership.id and not m.is_coordinator_up:
            raise ForbiddenError("You can only open your own support list.",
                                 code="not_your_list")

        rows = self.db.execute(
            select(Intervention, Student, Subject.name, SchoolClass)
            .join(Student, Student.id == Intervention.student_id)
            .outerjoin(Subject, Subject.id == Intervention.subject_id)
            .outerjoin(SchoolClass, SchoolClass.id == Student.class_id)
            .where(Intervention.org_id == m.org_id,
                   Intervention.owner_member_id == owner)
            .order_by(Subject.name, Student.full_name)).all()
        out = SupportList(as_of=today, week_start=week)
        if not rows:
            out.headline = ("No children are assigned to you yet. The admin assigns them "
                            "after a class is banded.")
            return out

        iv_ids = [iv.id for iv, _, _, _ in rows]
        checkpoints: dict[uuid.UUID, list[SupportCheckpoint]] = defaultdict(list)
        for cp in self.db.scalars(select(SupportCheckpoint).where(
                SupportCheckpoint.org_id == m.org_id,
                SupportCheckpoint.intervention_id.in_(iv_ids))
                .order_by(SupportCheckpoint.week_start.desc())):
            checkpoints[cp.intervention_id].append(cp)
        tiers = BandService(self.db).placements(m, [st.id for _, st, _, _ in rows])

        groups: dict[str, list[SupportStudentRow]] = defaultdict(list)
        done_this_week = 0
        active = 0
        for iv, st, subject_name, klass in rows:
            cps = checkpoints.get(iv.id, [])
            last = cps[0] if cps else None
            place = next((p for p in tiers.get(st.id, [])
                          if p.subject_id == iv.subject_id), None)
            row = SupportStudentRow(
                intervention_id=iv.id, student_id=st.id, full_name=st.full_name,
                class_label=_label(klass), subject_id=iv.subject_id,
                subject_name=subject_name, tier=place.tier if place else None,
                since=iv.created_at.date() if iv.created_at else None,
                checkins=len(cps),
                last_checkin=last.week_start if last else None,
                weeks_since_checkin=((week - last.week_start).days // 7) if last else None,
                checked_in_this_week=bool(last and last.week_start == week),
                ready_to_retest=bool(last and last.ready_to_retest),
                status=iv.status)
            if iv.status == "active":
                active += 1
                if row.checked_in_this_week:
                    done_this_week += 1
                groups[subject_name or "Support"].append(row)
            else:
                out.moved_on.append(row)

        out.groups = [{"subject_name": name, "rows": rows_}
                      for name, rows_ in sorted(groups.items())]
        # A finished week must read as finished — and nothing here is a
        # compliance score (`S-170`).
        overdue = [r for group in out.groups for r in group["rows"]
                   if (r.weeks_since_checkin or 99) >= 3]
        if not active:
            out.headline = "Everyone you were supporting has moved on. Nothing open."
        elif done_this_week >= active:
            out.headline = (f"All {active} checked in this week."
                            if active != 1 else "Your one child is checked in this week.")
        else:
            out.headline = f"{done_this_week} of your {active} checked in this week."
            if overdue:
                worst = min(overdue, key=lambda r: r.last_checkin or date.min)
                out.headline += (f" {worst.full_name} hasn't been checked in "
                                 f"{worst.weeks_since_checkin} weeks.")
        return out

    # ── /support/[id] — the child, opening already written (S-164) ───────────
    def child(self, m: CurrentMember, intervention_id: uuid.UUID,
              week_start: date | None = None) -> SupportChild:
        iv = self.db.scalar(select(Intervention).where(
            Intervention.id == intervention_id, Intervention.org_id == m.org_id))
        if iv is None:
            raise NotFoundError("Support plan")
        self._assert_owner(m, iv)
        student = self.db.get(Student, iv.student_id)
        klass = self.db.get(SchoolClass, student.class_id) if student.class_id else None
        subject = self.db.get(Subject, iv.subject_id) if iv.subject_id else None
        today = today_in(m.org.timezone)
        week = week_start or _monday(today)

        bands = BandService(self.db)
        place = next((p for p in bands.placements(m, [student.id]).get(student.id, [])
                      if p.subject_id == iv.subject_id), None)
        band_row = self.db.scalar(
            select(StudentBand).where(
                StudentBand.org_id == m.org_id, StudentBand.student_id == student.id,
                StudentBand.subject_id == iv.subject_id)
            .order_by(StudentBand.created_at.desc()).limit(1))
        owner_name = self.db.scalar(
            select(User.name).join(Membership, Membership.user_id == User.id)
            .where(Membership.id == iv.owner_member_id)) if iv.owner_member_id else None

        out = SupportChild(
            intervention_id=iv.id, student_id=student.id, full_name=student.full_name,
            class_label=_label(klass), subject_id=iv.subject_id,
            subject_name=subject.name if subject else None,
            tier=place.tier if place else None,
            since=band_row.created_at.date() if band_row and band_row.created_at else None,
            source=band_row.source if band_row else None,
            owner_name=owner_name, goal_text=iv.goal_text,
            exit_criterion=iv.exit_criterion, status=iv.status,
            week_start=week)

        # `S-166`: the letter never appears without its sentence — and both the
        # band he is in and the one he is working towards are on screen.
        if iv.subject_id and subject:
            texts = bands.descriptor_text(m)
            out.descriptors = [BandDescriptorOut(
                subject_id=iv.subject_id, subject_name=subject.name, tier=tier,
                text=texts[(iv.subject_id, tier)])
                for tier in TIERS if (iv.subject_id, tier) in texts]
        head = []
        if place and subject:
            head.append(f"Band {place.tier} in {subject.name}"
                        + (f" since {out.since:%d %b}" if out.since else "")
                        + (f" ({SOURCE_LABEL.get(out.source, '')})" if out.source else "")
                        + ".")
        if iv.exit_criterion:
            head.append(f"Moves to {iv.target_tier} when: {iv.exit_criterion}")
        elif iv.goal_text:
            head.append(iv.goal_text)
        out.headline = " ".join(head)

        out.week = self._week(m, student, week)
        out.checkpoints = self._checkpoints(m, iv.id)
        latest = self._latest_test(m, student.id, iv.subject_id)
        if latest:
            out.latest_pct, out.latest_test = latest
        return out

    def _week(self, m: CurrentMember, student: Student, week: date) -> list[SupportDayRow]:
        """His week as his teachers already recorded it — **nothing here was
        typed twice** (`S-164`). Five reads, one week, no new capture."""
        end = week + timedelta(days=6)
        rows: list[SupportDayRow] = []

        for period, status in self.db.execute(
                select(ClassPeriod, AttendanceException.status)
                .join(AttendanceException, AttendanceException.period_id == ClassPeriod.id)
                .where(AttendanceException.student_id == student.id,
                       ClassPeriod.org_id == m.org_id,
                       ClassPeriod.date >= week, ClassPeriod.date <= end)
                .order_by(ClassPeriod.date, ClassPeriod.period_no)).all():
            rows.append(SupportDayRow(
                date=period.date, kind="absent" if status == "absent" else "late",
                text=("absent" if status == "absent" else "came late")
                     + f" · period {period.period_no}"))

        for obs, teacher in self.db.execute(
                select(LessonObservation, User.name)
                .outerjoin(Membership, Membership.id == LessonObservation.member_id)
                .outerjoin(User, User.id == Membership.user_id)
                .where(LessonObservation.org_id == m.org_id,
                       LessonObservation.student_id == student.id,
                       LessonObservation.date >= week, LessonObservation.date <= end)
                .order_by(LessonObservation.date)).all():
            label = "needs work" if obs.rating == "needs_work" else "excellent"
            text = f"{label}, “{obs.concept or obs.section}”"
            if obs.note:
                text += f" — {obs.note}"
            if teacher:
                text += f" ({teacher})"
            rows.append(SupportDayRow(date=obs.date, kind="observation", text=text))

        for check, result in self.db.execute(
                select(DailyCheck, CheckResult)
                .join(CheckResult, CheckResult.check_id == DailyCheck.id)
                .where(DailyCheck.org_id == m.org_id, CheckResult.student_id == student.id,
                       DailyCheck.date >= week, DailyCheck.date <= end)
                .order_by(DailyCheck.date)).all():
            verb = "check missed" if result.status == "not_done" else "check note"
            rows.append(SupportDayRow(
                date=check.date, kind="check",
                text=f"{verb} — “{check.description}”"
                     + (f" ({result.note})" if result.note else "")))

        for assignment, result in self.db.execute(
                select(HomeworkAssignment, HomeworkResult)
                .join(HomeworkResult, HomeworkResult.assignment_id == HomeworkAssignment.id)
                .where(HomeworkAssignment.org_id == m.org_id,
                       HomeworkResult.student_id == student.id,
                       HomeworkAssignment.date >= week, HomeworkAssignment.date <= end)
                .order_by(HomeworkAssignment.date)).all():
            rows.append(SupportDayRow(
                date=assignment.date, kind="homework",
                text=f"homework {result.status.replace('_', ' ')} — {assignment.text}"))

        for meeting, log in self.db.execute(
                select(SessionMeeting, SessionStudentLog)
                .join(SessionStudentLog, SessionStudentLog.meeting_id == SessionMeeting.id)
                .where(SessionMeeting.org_id == m.org_id,
                       SessionStudentLog.student_id == student.id,
                       SessionMeeting.date >= week, SessionMeeting.date <= end)
                .order_by(SessionMeeting.date)).all():
            rows.append(SupportDayRow(
                date=meeting.date, kind="session",
                text=f"evening study — “{log.note}”"))

        rows.sort(key=lambda r: (r.date, r.kind))
        return rows[:_WEEK_ROWS]

    def _checkpoints(self, m: CurrentMember, intervention_id: uuid.UUID) -> list[CheckpointOut]:
        rows = self.db.execute(
            select(SupportCheckpoint, User.name)
            .outerjoin(Membership, Membership.id == SupportCheckpoint.author_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .where(SupportCheckpoint.org_id == m.org_id,
                   SupportCheckpoint.intervention_id == intervention_id)
            .order_by(SupportCheckpoint.week_start.desc(),
                      SupportCheckpoint.created_at.desc())).all()
        return [CheckpointOut(
            id=cp.id, week_start=cp.week_start, worked_on=cp.worked_on,
            what_changed=cp.what_changed, next_step=cp.next_step,
            ready_to_retest=cp.ready_to_retest, author_name=name,
            created_at=cp.created_at) for cp, name in rows]

    def _latest_test(self, m: CurrentMember, student_id: uuid.UUID,
                     subject_id: uuid.UUID | None) -> tuple[float, str] | None:
        """`S-178`: what a *ready to re-test* claim rests on. Read-only — the
        band still moves on a test, never on this number."""
        if subject_id is None:
            return None
        row = self.db.execute(
            select(AssessmentScore.score, AssessmentScore.max_score, AssessmentCycle.name)
            .join(AssessmentCycle, AssessmentCycle.id == AssessmentScore.cycle_id)
            .where(AssessmentScore.org_id == m.org_id,
                   AssessmentScore.student_id == student_id,
                   AssessmentScore.subject_id == subject_id)
            .order_by(AssessmentCycle.date.desc()).limit(1)).first()
        if not row or not row[1]:
            return None
        return round(float(row[0]) / float(row[1]) * 100, 1), row[2]

    # ── the weekly check-in (D-87 / S-165) ───────────────────────────────────
    def check_in(self, m: CurrentMember, intervention_id: uuid.UUID,
                 body: CheckpointIn) -> SupportChild:
        """One append row (law 3). Blank fields are allowed on purpose: a week
        where nothing happened is a true answer, and a required field is how a
        weekly habit turns into fiction."""
        iv = self.db.scalar(select(Intervention).where(
            Intervention.id == intervention_id, Intervention.org_id == m.org_id))
        if iv is None:
            raise NotFoundError("Support plan")
        self._assert_owner(m, iv)
        week = body.week_start or _monday(today_in(m.org.timezone))
        self.db.add(SupportCheckpoint(
            org_id=m.org_id, intervention_id=iv.id, week_start=week,
            worked_on=(body.worked_on or "").strip() or None,
            what_changed=(body.what_changed or "").strip() or None,
            next_step=(body.next_step or "").strip() or None,
            ready_to_retest=body.ready_to_retest,
            author_member_id=m.membership.id))
        self.db.flush()
        return self.child(m, iv.id, week)

    def close(self, m: CurrentMember, intervention_id: uuid.UUID, status: str,
              outcome_note: str | None) -> SupportChild:
        """**The fix the whole module was waiting on** (`S-180`).

        Nothing could set `status='achieved'`, and `RecommendationsService`
        filters on `status == 'active'` — so a goal met in July kept injecting a
        targeted daily check into the period card in March. Closing it stops the
        check and records what happened."""
        iv = self.db.scalar(select(Intervention).where(
            Intervention.id == intervention_id, Intervention.org_id == m.org_id))
        if iv is None:
            raise NotFoundError("Support plan")
        self._assert_owner(m, iv)
        iv.status = status
        iv.closed_at = datetime.now(UTC)
        iv.outcome_note = (outcome_note or "").strip() or None
        self.db.flush()
        return self.child(m, iv.id)

    def _assert_owner(self, m: CurrentMember, iv: Intervention) -> None:
        """The owner, or an admin. Not other owners' children (`S-170`)."""
        if m.is_coordinator_up or iv.owner_member_id == m.membership.id:
            return
        raise ForbiddenError("This child is another teacher's to support.",
                             code="not_your_student")
