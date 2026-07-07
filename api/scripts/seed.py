"""Seed the demo org — the shared dev fixture (plan §7.8).

Idempotent: wipes and recreates the demo org by name. Run:
    python -m scripts.seed
"""

from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    AcademicYear,
    Board,
    BoardMember,
    CalendarEvent,
    ClassSubject,
    FeeInstallmentTemplate,
    FeeStructure,
    Guardian,
    HomeworkAssignment,
    Installment,
    LessonLog,
    Membership,
    Organization,
    Plan,
    PlanEntry,
    SchoolClass,
    SessionAttendance,
    SessionMeeting,
    SessionStudent,
    Student,
    StudentCategory,
    StudentFee,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    TaskEvent,
    TaskInstance,
    Term,
    Transaction,
    User,
)
from app.models import Session as SessionModel
from app.services.calendar import expand_blocked_dates
from app.services.fee_math import proportional_installments, q, recompute_student_fee
from app.services.planner import distribute

IST = timezone(timedelta(hours=5, minutes=30))
DEMO_ORG_NAME = "SHANA Ops (demo)"


def _now() -> datetime:
    return datetime.now(UTC)


def _today_at(hour: int, minute: int = 0) -> datetime:
    """UTC datetime for today at the given org-local (IST) time."""
    local = datetime.now(IST).replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(UTC)


DEMO_EMAILS = ["kc@demo.trackbit.app", "priya@demo.trackbit.app",
               "ramesh@demo.trackbit.app", "anil@demo.trackbit.app"]
DEMO_PHONES = ["+919800000001", "+919800000002"]


def wipe_demo(db: Session) -> None:
    org = db.scalar(select(Organization).where(Organization.name == DEMO_ORG_NAME))
    if org:
        # FK cascades clean up boards/tasks/events/memberships under the org.
        db.execute(delete(Organization).where(Organization.id == org.id))
        db.flush()
    # Users are global — remove the demo people too so re-seeding is idempotent.
    db.execute(delete(User).where(User.email.in_(DEMO_EMAILS)))
    db.execute(delete(User).where(User.phone.in_(DEMO_PHONES)))
    db.flush()


