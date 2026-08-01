"""Per-period attendance (V2-M4, SPRD2 §5.4) — capture-by-exception.

"All present ✓" stamps `attendance_marked_at` on the class period; the teacher taps
only deviations, which become `attendance_exceptions` (absent | late). Present is
derived: roster minus absentees (late students are present-but-flagged).

The period row itself is the anchor (see models/periods.py). Marking opens it if
the teacher never tapped "Start attendance" — so the one-tap "All present" path
straight off a My Day card still works without a separate open call.

The day's FIRST attendance-marked period for a class fires guardian absence alerts
(§7) once — `alerted_at` on that period makes it idempotent across re-marks/edits.
Alerts carry plain "absent today" text only; never band/tier info (P4).
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError
from app.models import (
    AcademicYear,
    AttendanceException,
    ClassPeriod,
    Guardian,
    SchoolClass,
    Student,
    StudentAbsenceNote,
)
from app.schemas.attendance import (
    AbsenceNoteIn,
    AbsenceNoteOut,
    AbsenceReasonIn,
    AbsenceReasonOut,
    AttendanceMarkIn,
    AttendanceMarkOut,
    AttendanceRosterOut,
    AttendanceRosterRow,
)
from app.services.notify_guardian import notify_guardians
from app.services.periods import (
    assert_can_take_class,
    find_period,
    get_or_create_period,
    today_for,
)
from app.services.school_clock import marking_period_nos

# ── THE day-status rule (V1-0d, ux §9) ───────────────────────────────────────
# "Was this child absent today?" is rendered on six surfaces (admin board,
# class-teacher grid, parent Today, daily report, report card, Lucy) and was
# computed three different ways. These two pure functions are now the only
# definition; every consumer renders them, none re-derives.

def classify_day(scheduled: int, marked: int, absent: int,
                 am_absent: bool | None = None,
                 pm_absent: bool | None = None) -> str:
    """One student's day: present | partial | absent | left_after_lunch |
    not_marked | no_school.

    * absent  = absent in EVERY marked period of the day;
    * left_after_lunch (V1-3, Q-03/S-05) = present at the morning marking slot,
      absent at the after-lunch one — twice_daily mode's whole reason to exist.
      Its own named state, NEVER folded into "partial"; still not day-absent
      (present in a marked period), so it never extends a streak;
    * partial = absent in some but not all (came late, left early);
    * not_marked = periods were scheduled and nobody marked any — a gap in the
      record, never a judgement (ux §5);
    * no_school = nothing scheduled at all.
    """
    if scheduled == 0:
        return "no_school"
    if marked == 0:
        return "not_marked"
    if am_absent is False and pm_absent is True:
        return "left_after_lunch"
    if absent >= marked:
        return "absent"
    if absent > 0:
        return "partial"
    return "present"


def classify_marked_day(marked_periods: list[int], exceptions: dict[int, str],
                        marking_nos: list[int]) -> tuple[str, bool]:
    """(day status, was_late) for one student on a day the class marked
    something. THE per-day classifier behind the class-teacher register and
    the parent's month strip — both render this, neither re-derives.

    `marked_periods` = period numbers the class marked; `exceptions` = this
    student's period_no → absent|late; `marking_nos` = the org mode's marking
    slots (empty = every period marks)."""
    absent = sum(1 for p in marked_periods if exceptions.get(p) == "absent")
    late = any(exceptions.get(p) == "late" for p in marked_periods)
    am_absent = pm_absent = None
    if len(marking_nos) >= 2:
        am, pm = marking_nos[0], marking_nos[1]
        if am in marked_periods:
            am_absent = exceptions.get(am) == "absent"
        if pm in marked_periods:
            pm_absent = exceptions.get(pm) == "absent"
    status = classify_day(len(marked_periods) or 1, len(marked_periods), absent,
                          am_absent=am_absent, pm_absent=pm_absent)
    return status, late


def is_day_absent(marked: int, absent: int) -> bool:
    """The streak/red-list face of the same rule: day-absent only when absent in
    every marked period. A day with nothing marked is never day-absent — the
    school's gap in capture is not evidence about the child."""
    return bool(marked) and absent >= marked


