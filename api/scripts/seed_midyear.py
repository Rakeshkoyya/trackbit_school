"""The mid-year school fixture (V1-13, plan §5's acceptance test).

The demo org (`scripts/seed.py`) is a school that has been running since April.
This one is the case v1 was actually built against and the one no other fixture
exercises:

    A school adopts TrackBit part-way through a running year. The term that has
    already finished was never in the system. They hand over a roster and the
    CURRENT term's syllabus only. Next term they will size the rest.

Three states have to coexist on one screen without any of them reading as
failure — which is the whole point of the fixture:

    Term 1  pre-tracking, never planned  -> `unplanned`, a WORD in neutral grey.
                                            Never a RAG colour, never a red row,
                                            never inside a denominator.
    Term 2  sized and approved           -> the only term that is rated.
    Term 3  chapters exist, unsized      -> `unestimated`, with "size these" as
                                            the offered next action, not a warning.

`tracking_start_date` is set to the start of Term 2, so every denominator in the
product starts there. Plan §5 rule 2: a figure must name its window — *"82% of
school days since 1 Jul"*, never a bare 82%.

Run it after `scripts.seed`; the two orgs are independent and neither wipes the
other.

    uv run python -m scripts.seed_midyear
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    AcademicYear,
    AttendanceException,
    CalendarEvent,
    ClassPeriod,
    ClassSubject,
    Guardian,
    Installment,
    LessonLog,
    Membership,
    Organization,
    Plan,
    PlanApproval,
    PlanEntry,
    SchoolClass,
    Student,
    StudentFee,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    Term,
    TimetableSlot,
    Transaction,
    User,
)
from app.services.fee_math import recompute_student_fee

ORG_NAME = "Nalanda Vidyalaya (mid-year demo)"
SCHOOL_CODE = "MIDYR26"
EMAILS = [
    "head@midyear.trackbit.app",
    "asha@midyear.trackbit.app",
    "bhavani@midyear.trackbit.app",
    "chandra@midyear.trackbit.app",
    "divya@midyear.trackbit.app",
]

YEAR_START = date(2026, 4, 1)
YEAR_END = date(2027, 3, 31)
# Term 2 opens on 1 Jul and the school joined with it. "Today" in the demo data
# is early August, so there is roughly a month of real capture to render and
# three months of deliberate, honest emptiness before it.
T1 = (date(2026, 4, 1), date(2026, 6, 30))
T2 = (date(2026, 7, 1), date(2026, 10, 31))
T3 = (date(2026, 11, 1), date(2027, 3, 31))
TRACKING_START = T2[0]


def q(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def wipe(db: Session) -> None:
    org = db.scalar(select(Organization).where(Organization.name == ORG_NAME))
    if org:
        db.execute(delete(Organization).where(Organization.id == org.id))
        db.flush()
    db.execute(delete(User).where(User.email.in_(EMAILS)))
    db.flush()


def build() -> None:
    db = SessionLocal()
    try:
        wipe(db)
        now = datetime.now(UTC)
        today = date(2026, 8, 2) if date.today() < T2[0] else date.today()
        if today > T2[1]:
            today = T2[1]

        org = Organization(name=ORG_NAME, timezone="Asia/Kolkata", plan="pro",
                           school_code=SCHOOL_CODE, state="Telangana", board="CBSE")
        db.add(org)
        db.flush()

        head = User(name="Lakshmi (Head)", email=EMAILS[0],
                    password_hash=hash_password("demo1234"))
        asha = User(name="Asha", email=EMAILS[1], password_hash=hash_password("demo1234"))
        bhavani = User(name="Bhavani", email=EMAILS[2], password_hash=hash_password("demo1234"))
        chandra = User(name="Chandra", email=EMAILS[3], password_hash=hash_password("demo1234"))
        divya = User(name="Divya", email=EMAILS[4], password_hash=hash_password("demo1234"))
        db.add_all([head, asha, bhavani, chandra, divya])
        db.flush()

        mships: dict[User, Membership] = {}
        for role, u in [("admin", head), ("teacher", asha), ("teacher", bhavani),
                        ("teacher", chandra), ("teacher", divya)]:
            mem = Membership(org_id=org.id, user_id=u.id, org_role=role, last_active_at=now)
            db.add(mem)
            mships[u] = mem
        db.flush()

        # ── the year, and the line before which nothing is claimed ────────────
        year = AcademicYear(org_id=org.id, label="2026-27", start_date=YEAR_START,
                            end_date=YEAR_END, is_active=True,
                            tracking_start_date=TRACKING_START, periods_per_day=6)
        year.period_times = [
            {"start": f"{8 + i:02d}:30", "end": f"{9 + i:02d}:10", "kind": "period"}
            for i in range(6)
        ]
        db.add(year)
        db.flush()

        terms = {}
        for name, (a, b) in [("Term 1", T1), ("Term 2", T2), ("Term 3", T3)]:
            t = Term(org_id=org.id, academic_year_id=year.id, name=name,
                     start_date=a, end_date=b)
            db.add(t)
            terms[name] = t
        db.flush()

        db.add(CalendarEvent(org_id=org.id, academic_year_id=year.id, type="holiday",
                             title="Independence Day", start_date=date(2026, 8, 15),
                             end_date=date(2026, 8, 15)))

        subjects = {}
        for name in ["English", "Mathematics", "Science"]:
            s = Subject(org_id=org.id, name=name)
            db.add(s)
            subjects[name] = s
        db.flush()

        # Each class gets its own pair of teachers, so the grid cannot double-book
        # anyone (the same rule the demo seed now follows).
        staff = {"8-A": (asha, bhavani), "8-B": (chandra, divya)}
        classes = {}
        for cname, section, ct in [("8", "A", asha), ("8", "B", chandra)]:
            c = SchoolClass(org_id=org.id, academic_year_id=year.id, name=cname,
                            section=section, class_teacher_member_id=mships[ct].id)
            db.add(c)
            classes[f"{cname}-{section}"] = c
        db.flush()

        per_week = {"English": 5, "Mathematics": 5, "Science": 5}
        css: dict[tuple, ClassSubject] = {}
        for ckey, c in classes.items():
            sci_t, arts_t = staff[ckey]
            for sname, pw in per_week.items():
                teacher = sci_t if sname in ("Mathematics", "Science") else arts_t
                cs = ClassSubject(org_id=org.id, class_id=c.id, subject_id=subjects[sname].id,
                                  teacher_member_id=mships[teacher].id, periods_per_week=pw)
                db.add(cs)
                css[(ckey, sname)] = cs
        db.flush()

        # ── the roster ────────────────────────────────────────────────────────
        names = ["Aarav", "Diya", "Ishaan", "Kiara", "Neel", "Riya",
                 "Vivaan", "Anaya", "Reyansh", "Myra", "Advik", "Sara"]
        students: list[Student] = []
        for i, name in enumerate(names):
            ckey = "8-A" if i < 6 else "8-B"
            st = Student(org_id=org.id, admission_no=f"MY{100 + i}", full_name=name,
                         class_id=classes[ckey].id, roll_no=str((i % 6) + 1),
                         status="active",
                         date_of_birth=date(2012, ((i % 12) + 1), ((i % 27) + 1)),
                         # A school that joins mid-year admitted these children
                         # before it started tracking; enrolled_on says so rather
                         # than implying they appeared on 1 July.
                         enrolled_on=YEAR_START)
            db.add(st)
            db.flush()
            db.add(Guardian(org_id=org.id, student_id=st.id, name=f"{name}'s father",
                            relation="Father", phone=f"+9198111200{i:02d}", is_primary=True))
            students.append(st)
        db.flush()

        # ── the syllabus: one term sized, one never entered, one not yet sized ─
        #
        # This is the shape the whole fixture exists to produce. Do not "tidy" it
        # by sizing Term 1 or Term 3 — the states ARE the test.
        chapters = {
            "Term 1": {  # pre-tracking: recorded so the year is complete, never planned
                "Number Systems": ["Rational numbers", "Exponents"],
                "Light": ["Reflection", "Mirrors"],
            },
            "Term 2": {  # the live term: sized, planned and approved
                "Algebraic Expressions": ["Terms & factors", "Addition", "Multiplication"],
                "Motion": ["Speed", "Distance-time graphs"],
            },
            "Term 3": {  # known chapters, not yet sized -> "unestimated", never red
                "Mensuration": ["Area of a trapezium", "Volume of a cuboid"],
                "Sound": ["Production of sound", "Hearing"],
            },
        }

        approved_entries = 0
        for ckey in classes:
            for sname in per_week:
                cs = css[(ckey, sname)]
                pos = 0
                t2_topics: list[SyllabusTopic] = []
                for tname, units in chapters.items():
                    for utitle, ttitles in units.items():
                        unit = SyllabusUnit(org_id=org.id, class_subject_id=cs.id,
                                            position=pos, title=utitle,
                                            term_id=terms[tname].id)
                        db.add(unit)
                        db.flush()
                        pos += 1
                        for tpos, tt in enumerate(ttitles):
                            # est_periods is NULL for every term but the live one.
                            # NULL means "not sized yet": distribute skips it,
                            # approve refuses to lock it, and the forecast returns
                            # `unplanned` instead of inventing a green.
                            topic = SyllabusTopic(
                                org_id=org.id, unit_id=unit.id, position=tpos, title=tt,
                                est_periods=4 if tname == "Term 2" else None)
                            db.add(topic)
                            db.flush()
                            if tname == "Term 2":
                                t2_topics.append(topic)
                db.flush()

                # Term 2 only: an approved plan, laid out week by week inside the
                # term's own window. `plans.status` is a cache over the append-only
                # approval log, so both are written or the planner reads this as
                # unlocked.
                db.add(Plan(org_id=org.id, class_subject_id=cs.id, status="approved",
                            approved_by=head.id, approved_at=now))
                db.add(PlanApproval(org_id=org.id, class_subject_id=cs.id,
                                    term_id=terms["Term 2"].id, action="approve",
                                    actor_user_id=head.id))
                wk = T2[0] - timedelta(days=T2[0].weekday())
                for topic in t2_topics:
                    db.add(PlanEntry(org_id=org.id, class_subject_id=cs.id,
                                     topic_id=topic.id, week_start=wk))
                    approved_entries += 1
                    wk += timedelta(days=7)
        db.flush()

        # ── the timetable ─────────────────────────────────────────────────────
        subj_order = ["English", "Mathematics", "Science"]
        for offset, ckey in enumerate(classes):
            row = [css[(ckey, s)] for s in subj_order]
            idx = offset
            for wd in range(5):
                for period in range(1, 6):
                    db.add(TimetableSlot(
                        org_id=org.id, class_id=classes[ckey].id, weekday=wd,
                        period_no=period, class_subject_id=row[idx % len(row)].id,
                        effective_from=TRACKING_START, effective_to=None))
                    idx += 1
        db.flush()

        # ── capture, but only ever on or after the tracking start ─────────────
        #
        # Nothing is written before TRACKING_START. That is the property the
        # fixture is checking: the pre-adoption months must read as no-data, and
        # they can only do that if there is genuinely no data there.
        cs_teacher = {c.id: c.teacher_member_id for c in css.values()}
        marked_days = 0
        day = today
        while marked_days < 8 and day >= TRACKING_START:
            if day.weekday() < 5:
                for ckey, c in classes.items():
                    row = [css[(ckey, s)] for s in subj_order]
                    idx = list(classes).index(ckey)
                    for period in range(1, 6):
                        cs = row[(idx + (day.weekday() * 5) + (period - 1)) % len(row)]
                        cp = ClassPeriod(
                            org_id=org.id, class_id=c.id, date=day, period_no=period,
                            class_subject_id=cs.id,
                            marked_by_member_id=cs_teacher[cs.id],
                            teacher_member_id=cs_teacher[cs.id],
                            opened_at=now, status="held", attendance_marked_at=now)
                        db.add(cp)
                        db.flush()
                        # Capture-by-exception: one absentee on the first period
                        # of the most recent day, and nothing else. "All present"
                        # is the empty set, not 12 present rows.
                        if day == today and period == 1 and ckey == "8-A":
                            db.add(AttendanceException(
                                org_id=org.id, period_id=cp.id,
                                student_id=students[0].id, status="absent",
                                reason="fever"))
                marked_days += 1
            day -= timedelta(days=1)
        db.flush()

        # A few logged lessons against Term 2 topics, so coverage is partial and
        # real rather than 0% or 100%.
        logged = 0
        for ckey in classes:
            for sname in per_week:
                cs = css[(ckey, sname)]
                topics = db.scalars(
                    select(SyllabusTopic)
                    .join(SyllabusUnit, SyllabusUnit.id == SyllabusTopic.unit_id)
                    .where(SyllabusUnit.class_subject_id == cs.id,
                           SyllabusTopic.est_periods.is_not(None))
                    .order_by(SyllabusUnit.position, SyllabusTopic.position)
                ).all()
                for n, topic in enumerate(topics[:2]):
                    db.add(LessonLog(
                        org_id=org.id, class_subject_id=cs.id,
                        date=today - timedelta(days=(n + 1) * 3),
                        member_id=cs.teacher_member_id, topic_id=topic.id,
                        coverage="full" if n == 0 else "partial"))
                    logged += 1
        db.flush()

        # ── fees: the November-school case (`D-88`) ───────────────────────────
        #
        # These families paid two instalments to the school before the school had
        # TrackBit. That must NOT be invented as transactions in this year's
        # ledger — it is `opening_dues`, its own labelled line, outside every
        # figure this year's totals report.
        carried = paid = 0
        for i, st in enumerate(students):
            sf = StudentFee(
                org_id=org.id, student_id=st.id, academic_year_id=year.id,
                total_fee=q(24000), discount=q(0), net_fee=q(24000), created_by=head.id,
                installments=[
                    Installment(org_id=org.id, installment_number=n, label=f"Installment {n}",
                                amount=q(8000), due_date=due)
                    for n, due in [(1, date(2026, 7, 15)), (2, date(2026, 10, 15)),
                                   (3, date(2027, 1, 15))]
                ])
            db.add(sf)
            db.flush()
            if i % 4 == 0:
                sf.opening_dues = q(6000)
                carried += 1
            # Most families paid the July instalment; two did not. A fixture where
            # nobody has paid makes the whole board red for a reason that belongs
            # to the fixture rather than to the product, and the acceptance test
            # is precisely "nothing red that shouldn't be".
            if i % 6 != 0:
                inst = sf.installments[0]
                inst.paid_amount = inst.amount
                inst.paid_date = date(2026, 7, 12)
                db.add(Transaction(
                    org_id=org.id, student_fee_id=sf.id, installment_id=inst.id,
                    amount=inst.amount, type="payment", mode="cash",
                    created_by=head.id, created_by_name=head.name))
                paid += 1
            recompute_student_fee(sf)
        db.flush()

        db.commit()
        print(f"Seeded '{ORG_NAME}': org={org.id}")
        print(f"  school code    {SCHOOL_CODE}   (parent login)")
        print(f"  year 2026-27, tracking from {TRACKING_START} — "
              f"Term 1 ({T1[0]}..{T1[1]}) is BEFORE it and was never planned")
        print("  Term 1  unplanned (pre-tracking)   · Term 2  sized + approved"
              f" ({approved_entries} entries) · Term 3  chapters unsized")
        print(f"  2 classes, {len(students)} students, {marked_days} days of attendance,"
              f" {logged} lesson logs")
        print(f"  fees: {paid} of {len(students)} paid the July instalment, "
              f"{carried} families carrying dues from before adoption")
        print("  login: head@midyear.trackbit.app / demo1234  (admin)")
        print("         asha@midyear.trackbit.app / demo1234  (teacher, 8-A)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    build()