def _seed_school(db: Session, org: Organization, kc: User, mships: dict) -> dict:
    """Populate one demo year: calendar, classes/subjects, a roster, and fees —
    so every academic + fee screen renders meaningfully on review."""
    teachers = [u for u, m in mships.items() if m.org_role == "teacher"]
    ramesh, anil = teachers[0], teachers[1]
    priya = next(u for u, m in mships.items() if m.org_role == "coordinator")

    year = AcademicYear(org_id=org.id, label="2026-27", start_date=date(2026, 4, 1),
                        end_date=date(2027, 3, 31), is_active=True)
    db.add(year)
    db.flush()
    db.add_all([
        Term(org_id=org.id, academic_year_id=year.id, name="Term 1",
             start_date=date(2026, 4, 1), end_date=date(2026, 9, 30)),
        Term(org_id=org.id, academic_year_id=year.id, name="Term 2",
             start_date=date(2026, 10, 1), end_date=date(2027, 3, 31)),
    ])

    subjects = {}
    for name in ["English", "Mathematics", "Science", "Social Studies", "Hindi"]:
        s = Subject(org_id=org.id, name=name)
        db.add(s)
        subjects[name] = s
    db.flush()

    # Calendar — a holiday, a celebration, and an exam block (drive effective days).
    db.add_all([
        CalendarEvent(org_id=org.id, academic_year_id=year.id, type="holiday",
                      title="Independence Day", start_date=date(2026, 8, 15),
                      end_date=date(2026, 8, 15)),
        CalendarEvent(org_id=org.id, academic_year_id=year.id, type="celebration",
                      title="Teachers' Day", start_date=date(2026, 9, 5), end_date=date(2026, 9, 5)),
        CalendarEvent(org_id=org.id, academic_year_id=year.id, type="exam_block",
                      title="Half-yearly Exams", start_date=date(2026, 9, 21),
                      end_date=date(2026, 9, 30)),
        CalendarEvent(org_id=org.id, academic_year_id=year.id, type="holiday",
                      title="Dussehra Break", start_date=date(2026, 10, 19),
                      end_date=date(2026, 10, 23)),
    ])

    classes = {}
    for cname, section, teacher in [("6", "A", ramesh), ("6", "B", anil), ("7", "A", priya)]:
        c = SchoolClass(org_id=org.id, academic_year_id=year.id, name=cname, section=section,
                        class_teacher_member_id=mships[teacher].id)
        db.add(c)
        classes[f"{cname}-{section}"] = c
    db.flush()

    periods = {"English": 6, "Mathematics": 6, "Science": 5, "Social Studies": 4, "Hindi": 4}
    class_subjects: dict[tuple, ClassSubject] = {}
    for ckey, c in classes.items():
        for sname, pw in periods.items():
            teacher = ramesh if sname in ("Mathematics", "Science") else anil
            cs = ClassSubject(org_id=org.id, class_id=c.id, subject_id=subjects[sname].id,
                              teacher_member_id=mships[teacher].id, periods_per_week=pw)
            db.add(cs)
            class_subjects[(ckey, sname)] = cs
    db.flush()

    # Syllabus + an APPROVED plan for 6-A Science (populates the plan/forecast view).
    sci = class_subjects[("6-A", "Science")]
    blocked = expand_blocked_dates([
        (date(2026, 8, 15), date(2026, 8, 15), True),
        (date(2026, 9, 5), date(2026, 9, 5), True),
        (date(2026, 9, 21), date(2026, 9, 30), True),
        (date(2026, 10, 19), date(2026, 10, 23), True),
    ])
    syllabus = {
        "Food & Nutrition": ["Components of food", "Balanced diet", "Deficiency diseases"],
        "The Living World": ["Cells", "Tissues", "Plant & animal life"],
        "Matter": ["States of matter", "Separation of substances"],
        "Motion & Measurement": ["Types of motion", "Measuring length"],
    }
    all_topics: list[SyllabusTopic] = []
    for upos, (utitle, ttitles) in enumerate(syllabus.items()):
        unit = SyllabusUnit(org_id=org.id, class_subject_id=sci.id, position=upos, title=utitle)
        db.add(unit)
        db.flush()
        for tpos, tt in enumerate(ttitles):
            topic = SyllabusTopic(org_id=org.id, unit_id=unit.id, position=tpos, title=tt,
                                  est_periods=3)
            db.add(topic)
            all_topics.append(topic)
    db.flush()
    weeks = distribute([t.est_periods for t in all_topics], periods_per_week=5,
                       working_weekdays=year.working_weekdays, blocked=blocked,
                       year_start=year.start_date, year_end=year.end_date)
    db.add(Plan(org_id=org.id, class_subject_id=sci.id, status="approved",
                approved_by=kc.id, approved_at=_now()))
    for topic, wk in zip(all_topics, weeks, strict=True):
        db.add(PlanEntry(org_id=org.id, class_subject_id=sci.id, topic_id=topic.id, week_start=wk))

    # A day of classroom capture for Ramesh (6-A Math) so My Day + compliance have
    # data: today's class logged, and yesterday's homework awaiting a completion count.
    today_ist = datetime.now(IST).date()
    math = class_subjects[("6-A", "Mathematics")]
    db.add(LessonLog(org_id=org.id, class_subject_id=math.id, date=today_ist,
                     member_id=mships[ramesh].id, coverage="full"))
    db.add(HomeworkAssignment(org_id=org.id, class_subject_id=math.id,
                              date=today_ist - timedelta(days=1), text="Exercise 4.2, sums 1–10",
                              due_date=today_ist + timedelta(days=1), notified_at=_now()))

    cats = {}
    for name in ["Day Scholar", "Hosteller"]:
        cat = StudentCategory(org_id=org.id, name=name)
        db.add(cat)
        cats[name] = cat
    db.flush()

    # Roster — 15 students across the three classes, with a primary guardian.
    first = ["Asha", "Bhavya", "Chetan", "Divya", "Esha", "Farhan", "Gita", "Harsh",
             "Isha", "Jatin", "Kiran", "Lata", "Manoj", "Nisha", "Omar"]
    class_keys = ["6-A", "6-B", "7-A"]
    students = []
    for i, name in enumerate(first):
        ckey = class_keys[i % 3]
        cat = cats["Hosteller"] if i % 4 == 0 else cats["Day Scholar"]
        st = Student(org_id=org.id, admission_no=f"A{601 + i}", full_name=f"{name} Kumar",
                     class_id=classes[ckey].id, roll_no=str(i + 1), category_id=cat.id)
        db.add(st)
        db.flush()
        db.add(Guardian(org_id=org.id, student_id=st.id, name=f"Mr. {name}'s Father",
                        relation="Father", phone=f"+9198000100{i:02d}", is_primary=True))
        students.append(st)

    # Fee structure for class 6, then enrol the class-6 students + a couple of payments.
    fs = FeeStructure(org_id=org.id, class_name="6", academic_year_id=year.id,
                      total_amount=q(30000), num_installments=3, created_by=kc.id,
                      templates=[
                          FeeInstallmentTemplate(org_id=org.id, installment_number=n,
                                                 label=f"Installment {n}", amount=q(10000),
                                                 due_date=due)
                          for n, due in [(1, date(2026, 4, 15)), (2, date(2026, 8, 15)),
                                         (3, date(2026, 12, 15))]
                      ])
    db.add(fs)
    db.flush()

    enrolled = 0
    for idx, st in enumerate(s for s in students if s.class_id in
                             (classes["6-A"].id, classes["6-B"].id)):
        scaled = proportional_installments(q(30000), [q(10000)] * 3)
        sf = StudentFee(org_id=org.id, student_id=st.id, fee_structure_id=fs.id,
                        academic_year_id=year.id, total_fee=q(30000), discount=q(0),
                        net_fee=q(30000), created_by=kc.id, installments=[
                            Installment(org_id=org.id, installment_number=n + 1,
                                        label=t.label, amount=scaled[n], due_date=t.due_date)
                            for n, t in enumerate(sorted(fs.templates,
                                                         key=lambda x: x.installment_number))
                        ])
        db.add(sf)
        db.flush()
        # First two enrolments have paid installment 1.
        if idx < 2:
            inst = sf.installments[0]
            inst.paid_amount = q(10000)
            inst.paid_date = date(2026, 4, 10)
            db.add(Transaction(org_id=org.id, student_fee_id=sf.id, installment_id=inst.id,
                               amount=q(10000), type="payment", mode="cash",
                               created_by=kc.id, created_by_name=kc.name))
        recompute_student_fee(sf)
        enrolled += 1
    db.flush()

    # Ramesh's after-school homework class (Flow 6): 6-A roster + today's meeting with
    # attendance captured — so Sessions + the records feed render on review.
    sixa = [s for s in students if s.class_id == classes["6-A"].id]
    session = SessionModel(org_id=org.id, name="Homework Class 6A",
                           owner_member_id=mships[ramesh].id, weekdays=[0, 2, 4], time="16:15")
    db.add(session)
    db.flush()
    for st in sixa:
        db.add(SessionStudent(org_id=org.id, session_id=session.id, student_id=st.id))
    meeting = SessionMeeting(org_id=org.id, session_id=session.id, date=today_ist)
    db.add(meeting)
    db.flush()
    for i, st in enumerate(sixa):
        status = "absent" if i == 0 else "late" if i == 1 else "present"
        db.add(SessionAttendance(
            org_id=org.id, meeting_id=meeting.id, student_id=st.id, status=status,
            late_minutes=8 if status == "late" else None,
            homework_done=(status != "absent" and i % 2 == 0)))

    db.flush()
    return {"students": len(students), "classes": len(classes), "enrolled": enrolled}


