"""Generate recent CAPTURE for an existing demo school, so every board has data.

`scripts/seed.py` builds a school — years, classes, students, timetable, plans.
This fills in what a school *does with it day to day*, which is what the DASH3
operating board reads: marked periods, lesson logs, homework checks, staff
attendance, timesheets, leave and confirmed daily checks.

**Every write goes through the real service**, never a raw INSERT. That is the
whole point: `AttendanceService.mark` writes exception rows and stamps
`attendance_marked_at`; `check_homework` recomputes `done_count`; `LeaveService`
appends to the event log and derives the status cache. Data faked around those
services would look right in the table and wrong on the board — which is exactly
the class of bug this script exists to help catch.

Idempotent: every service used is a full-replace or get-or-create, so re-running
corrects rather than duplicates. Deterministic: the RNG is seeded from the org id,
so the same school always gets the same story.

Usage (from `api/`):

    uv run python -m scripts.demo_activity                    # active org, 10 school days
    uv run python -m scripts.demo_activity --org sunrise --days 14
    DATABASE_URL=... uv run python -m scripts.demo_activity   # target another database

Safety: it refuses to touch an org with more than one non-demo signal unless
`--force` is passed, and it only ever writes inside the window it is given.
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select

from app.core.context import CurrentMember
from app.core.database import SessionLocal
from app.core.work_types import WORK_TYPES
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    HomeworkAssignment,
    Membership,
    Organization,
    SchoolClass,
    Student,
    TimetableSlot,
    User,
)
from app.schemas.attendance import AttendanceExceptionIn, AttendanceMarkIn
from app.schemas.classroom import HomeworkCheckIn, HomeworkResultIn, LessonLogIn
from app.schemas.staff import LeaveApplyIn, LeaveDecisionIn, StaffAttendanceIn, TimesheetEntryIn
from app.services.attendance import AttendanceService
from app.services.calendar import event_rows, expand_blocked_dates
from app.services.classroom import ClassroomService
from app.services.leave import LeaveService
from app.services.staff_attendance import StaffAttendanceService
from app.services.timesheet import TimesheetService

# How the generated school behaves. Tuned so every board has something to show
# AND something to worry about — a board where everything is green teaches the
# reader nothing about whether it works.
ABSENT_RATE = 0.04          # share of student-periods marked absent
LATE_RATE = 0.015
UNMARKED_PERIOD_RATE = 0.12  # periods nobody captured — the heatmap's whole point
HOMEWORK_CHECK_RATE = 0.75   # the rest stay `not_checked` (a teacher gap, not a miss)
HOMEWORK_MISS_RATE = 0.12
STREAK_STUDENTS = 2          # students given a real 3+ day absence streak
WORK_NOTES = {
    "notebook_checking": "Marked class notebooks",
    "exam_work": "Setting the unit test paper",
    "event_work": "Sports day rehearsal",
    "student_support": "Extra help with fractions",
    "prep": "Next week's lesson plans",
    "meeting": "Department catch-up",
    "admin_work": "Records and filing",
    "other": "Library duty",
}


def _ctx(db, org: Organization, membership: Membership) -> CurrentMember:
    """A synthetic request context — the same shape the API builds from a token,
    so services enforce exactly the guards they would in production."""
    return CurrentMember(user=db.get(User, membership.user_id), org=org, membership=membership)


def _pick_org(db, needle: str | None) -> Organization:
    q = select(Organization).order_by(Organization.created_at)
    orgs = list(db.scalars(q))
    if not orgs:
        sys.exit("No organizations in this database — run scripts.seed first.")
    if needle:
        hit = [o for o in orgs if needle.lower() in o.name.lower() or str(o.id) == needle]
        if not hit:
            sys.exit(f"No org matching {needle!r}. Found: {[o.name for o in orgs]}")
        return hit[0]
    # Default to the org that actually looks like a school (has classes).
    for o in orgs:
        if db.scalar(select(func.count(SchoolClass.id)).where(SchoolClass.org_id == o.id)):
            return o
    return orgs[0]


def _school_days(db, org: Organization, year: AcademicYear, n: int, until: date) -> list[date]:
    """The last `n` working days up to `until`, holidays excluded."""
    blocked = expand_blocked_dates(event_rows(db.scalars(
        select(CalendarEvent).where(CalendarEvent.org_id == org.id,
                                    CalendarEvent.academic_year_id == year.id))))
    working = set(year.working_weekdays or [0, 1, 2, 3, 4, 5])
    out: list[date] = []
    d = until
    guard = 0
    while len(out) < n and guard < 120:
        if d.weekday() in working and d not in blocked and d >= year.start_date:
            out.append(d)
        d -= timedelta(days=1)
        guard += 1
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--org", help="org name fragment or id (default: the first org with classes)")
    ap.add_argument("--days", type=int, default=10, help="school days of activity (default 10)")
    ap.add_argument("--today", help="pretend today is this ISO date")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        org = _pick_org(db, args.org)
        year = db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == org.id, AcademicYear.is_active.is_(True)))
        if year is None:
            sys.exit(f"{org.name} has no active academic year.")

        today = date.fromisoformat(args.today) if args.today else datetime.now(UTC).date()
        days = _school_days(db, org, year, max(1, args.days), today)
        rng = random.Random(int(str(org.id).replace("-", "")[:8], 16))

        staff = list(db.execute(
            select(Membership, User.name).join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org.id, Membership.status == "active")
            .order_by(User.name)).all())
        admins = [(ms, n) for ms, n in staff if ms.org_role == "admin"]
        teachers = [(ms, n) for ms, n in staff if ms.org_role == "teacher"]
        if not admins:
            sys.exit(f"{org.name} has no admin member.")
        admin = _ctx(db, org, admins[0][0])

        print(f"Org: {org.name} ({org.id})")
        print(f"Window: {days[0]} -> {days[-1]} ({len(days)} school days)\n")

        _attendance_and_logs(db, admin, org, year, days, rng)
        _homework(db, admin, org, days, rng)
        # Leave BEFORE staff attendance, deliberately: an approved leave
        # pre-unticks that person on the attendance sheet, and marking the day
        # first would leave them recorded present while on approved leave — the
        # two modules would disagree on the board.
        _leave(db, org, teachers, today, admins[0][0])
        _staff_attendance(db, admin, org, days, teachers, rng)
        _timesheets(db, admin, org, days, teachers, rng)
        _daily_checks(db, admin, org, today)
        _report(db, org, today)

        db.commit()
        print("\nDone. Open /dashboard - every tab now has data.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── capture ──────────────────────────────────────────────────────────────────
def _attendance_and_logs(db, admin, org, year, days, rng) -> None:
    """Mark periods off the timetable, with deliberate gaps and a real streak."""
    classes = list(db.scalars(select(SchoolClass).where(
        SchoolClass.org_id == org.id, SchoolClass.academic_year_id == year.id)))
    roster = {
        c.id: list(db.scalars(select(Student.id).where(
            Student.org_id == org.id, Student.class_id == c.id, Student.status == "active")))
        for c in classes
    }
    # Two students who will be absent EVERY marked period of the last 3 school
    # days — so the red list has someone in it and the rule is visibly exercised.
    streakers: set[uuid.UUID] = set()
    for c in classes:
        if roster[c.id] and len(streakers) < STREAK_STUDENTS:
            streakers.add(rng.choice(roster[c.id]))
    streak_days = set(days[-3:])

    att = AttendanceService(db)
    room = ClassroomService(db)
    marked = skipped = logged = 0

    for d in days:
        slots = list(db.execute(
            select(TimetableSlot.class_id, TimetableSlot.period_no,
                   TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == org.id, TimetableSlot.weekday == d.weekday(),
                   TimetableSlot.effective_from <= d,
                   (TimetableSlot.effective_to.is_(None)) | (TimetableSlot.effective_to > d))
            .order_by(TimetableSlot.class_id, TimetableSlot.period_no)).all())
        for class_id, period_no, cs_id in slots:
            # Some periods are simply never captured. That is realistic AND it is
            # what makes the capture heatmap worth looking at.
            if rng.random() < UNMARKED_PERIOD_RATE:
                skipped += 1
                continue
            students = roster.get(class_id, [])
            exceptions: list[AttendanceExceptionIn] = []
            for sid in students:
                if sid in streakers and d in streak_days:
                    exceptions.append(AttendanceExceptionIn(student_id=sid, status="absent"))
                elif rng.random() < ABSENT_RATE:
                    exceptions.append(AttendanceExceptionIn(student_id=sid, status="absent"))
                elif rng.random() < LATE_RATE:
                    exceptions.append(AttendanceExceptionIn(
                        student_id=sid, status="late", late_minutes=rng.choice([5, 10, 15])))
            # One row per student per period is a database invariant
            # (`uq_attendance_exceptions_period_student`). The loop above cannot
            # produce a repeat from a distinct roster, but a roster query that
            # ever returned one would surface as an opaque IntegrityError deep in
            # a flush — so assert it here, where the payload is still in hand.
            seen = [e.student_id for e in exceptions]
            if len(seen) != len(set(seen)):
                dupes = {s for s in seen if seen.count(s) > 1}
                raise RuntimeError(
                    f"duplicate student(s) {dupes} in {class_id} P{period_no} on {d}")
            try:
                att.mark(admin, AttendanceMarkIn(
                    class_id=class_id, period_no=period_no, class_subject_id=cs_id,
                    date=d, exceptions=exceptions))
            except Exception as exc:
                # Name the offending period instead of dying inside SQLAlchemy.
                raise RuntimeError(
                    f"mark failed: class={class_id} period={period_no} date={d} "
                    f"exceptions={[(str(e.student_id), e.status) for e in exceptions]}") from exc
            marked += 1

            # A lesson log on most captured periods — the ones without it are the
            # "attendance but no log" ambiguity the daily report reports.
            if rng.random() < 0.85:
                room.log(admin, LessonLogIn(
                    class_subject_id=cs_id, date=d, period_no=period_no,
                    coverage="full" if rng.random() < 0.8 else "partial",
                    note=None))
                logged += 1
        db.commit()
        print(f"    ...{d}: {marked} marked so far", flush=True)
    print(f"  attendance : {marked} periods marked, {skipped} deliberately left uncaptured")
    print(f"  lessons    : {logged} logged")
    print(f"  streaks    : {len(streakers)} student(s) absent across the last 3 school days")


def _homework(db, admin, org, days, rng) -> None:
    """Check most homework, leave the rest `not_checked` — never as a miss."""
    rows = list(db.scalars(select(HomeworkAssignment).where(
        HomeworkAssignment.org_id == org.id,
        HomeworkAssignment.date >= days[0], HomeworkAssignment.date <= days[-1])))
    room = ClassroomService(db)
    checked = misses = 0
    for hw in rows:
        if rng.random() > HOMEWORK_CHECK_RATE:
            continue  # stays not_checked: the teacher's gap, and a real signal
        sheet = room.homework_sheet(admin, hw.id)
        results = [
            HomeworkResultIn(student_id=r.student_id,
                             status="not_done" if rng.random() < 0.7 else "partial")
            for r in sheet.roster if rng.random() < HOMEWORK_MISS_RATE
        ]
        room.check_homework(admin, hw.id, HomeworkCheckIn(results=results))
        checked += 1
        misses += len(results)
    db.commit()
    print(f"  homework   : {checked}/{len(rows)} checked, {misses} student misses recorded")


def _staff_attendance(db, admin, org, days, teachers, rng) -> None:
    """Mark each day the way an admin actually would: open the sheet, accept the
    people it already pre-unticked for approved leave, untick a few more, save."""
    svc = StaffAttendanceService(db)
    away_total = on_leave_total = 0
    for d in days:
        roster = svc.roster(admin, d)
        # Whoever the leave module already says is away — taking these from the
        # roster rather than re-deriving them is what keeps the two modules
        # agreeing on the board.
        on_leave = [r.member_id for r in roster.roster if r.on_leave]
        extra = [ms.id for ms, _n in teachers
                 if ms.id not in on_leave and rng.random() < 0.08]
        notes = {mid: rng.choice(["Sick", "Family function", "Personal"]) for mid in extra}
        svc.mark(admin, StaffAttendanceIn(
            date=d, absent_member_ids=on_leave + extra, notes=notes))
        away_total += len(extra)
        on_leave_total += len(on_leave)
    db.commit()
    print(f"  staff      : {len(days)} days marked, {away_total} absence(s) "
          f"+ {on_leave_total} on approved leave")


def _timesheets(db, admin, org, days, teachers, rng) -> None:
    """Fill SOME free periods. Leaving the rest empty is deliberate — the board's
    `unfilled_free_periods` is the timesheet's own adoption number."""
    svc = TimesheetService(db)
    keys = list(WORK_TYPES)
    written = 0
    for d in days[-5:]:
        for ms, _name in teachers:
            day = svc.day(admin, ms.id, d)
            free = [s.period_no for s in day.slots if s.kind == "free"]
            for period_no in free:
                if rng.random() > 0.55:
                    continue
                wt = rng.choice(keys)
                try:
                    svc.set_entry(admin, TimesheetEntryIn(
                        date=d, period_no=period_no, work_type=wt,
                        note=WORK_NOTES.get(wt), member_id=ms.id))
                    written += 1
                except Exception:      # a period the grid claimed meanwhile
                    continue
        db.commit()
    print(f"  timesheet  : {written} non-teaching periods recorded")


