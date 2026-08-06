"""Period cover for an absent teacher (DASH3 PR-2).

This is the P2 shape applied to a single period: **the substitution is the plan,
`class_periods.teacher_member_id` is the actual.** Assigning a cover does not
claim the period happened — it puts the period into someone's My Day so that it
can. What actually took place is still whatever the person who opened the period
captured.

Two rules the service enforces, because an unenforced substitution is worse than
none at all:

  * **The substitute must genuinely be free.** Already teaching that period,
    already covering another class that period, or marked absent/on leave today —
    each is refused with the reason, not silently accepted. A double-booked
    substitute is how a period ends up with nobody in it.
  * **Cancelling appends, it never deletes.** `cancelled_at` is stamped and the
    row stays, so "we moved the cover twice this morning" is still readable at
    4pm. The unique index is partial (live rows only), so the period can be
    re-covered afterwards.

The read side is deliberately tiny — `for_teacher` is what My Day unions in, and
`covers` is what lets the period card open for someone who does not teach the
class. Both are one query.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.staff import not_operator
from app.models import (
    AcademicYear,
    ClassSubject,
    LeaveRequest,
    Membership,
    PeriodSubstitution,
    SchoolClass,
    StaffAbsence,
    StaffAttendanceDay,
    Subject,
    TimetableSlot,
    User,
)
from app.schemas.insights import SubstitutionIn, SubstitutionOut
from app.services import notifications
from app.services.school_clock import half_day_periods


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


def covers_between(db: Session, org_id: uuid.UUID, start: date, end: date,
                   member_id: uuid.UUID | None = None,
                   ) -> dict[uuid.UUID, dict[tuple[date, int], tuple[str, str | None]]]:
    """Live cover assignments in [start, end]: substitute → (date, period_no) →
    (class_label, subject_name).

    THE one read for "which periods is X covering" (ux §9). The teacher's own
    week (Q-37), the admin's day grid (S-72) and the live board all render this
    rather than re-deriving it — before this existed, a teacher covering three
    periods showed three free cells on two different screens.
    """
    q = select(PeriodSubstitution).where(
        PeriodSubstitution.org_id == org_id,
        PeriodSubstitution.date >= start, PeriodSubstitution.date <= end,
        PeriodSubstitution.cancelled_at.is_(None))
    if member_id is not None:
        q = q.where(PeriodSubstitution.substitute_member_id == member_id)
    rows = list(db.scalars(q))
    if not rows:
        return {}
    labels = {
        cid: _label(name, section) for cid, name, section in db.execute(
            select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
            .where(SchoolClass.id.in_({r.class_id for r in rows}))).all()
    }
    subjects = {
        cs_id: name for cs_id, name in db.execute(
            select(ClassSubject.id, Subject.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.id.in_({r.class_subject_id for r in rows
                                        if r.class_subject_id}))).all()
    }
    out: dict[uuid.UUID, dict[tuple[date, int], tuple[str, str | None]]] = {}
    for r in rows:
        out.setdefault(r.substitute_member_id, {})[(r.date, r.period_no)] = (
            labels.get(r.class_id, "?"), subjects.get(r.class_subject_id))
    return out


class SubstitutionService:
    def __init__(self, db: Session):
        self.db = db
        self._half_cache: dict[str, set[int]] = {}

    # ── reads ────────────────────────────────────────────────────────────────
    def live(self, org_id: uuid.UUID, on: date) -> list[PeriodSubstitution]:
        return list(self.db.scalars(
            select(PeriodSubstitution).where(
                PeriodSubstitution.org_id == org_id, PeriodSubstitution.date == on,
                PeriodSubstitution.cancelled_at.is_(None))))

    def for_teacher(self, org_id: uuid.UUID, member_id: uuid.UUID,
                    on: date) -> list[PeriodSubstitution]:
        return [s for s in self.live(org_id, on) if s.substitute_member_id == member_id]

    def covers(self, org_id: uuid.UUID, member_id: uuid.UUID, class_id: uuid.UUID,
               on: date, period_no: int | None) -> bool:
        """Is this member covering this period today? The period card's access
        check calls it, so a substitute can actually open the card they were
        given — without it the period appears in My Day and refuses to open."""
        q = select(PeriodSubstitution.id).where(
            PeriodSubstitution.org_id == org_id, PeriodSubstitution.date == on,
            PeriodSubstitution.class_id == class_id,
            PeriodSubstitution.substitute_member_id == member_id,
            PeriodSubstitution.cancelled_at.is_(None))
        if period_no is not None:
            q = q.where(PeriodSubstitution.period_no == period_no)
        return self.db.scalar(q.limit(1)) is not None

    def _out(self, s: PeriodSubstitution) -> SubstitutionOut:
        klass = self.db.get(SchoolClass, s.class_id)
        subject_name = None
        if s.class_subject_id:
            subject_name = self.db.scalar(
                select(Subject.name).join(ClassSubject, ClassSubject.subject_id == Subject.id)
                .where(ClassSubject.id == s.class_subject_id))
        names = self._names([s.absent_member_id, s.substitute_member_id])
        return SubstitutionOut(
            id=s.id, date=s.date, class_id=s.class_id,
            class_label=_label(klass.name, klass.section) if klass else None,
            period_no=s.period_no, class_subject_id=s.class_subject_id,
            subject_name=subject_name,
            absent_member_id=s.absent_member_id, absent_name=names.get(s.absent_member_id),
            substitute_member_id=s.substitute_member_id,
            substitute_name=names.get(s.substitute_member_id),
            note=s.note, cancelled_at=s.cancelled_at)

    def _names(self, member_ids) -> dict[uuid.UUID, str]:
        ids = [i for i in member_ids if i]
        if not ids:
            return {}
        return {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name)
                .join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(ids))).all()
        }

    def list_for_date(self, m: CurrentMember, on: date) -> list[SubstitutionOut]:
        return [self._out(s) for s in
                sorted(self.live(m.org_id, on), key=lambda s: (s.period_no,))]

    # ── the availability check ───────────────────────────────────────────────
    def busy_reason(self, org_id: uuid.UUID, member_id: uuid.UUID, on: date,
                   period_no: int) -> str | None:
        """Why this member cannot take the period, or None if they are free.

        Deliberately three separate reasons rather than one boolean — the admin
        picking a substitute needs to know whether the person is teaching, already
        covering, or not even in the building today.
        """
        teaching = self.db.scalar(
            select(TimetableSlot.id)
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == org_id,
                   TimetableSlot.weekday == on.weekday(),
                   TimetableSlot.period_no == period_no,
                   TimetableSlot.effective_from <= on,
                   or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > on),
                   ClassSubject.teacher_member_id == member_id).limit(1))
        if teaching is not None:
            return "already teaching that period"
        covering = self.db.scalar(
            select(PeriodSubstitution.id).where(
                PeriodSubstitution.org_id == org_id, PeriodSubstitution.date == on,
                PeriodSubstitution.period_no == period_no,
                PeriodSubstitution.substitute_member_id == member_id,
                PeriodSubstitution.cancelled_at.is_(None)).limit(1))
        if covering is not None:
            return "already covering another class that period"
        away = self.db.execute(
            select(StaffAbsence.status, StaffAbsence.portion)
            .join(StaffAttendanceDay, StaffAttendanceDay.id == StaffAbsence.day_id)
            .where(StaffAbsence.org_id == org_id, StaffAttendanceDay.date == on,
                   StaffAbsence.member_id == member_id).limit(1)).first()
        if away is not None:
            status, portion = away
            # V1-4 (D-04): `late` is present, and a half-day only costs its own
            # half. Refusing a substitute for the half she IS in would hand the
            # admin an empty candidate list on the exact morning cover matters.
            if status == "absent":
                return "marked away today"
            if status == "half_day" and period_no in self.half_periods(org_id, on, portion):
                return f"away for the {portion or 'am'} half today"
        # S-82: a future date has no staff-absence row, so without this clause an
        # admin arranging Friday's cover from a leave approval (D-27) could assign
        # it to someone who is herself on approved leave that Friday.
        leave = self.db.execute(
            select(LeaveRequest.is_half_day, LeaveRequest.portion).where(
                LeaveRequest.org_id == org_id, LeaveRequest.member_id == member_id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= on, LeaveRequest.end_date >= on).limit(1)).first()
        if leave is not None:
            is_half, portion = leave
            if not is_half:
                return "on approved leave that day"
            if period_no in self.half_periods(org_id, on, portion):
                return f"on approved half-day leave that {portion or 'am'}"
        return None

    def half_periods(self, org_id: uuid.UUID, on: date, portion: str | None) -> set[int]:
        """Period numbers covered by a half-day absence — `school_clock`'s cut.

        Cached per service instance: ranking six candidates for eight periods
        would otherwise re-read the year once per (candidate, period) pair.
        """
        key = portion or "am"
        if key not in self._half_cache:
            year = self.db.scalar(select(AcademicYear).where(
                AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True)))
            self._half_cache[key] = set(half_day_periods(
                year.period_times if year else [], key,
                year.periods_per_day if year else 8))
        return self._half_cache[key]

    # ── writes ───────────────────────────────────────────────────────────────
    def create(self, m: CurrentMember, body: SubstitutionIn) -> SubstitutionOut:
        klass = self.db.scalar(
            select(SchoolClass).where(SchoolClass.id == body.class_id,
                                      SchoolClass.org_id == m.org_id))
        if klass is None:
            raise NotFoundError("Class")
        cs = self.db.scalar(
            select(ClassSubject).where(ClassSubject.id == body.class_subject_id,
                                       ClassSubject.org_id == m.org_id))
        if cs is None:
            raise NotFoundError("Class-subject")
        if cs.class_id != body.class_id:
            raise ValidationError("That subject is not taught in this class.")
        sub = self.db.scalar(
            select(Membership).where(Membership.id == body.substitute_member_id,
                                     Membership.org_id == m.org_id,
                                     Membership.status == "active",
                                     not_operator()))
        if sub is None:
            raise NotFoundError("Member")
        if body.absent_member_id and sub.id == body.absent_member_id:
            raise ValidationError("A teacher cannot substitute for themselves.")

        reason = self.busy_reason(m.org_id, sub.id, body.date, body.period_no)
        if reason:
            name = self.db.scalar(select(User.name).where(User.id == sub.user_id)) or "That teacher"
            raise ConflictError(f"{name} is {reason}.", code="substitute_busy")

        existing = self.db.scalar(
            select(PeriodSubstitution).where(
                PeriodSubstitution.org_id == m.org_id, PeriodSubstitution.date == body.date,
                PeriodSubstitution.class_id == body.class_id,
                PeriodSubstitution.period_no == body.period_no,
                PeriodSubstitution.cancelled_at.is_(None)))
        if existing is not None:
            # Re-covering a period is a real correction, not an error: cancel the
            # old row (it stays, law-3 spirit) and write the new one.
            existing.cancelled_at = datetime.now(UTC)
            self.db.flush()

        row = PeriodSubstitution(
            org_id=m.org_id, date=body.date, class_id=body.class_id,
            period_no=body.period_no, class_subject_id=body.class_subject_id,
            absent_member_id=body.absent_member_id, substitute_member_id=sub.id,
            created_by_member_id=m.membership.id, note=body.note)
        self.db.add(row)
        self.db.flush()

        subject_name = self.db.scalar(
            select(Subject.name).where(Subject.id == cs.subject_id))
        notifications.enqueue(
            self.db, org_id=m.org_id, user_id=sub.user_id, instance_id=None,
            notif_type="substitute",
            payload={
                "subject": "You're covering a period",
                "body": (f"{_label(klass.name, klass.section)} {subject_name or ''} · "
                         f"period {body.period_no} on {body.date:%d %b}"
                         + (f" — {body.note}" if body.note else "")),
                "url": "/my-day",
            },
            dedupe_key=f"sub:{row.id}")
        return self._out(row)

    def cancel(self, m: CurrentMember, substitution_id: uuid.UUID) -> SubstitutionOut:
        row = self.db.scalar(
            select(PeriodSubstitution).where(PeriodSubstitution.id == substitution_id,
                                             PeriodSubstitution.org_id == m.org_id))
        if row is None:
            raise NotFoundError("Substitution")
        if row.cancelled_at is None:
            row.cancelled_at = datetime.now(UTC)
            self.db.flush()
        return self._out(row)
