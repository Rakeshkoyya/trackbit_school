"""Bring an existing demo school up to *today*, so every screen reads as running.

`scripts/seed.py` builds a school and `scripts/demo_activity.py` generates a few
days of capture. This is the wider pass: it walks the school forward to today AND
fills the modules that had a write side but no data — bands and the support
programme, observations, guardian messages, cover, fee collection, exam locking,
dates of birth.

**Every write goes through the real service, as the person who would have done
it.** Attendance is marked by the subject teacher, not the admin, so
`marked_by_member_id` and `class_periods.teacher_member_id` name a real person and
the day-book reads correctly. Data faked around the services looks right in the
table and wrong on the board — which is the class of bug this script must not
create.

Idempotent: every service used is a full-replace or a get-or-create, and the RNG
is seeded from the org id, so a re-run corrects rather than duplicates.

Usage (from `api/`):

    uv run python -m scripts.demo_fill --org sunrise --list
    uv run python -m scripts.demo_fill --org sunrise --only identity,capture
    uv run python -m scripts.demo_fill --org sunrise              # everything

⚠️  Read the `# ─── ACTIVE:` banner in `api/.env` first. In PRODUCTION mode this
writes to the live database.
"""

from __future__ import annotations

import argparse
import random
import sys
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from app.core.context import CurrentMember
from app.core.database import SessionLocal
from app.core.work_types import WORK_TYPES
from app.models import (
    AcademicYear,
    AssessmentCycle,
    AssessmentScore,
    AttendanceException,
    CalendarEvent,
    ClassPeriod,
    ClassSubject,
    Guardian,
    HomeworkAssignment,
    HomeworkCheck,
    Installment,
    Intervention,
    LessonLog,
    Membership,
    Organization,
    PlanEntry,
    SchoolClass,
    Student,
    StudentFee,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    Term,
    TimetableSlot,
    User,
)
from app.schemas.attendance import AttendanceExceptionIn, AttendanceMarkIn
from app.schemas.classroom import (
    HomeworkCheckIn,
    HomeworkIn,
    HomeworkResultIn,
    LessonLogIn,
    ObservationConceptIn,
    ObservationSectionIn,
    ObservationStudentIn,
)
from app.services.attendance import AttendanceService
from app.services.calendar import event_rows, expand_blocked_dates
from app.services.classroom import ClassroomService
from app.services.timesheet import TimesheetService

# ── how the generated school behaves ─────────────────────────────────────────
# Tuned so every board has something to show AND something to worry about: a
# board where everything is green teaches the reader nothing about whether it
# works, and `not_captured` is a designed state that must appear somewhere.
ABSENT_RATE = 0.045
LATE_RATE = 0.02
UNMARKED_PERIOD_RATE = 0.07   # periods nobody captured — the heatmap's whole point
LOG_RATE = 0.92               # the rest are the attendance-without-log ambiguity
PARTIAL_COVERAGE_RATE = 0.18
HOMEWORK_PER_DAY = 0.45       # chance a class-subject sets homework on a taught day
HOMEWORK_CHECK_RATE = 0.82    # the rest stay `not_checked` — a teacher gap, never a miss
HOMEWORK_MISS_RATE = 0.13

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

HOMEWORK_TEXT = [
    "Exercise {n}, questions 1-8",
    "Read the chapter and write five key points",
    "Worksheet {n} — complete both sides",
    "Practise sums {n}-{m} in the workbook",
    "Learn the new words and write sentences",
    "Finish the map work started in class",
    "Revise today's topic for a short test tomorrow",
]

OBSERVATION_PLAN = {
    "Mathematics": ("Number work", ["Long division", "Word problems"]),
    "English": ("Reading", ["Comprehension", "Reading aloud"]),
    "Science": ("Practical", ["Observation", "Recording results"]),
    "Hindi": ("भाषा", ["Reading", "Writing"]),
    "Social Studies": ("Map work", ["Locating places", "Explaining causes"]),
    "EVS": ("Around us", ["Observation", "Discussion"]),
}


# ── plumbing ─────────────────────────────────────────────────────────────────
def _ctx(db, org: Organization, membership: Membership) -> CurrentMember:
    """A synthetic request context — the same shape the API builds from a token,
    so services enforce exactly the guards they would in production."""
    return CurrentMember(user=db.get(User, membership.user_id), org=org, membership=membership)