def _leave(db, org, teachers, today, admin_ms) -> None:
    """One pending application (so the queue has a decision waiting) and one
    approved covering today (so someone reads as on leave, pre-unticked)."""
    if len(teachers) < 2:
        print("  leave      : skipped (needs two teachers)")
        return
    svc = LeaveService(db)
    admin = _ctx(db, org, admin_ms)
    made = []
    for ms, name, start, end, reason in [
        (teachers[0][0], teachers[0][1], today + timedelta(days=3),
         today + timedelta(days=3), "Family wedding"),
        (teachers[1][0], teachers[1][1], today, today, "Fever"),
    ]:
        who = _ctx(db, org, ms)
        try:
            req = svc.apply(who, LeaveApplyIn(start_date=start, end_date=end, reason=reason))
            made.append((req, name, start == today))
        except Exception as exc:       # already has leave covering those dates
            print(f"  leave      : {name} skipped ({exc})")
    for req, _name, approve_now in made:
        if approve_now:
            svc.decide(admin, req.id, LeaveDecisionIn(action="approved", note="Get well"))
    db.commit()
    print(f"  leave      : {len(made)} request(s) - "
          f"{sum(1 for _r, _n, a in made if a)} approved for today, the rest pending")


def _daily_checks(db, admin, org, today) -> None:
    """Recommendations generate themselves from the plan; confirm most of them."""
    from app.schemas.checks import CheckConfirmIn  # noqa: PLC0415
    from app.services.recommendations import RecommendationsService  # noqa: PLC0415

    svc = RecommendationsService(db)
    cs_ids = list(db.scalars(select(ClassSubject.id).where(ClassSubject.org_id == org.id)))
    confirmed = 0
    for cs_id in cs_ids[:20]:
        try:
            out = svc.ensure(admin, cs_id, today)
            for chk in out.checks[:2]:
                svc.confirm(admin, chk.id, CheckConfirmIn(exceptions=[]))
                confirmed += 1
        except Exception:
            continue
    db.commit()
    print(f"  checks     : {confirmed} daily check(s) confirmed")


def _report(db, org, today) -> None:
    from app.services.daily_report import DailyReportService  # noqa: PLC0415

    try:
        DailyReportService(db).generate(org, today)
        db.commit()
        print("  report     : today's briefing regenerated")
    except Exception as exc:
        print(f"  report     : skipped ({exc})")


if __name__ == "__main__":
    raise SystemExit(main())
