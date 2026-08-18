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
from calendar import monthrange
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core import day_shape
from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    AttendanceException,
    CalendarEvent,
    ClassPeriod,
    ClassSubject,
    Guardian,
    Membership,
    SchoolClass,
    Student,
    StudentAbsenceNote,
    Subject,
    TimetableSlot,
    User,
)
from app.schemas.attendance import (
    AbsenceNoteIn,
    AbsenceNoteOut,
    AbsenceReasonIn,
    AbsenceReasonOut,
    AssemblyClassOut,
    AssemblyMarkIn,
    AssemblyMarkOut,
    AssemblyRosterOut,
    AttendanceMarkIn,
    AttendanceMarkOut,
    AttendanceRosterOut,
    AttendanceRosterRow,
    MyAttendanceClass,
    MyAttendanceOut,
)
from app.schemas.my_class import (
    DayTally,
    RegisterCell,
    RegisterOut,
    RegisterRow,
)
from app.services.calendar import event_rows, expand_blocked_dates, org_working_days
from app.services.notify_guardian import notify_guardians
from app.services.periods import (
    assert_can_take_class,
    find_period,
    get_or_create_period,
    today_for,
    visible_class_ids,
)
from app.services.school_clock import marking_period_nos, today_in

if TYPE_CHECKING:  # `timetable` imports nothing from here; kept lazy anyway so
    from app.services.timetable import BlockRoom  # the two services stay uncoupled.

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