def day_absence_maps(db: Session, org_id: uuid.UUID, since: date, until: date,
                     ) -> tuple[dict[tuple[uuid.UUID, date], int],
                                dict[uuid.UUID, dict[date, int]]]:
    """The batched facts behind `is_day_absent`, for a whole org and window:
    (class_id, date) → marked periods · student_id → {date: absent periods}.

    Two grouped queries however many students. The absence streaks board and the
    daily report's repeat-absentee rule both read THIS — before V1-0 the report
    used a looser rule (any absent exception = an absent day), so a child who
    came in late could be reported as a repeat absentee.
    """
    marked = {
        (cid, d): int(n) for cid, d, n in db.execute(
            select(ClassPeriod.class_id, ClassPeriod.date, func.count(ClassPeriod.id))
            .where(ClassPeriod.org_id == org_id, ClassPeriod.date >= since,
                   ClassPeriod.date <= until,
                   ClassPeriod.attendance_marked_at.is_not(None))
            .group_by(ClassPeriod.class_id, ClassPeriod.date)).all()
    }
    absents: dict[uuid.UUID, dict[date, int]] = {}
    for sid, d, n in db.execute(
        select(AttendanceException.student_id, ClassPeriod.date,
               func.count(AttendanceException.id))
        .join(ClassPeriod, ClassPeriod.id == AttendanceException.period_id)
        .where(AttendanceException.org_id == org_id,
               AttendanceException.status == "absent",
               ClassPeriod.date >= since, ClassPeriod.date <= until,
               ClassPeriod.attendance_marked_at.is_not(None))
        .group_by(AttendanceException.student_id, ClassPeriod.date)
    ).all():
        absents.setdefault(sid, {})[d] = int(n)
    return marked, absents


def day_matrix(db: Session, org_id: uuid.UUID, class_ids: list[uuid.UUID],
               since: date, until: date,
               ) -> tuple[dict[tuple[uuid.UUID, date], list[int]],
                          dict[tuple[uuid.UUID, date], dict[int, tuple[str, bool]]]]:
    """The period-level facts behind every day-status render (V1-3):

    (class_id, date) → marked period numbers ·
    (student_id, date) → {period_no: (status, has_reason)}.

    Two queries for any window and roster size. The class-teacher register, the
    admin call board and the parent month strip all classify from THIS — the
    classifier is `classify_marked_day`, and nothing re-derives it.
    """
    if not class_ids:
        return {}, {}
    marked: dict[tuple[uuid.UUID, date], list[int]] = {}
    for cid, d, pno in db.execute(
        select(ClassPeriod.class_id, ClassPeriod.date, ClassPeriod.period_no)
        .where(ClassPeriod.org_id == org_id, ClassPeriod.class_id.in_(class_ids),
               ClassPeriod.date >= since, ClassPeriod.date <= until,
               ClassPeriod.attendance_marked_at.is_not(None))
    ).all():
        marked.setdefault((cid, d), []).append(int(pno))
    exc: dict[tuple[uuid.UUID, date], dict[int, tuple[str, bool]]] = {}
    for sid, d, pno, status, reason_at in db.execute(
        select(AttendanceException.student_id, ClassPeriod.date,
               ClassPeriod.period_no, AttendanceException.status,
               AttendanceException.reason_at)
        .join(ClassPeriod, ClassPeriod.id == AttendanceException.period_id)
        .where(AttendanceException.org_id == org_id,
               ClassPeriod.class_id.in_(class_ids),
               ClassPeriod.date >= since, ClassPeriod.date <= until,
               ClassPeriod.attendance_marked_at.is_not(None))
    ).all():
        exc.setdefault((sid, d), {})[int(pno)] = (status, reason_at is not None)
    return marked, exc


def _label(klass: SchoolClass) -> str:
    return klass.name + (f"-{klass.section}" if klass.section else "")