class World:
    """Everything the sections share, read once."""

    def __init__(self, db, org: Organization, year: AcademicYear, today: date, days: int):
        self.db, self.org, self.year, self.today = db, org, year, today
        self.rng = random.Random(int(str(org.id).replace("-", "")[:8], 16))

        self.staff = list(db.execute(
            select(Membership, User.name).join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org.id, Membership.status == "active")
            .order_by(User.name)).all())
        self.admins = [(ms, n) for ms, n in self.staff if ms.org_role == "admin"]
        self.teachers = [(ms, n) for ms, n in self.staff if ms.org_role == "teacher"]
        if not self.admins:
            sys.exit(f"{org.name} has no admin member.")
        self.admin = _ctx(db, org, self.admins[0][0])
        self.name_of = {ms.id: n for ms, n in self.staff}
        self._ctx_cache: dict[uuid.UUID, CurrentMember] = {}

        self.classes = list(db.scalars(select(SchoolClass).where(
            SchoolClass.org_id == org.id, SchoolClass.academic_year_id == year.id)
            .order_by(SchoolClass.name, SchoolClass.section)))
        self.roster = {
            c.id: list(db.scalars(select(Student).where(
                Student.org_id == org.id, Student.class_id == c.id,
                Student.status == "active").order_by(Student.roll_no, Student.full_name)))
            for c in self.classes
        }
        self.cs = {r.id: r for r in db.scalars(select(ClassSubject).where(
            ClassSubject.org_id == org.id))}
        self.subject_name = dict(db.execute(
            select(Subject.id, Subject.name).where(Subject.org_id == org.id)).all())
        self.terms = list(db.scalars(select(Term).where(Term.org_id == org.id)
                                     .order_by(Term.start_date)))
        self.days = self._school_days(days)

    def teacher_ctx(self, member_id: uuid.UUID | None) -> CurrentMember:
        """Act as the person who would really have done it — falling back to the
        admin, who may take any class, when the class-subject has no teacher."""
        if member_id is None:
            return self.admin
        hit = self._ctx_cache.get(member_id)
        if hit is None:
            ms = next((m for m, _ in self.staff if m.id == member_id), None)
            hit = self.admin if ms is None else _ctx(self.db, self.org, ms)
            self._ctx_cache[member_id] = hit
        return hit

    def class_label(self, class_id: uuid.UUID) -> str:
        c = next((c for c in self.classes if c.id == class_id), None)
        return "?" if c is None else c.name + (f"-{c.section}" if c.section else "")

    def _school_days(self, n: int) -> list[date]:
        blocked = expand_blocked_dates(event_rows(self.db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.org_id == self.org.id,
                CalendarEvent.academic_year_id == self.year.id))))
        working = set(self.year.working_weekdays or [0, 1, 2, 3, 4, 5])
        out: list[date] = []
        d, guard = self.today, 0
        while len(out) < n and guard < 200:
            if d.weekday() in working and d not in blocked and d >= self.year.start_date:
                out.append(d)
            d -= timedelta(days=1)
            guard += 1
        return sorted(out)

    def slots_on(self, d: date) -> list[tuple[uuid.UUID, int, uuid.UUID]]:
        return list(self.db.execute(
            select(TimetableSlot.class_id, TimetableSlot.period_no,
                   TimetableSlot.class_subject_id)
            .where(TimetableSlot.org_id == self.org.id, TimetableSlot.weekday == d.weekday(),
                   TimetableSlot.effective_from <= d,
                   (TimetableSlot.effective_to.is_(None)) | (TimetableSlot.effective_to > d))
            .order_by(TimetableSlot.class_id, TimetableSlot.period_no)).all())


# ── 1. identity: dates of birth, class teachers ──────────────────────────────
def identity(w: World) -> None:
    """DOB is not decoration. `parent_login` proves a child with their date of
    birth (V1-11 `D-13`), so a portal with no DOBs literally cannot be entered —
    and `whats_on` derives every birthday from this column rather than storing
    events (`S-121`)."""
    db, rng = w.db, w.rng
    # Students: age from the class number, spread across the year, with a handful
    # deliberately landing in the next fortnight so What's-on has something on it.
    soon = [w.today + timedelta(days=i) for i in range(0, 12)]
    filled = 0
    todo = [s for c in w.classes for s in w.roster[c.id] if s.date_of_birth is None]
    picked = set(rng.sample(range(len(todo)), min(len(soon), len(todo)))) if todo else set()
    for i, s in enumerate(todo):
        klass = next((c for c in w.classes if c.id == s.class_id), None)
        try:
            grade = int("".join(ch for ch in (klass.name if klass else "1") if ch.isdigit()) or 1)
        except ValueError:
            grade = 1
        birth_year = w.year.start_date.year - (grade + 5)
        if i in picked:
            anchor = soon[list(picked).index(i) % len(soon)]
            s.date_of_birth = date(birth_year, anchor.month, anchor.day)
        else:
            s.date_of_birth = date(birth_year, rng.randint(1, 12), rng.randint(1, 28))
        filled += 1
    db.flush()
    print(f"  students   : {filled} date(s) of birth filled "
          f"({len(picked)} in the next fortnight)")

    staff_filled = 0
    for i, (ms, _n) in enumerate(w.staff):
        if ms.date_of_birth is not None:
            continue
        if i < 3:      # a couple of staff birthdays on the strip too
            anchor = w.today + timedelta(days=i * 3)
            ms.date_of_birth = date(1988 + i, anchor.month, anchor.day)
        else:
            ms.date_of_birth = date(rng.randint(1976, 1996), rng.randint(1, 12),
                                    rng.randint(1, 28))
        staff_filled += 1
    db.flush()
    print(f"  staff      : {staff_filled} date(s) of birth filled")

    # A class teacher per class — the default owner for support plans (`S-168`)
    # and the one-tap assignee on the follow-up rail.
    assigned = 0
    for i, c in enumerate(w.classes):
        if c.class_teacher_member_id is not None:
            continue
        teaching = list(db.scalars(select(ClassSubject.teacher_member_id).where(
            ClassSubject.org_id == w.org.id, ClassSubject.class_id == c.id,
            ClassSubject.teacher_member_id.is_not(None))))
        c.class_teacher_member_id = (teaching[i % len(teaching)] if teaching
                                     else w.teachers[i % len(w.teachers)][0].id)
        assigned += 1
    db.flush()
    print(f"  classes    : {assigned} class teacher(s) assigned")