# Day statuses that mean "the child was in school at some point".
PRESENT_STATUSES = ("present", "partial", "left_after_lunch")


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
    def _combined_rows(self, m: CurrentMember, class_ids: list[uuid.UUID],
                       labels: dict[uuid.UUID, str], d: date,
                       period_no: int) -> tuple[list[AttendanceRosterRow], int, int, bool]:
        """The whole room's sheet: every class's roster, each carrying its label.

        Marks are read per class, from that class's own register, because that is
        where they are written. `marked` is ALL of them: a room where one class's
        register is in and the other's is not has not had its roll taken, and
        saying otherwise would leave a class silently unmarked for the day.
        """
        rows: list[AttendanceRosterRow] = []
        marked_all = True
        for cid in class_ids:
            sheet = self._sheet_for(m, cid, period_no, d)
            marked_all = marked_all and sheet.marked
            for r in sheet.roster:
                rows.append(r.model_copy(update={
                    "class_id": cid, "class_label": labels.get(cid)}))
        absent = sum(1 for r in rows if r.status == "absent")
        late = sum(1 for r in rows if r.status == "late")
        return rows, absent, late, marked_all

    def roster(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
               on_date: date | None = None,
               combined: bool = True) -> AttendanceRosterOut:
        """The capture sheet for one period.

        TT-4: when the period is a COMBINED meeting the sheet is the room, not
        the class — every child the teacher can see in front of her, grouped by
        class. `combined=False` asks for this class alone, which is what the
        period card wants for its per-class sections.
        """
        d = on_date or self._today(m)
        if combined:
            from app.services.timetable import TimetableService, combined_label  # noqa: PLC0415

            combo = TimetableService(self.db).combined_meeting(m, class_id, period_no, d)
            if combo is not None:
                assert_can_take_class(self.db, m, class_id, None, d, period_no)
                ids = [c.class_id for c in combo.classes]
                labels = {c.class_id: c.class_label for c in combo.classes}
                rows, absent, late, marked = self._combined_rows(
                    m, ids, labels, d, period_no)
                label = combined_label([c.class_label for c in combo.classes])
                return AttendanceRosterOut(
                    class_id=class_id, class_label=label, period_no=period_no, date=d,
                    period_id=None, marked=marked, once_per_day=self.once_per_day(m),
                    roster=rows, present_count=len(rows) - absent,
                    absent_count=absent, late_count=late,
                    combined_id=combo.id, combined_class_ids=ids, combined_label=label)
        return self._sheet_for(m, class_id, period_no, d)

    def _sheet_for(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
                   d: date, *, taking_block_id: uuid.UUID | None = None,
                   ) -> AttendanceRosterOut:
        klass = self._class(m.org_id, class_id)
        # TT-6: the assembly sheet is read through the block's door, which its
        # taker has already passed. See `mark`.
        if taking_block_id is None:
            assert_can_take_class(self.db, m, class_id, None, d, period_no)
        roster = self._roster(m.org_id, class_id)
        # In a once-per-day school the sheet must OPEN on the day's register
        # wherever it was taken, so a teacher arriving at period 5 sees this
        # morning's marks and edits them, rather than a blank "everyone present"
        # she would then save as a second register. `mark` redirects the write
        # the same way — the read and the write have to agree about which period
        # holds the day, or the sheet shows one thing and saves another.
        held = (self.day_register_period(m.org_id, class_id, d)
                if self.once_per_day(m) else None)
        if held is not None:
            period_no = held.period_no
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
            once_per_day=self.once_per_day(m), roster=rows,
            present_count=len(rows) - absent, absent_count=absent, late_count=late)

    # ── the day's register, in a once-per-day school ─────────────────────────
    def day_register_period(self, org_id: uuid.UUID, class_id: uuid.UUID,
                            d: date) -> ClassPeriod | None:
        """The period that HOLDS this class's register for the day, if any.

        In `first_period` / `twice_daily` the register is the DAY's, not the
        period's, so there is at most one of these per class per day and every
        surface that shows or edits attendance has to find it rather than assume
        period 1 — the whole point of the founder's 2026-08-05 rule is that when
        period 1 does not happen, some later period takes it instead.
        """
        return self.db.scalar(
            select(ClassPeriod).where(
                ClassPeriod.org_id == org_id, ClassPeriod.class_id == class_id,
                ClassPeriod.date == d,
                ClassPeriod.attendance_marked_at.is_not(None))
            .order_by(ClassPeriod.period_no).limit(1))

    def once_per_day(self, m: CurrentMember) -> bool:
        """Does this school take ONE register a day? (`first_period` mode.)

        `twice_daily` deliberately does not count: it keeps two registers on
        purpose — the morning one and the after-lunch one whose difference is
        the whole reason a school picks it (`Q-03`/`S-05`).
        """
        return m.org.attendance_mode == "first_period"

    # ── mark (the one-tap capture) ───────────────────────────────────────────
    def _mark_combined(self, m: CurrentMember, body: AttendanceMarkIn,
                       d: date) -> AttendanceMarkOut:
        """One roll call over a combined room → one register PER CLASS (TT-4).

        Deliberately a fan-out over the ordinary `mark`, not a second write path.
        Everything that makes attendance correct — the once-a-day redirect, the
        kept absence reasons, the guardian alert firing on the day's first marked
        period — is written once and would have to be written twice if a combined
        register were its own thing. Splitting the exceptions is free: `mark`
        already ignores students who are not on the class's roster, so each class
        picks up exactly its own children.
        """
        from app.services.timetable import TimetableService  # noqa: PLC0415

        combo = TimetableService(self.db).combined_meeting(
            m, body.class_id, body.period_no, d)
        if combo is None:
            raise ValidationError(
                "These classes are not combined in this period. Take each "
                "class's register on its own.")
        allowed = {c.class_id: c for c in combo.classes}
        asked = [cid for cid in dict.fromkeys(body.class_ids) if cid in allowed]
        unknown = [cid for cid in body.class_ids if cid not in allowed]
        if unknown or not asked:
            raise ValidationError(
                "One of those classes is not in this combined period. Reload the "
                "sheet and try again.")

        roster_count = present = absent = late = alerted = 0
        primary: AttendanceMarkOut | None = None
        for cid in asked:
            one = self.mark(m, body.model_copy(update={
                "class_id": cid, "class_ids": [],
                "class_subject_id": allowed[cid].class_subject_id}))
            if cid == body.class_id or primary is None:
                primary = one
            roster_count += one.roster_count
            present += one.present_count
            absent += one.absent_count
            late += one.late_count
            alerted += one.alerted_count
        return primary.model_copy(update={
            "roster_count": roster_count, "present_count": present,
            "absent_count": absent, "late_count": late, "alerted_count": alerted})

    def mark(self, m: CurrentMember, body: AttendanceMarkIn, *,
             taking_block_id: uuid.UUID | None = None) -> AttendanceMarkOut:
        """Write one class's register.

        `taking_block_id` says the caller is standing in a whole-school block and
        has ALREADY been authorized for it (TT-6) — the assembly warden takes the
        register for every class in the hall and teaches almost none of them, so
        `assert_can_take_class` would refuse her on the very roll the school asked
        her to take. It is a *different door*, never a wider one: the only caller
        that may pass it is `mark_assembly`, which checks `assert_may_take_block`
        first and then only fans out over the classes that block actually has on
        the grid at that period.
        """
        d = body.date or self._today(m)
        if body.class_ids and set(body.class_ids) - {body.class_id}:
            return self._mark_combined(m, body, d)
        klass = self._class(m.org_id, body.class_id)
        if taking_block_id is None:
            assert_can_take_class(self.db, m, body.class_id, body.class_subject_id,
                                  d, body.period_no)
        roster_ids = {s.id for s in self._roster(m.org_id, body.class_id)}

        # **One register a day means one register a day** (founder, 2026-08-05).
        # A school on `first_period` that had period 1 cancelled takes the roll
        # in period 3 — and a teacher opening period 5 later to fix a mis-tap
        # must edit THAT register, not open a second one. So the mark lands on
        # the day's existing register wherever it was taken, and the requested
        # period is only where it goes when there is not one yet.
        #
        # Without this the day would carry two `attendance_marked_at` periods
        # and `classify_marked_day` would score a child absent-in-1-of-2 as
        # `partial` — a child who was simply away all day reading as "came late"
        # because two people touched the register.
        held = (self.day_register_period(m.org_id, body.class_id, d)
                if self.once_per_day(m) else None)
        if held is not None and held.period_no != body.period_no:
            # `class_subject_id` is cleared with it: the register moves, the
            # PERIOD does not. Carrying the caller's subject across would
            # relabel period 1 as Science because the Science teacher fixed a
            # typo in period 3.
            body = body.model_copy(
                update={"period_no": held.period_no, "class_subject_id": None})

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

    # ── the whole-school register, taken at assembly (TT-6) ──────────────────
    # Founder, 2026-08-18: assembly is at period 1, every child in the school is
    # standing in it, and the roll taken there should BE each class's register
    # for the day rather than a second list nobody reads.
    #
    # Deliberately a fan-out over the ordinary `mark`, exactly as TT-4's combined
    # roll call is. Everything that makes attendance correct — the once-a-day
    # redirect, the reasons that survive a re-mark, the guardian alert on the
    # day's first marked period — is written once and would have to be written
    # twice if the hall's register were its own kind of row.

    def _assembly_room(self, m: CurrentMember, session_id: uuid.UUID, d: date,
                       period_no: int | None = None) -> "BlockRoom":
        """The hall, once every door has been checked.

        Three refusals, in this order, because each one answers a different
        question a caller can get wrong: *may you take this block*, *does this
        kind of block take the school register at all*, and *is it on today's
        grid*. The last is a state rather than a fault — assembly does not run on
        Sunday — but it still has no period to file against, so it cannot write.
        """
        from app.models import Session as SessionModel  # noqa: PLC0415
        from app.services.timetable import TimetableService  # noqa: PLC0415

        tt = TimetableService(self.db)
        tt.assert_may_take_block(m, session_id)
        block = self.db.scalar(select(SessionModel).where(
            SessionModel.id == session_id, SessionModel.org_id == m.org_id))
        if block is None:
            raise NotFoundError("Block")
        if not day_shape.capture_for(block.kind).school_roll:
            raise ValidationError(
                f"A {day_shape.label_for(block.kind).lower()} block does not take "
                "the school register — its roll is its own.",
                code="no_school_roll")
        room = tt.block_room(m, session_id, d, period_no)
        if room is None:
            raise ValidationError(
                f"{block.name} is not on the timetable for {d:%A}, so there is no "
                "period to file the register against.",
                code="block_not_on_grid")
        return room

    def assembly_sheet(self, m: CurrentMember, session_id: uuid.UUID,
                       on_date: date | None = None,
                       period_no: int | None = None) -> AssemblyRosterOut:
        """Every child in the hall on one sheet, grouped by class.

        Each class's rows are read from that class's OWN register, because that
        is where they are written and where they will be read back — the month
        grid, the report card and the parent's Today all keep working on a class
        at a time and learn nothing about assembly.
        """
        d = on_date or self._today(m)
        room = self._assembly_room(m, session_id, d, period_no)

        rows: list[AttendanceRosterRow] = []
        classes: list[AssemblyClassOut] = []
        marked_all = True
        for cid in room.class_ids:
            sheet = self._sheet_for(m, cid, room.period_no, d,
                                    taking_block_id=room.session_id)
            marked_all = marked_all and sheet.marked
            label = room.class_labels.get(cid) or sheet.class_label
            for r in sheet.roster:
                rows.append(r.model_copy(update={"class_id": cid, "class_label": label}))
            classes.append(AssemblyClassOut(
                class_id=cid, class_label=label, roster=len(sheet.roster),
                marked=sheet.marked, absent=sheet.absent_count, late=sheet.late_count))

        absent = sum(1 for r in rows if r.status == "absent")
        late = sum(1 for r in rows if r.status == "late")
        n, k = len(rows), len(classes)
        children = "child" if n == 1 else "children"
        klasses = "class" if k == 1 else "classes"
        headline = (
            f"{n - absent} of {n} present · filed to {k} {klasses}"
            if marked_all else
            # Never a zero and never red: an untaken register is a state of the
            # record, not news about the children (ux §5).
            f"Not taken yet · {n} {children} across {k} {klasses}")
        return AssemblyRosterOut(
            session_id=room.session_id, block_name=room.name, block_kind=room.kind,
            kind_label=day_shape.label_for(room.kind), period_no=room.period_no,
            date=d, marked=marked_all and bool(classes),
            once_per_day=self.once_per_day(m), classes=classes, roster=rows,
            present_count=n - absent, absent_count=absent, late_count=late,
            headline=headline)

    def mark_assembly(self, m: CurrentMember, body: AssemblyMarkIn) -> AssemblyMarkOut:
        """One roll call in the hall → one register PER CLASS.

        The whole hall's exception list goes to every class untouched: `mark`
        already ignores students who are not on the class's roster, so each class
        picks up exactly its own absentees and nothing has to be split here.
        """
        d = body.date or self._today(m)
        room = self._assembly_room(m, body.session_id, d, body.period_no)
        exceptions = list(body.exceptions)

        roster_count = present = absent = late = alerted = 0
        for cid in room.class_ids:
            one = self.mark(
                m,
                AttendanceMarkIn(class_id=cid, period_no=room.period_no, date=d,
                                 exceptions=exceptions),
                taking_block_id=room.session_id)
            roster_count += one.roster_count
            present += one.present_count
            absent += one.absent_count
            late += one.late_count
            alerted += one.alerted_count
        k = len(room.class_ids)
        return AssemblyMarkOut(
            session_id=room.session_id, period_no=room.period_no, date=d,
            classes_marked=k, roster_count=roster_count, present_count=present,
            absent_count=absent, late_count=late, alerted_count=alerted,
            headline=(f"{present} of {roster_count} present · filed to {k} "
                      f"{'class' if k == 1 else 'classes'}"))

    def assembly_state(self, org_id: uuid.UUID, class_ids: list[uuid.UUID],
                       period_no: int, d: date) -> dict:
        """Where the hall's register stands — for My Day's assembly row.

        `marked` is an ALL over the room for the same reason the sheet's is: a
        hall with one class still unmarked has not had its roll taken, and a
        green row there would let a class's day go missing quietly.
        """
        if not class_ids:
            return {"marked": False, "roster_count": 0}
        sizes = self.roster_sizes(org_id, class_ids)
        states = self.period_states(org_id, class_ids, d)
        # Once a day, a class's register may sit on a different period than the
        # block's — a class whose period 1 was cancelled took it later. The hall
        # asks the day's question, so any marked period of the day counts.
        marked_of: dict[uuid.UUID, dict] = {}
        for (cid, pno), s in states.items():
            if not s.get("marked"):
                continue
            if cid not in marked_of or pno == period_no:
                marked_of[cid] = s
        marked = all(cid in marked_of for cid in class_ids)
        return {
            "marked": marked,
            "roster_count": sum(sizes.get(cid, 0) for cid in class_ids),
            "absent_count": (sum(s.get("absent_count") or 0
                                 for s in marked_of.values()) if marked else None),
            "late_count": (sum(s.get("late_count") or 0
                               for s in marked_of.values()) if marked else None),
        }

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
            select(Student.id, Student.full_name, Guardian)
            .join(Guardian, Guardian.student_id == Student.id)
            .where(Student.org_id == m.org_id, Student.id.in_(absent_ids))
        ).all()
        # Group guardians by student so each family gets one message.
        by_student: dict[uuid.UUID, tuple[str, list[Guardian]]] = {}
        for sid, full_name, guardian in rows:
            by_student.setdefault(sid, (full_name, []))[1].append(guardian)
        for sid, (full_name, guardians) in by_student.items():
            message = f"{full_name} was marked absent at {m.org.name} today ({d.isoformat()})."
            sent += notify_guardians(
                self.db, org_id=m.org_id, student_id=sid, guardians=guardians,
                kind="absence", title=f"{full_name} was marked absent", body=message,
                # One absence alert per child per day, however many periods are
                # marked after it — the family is told once, not eight times.
                dedupe_key=f"absence:{sid}:{d.isoformat()}").notified
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
            select(Student.id, Student.full_name, Guardian)
            .join(Guardian, Guardian.student_id == Student.id)
            .where(Student.org_id == m.org_id, Student.id.in_(left))).all()
        by_student: dict[uuid.UUID, tuple[str, list[Guardian]]] = {}
        for sid, full_name, guardian in rows:
            by_student.setdefault(sid, (full_name, []))[1].append(guardian)
        for sid, (full_name, guardians) in by_student.items():
            message = (f"{full_name} was present this morning at {m.org.name} but was "
                       f"marked absent after lunch today ({d.isoformat()}).")
            sent += notify_guardians(
                self.db, org_id=m.org_id, student_id=sid, guardians=guardians,
                kind="left_after_lunch", title=f"{full_name} left after lunch",
                body=message,
                dedupe_key=f"left_after_lunch:{sid}:{d.isoformat()}").notified
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

    def class_register(self, m: CurrentMember, class_id: uuid.UUID,
                       month: str | None = None) -> RegisterOut:
        """The month register for any class this teacher may open.

        Same drawing as My Class's grid (`build_register`) behind a wider door:
        the class teacher owns her homeroom's, but every teacher of a class can
        READ the register she may be asked to take. Reading is deliberately not
        narrower than writing — a teacher who can mark the roll and cannot see
        last week's is being asked to work blind.
        """
        klass = self._class(m.org_id, class_id)
        allowed = visible_class_ids(self.db, m)
        if allowed is not None and class_id not in allowed:
            raise ForbiddenError("You don't teach this class.", code="not_your_class")
        return build_register(self.db, m, klass, month)

    # ── the teacher's own attendance board (founder, 2026-08-05) ─────────────
    def my_board(self, m: CurrentMember, on_date: date | None = None) -> MyAttendanceOut:
        """Every class this teacher may take the register for, on any date.

        The school's rule, made reachable: **the class teacher takes it at period
        one, and if she is away any teacher of the class can.** Until now
        attendance could only be opened from a My Day period card, so a teacher
        who was not standing in front of that class at that moment had no door
        into it at all — which is precisely the situation the rule exists for.

        Nothing here widens permission. `assert_can_take_class` has allowed this
        exact set since V2-P2 (a subject teacher of the class, a substitute
        covering it today, an admin); what was missing was the screen. An
        already-marked class is still editable by the same set — correcting a
        mis-tap is not a privilege — and the day's FIRST marked period keeps
        being the one that fires guardian alerts, so a later correction never
        messages a family twice.

        Six queries for the whole board, whatever the class count.
        """
        d = on_date or self._today(m)
        open_day = bool(org_working_days(self.db, m.org_id, d, d))

        # Which classes she may open. Admin: every class in the active year.
        allowed = visible_class_ids(self.db, m)
        year = self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))
        q = select(SchoolClass).where(SchoolClass.org_id == m.org_id)
        if year is not None:
            q = q.where(SchoolClass.academic_year_id == year.id)
        if allowed is not None:
            if not allowed:
                return MyAttendanceOut(
                    date=d, is_today=d == self._today(m), school_open=open_day,
                    headline="You are not assigned to any class yet.")
            q = q.where(SchoolClass.id.in_(allowed))
        classes = list(self.db.scalars(q.order_by(SchoolClass.name, SchoolClass.section)))
        if not classes:
            return MyAttendanceOut(
                date=d, is_today=d == self._today(m), school_open=open_day,
                headline="No classes are set up for this year yet.")
        class_ids = [c.id for c in classes]

        rosters = self.roster_sizes(m.org_id, class_ids)
        marked, exc = day_matrix(self.db, m.org_id, class_ids, d, d)

        # Her subject in each class — what the mark gets filed against.
        mine: dict[uuid.UUID, tuple[uuid.UUID, str]] = {}
        for cs_id, cls_id, sub_name in self.db.execute(
            select(ClassSubject.id, ClassSubject.class_id, Subject.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == m.org_id,
                   ClassSubject.class_id.in_(class_ids),
                   *([] if m.is_coordinator_up
                     else [ClassSubject.teacher_member_id == m.membership.id]))
            .order_by(Subject.name)).all():
            mine.setdefault(cls_id, (cs_id, sub_name))

        # Who actually opened each register, and when. One query for the board.
        openers: dict[uuid.UUID, tuple[int, str | None, datetime]] = {}
        for cls_id, period_no, marked_at, name in self.db.execute(
            select(ClassPeriod.class_id, ClassPeriod.period_no,
                   ClassPeriod.attendance_marked_at, User.name)
            .outerjoin(Membership, Membership.id == ClassPeriod.marked_by_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .where(ClassPeriod.org_id == m.org_id,
                   ClassPeriod.class_id.in_(class_ids), ClassPeriod.date == d,
                   ClassPeriod.attendance_marked_at.is_not(None))
            .order_by(ClassPeriod.period_no)).all():
            openers.setdefault(cls_id, (int(period_no), name, marked_at))

        # Which period the "Take the register" button should open.
        #
        # Once-per-day: the day's register wherever it already is, else the
        # mode's marking slot (period 1). NOT her own first slot — in a
        # once-per-day school the register is the day's, so a Science teacher
        # opening it in period 4 must land on the same sheet the class teacher
        # would have, or the two of them write two registers.
        #
        # Every-period: her own first period with the class, because there the
        # register genuinely belongs to the period she is standing in.
        first_slot: dict[uuid.UUID, int] = {}
        for cls_id, period_no in self.db.execute(
            select(ClassSubject.class_id, func.min(TimetableSlot.period_no))
            .join(ClassSubject, ClassSubject.id == TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == m.org_id,
                   ClassSubject.class_id.in_(class_ids),
                   TimetableSlot.weekday == d.weekday(),
                   TimetableSlot.effective_from <= d,
                   (TimetableSlot.effective_to.is_(None))
                   | (TimetableSlot.effective_to >= d))
            .group_by(ClassSubject.class_id)).all():
            first_slot[cls_id] = int(period_no)

        names = {
            sid: name for sid, name in self.db.execute(
                select(Student.id, Student.full_name)
                .where(Student.org_id == m.org_id,
                       Student.class_id.in_(class_ids),
                       Student.status == "active")).all()
        }
        marking = marking_period_nos(
            year.period_times if year else None, m.org.attendance_mode)
        once = self.once_per_day(m)

        rows: list[MyAttendanceClass] = []
        for klass in classes:
            cs = mine.get(klass.id)
            periods = marked.get((klass.id, d), [])
            if once:
                suggested = (openers[klass.id][0] if klass.id in openers
                             else (marking[0] if marking else 1))
            else:
                suggested = first_slot.get(klass.id, 1)
            row = MyAttendanceClass(
                class_id=klass.id, class_label=_label(klass),
                roster=rosters.get(klass.id, 0),
                is_class_teacher=klass.class_teacher_member_id == m.membership.id,
                class_subject_id=cs[0] if cs else None,
                subject_name=cs[1] if cs else None,
                marked=bool(periods), periods_marked=len(periods),
                first_of_day=not periods,
                suggested_period_no=suggested)
            if klass.id in openers:
                pno, by, at = openers[klass.id]
                row.marked_period_no, row.marked_by_name, row.marked_at = pno, by, at

            if periods:
                absentees: list[str] = []
                for sid, full_name in names.items():
                    per = exc.get((sid, d), {})
                    if not per:
                        continue
                    status, was_late = classify_marked_day(
                        periods, {p: st for p, (st, _r) in per.items()}, marking)
                    if was_late:
                        row.late += 1
                    if status == "absent":
                        absentees.append(full_name)
                row.absent = len(absentees)
                row.present = max(0, row.roster - row.absent)
                row.pct = round(row.present / row.roster * 100, 1) if row.roster else None
                row.absentee_names = sorted(absentees)
                row.headline = (
                    f"Taken by {row.marked_by_name or 'a colleague'}"
                    + (f" · {row.absent} away" if row.absent else " · everyone in"))
                row.tone = "green" if not row.absent else "amber"
            elif not open_day:
                row.headline = "School is closed."
            else:
                # Never a zero and never red — an unopened register is a state
                # of the record, not news about the children (ux §5).
                row.headline = f"Not taken yet · {row.roster} on the roll"
                row.tone = "neutral"
            rows.append(row)

        pending = [r for r in rows if not r.marked]
        if not open_day:
            headline = f"School is closed on {d:%a %d %b}."
        elif not pending:
            headline = (f"Every one of your {len(rows)} "
                        f"{'class' if len(rows) == 1 else 'classes'} has been marked.")
        else:
            headline = (f"{len(pending)} of your {len(rows)} "
                        f"{'class' if len(rows) == 1 else 'classes'} still needs "
                        "the register taken.")
        return MyAttendanceOut(
            date=d, is_today=d == self._today(m), school_open=open_day,
            mode=m.org.attendance_mode, once_per_day=once,
            classes=rows, headline=headline)


# ── THE month register (extracted 2026-08-05) ────────────────────────────────

def build_register(db: Session, m: CurrentMember, klass: SchoolClass,
                   month: str | None = None) -> RegisterOut:
    """Student × school day, one status per cell — the ruled register book.

    Lifted out of `MyClassService.register` so the class teacher's grid and the
    every-teacher attendance screen are ONE computation with two doors. They
    differ only in **who may open which class**; a second implementation would
    eventually paint the same October two different ways, which is the `S-51`
    defect this codebase keeps closing.

    Two rules the drawing itself enforces, and neither is cosmetic:

      * cells stop at **today** — the future is blank, not a state;
      * a day the class marked nothing is `not_marked`, **never** "present".
        That distinction is the entire reason this is a grid rather than a
        percentage: a percentage cannot show a hole in the record.

    Guarding is deliberately the CALLER's job. `MyClassService` admits only the
    homeroom's own teacher; the attendance screen admits anyone who teaches the
    class. Neither rule belongs inside a drawing.
    """
    class_id = klass.id
    today = today_in(m.org.timezone)
    if month:
        try:
            y, mo = int(month[:4]), int(month[5:7])
            first = date(y, mo, 1)
        except (ValueError, IndexError):
            first = today.replace(day=1)
    else:
        first = today.replace(day=1)
    last = min(date(first.year, first.month,
                    monthrange(first.year, first.month)[1]), today)

    year = db.get(AcademicYear, klass.academic_year_id)
    working = set(year.working_weekdays or [0, 1, 2, 3, 4, 5]) if year \
        else {0, 1, 2, 3, 4, 5}
    blocked = expand_blocked_dates(event_rows(db.scalars(
        select(CalendarEvent).where(
            CalendarEvent.org_id == m.org_id,
            CalendarEvent.academic_year_id == klass.academic_year_id,
            CalendarEvent.end_date >= first, CalendarEvent.start_date <= last))))
    marking = marking_period_nos(
        year.period_times if year else None, m.org.attendance_mode)
    days = [d for d in (date.fromordinal(o)
                        for o in range(first.toordinal(), last.toordinal() + 1))
            if d.weekday() in working and d not in blocked] if last >= first else []

    roster = list(db.scalars(
        select(Student).where(
            Student.org_id == m.org_id, Student.class_id == class_id,
            Student.status == "active").order_by(Student.full_name)))
    marked, exc = day_matrix(db, m.org_id, [class_id], first, last)

    # Covering informed-absence notes for the window (S-24): explained days.
    noted: dict[uuid.UUID, list[tuple[date, date]]] = {}
    for n in db.scalars(select(StudentAbsenceNote).where(
            StudentAbsenceNote.org_id == m.org_id,
            StudentAbsenceNote.student_id.in_([s.id for s in roster]),
            StudentAbsenceNote.from_date <= last,
            StudentAbsenceNote.to_date >= first)):
        noted.setdefault(n.student_id, []).append((n.from_date, n.to_date))

    rows: list[RegisterRow] = []
    for s in roster:
        cells: list[RegisterCell] = []
        present_days = marked_days = 0
        since = s.enrolled_on  # S-02: a joiner's denominator starts here
        for d in days:
            if since and d < since:
                cells.append(RegisterCell(date=d, status="no_school"))
                continue
            periods = marked.get((class_id, d))
            if not periods:
                cells.append(RegisterCell(date=d, status="not_marked"))
                continue
            per = exc.get((s.id, d), {})
            status, late = classify_marked_day(
                periods, {p: st for p, (st, _r) in per.items()}, marking)
            has_reason = any(r for _st, r in per.values()) or any(
                a <= d <= b for a, b in noted.get(s.id, []))
            marked_days += 1
            if status in PRESENT_STATUSES:
                present_days += 1
            cells.append(RegisterCell(
                date=d, status=status, late=late, has_reason=has_reason))
        rows.append(RegisterRow(
            student_id=s.id, full_name=s.full_name, roll_no=s.roll_no,
            cells=cells, present_days=present_days, marked_days=marked_days))

    # The column totals the paper register carries in its bottom margin: how
    # many were in on each day, out of how many it could account for. `None` on
    # a day nobody marked — the one figure this grid must never invent.
    day_totals: list[DayTally] = []
    for i, d in enumerate(days):
        counted = [r.cells[i] for r in rows if r.cells[i].status != "no_school"]
        rated = [c for c in counted if c.status != "not_marked"]
        present = sum(1 for c in rated if c.status in PRESENT_STATUSES)
        day_totals.append(DayTally(
            date=d, marked=bool(rated), present=present,
            absent=len(rated) - present, counted=len(rated),
            pct=round(present / len(rated) * 100, 1) if rated else None))

    marked_days_total = sum(1 for t in day_totals if t.marked)
    rated_cells = sum(t.counted for t in day_totals)
    present_cells = sum(t.present for t in day_totals)
    return RegisterOut(
        class_id=class_id, class_label=_label(klass),
        month=f"{first.year:04d}-{first.month:02d}",
        mode=m.org.attendance_mode,
        once_per_day=m.org.attendance_mode == "first_period",
        days=days, rows=rows, school_days=len(days),
        day_totals=day_totals, marked_days=marked_days_total,
        pct=round(present_cells / rated_cells * 100, 1) if rated_cells else None,
        headline=(
            f"{round(present_cells / rated_cells * 100, 1)}% present across the "
            f"{marked_days_total} of {len(days)} school "
            f"{'day' if len(days) == 1 else 'days'} this class marked"
            if rated_cells else
            f"Nothing marked yet this month — {len(days)} school "
            f"{'day' if len(days) == 1 else 'days'} so far"))