class AttendanceService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_for(m)

    def _class(self, org_id: uuid.UUID, class_id: uuid.UUID) -> SchoolClass:
        klass = self.db.scalar(
            select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.org_id == org_id))
        if klass is None:
            raise NotFoundError("Class")
        return klass

    def _roster(self, org_id: uuid.UUID, class_id: uuid.UUID) -> list[Student]:
        return list(self.db.scalars(
            select(Student).where(
                Student.org_id == org_id, Student.class_id == class_id,
                Student.status == "active").order_by(Student.full_name)))

    # ── roster for the capture sheet ─────────────────────────────────────────
    def roster(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
               on_date: date | None = None) -> AttendanceRosterOut:
        klass = self._class(m.org_id, class_id)
        d = on_date or self._today(m)
        assert_can_take_class(self.db, m, class_id, None, d, period_no)
        roster = self._roster(m.org_id, class_id)
        period = self.db.scalar(
            select(ClassPeriod).where(
                ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == class_id,
                ClassPeriod.date == d, ClassPeriod.period_no == period_no)
            .options(selectinload(ClassPeriod.exceptions)))
        exc = {e.student_id: e for e in period.exceptions} if period else {}
        rows = [
            AttendanceRosterRow(
                student_id=s.id, full_name=s.full_name, roll_no=s.roll_no,
                status=exc[s.id].status if s.id in exc else None,
                late_minutes=exc[s.id].late_minutes if s.id in exc else None)
            for s in roster
        ]
        absent = sum(1 for r in rows if r.status == "absent")
        late = sum(1 for r in rows if r.status == "late")
        return AttendanceRosterOut(
            class_id=class_id, class_label=_label(klass), period_no=period_no, date=d,
            period_id=period.id if period else None,
            marked=period is not None and period.attendance_marked_at is not None,
            roster=rows,
            present_count=len(rows) - absent, absent_count=absent, late_count=late)

    # ── mark (the one-tap capture) ───────────────────────────────────────────
    def mark(self, m: CurrentMember, body: AttendanceMarkIn) -> AttendanceMarkOut:
        klass = self._class(m.org_id, body.class_id)
        d = body.date or self._today(m)
        assert_can_take_class(self.db, m, body.class_id, body.class_subject_id,
                              d, body.period_no)
        roster_ids = {s.id for s in self._roster(m.org_id, body.class_id)}

        existing = find_period(self.db, m.org_id, body.class_id, d, body.period_no)
        # First *attendance-marked* period of the day for this class? Decide before
        # we stamp this one. An opened-but-unmarked period must not count.
        others_marked = self.db.scalar(
            select(func.count(ClassPeriod.id)).where(
                ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == body.class_id,
                ClassPeriod.date == d, ClassPeriod.period_no != body.period_no,
                ClassPeriod.attendance_marked_at.is_not(None)))
        already_marked = existing is not None and existing.attendance_marked_at is not None
        first_of_day = not already_marked and (others_marked or 0) == 0

        period = get_or_create_period(
            self.db, m, body.class_id, d, body.period_no, body.class_subject_id)
        if body.class_subject_id is not None:
            period.class_subject_id = body.class_subject_id
        period.marked_by_member_id = m.membership.id
        period.attendance_marked_at = datetime.now(UTC)
        if period.teacher_member_id is None:
            period.teacher_member_id = m.membership.id
        # Full-replace the exception set (idempotent re-capture) — but a reason
        # someone already recorded on this absence must SURVIVE the re-mark
        # (V1-3, D-02): correcting a mis-tap is not un-explaining the child.
        kept_reasons = {
            e.student_id: (e.reason_code, e.reason_note, e.reason_by_member_id, e.reason_at)
            for e in self.db.scalars(
                select(AttendanceException).where(
                    AttendanceException.period_id == period.id,
                    AttendanceException.reason_at.is_not(None)))
        }
        self.db.execute(
            AttendanceException.__table__.delete().where(
                AttendanceException.period_id == period.id))
        self.db.flush()

        absent_ids: list[uuid.UUID] = []
        for e in body.exceptions:
            if e.student_id not in roster_ids:
                continue  # ignore students not on this class's roster
            code, note, by, at = kept_reasons.get(e.student_id, (None, None, None, None))
            self.db.add(AttendanceException(
                org_id=m.org_id, period_id=period.id, student_id=e.student_id,
                status=e.status, late_minutes=e.late_minutes if e.status == "late" else None,
                reason_code=code, reason_note=note,
                reason_by_member_id=by, reason_at=at))
            if e.status == "absent":
                absent_ids.append(e.student_id)
        self.db.flush()

        alerted = 0
        if first_of_day and period.alerted_at is None:
            alerted = self._alert_absences(m, klass, absent_ids, d)
            period.alerted_at = datetime.now(UTC)
            self.db.flush()
        elif not first_of_day and period.alerted_at is None:
            # V1-3 (Q-03/S-05): in twice_daily mode the after-lunch marking slot
            # carries its own signal — a child present in the morning and absent
            # now LEFT AFTER LUNCH, which is the single fact this mode exists to
            # catch. One message, idempotent through the same alerted_at stamp.
            alerted = self._maybe_alert_left_after_lunch(
                m, body.class_id, period, absent_ids, d)

        roster_count = len(roster_ids)
        absent_count = len(absent_ids)
        late_count = sum(1 for e in body.exceptions
                         if e.status == "late" and e.student_id in roster_ids)
        return AttendanceMarkOut(
            period_id=period.id, mark_id=period.id, class_id=body.class_id,
            period_no=body.period_no, date=d,
            roster_count=roster_count, present_count=roster_count - absent_count,
            absent_count=absent_count, late_count=late_count, alerted_count=alerted)

    def noted_student_ids(self, org_id: uuid.UUID, student_ids: list[uuid.UUID],
                          on: date) -> set[uuid.UUID]:
        """Students whose absence on `on` is covered by an informed-absence note
        (S-24) — the school already knows, so nothing should alert or turn red."""
        if not student_ids:
            return set()
        return set(self.db.scalars(
            select(StudentAbsenceNote.student_id).where(
                StudentAbsenceNote.org_id == org_id,
                StudentAbsenceNote.student_id.in_(student_ids),
                StudentAbsenceNote.from_date <= on,
                StudentAbsenceNote.to_date >= on).distinct()))

    def _alert_absences(self, m: CurrentMember, klass: SchoolClass,
                        absent_ids: list[uuid.UUID], d: date) -> int:
        """Notify each absent student's guardians (§7). Plain text only (P4).
        S-13: a family that already told the school ("away till Friday") is
        never messaged about the absence they announced."""
        absent_ids = [sid for sid in absent_ids
                      if sid not in self.noted_student_ids(m.org_id, absent_ids, d)]
        if not absent_ids:
            return 0
        sent = 0
        rows = self.db.execute(
            select(Student.full_name, Guardian.phone, Guardian.notify_opt_out)
            .join(Guardian, Guardian.student_id == Student.id)
            .where(Student.org_id == m.org_id, Student.id.in_(absent_ids))
        ).all()
        # Group guardians by student so each family gets one message.
        by_student: dict[str, list[tuple[str | None, bool]]] = {}
        for full_name, phone, opt_out in rows:
            by_student.setdefault(full_name, []).append((phone, opt_out))
        for full_name, recipients in by_student.items():
            message = f"{full_name} was marked absent at {m.org.name} today ({d.isoformat()})."
            sent += notify_guardians(recipients, message)
        return sent

    def _maybe_alert_left_after_lunch(self, m: CurrentMember, class_id: uuid.UUID,
                                      period: ClassPeriod,
                                      absent_ids: list[uuid.UUID], d: date) -> int:
        """The after-lunch signal (V1-3, Q-03/S-05) — twice_daily mode only,
        and only on the PM marking slot. Alerts guardians of students who were
        PRESENT at the morning slot and are absent now."""
        if m.org.attendance_mode != "twice_daily" or not absent_ids:
            return 0
        year = self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))
        marking = marking_period_nos(year.period_times if year else None, "twice_daily")
        if len(marking) < 2 or period.period_no != marking[1]:
            return 0
        am = self.db.scalar(select(ClassPeriod).where(
            ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == class_id,
            ClassPeriod.date == d, ClassPeriod.period_no == marking[0],
            ClassPeriod.attendance_marked_at.is_not(None)))
        if am is None:
            return 0
        am_absent = set(self.db.scalars(
            select(AttendanceException.student_id).where(
                AttendanceException.period_id == am.id,
                AttendanceException.status == "absent")))
        left = [sid for sid in absent_ids if sid not in am_absent]
        left = [sid for sid in left
                if sid not in self.noted_student_ids(m.org_id, left, d)]
        if not left:
            return 0
        sent = 0
        rows = self.db.execute(
            select(Student.full_name, Guardian.phone, Guardian.notify_opt_out)
            .join(Guardian, Guardian.student_id == Student.id)
            .where(Student.org_id == m.org_id, Student.id.in_(left))).all()
        by_student: dict[str, list[tuple[str | None, bool]]] = {}
        for full_name, phone, opt_out in rows:
            by_student.setdefault(full_name, []).append((phone, opt_out))
        for full_name, recipients in by_student.items():
            message = (f"{full_name} was present this morning at {m.org.name} but was "
                       f"marked absent after lunch today ({d.isoformat()}).")
            sent += notify_guardians(recipients, message)
        period.alerted_at = datetime.now(UTC)
        self.db.flush()
        return sent

    # ── reasons + informed absence (V1-3, D-02/S-24) ─────────────────────────
    def set_absence_reason(self, m: CurrentMember,
                           body: AbsenceReasonIn) -> AbsenceReasonOut:
        """Stamp the reason on every absent exception for that student-day.
        The reason belongs to the absence, not to one period of it (D-02)."""
        student = self.db.scalar(select(Student).where(
            Student.id == body.student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        rows = list(self.db.scalars(
            select(AttendanceException)
            .join(ClassPeriod, ClassPeriod.id == AttendanceException.period_id)
            .where(AttendanceException.org_id == m.org_id,
                   AttendanceException.student_id == body.student_id,
                   AttendanceException.status == "absent",
                   ClassPeriod.date == body.date)))
        now = datetime.now(UTC)
        for r in rows:
            r.reason_code = body.reason_code
            r.reason_note = body.note
            r.reason_by_member_id = m.membership.id
            r.reason_at = now
        self.db.flush()
        return AbsenceReasonOut(
            student_id=body.student_id, date=body.date,
            reason_code=body.reason_code, note=body.note,
            updated_periods=len(rows))

    def add_absence_note(self, m: CurrentMember, body: AbsenceNoteIn) -> AbsenceNoteOut:
        """Informed/planned absence (S-24) — append-only (law 3)."""
        student = self.db.scalar(select(Student).where(
            Student.id == body.student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        note = StudentAbsenceNote(
            org_id=m.org_id, student_id=body.student_id,
            from_date=body.from_date, to_date=body.to_date,
            reason_code=body.reason_code, note=body.note, source=body.source,
            created_by_member_id=m.membership.id)
        self.db.add(note)
        self.db.flush()
        return AbsenceNoteOut(
            id=note.id, student_id=note.student_id, from_date=note.from_date,
            to_date=note.to_date, reason_code=note.reason_code, note=note.note,
            source=note.source, created_by_name=m.user.name,
            created_at=note.created_at)

    def list_absence_notes(self, m: CurrentMember,
                           student_id: uuid.UUID) -> list[AbsenceNoteOut]:
        from app.models import Membership, User  # noqa: PLC0415

        rows = list(self.db.scalars(
            select(StudentAbsenceNote).where(
                StudentAbsenceNote.org_id == m.org_id,
                StudentAbsenceNote.student_id == student_id)
            .order_by(StudentAbsenceNote.from_date.desc()).limit(50)))
        names = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name)
                .join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(
                    {r.created_by_member_id for r in rows if r.created_by_member_id})))
        } if rows else {}
        return [AbsenceNoteOut(
            id=r.id, student_id=r.student_id, from_date=r.from_date,
            to_date=r.to_date, reason_code=r.reason_code, note=r.note,
            source=r.source,
            created_by_name=names.get(r.created_by_member_id),
            created_at=r.created_at) for r in rows]

    # ── My Day integration: per-period state for a set of classes ────────────
    def roster_sizes(
        self, org_id: uuid.UUID, class_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, int]:
        """class_id → active-roster size (shown on the card even before marking)."""
        if not class_ids:
            return {}
        return dict(self.db.execute(
            select(Student.class_id, func.count(Student.id))
            .where(Student.org_id == org_id, Student.class_id.in_(class_ids),
                   Student.status == "active")
            .group_by(Student.class_id)
        ).all())

    def period_states(
        self, org_id: uuid.UUID, class_ids: list[uuid.UUID], on_date: date,
    ) -> dict[tuple[uuid.UUID, int], dict]:
        """(class_id, period_no) → card state for every *opened* period. `marked` is
        false for a period that was opened but whose attendance was never submitted.
        Roster size for un-opened periods comes from roster_sizes()."""
        if not class_ids:
            return {}
        roster_counts = self.roster_sizes(org_id, class_ids)
        periods = list(self.db.scalars(
            select(ClassPeriod).where(
                ClassPeriod.org_id == org_id, ClassPeriod.class_id.in_(class_ids),
                ClassPeriod.date == on_date)
            .options(selectinload(ClassPeriod.exceptions))))
        out: dict[tuple[uuid.UUID, int], dict] = {}
        for p in periods:
            marked = p.attendance_marked_at is not None
            absent = sum(1 for e in p.exceptions if e.status == "absent")
            late = sum(1 for e in p.exceptions if e.status == "late")
            roster_count = roster_counts.get(p.class_id, 0)
            out[(p.class_id, p.period_no)] = {
                "period_id": p.id, "status": p.status,
                "closed": p.closed_at is not None,
                "marked": marked, "roster_count": roster_count,
                "present_count": roster_count - absent if marked else None,
                "absent_count": absent if marked else None,
                "late_count": late if marked else None}
        return out