# ── 2. capture: attendance + lesson logs, marked by the real teacher ─────────
def _next_topics(w: World) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Per class-subject, the topics still unlogged, in plan order.

    Logging against a real topic is what makes coverage and pace mean anything —
    a log with `topic_id = NULL` advances no syllabus and leaves the board
    reporting a school that teaches nothing.
    """
    logged: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for cs_id, topic_id in w.db.execute(
            select(LessonLog.class_subject_id, LessonLog.topic_id)
            .where(LessonLog.org_id == w.org.id, LessonLog.topic_id.is_not(None))).all():
        logged[cs_id].add(topic_id)

    ordered: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    # Plan order first (the approved baseline), then anything else in the syllabus.
    for cs_id, topic_id in w.db.execute(
            select(PlanEntry.class_subject_id, PlanEntry.topic_id)
            .where(PlanEntry.org_id == w.org.id)
            .order_by(PlanEntry.week_start, PlanEntry.created_at)).all():
        if topic_id not in logged[cs_id]:
            ordered[cs_id].append(topic_id)
    for cs_id, topic_id in w.db.execute(
            select(SyllabusUnit.class_subject_id, SyllabusTopic.id)
            .join(SyllabusTopic, SyllabusTopic.unit_id == SyllabusUnit.id)
            .where(SyllabusUnit.org_id == w.org.id)
            .order_by(SyllabusUnit.position, SyllabusTopic.position)).all():
        if topic_id not in logged[cs_id] and topic_id not in ordered[cs_id]:
            ordered[cs_id].append(topic_id)
    return ordered


def capture(w: World, mark_today_fully: bool) -> None:
    db, rng = w.db, w.rng
    att, room = AttendanceService(db), ClassroomService(db)
    upcoming = _next_topics(w)
    cursor: dict[uuid.UUID, int] = defaultdict(int)

    # Two children given a real absence streak, so the red list has someone in it
    # and the "absent in every marked period of consecutive school days" rule is
    # visibly exercised rather than merely implemented.
    streakers: set[uuid.UUID] = set()
    for c in w.classes[:2]:
        if w.roster[c.id]:
            streakers.add(rng.choice(w.roster[c.id]).id)
    streak_days = set(w.days[-3:])

    marked = skipped = logged = hw_set = 0
    for d in w.days:
        is_today = d == w.today
        for class_id, period_no, cs_id in w.slots_on(d):
            cs = w.cs.get(cs_id)
            who = w.teacher_ctx(cs.teacher_member_id if cs else None)
            skip_rate = UNMARKED_PERIOD_RATE if (mark_today_fully or not is_today) else 0.0
            if rng.random() < skip_rate:
                skipped += 1
                continue
            exceptions: list[AttendanceExceptionIn] = []
            for s in w.roster.get(class_id, []):
                if s.id in streakers and d in streak_days:
                    exceptions.append(AttendanceExceptionIn(student_id=s.id, status="absent"))
                elif rng.random() < ABSENT_RATE:
                    exceptions.append(AttendanceExceptionIn(student_id=s.id, status="absent"))
                elif rng.random() < LATE_RATE:
                    exceptions.append(AttendanceExceptionIn(
                        student_id=s.id, status="late", late_minutes=rng.choice([5, 10, 15])))
            try:
                att.mark(who, AttendanceMarkIn(
                    class_id=class_id, period_no=period_no, class_subject_id=cs_id,
                    date=d, exceptions=exceptions))
            except Exception as exc:
                raise RuntimeError(
                    f"mark failed: class={w.class_label(class_id)} P{period_no} {d}") from exc
            marked += 1

            if rng.random() < LOG_RATE:
                queue = upcoming.get(cs_id) or []
                idx = cursor[cs_id]
                topic_id = queue[idx] if idx < len(queue) else None
                coverage = "partial" if rng.random() < PARTIAL_COVERAGE_RATE else "full"
                room.log(who, LessonLogIn(
                    class_subject_id=cs_id, date=d, period_no=period_no,
                    topic_id=topic_id, coverage=coverage, note=None))
                if topic_id is not None and coverage == "full":
                    cursor[cs_id] = idx + 1
                logged += 1

                # Homework set from the period it belongs to, which is what makes
                # the parent's Today and the checking queue non-empty.
                if rng.random() < HOMEWORK_PER_DAY:
                    n = rng.randint(1, 9)
                    text = rng.choice(HOMEWORK_TEXT).format(n=n, m=n + 7)
                    room.add_homework(who, HomeworkIn(
                        class_subject_id=cs_id, text=text, date=d,
                        due_date=d + timedelta(days=1)))
                    hw_set += 1
        db.commit()
        print(f"    ...{d}: {marked} marked, {logged} logged, {hw_set} homework set",
              flush=True)
    print(f"  attendance : {marked} periods marked, {skipped} deliberately left uncaptured")
    print(f"  lessons    : {logged} logged against the plan's next topic")
    print(f"  homework   : {hw_set} assignment(s) set")


# ── 3. homework checking ─────────────────────────────────────────────────────
def homework(w: World, back_days: int = 21) -> None:
    """Check most of the backlog. The rest stay `not_checked` on purpose — a
    homework nobody opened is the TEACHER's gap and may never render as a
    child's miss (HW-1), so the boards need some of it to exist.

    The absentee set is read in ONE query for the whole window rather than via
    `homework_sheet`, which computes a per-student miss streak and costs ~430
    round-trips per assignment. `check_homework` is still the only writer, so the
    derived caches (`done_count`/`total_count`) and `checked_by` are exactly what
    the teacher's own tap would have produced.
    """
    db, rng = w.db, w.rng
    room = ClassroomService(db)
    since = w.today - timedelta(days=back_days)
    rows = list(db.scalars(select(HomeworkAssignment).where(
        HomeworkAssignment.org_id == w.org.id, HomeworkAssignment.date >= since,
        HomeworkAssignment.date < w.today)
        .order_by(HomeworkAssignment.date)))
    already = set(db.scalars(select(HomeworkCheck.assignment_id).where(
        HomeworkCheck.org_id == w.org.id)))

    # (class_id, date) -> students absent in any marked period that day.
    absent: dict[tuple[uuid.UUID, date], set[uuid.UUID]] = defaultdict(set)
    for class_id, d, student_id in db.execute(
            select(ClassPeriod.class_id, ClassPeriod.date, AttendanceException.student_id)
            .join(AttendanceException, AttendanceException.period_id == ClassPeriod.id)
            .where(ClassPeriod.org_id == w.org.id, ClassPeriod.date >= since,
                   AttendanceException.status == "absent")).all():
        absent[(class_id, d)].add(student_id)

    checked = misses = 0
    for hw in rows:
        if hw.id in already or rng.random() > HOMEWORK_CHECK_RATE:
            continue
        cs = w.cs.get(hw.class_subject_id)
        if cs is None:
            continue
        who = w.teacher_ctx(cs.teacher_member_id)
        roster = ([s for s in w.roster.get(cs.class_id, []) if s.id == hw.student_id]
                  if hw.student_id else w.roster.get(cs.class_id, []))
        away = absent.get((cs.class_id, hw.date), set())
        results: list[HomeworkResultIn] = []
        for s in roster:
            if s.id in away:
                # Absent the day it was set: `carried`, which leaves the
                # denominator entirely (`D-34`). Never a refusal.
                results.append(HomeworkResultIn(student_id=s.id, status="carried"))
            elif rng.random() < HOMEWORK_MISS_RATE:
                results.append(HomeworkResultIn(
                    student_id=s.id,
                    status=rng.choices(["not_done", "partial", "late"],
                                       weights=[6, 2, 2])[0]))
        try:
            room.check_homework(who, hw.id, HomeworkCheckIn(results=results))
        except Exception:
            continue
        checked += 1
        misses += len(results)
        if checked % 25 == 0:
            db.commit()
            print(f"    ...{checked} checked", flush=True)
    db.commit()
    print(f"  homework   : {checked} newly checked of {len(rows)}, {misses} verdicts "
          f"({len(rows) - checked - len(already & {r.id for r in rows})} left "
          f"not_checked on purpose)")


# ── 4. observations: the optional deep log ───────────────────────────────────
def observations(w: World) -> None:
    """Named sections with only the deviating students flagged (exception-only,
    P1v2). Growth and the report card have an observations block that has been
    empty since it shipped."""
    db, rng = w.db, w.rng
    room = ClassroomService(db)
    written = flags = 0
    for d in w.days[-6:]:
        for class_id, period_no, cs_id in w.slots_on(d):
            cs = w.cs.get(cs_id)
            if cs is None:
                continue
            plan = OBSERVATION_PLAN.get(w.subject_name.get(cs.subject_id, ""))
            if plan is None or rng.random() > 0.22:
                continue
            section, concepts = plan
            roster = w.roster.get(class_id, [])
            if not roster:
                continue
            who = w.teacher_ctx(cs.teacher_member_id)
            concept_rows = []
            for concept in concepts:
                picks = rng.sample(roster, min(len(roster), rng.randint(0, 3)))
                concept_rows.append(ObservationConceptIn(
                    concept=concept,
                    students=[ObservationStudentIn(
                        student_id=s.id,
                        rating=rng.choices(["needs_work", "excellent"], weights=[3, 2])[0],
                        note=None) for s in picks]))
                flags += len(picks)
            try:
                room.save_observation_section(who, ObservationSectionIn(
                    class_subject_id=cs_id, section=section, date=d,
                    period_no=period_no, concepts=concept_rows))
                written += 1
            except Exception:
                continue
        db.commit()
    print(f"  deep log   : {written} section(s), {flags} student flag(s)")


# ── 5. daily checks ──────────────────────────────────────────────────────────
def checks(w: World) -> None:
    """Recommendations generate themselves from the plan × band distribution —
    zero teacher setup — and the teacher confirms "class did it ✓"."""
    from app.schemas.checks import CheckConfirmIn  # noqa: PLC0415
    from app.services.recommendations import RecommendationsService  # noqa: PLC0415

    db, rng = w.db, w.rng
    svc = RecommendationsService(db)
    made = confirmed = 0
    for d in w.days[-4:]:
        for _class_id, _period_no, cs_id in w.slots_on(d):
            cs = w.cs.get(cs_id)
            if cs is None:
                continue
            who = w.teacher_ctx(cs.teacher_member_id)
            try:
                out = svc.ensure(who, cs_id, d)
            except Exception:
                continue
            made += len(out.checks)
            for chk in out.checks:
                if chk.confirmed or rng.random() > 0.78:
                    continue
                try:
                    svc.confirm(who, chk.id, CheckConfirmIn(exceptions=[]))
                    confirmed += 1
                except Exception:
                    continue
        db.commit()
    print(f"  checks     : {made} generated, {confirmed} confirmed")


# ── 6. staff: attendance, cover, timesheets, leave ───────────────────────────
def staff(w: World) -> None:
    from app.schemas.insights import SubstitutionIn  # noqa: PLC0415
    from app.schemas.staff import (  # noqa: PLC0415
        LeaveApplyIn,
        LeaveDecisionIn,
        StaffAttendanceIn,
    )
    from app.services.leave import LeaveService  # noqa: PLC0415
    from app.services.staff_attendance import StaffAttendanceService  # noqa: PLC0415
    from app.services.substitution import SubstitutionService  # noqa: PLC0415

    db, rng = w.db, w.rng
    # Leave BEFORE attendance, deliberately: an approved leave pre-unticks that
    # person on the sheet, and marking the day first would record them present
    # while on approved leave — the two modules would disagree on the board.
    leave = LeaveService(db)
    made = 0
    plan = [
        (0, w.today + timedelta(days=2), w.today + timedelta(days=4), "Family wedding", None),
        (1, w.today, w.today, "Fever", "approved"),
        (2, w.today, w.today + timedelta(days=1), "Medical procedure", "approved"),
        (3, w.today + timedelta(days=6), w.today + timedelta(days=6), "Personal work", None),
    ]
    for idx, start, end, reason, decision in plan:
        if idx >= len(w.teachers):
            continue
        ms = w.teachers[idx][0]
        try:
            req = leave.apply(_ctx(db, w.org, ms),
                              LeaveApplyIn(start_date=start, end_date=end, reason=reason))
        except Exception:
            continue
        made += 1
        if decision:
            try:
                leave.decide(w.admin, req.id, LeaveDecisionIn(action=decision, note="Approved"))
            except Exception:
                pass
    db.commit()
    print(f"  leave      : {made} request(s), 2 approved and covering today")

    # Staff attendance: open the sheet, accept the people leave already
    # pre-unticked, untick a few more, save. Taking the on-leave list FROM the
    # roster rather than re-deriving it is what keeps the two agreeing.
    sa = StaffAttendanceService(db)
    away = on_leave = 0
    for d in w.days:
        roster = sa.roster(w.admin, d)
        booked = [r.member_id for r in roster.roster if r.on_leave]
        extra = [ms.id for ms, _n in w.teachers
                 if ms.id not in booked and rng.random() < 0.05]
        notes = {mid: rng.choice(["Sick", "Family function", "Personal"]) for mid in extra}
        try:
            sa.mark(w.admin, StaffAttendanceIn(
                date=d, absent_member_ids=booked + extra, notes=notes))
        except Exception:
            continue
        away += len(extra)
        on_leave += len(booked)
    db.commit()
    print(f"  staff      : {len(w.days)} day(s) marked, {away} absence(s) "
          f"+ {on_leave} on approved leave")

    # Cover for whoever is away today — the board is the point of recording it.
    sub = SubstitutionService(db)
    covered = 0
    for d in w.days[-3:]:
        try:
            absent_ids = {r.member_id for r in sa.roster(w.admin, d).roster if not r.present}
        except Exception:
            continue
        if not absent_ids:
            continue
        for class_id, period_no, cs_id in w.slots_on(d):
            cs = w.cs.get(cs_id)
            if cs is None or cs.teacher_member_id not in absent_ids:
                continue
            free = [ms.id for ms, _n in w.teachers if ms.id not in absent_ids]
            rng.shuffle(free)
            for candidate in free[:6]:
                try:
                    sub.create(w.admin, SubstitutionIn(
                        date=d, class_id=class_id, period_no=period_no,
                        class_subject_id=cs_id, substitute_member_id=candidate,
                        absent_member_id=cs.teacher_member_id, note="Cover arranged"))
                    covered += 1
                    break
                except Exception:
                    continue
        db.commit()
    print(f"  cover      : {covered} period(s) covered")


def timesheets(w: World) -> None:
    """Fill SOME free periods. Leaving the rest empty is deliberate —
    `unfilled_free_periods` is the timesheet's own adoption number, and under
    `D-23` an unfilled period genuinely IS free.

    Its own section because it is the slowest thing here (`TimesheetService.day`
    rebuilds the whole day view per teacher per date) and it is the piece most
    likely to need re-running on its own.
    """
    from app.schemas.staff import TimesheetEntryIn  # noqa: PLC0415

    db, rng = w.db, w.rng
    ts = TimesheetService(db)
    keys = list(WORK_TYPES)
    written = 0
    for d in w.days:
        for ms, _n in w.teachers:
            try:
                day = ts.day(w.admin, ms.id, d)
            except Exception:
                continue
            for slot in day.slots:
                if slot.kind != "free" or rng.random() > 0.6:
                    continue
                wt = rng.choice(keys)
                try:
                    ts.set_entry(w.admin, TimesheetEntryIn(
                        date=d, period_no=slot.period_no, work_type=wt,
                        note=WORK_NOTES.get(wt), member_id=ms.id))
                    written += 1
                except Exception:
                    continue
        db.commit()
        print(f"    ...{d}: {written} recorded so far", flush=True)
    print(f"  timesheet  : {written} non-teaching period(s) recorded")


# ── 7. bands + the support programme ─────────────────────────────────────────
def bands(w: World) -> None:
    """`band_descriptors` was empty, and V1-9's rule is that **the letter never
    renders without its sentence** (`S-166`) — so every band surface was either
    blank or showing a bare letter. And every existing row had
    `subject_id = NULL`, which is the retired overall letter, read by nothing
    (`D-75`)."""
    from app.schemas.bands import BandFileIn, BandFileRow, CheckpointIn  # noqa: PLC0415
    from app.services.bands import BandService  # noqa: PLC0415
    from app.services.support import SupportService  # noqa: PLC0415

    db, rng = w.db, w.rng
    svc = BandService(db)
    core = ["English", "Mathematics", "Science", "Hindi", "Social Studies"]
    ids = [sid for sid, name in w.subject_name.items() if name in core]
    svc.set_monitored(w.admin, ids)      # seeds the three descriptors per subject
    db.commit()
    print(f"  descriptors: {len(ids)} monitored subject(s) x 3 tiers seeded")

    term = next((t for t in w.terms if t.start_date <= w.today <= t.end_date),
                w.terms[-1] if w.terms else None)
    if term is None:
        print("  bands      : skipped (no term)")
        return

    # File each monitored class-subject from the marks that exist, so the tier
    # has a reason behind it rather than being a coin toss.
    pcts = _score_pct_by_student_subject(w)
    thresholds = svc.thresholds(w.admin)
    filed = 0
    c_children: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = []   # student, subject, class
    for c in w.classes:
        for sid in ids:
            cs = next((r for r in w.cs.values()
                       if r.class_id == c.id and r.subject_id == sid), None)
            if cs is None:
                continue
            a_min, b_min = thresholds.get(sid, (75, 50))
            rows: list[BandFileRow] = []
            for s in w.roster[c.id]:
                pct = pcts.get((s.id, sid))
                if pct is None:
                    # Did not sit anything in this subject: **not assessed** is a
                    # word, never a C (ux §5). Most children still get a tier so
                    # the board is not mostly blanks.
                    tier = None if rng.random() < 0.08 else rng.choices(
                        ["A", "B", "C"], weights=[3, 5, 2])[0]
                else:
                    tier = "A" if pct >= a_min else "B" if pct >= b_min else "C"
                rows.append(BandFileRow(student_id=s.id, tier=tier))
                if tier == "C":
                    c_children.append((s.id, sid, c.id))
            try:
                filed += svc.file_bands(w.admin, BandFileIn(
                    class_id=c.id, subject_id=sid, term_id=term.id,
                    source="test", note="Term assessment", rows=rows))
            except Exception:
                continue
        db.commit()
    print(f"  bands      : {filed} per-subject placement(s) filed for {term.name}")

    # Every C child gets an owner by name (`D-77`) — assign_owner creates the
    # support plan, which is what makes /support non-empty.
    owned = 0
    for student_id, subject_id, _class_id in c_children:
        try:
            svc.assign_owner(w.admin, student_id, subject_id, None, term.id)
            owned += 1
        except Exception:
            continue
    db.commit()
    print(f"  support    : {owned} C child(ren) given an owner")

    # A few weeks of check-ins, so the weekly habit has a history to read.
    sup = SupportService(db)
    ivs = list(db.scalars(select(Intervention).where(
        Intervention.org_id == w.org.id, Intervention.status == "active")))
    monday = w.today - timedelta(days=w.today.weekday())
    notes = [
        ("Extra reading practice, 10 minutes daily", "Reads more fluently aloud",
         "Move to unseen passages"),
        ("Worked through the tables again", "Fewer slips in multiplication",
         "Try two-step word problems"),
        ("Paired him with a stronger partner", "Asks for help now instead of stopping",
         "Keep the pairing another week"),
    ]
    # A sample, not all of them: a support plan with no check-in yet is the
    # honest state for a programme that started this term, and it is what the
    # board's "nothing recorded" row exists to show.
    ins = 0
    sample = ivs if len(ivs) <= 80 else rng.sample(ivs, 80)
    for iv in sample:
        owner = w.teacher_ctx(iv.owner_member_id)
        for back in range(rng.randint(1, 3)):
            worked, changed, nxt = rng.choice(notes)
            try:
                sup.check_in(owner, iv.id, CheckpointIn(
                    week_start=monday - timedelta(days=7 * back),
                    worked_on=worked, what_changed=changed, next_step=nxt,
                    ready_to_retest=rng.random() < 0.2))
                ins += 1
            except Exception:
                continue
        if ins % 30 == 0:
            db.commit()
    db.commit()
    print(f"  check-ins  : {ins} weekly check-in(s) across {len(sample)} of "
          f"{len(ivs)} support plan(s)")


def _score_pct_by_student_subject(w: World) -> dict[tuple[uuid.UUID, uuid.UUID], float]:
    out: dict[tuple[uuid.UUID, uuid.UUID], list[float]] = defaultdict(lambda: [0.0, 0.0])
    for sid, subj, score, mx in w.db.execute(
            select(AssessmentScore.student_id, AssessmentScore.subject_id,
                   AssessmentScore.score, AssessmentScore.max_score)
            .where(AssessmentScore.org_id == w.org.id,
                   AssessmentScore.subject_id.is_not(None))).all():
        if not mx:
            continue
        pair = out[(sid, subj)]
        pair[0] += float(score)
        pair[1] += float(mx)
    return {k: v[0] / v[1] * 100 for k, v in out.items() if v[1]}


# ── 8. exams: the school's own type, then verify and lock ────────────────────
def exams(w: World) -> None:
    """0 of 181 cycles were locked, so no exam could show *verified*, no score
    carried a `verified_by`, and band promotion (`D-76`, locked-only) was
    impossible on every exam in the school."""
    from app.services.exam_types import ExamTypeService  # noqa: PLC0415
    from app.services.exams import ExamService  # noqa: PLC0415

    db, rng = w.db, w.rng
    types = {t.system_type: t for t in ExamTypeService(db).ensure_defaults(w.admin)}
    db.commit()

    cycles = list(db.scalars(select(AssessmentCycle).where(
        AssessmentCycle.org_id == w.org.id).order_by(AssessmentCycle.date)))
    typed = 0
    for cyc in cycles:
        et = types.get(cyc.type)
        if et is not None and cyc.exam_type_id is None:
            cyc.exam_type_id = et.id
            cyc.scale = et.scale
            typed += 1
    db.flush()
    db.commit()
    print(f"  exam types : {typed} exam(s) filed under the school's own type")

    svc = ExamService(db)
    locked = 0
    for cyc in cycles:
        if cyc.locked_at is not None or cyc.date >= w.today - timedelta(days=3):
            continue          # this week's marks are still being entered
        if rng.random() > 0.85:
            continue          # a few left open, which is the honest state
        try:
            svc.lock(w.admin, cyc.id)
            locked += 1
        except Exception:
            continue
        if locked % 30 == 0:
            db.commit()
    db.commit()
    print(f"  exams      : {locked}/{len(cycles)} verified and locked")


# ── 9. fees: money actually collected ────────────────────────────────────────
def fees(w: World) -> None:
    """`fee_transactions` was empty: 240 families, ₹54.6L due, nothing received —
    so the collection board read 0% and the defaulter list was every child in the
    school, which is a board nobody can act on."""
    from app.schemas.fees import PaymentIn  # noqa: PLC0415
    from app.services.fees import FeeService  # noqa: PLC0415

    db, rng = w.db, w.rng
    svc = FeeService(db)
    sfs = list(db.scalars(select(StudentFee).where(StudentFee.org_id == w.org.id)))
    modes = ["cash", "upi", "cheque", "bank"]
    paid = partial = 0
    receipt = 1000
    for i, sf in enumerate(sfs):
        insts = sorted(db.scalars(select(Installment).where(
            Installment.student_fee_id == sf.id)), key=lambda x: x.installment_number)
        roll = rng.random()
        # ~72% have cleared the first instalment, ~10% part-paid, ~18% still owe
        # it — enough of a defaulter list to call, not so much it is meaningless.
        for inst in insts:
            if inst.due_date is None or inst.due_date > w.today:
                continue
            if float(inst.paid_amount or 0) >= float(inst.amount):
                continue
            if roll < 0.72:
                amount = Decimal(str(inst.amount)) - Decimal(str(inst.paid_amount or 0))
                paid += 1
            elif roll < 0.82:
                due = Decimal(str(inst.amount)) - Decimal(str(inst.paid_amount or 0))
                amount = (due / 2).quantize(Decimal("1"))
                partial += 1
            else:
                continue
            receipt += 1
            try:
                svc.pay(w.admin, inst.id, PaymentIn(
                    amount=amount, mode=rng.choice(modes),
                    receipt_number=f"R{receipt}",
                    paid_on=inst.due_date + timedelta(days=rng.randint(0, 20)),
                    note=None))
            except Exception:
                continue
        if i % 40 == 0:
            db.commit()
    db.commit()
    print(f"  fees       : {paid} instalment(s) cleared, {partial} part-paid")

    # The conversation history (`D-84`) — "reminded" is an event, but what makes
    # a row go away is what the family actually said (`S-161`).
    from app.models import FeeNote  # noqa: PLC0415

    said = [
        "Spoke to the mother — paying after the 15th, salary date.",
        "Called twice, no answer. Will try the father's number.",
        "Father came to the office, asked for a two-instalment split.",
        "Reminded at the PTM. Says the cheque is written.",
        "Requested a concession — sent to the Director.",
    ]
    outstanding = [sf for sf in sfs if sf.status != "paid"]
    rng.shuffle(outstanding)
    notes = 0
    for sf in outstanding[:22]:
        db.add(FeeNote(org_id=w.org.id, student_fee_id=sf.id, kind="call",
                       said=rng.choice(said),
                       author_member_id=w.admin.membership.id))
        notes += 1
    db.commit()
    print(f"  fee notes  : {notes} conversation(s) recorded")


# ── 10. tasks + the guardian week note ───────────────────────────────────────
def tasks(w: World) -> None:
    from app.models import Board  # noqa: PLC0415
    from app.schemas.task import TaskCreateRequest  # noqa: PLC0415
    from app.services.task import TaskService  # noqa: PLC0415

    db, rng = w.db, w.rng
    svc = TaskService(db)
    board = db.scalar(select(Board).where(Board.org_id == w.org.id, Board.name == "General"))
    if board is None:
        print("  tasks      : skipped (no board)")
        return
    plan = [
        ("Order lab consumables for Term 2 practicals", "admin_work", -2),
        ("Fix the leaking tap in the junior washroom", "maintenance", -1),
        ("Collect consent forms for the science excursion", "admin_work", 1),
        ("Print the Term 2 exam datesheet for notice boards", "exam_work", 2),
        ("Service the projector in Class 7", "maintenance", 3),
        ("Call the vendor about the library book order", "admin_work", -4),
        ("Prepare the assembly rota for August", "prep", 1),
        ("Check the fire extinguisher expiry dates", "maintenance", 5),
        ("Photocopy the Class 5 revision worksheets", "prep", 0),
        ("Update the emergency contact list", "admin_work", -3),
        ("Arrange transport for the inter-school match", "event_work", 4),
        ("Deep clean the science laboratory", "maintenance", 6),
    ]
    made = done = 0
    for title, category, offset in plan:
        assignee = rng.choice(w.teachers)[0] if w.teachers else None
        try:
            t = svc.create(w.admin, TaskCreateRequest(
                board_id=board.id, title=title, category=category,
                due_at=datetime.combine(w.today + timedelta(days=offset),
                                        datetime.min.time(), tzinfo=UTC) + timedelta(hours=12),
                # No `is_critical`: it is plan-gated (`enforce_critical_allowed`),
                # and a demo school on the free plan would lose the task silently.
                assignee_id=assignee.user_id if assignee else None,
                priority=2 if offset < 0 else 0))
        except Exception:
            continue
        made += 1
        # Some of the past-due ones were actually finished — a board where
        # everything is open reads as a school that never closes anything.
        if offset < 0 and rng.random() < 0.5:
            try:
                svc.complete(w.admin, t.id, None)
                done += 1
            except Exception:
                pass
    db.commit()
    print(f"  tasks      : {made} created, {done} already completed")

    # The Saturday guardian note — the third of the three guardian message kinds,
    # so the parent inbox and the reach block have more than absence alerts.
    from app.services.notify_guardian import notify_guardians  # noqa: PLC0415

    sent = 0
    for c in w.classes:
        by_student: dict[uuid.UUID, list[Guardian]] = defaultdict(list)
        for sid, g in db.execute(
                select(Student.id, Guardian).join(Guardian, Guardian.student_id == Student.id)
                .where(Student.org_id == w.org.id, Student.class_id == c.id)).all():
            by_student[sid].append(g)
        for sid, guardians in by_student.items():
            student = next((s for s in w.roster[c.id] if s.id == sid), None)
            if student is None:
                continue
            sent += notify_guardians(
                db, org_id=w.org.id, student_id=sid, guardians=guardians,
                kind="week_summary", title="This week at school",
                body=(f"{student.full_name.split()[0]} attended school this week. "
                      f"Homework was set in most subjects — please check the diary."),
                dedupe_key=f"week:{w.today.isoformat()}:{sid}").notified
        db.commit()
    print(f"  guardians  : {sent} week note(s) delivered")


# ── 11. the briefing ─────────────────────────────────────────────────────────
def report(w: World) -> None:
    from app.services.daily_report import DailyReportService  # noqa: PLC0415

    svc = DailyReportService(w.db)
    n = 0
    for d in w.days[-5:]:
        try:
            svc.generate(w.org, d)
            w.db.commit()
            n += 1
        except Exception as exc:
            w.db.rollback()
            print(f"  report     : {d} skipped ({exc})")
    print(f"  report     : {n} daily briefing(s) regenerated")


SECTIONS = {
    "identity": identity,
    "capture": None,          # takes an extra flag, dispatched below
    "homework": homework,
    "observations": observations,
    "checks": checks,
    "staff": staff,
    "timesheets": timesheets,
    "bands": bands,
    "exams": exams,
    "fees": fees,
    "tasks": tasks,
    "report": report,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--org", help="org name fragment or id")
    ap.add_argument("--days", type=int, default=6, help="school days to (re)capture")
    ap.add_argument("--today", help="pretend today is this ISO date")
    ap.add_argument("--only", help="comma-separated sections (default: all)")
    ap.add_argument("--list", action="store_true", help="list the sections and exit")
    ap.add_argument("--partial-today", action="store_true",
                    help="leave today's later periods uncaptured, as a live school would")
    args = ap.parse_args()

    if args.list:
        print("sections:", ", ".join(SECTIONS))
        return 0

    db = SessionLocal()
    try:
        orgs = list(db.scalars(select(Organization).order_by(Organization.created_at)))
        needle = args.org
        org = None
        if needle:
            org = next((o for o in orgs
                        if needle.lower() in o.name.lower() or str(o.id) == needle), None)
            if org is None:
                sys.exit(f"No org matching {needle!r}: {[o.name for o in orgs]}")
        else:
            org = next((o for o in orgs if db.scalar(select(func.count(SchoolClass.id))
                                                     .where(SchoolClass.org_id == o.id))), None)
        if org is None:
            sys.exit("No organizations with classes in this database.")
        year = db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == org.id, AcademicYear.is_active.is_(True)))
        if year is None:
            sys.exit(f"{org.name} has no active academic year.")

        today = date.fromisoformat(args.today) if args.today else datetime.now(UTC).date()
        w = World(db, org, year, today, max(1, args.days))
        wanted = ([s.strip() for s in args.only.split(",")] if args.only else list(SECTIONS))
        unknown = [s for s in wanted if s not in SECTIONS]
        if unknown:
            sys.exit(f"Unknown section(s) {unknown}. Known: {list(SECTIONS)}")

        print(f"Org    : {org.name} ({org.id})")
        print(f"Window : {w.days[0]} -> {w.days[-1]} ({len(w.days)} school days)")
        print(f"Sections: {', '.join(wanted)}\n")

        for name in wanted:
            print(f"[{name}]")
            if name == "capture":
                capture(w, mark_today_fully=not args.partial_today)
            else:
                SECTIONS[name](w)
            db.commit()
            print()

        print("Done.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