def seed() -> None:
    db = SessionLocal()
    try:
        wipe_demo(db)

        org = Organization(name=DEMO_ORG_NAME, timezone="Asia/Kolkata", plan="pro")
        db.add(org)
        db.flush()

        # --- People ---------------------------------------------------------
        kc = User(name="KC", email="kc@demo.trackbit.app", password_hash=hash_password("demo1234"))
        priya = User(name="Priya", email="priya@demo.trackbit.app",
                     password_hash=hash_password("demo1234"))
        # Teachers get a login too so the reviewer can experience the teacher flow.
        ramesh = User(name="Ramesh", email="ramesh@demo.trackbit.app", phone="+919800000001",
                      password_hash=hash_password("demo1234"))
        anil = User(name="Anil", email="anil@demo.trackbit.app", phone="+919800000002",
                    password_hash=hash_password("demo1234"))
        db.add_all([kc, priya, ramesh, anil])
        db.flush()

        # School roles (SPRD §3.2): KC director, Priya coordinator, the rest teachers.
        mships: dict[User, Membership] = {}
        for role, user in [
            ("admin", kc), ("coordinator", priya), ("teacher", ramesh), ("teacher", anil),
        ]:
            mem = Membership(org_id=org.id, user_id=user.id, org_role=role, last_active_at=_now())
            db.add(mem)
            mships[user] = mem
        db.flush()

        # --- School master data + academics (M1) + fees (M6) ----------------
        counts = _seed_school(db, org, kc, mships)

        # --- Boards ---------------------------------------------------------
        daily = Board(org_id=org.id, name="Daily Ops", visibility="public",
                      category="tasks", created_by=kc.id, owner_id=kc.id)
        admissions = Board(org_id=org.id, name="Admissions", visibility="private",
                           category="tasks", created_by=kc.id, owner_id=kc.id)
        # Ops board templates (SPRD §5.5, zero new code) — the director's
        # repair/maintenance and cleaning trackers ship as ready-made boards.
        maintenance = Board(org_id=org.id, name="Maintenance", visibility="public",
                            category="tasks", created_by=kc.id, owner_id=kc.id)
        housekeeping = Board(org_id=org.id, name="Housekeeping", visibility="public",
                             category="tasks", created_by=kc.id, owner_id=kc.id)
        db.add_all([daily, admissions, maintenance, housekeeping])
        db.flush()

        # Board membership. Owners are always board members (so a flip to private
        # never locks them out). Private "Admissions" = KC + Priya only.
        db.add_all([
            BoardMember(board_id=daily.id, user_id=kc.id),
            BoardMember(board_id=admissions.id, user_id=kc.id),
            BoardMember(board_id=admissions.id, user_id=priya.id),
            BoardMember(board_id=maintenance.id, user_id=kc.id),
            BoardMember(board_id=housekeeping.id, user_id=kc.id),
        ])
        db.flush()

        instances: list[TaskInstance] = []

        def add_task(board, title, *, assignee=None, due=None, status="open", all_day=False,
                     pass_count=0, completed_by=None, completed_at=None, created_at=None,
                     events=None):
            created = created_at or (_now() - timedelta(hours=20))
            inst = TaskInstance(
                org_id=org.id, board_id=board.id, title=title,
                assignee_id=assignee.id if assignee else None,
                due_at=due, all_day=all_day, status=status, pass_count=pass_count,
                completed_by=completed_by.id if completed_by else None,
                completed_at=completed_at, created_by=kc.id, created_at=created,
            )
            db.add(inst)
            db.flush()
            # Every instance starts with a 'created' event, then its history.
            chain = [{"type": "created", "actor": kc.id, "when": created}] + (events or [])
            for ev in chain:
                db.add(TaskEvent(
                    org_id=org.id, instance_id=inst.id, actor_id=ev.get("actor"),
                    event_type=ev["type"], payload=ev.get("payload"),
                    created_at=ev.get("when", created),
                ))
            instances.append(inst)
            return inst

        yesterday = _now() - timedelta(days=1)

        # Overdue (one-time, surfaces in Overdue section)
        add_task(daily, "Email parent group", assignee=priya, due=yesterday,
                 events=[{"type": "assigned", "actor": kc.id,
                          "payload": {"to": str(priya.id)}, "when": yesterday}])

        # Due today (timed)
        add_task(daily, "Submit attendance", assignee=priya, due=_today_at(10, 0),
                 events=[{"type": "assigned", "actor": kc.id, "payload": {"to": str(priya.id)}}])
        add_task(daily, "Restock display", assignee=ramesh, due=_today_at(14, 0),
                 events=[{"type": "assigned", "actor": kc.id, "payload": {"to": str(ramesh.id)}}])
        # Passed task (shows "passed by Ramesh ↩")
        add_task(daily, "Reply to reviews", assignee=priya, due=_today_at(16, 0), pass_count=1,
                 events=[
                     {"type": "assigned", "actor": kc.id, "payload": {"to": str(ramesh.id)}},
                     {"type": "passed", "actor": ramesh.id,
                      "payload": {"from": str(ramesh.id), "to": str(priya.id)}},
                 ])

        # Anytime today (untimed, assigned — never missed, plan G5)
        add_task(daily, "Tidy storeroom", assignee=ramesh, due=None)

        # Claimable (unassigned, public board)
        add_task(daily, "Update pricing sheet", assignee=None, due=_today_at(17, 0))
        add_task(daily, "Check supplier emails", assignee=None, due=None)

        # Done today
        add_task(daily, "Open shop", assignee=ramesh, due=_today_at(9, 0), status="done",
                 completed_by=ramesh, completed_at=_today_at(9, 30),
                 events=[
                     {"type": "assigned", "actor": kc.id, "payload": {"to": str(ramesh.id)}},
                     {"type": "completed", "actor": ramesh.id, "when": _today_at(9, 30)},
                 ])
        add_task(daily, "Morning headcount", assignee=priya, due=_today_at(9, 15), status="done",
                 completed_by=priya, completed_at=_today_at(9, 12),
                 events=[
                     {"type": "assigned", "actor": kc.id, "payload": {"to": str(priya.id)}},
                     {"type": "completed", "actor": priya.id, "when": _today_at(9, 12)},
                 ])

        # Missed (one-time miss yesterday)
        add_task(daily, "Lock back gate", assignee=anil, due=yesterday, status="missed",
                 events=[
                     {"type": "assigned", "actor": kc.id, "payload": {"to": str(anil.id)}},
                     {"type": "missed", "actor": None, "when": yesterday + timedelta(hours=6)},
                 ])

        # Private board tasks (only KC + Priya can see)
        add_task(admissions, "Call shortlisted parents", assignee=priya, due=_today_at(11, 0),
                 events=[{"type": "assigned", "actor": kc.id, "payload": {"to": str(priya.id)}}])
        add_task(admissions, "Verify documents", assignee=priya, due=_today_at(15, 0),
                 status="done", completed_by=priya, completed_at=_today_at(13, 0),
                 events=[
                     {"type": "assigned", "actor": kc.id, "payload": {"to": str(priya.id)}},
                     {"type": "completed", "actor": priya.id, "when": _today_at(13, 0)},
                 ])

        # Ops board templates in action.
        add_task(maintenance, "Fix broken fan in 6-B", assignee=anil, due=_today_at(12, 0))
        add_task(housekeeping, "Clean science lab", assignee=ramesh, due=_today_at(17, 0))

        db.commit()
        print(f"Seeded '{DEMO_ORG_NAME}': org={org.id}")
        print("  users=4 (director KC, coordinator Priya, teachers Ramesh/Anil)")
        print("  boards=4 (Daily Ops, Admissions, Maintenance, Housekeeping)")
        print(f"  tasks={len(instances)}")
        print(f"  school: {counts['classes']} classes, {counts['students']} students, "
              f"{counts['enrolled']} fee enrolments (year 2026-27)")
        print("  login: kc@demo.trackbit.app / demo1234")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
