"""P3 — writing the pack (SETUP-REDESIGN-PLAN §7).

What each test is defending:

  * **one upload builds a whole school** — year, terms, staff, classes,
    subjects, class-subjects, syllabus, students, timetable, calendar and fees,
    from a single workbook;
  * **a second upload changes nothing it should not.** The operator will upload
    the corrected pack three times; every write is keyed on something natural so
    the second run updates instead of doubling;
  * **syllabus is additive** (D-4). A school that sends Term 3 in December must
    keep the Term 1 chapters its teachers have already been logging against —
    appending must never require a destructive replace;
  * **a blank Section fans out** to every section, which is what makes one sheet
    enough for the whole school (D-5);
  * **Topic is optional** (D-5): a chapter-only sheet — which is what the
    founder's reference file actually is — becomes one topic per chapter
    carrying that chapter's periods, so coverage arithmetic is unchanged;
  * **a mid-year school lands intact**: tracking_start_date set, unsized
    chapters stored as NULL and never as 1.
"""

import io
import uuid

import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.core.context import CurrentMember
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    ExamPortion,
    ExamPortionUnit,
    FeeStructure,
    Installment,
    Membership,
    Organization,
    Plan,
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
from app.services.dashboard import DashboardService
from app.services.setup_pack import PackCommitter, build_pack, parse_pack, validate

SCHOOL = [
    ["Field", "Value"],
    ["School name", "Sunrise Public School"],
    ["State", "Karnataka"],
    ["Academic year", "2026-27"],
    ["Year starts", "01/06/2026"],
    ["Year ends", "30/04/2027"],
    ["Tracking starts from", "10/08/2026"],
    ["Working days", "Mon-Sat"],
    ["Periods per day", 8],
    ["First period starts", "08:30"],
    ["Period length (minutes)", 40],
    ["Lunch after period", 4],
    ["Lunch length (minutes)", 30],
    ["Parent portal", "Yes"],
]
# A term IS its exam: the school gives the exam window and the term is the
# teaching that leads up to it. Term 1 = 01/06 → 27/09, Term 2 = 28/09 → 25/04.
TERMS = [
    ["Term", "Exam", "Exam starts", "Exam ends"],
    ["Term 1", "Half-yearly", "22/09/2026", "27/09/2026"],
    ["Term 2", "Annual", "20/04/2027", "25/04/2027"],
]
CLASSES = [
    ["Class", "Section", "Class teacher"],
    ["6", "A", "Anita Desai"],
    ["6", "B", "Vikram Rao"],
]
STAFF = [
    ["Name", "Employee ID", "Email", "Role"],
    ["Anita Desai", "anita.desai", "", "Teacher"],
    ["Vikram Rao", "vikram.rao", "", "Admin"],
]
ASSIGNMENTS = [
    ["Class", "Section", "Subject", "Teacher", "Periods per week"],
    # Blank section: applies to 6-A and 6-B alike.
    ["6", "", "Mathematics", "Anita Desai", 6],
    ["6", "A", "Science", "Vikram Rao", 5],
]
SYLLABUS = [
    ["Class", "Section", "Subject", "Term", "Ch #", "Chapter", "Est. periods"],
    # Chapter and periods, nothing else — the shape of the reference tracker.
    ["6", "", "Mathematics", "Term 1", 1, "Integers", 4],
    ["6", "", "Mathematics", "Term 1", 2, "Fractions", None],
    # Every subject that is TAUGHT has a syllabus. Without this the school is
    # incomplete and "6-A Science has no plan yet" is an honest alert — which is
    # the validator's job to flag at review, not something a commit can invent.
    ["6", "A", "Science", "Term 1", 1, "Food and Nutrition", 3],
]
STUDENTS = [
    ["Student name", "Admission no", "Roll no", "Class", "Section",
     "Date of birth", "Father name", "Father phone"],
    ["Aarav Sharma", "1021", "12", "6", "A", "14/06/2014", "Rajesh Sharma",
     "9876543210"],
    ["Diya Patel", "1022", "13", "6", "B", "02/11/2013", "Amit Patel",
     "9876543212"],
]
TIMETABLE = [
    ["Class", "Section", "Day", "Period", "Subject"],
    ["6", "A", "Monday", 1, "Mathematics"],
    ["6", "A", "Monday", 2, "Science"],
]
CALENDAR = [
    ["From", "To", "Name", "Type"],
    ["15/08/2026", "", "Independence Day", "Holiday"],
    ["08/11/2026", "10/11/2026", "Diwali break", "Holiday"],
]
FEES = [
    ["Class", "Category", "Total amount", "Installment no", "Installment name",
     "Due date", "Amount"],
    ["6", "", 24000, 1, "Quarter 1", "15/06/2026", 12000],
    ["6", "", 24000, 2, "Quarter 2", "15/09/2026", 12000],
]

TITLES = {
    "school": "School", "terms": "Terms", "classes": "Classes", "staff": "Staff",
    "assignments": "Teaching Assignments", "syllabus": "Syllabus",
    "students": "Students", "timetable": "Timetable", "calendar": "Calendar",
    "fees": "Fees",
}


def _pack(**overrides):
    sheets = {
        "School": SCHOOL, "Terms": TERMS, "Classes": CLASSES, "Staff": STAFF,
        "Teaching Assignments": ASSIGNMENTS, "Syllabus": SYLLABUS,
        "Students": STUDENTS, "Timetable": TIMETABLE, "Calendar": CALENDAR,
        "Fees": FEES,
    }
    for key, rows in overrides.items():
        sheets[TITLES[key]] = rows
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        for row in rows:
            ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return parse_pack(buf.getvalue())


@pytest.fixture
def org(client, cleanup, db_session):
    """A throwaway school with one admin, and the CurrentMember to write as."""
    email = f"op-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org", json={
        "org_name": "Pack Test School", "name": "Operator", "email": email,
        "password": "supersecret1", "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))

    org_id = uuid.UUID(reg["org"]["id"])
    organization = db_session.get(Organization, org_id)
    user = db_session.get(User, uuid.UUID(reg["user"]["id"]))
    membership = db_session.scalar(select(Membership).where(
        Membership.org_id == org_id, Membership.user_id == user.id))
    return CurrentMember(user=user, org=organization, membership=membership)


def _commit(db_session, member, pack, **kwargs):
    result = PackCommitter(db_session).commit(member, pack, **kwargs)
    db_session.commit()
    return result


def _count(db_session, model, org_id, *where):
    return len(list(db_session.scalars(
        select(model).where(model.org_id == org_id, *where))))


# ── one upload builds a school ───────────────────────────────────────────────
def test_one_upload_builds_the_whole_school(org, db_session):
    result = _commit(db_session, org, _pack())
    oid = org.org_id

    assert _count(db_session, Term, oid) == 2
    assert _count(db_session, SchoolClass, oid) == 2
    assert _count(db_session, Subject, oid) == 2
    assert _count(db_session, Student, oid) == 2
    assert _count(db_session, TimetableSlot, oid) == 2
    assert _count(db_session, CalendarEvent, oid) == 4  # 2 holidays + 2 term exams
    assert _count(db_session, FeeStructure, oid) == 1
    assert result.academic_year_id is not None


def test_the_year_records_a_mid_year_start_and_the_bell_schedule(org, db_session):
    _commit(db_session, org, _pack())
    year = db_session.scalar(select(AcademicYear).where(
        AcademicYear.org_id == org.org_id))
    assert year.label == "2026-27"
    # D-3: the school joined in August, not June.
    assert year.tracking_start_date.isoformat() == "2026-08-10"
    assert year.working_weekdays == [0, 1, 2, 3, 4, 5]
    assert year.periods_per_day == 8
    kinds = [p["kind"] for p in year.period_times]
    assert kinds.count("period") == 8 and kinds.count("lunch") == 1
    assert year.period_times[0]["start"] == "08:30"
    # Lunch lands after period 4, so period 5 starts half an hour later.
    assert year.period_times[5]["start"] == "11:40"


def test_the_school_sheet_fills_in_the_organization(org, db_session):
    _commit(db_session, org, _pack())
    db_session.refresh(org.org)
    assert org.org.name == "Sunrise Public School"
    assert org.org.state == "Karnataka"


# ── a blank section fans out (D-5) ───────────────────────────────────────────
def test_a_blank_section_gives_both_sections_the_subject(org, db_session):
    _commit(db_session, org, _pack())
    maths = db_session.scalar(select(Subject).where(
        Subject.org_id == org.org_id, Subject.name == "Mathematics"))
    rows = list(db_session.scalars(select(ClassSubject).where(
        ClassSubject.org_id == org.org_id, ClassSubject.subject_id == maths.id)))
    assert len(rows) == 2, "one row for 6-A and one for 6-B"
    assert all(r.periods_per_week == 6 for r in rows)
    assert all(r.teacher_member_id is not None for r in rows)


def test_the_class_teacher_is_linked_from_the_staff_sheet(org, db_session):
    _commit(db_session, org, _pack())
    six_a = db_session.scalar(select(SchoolClass).where(
        SchoolClass.org_id == org.org_id, SchoolClass.name == "6",
        SchoolClass.section == "A"))
    assert six_a.class_teacher_member_id is not None


def test_the_role_column_makes_an_admin(org, db_session):
    """StaffImporter only ever made teachers; the pack's Role column is applied
    on top of it."""
    _commit(db_session, org, _pack())
    roles = {
        user.name: membership.org_role
        for membership, user in db_session.execute(
            select(Membership, User).join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org.org_id)).all()
    }
    assert roles["Vikram Rao"] == "admin"
    assert roles["Anita Desai"] == "teacher"


# ── Topic is optional, and blank periods stay NULL ───────────────────────────
def test_a_chapter_only_sheet_becomes_one_topic_per_chapter(org, db_session):
    """The sheet carries Chapter and Est. periods only — the chapter IS the
    unit of planning, and becomes one topic named for itself."""
    _commit(db_session, org, _pack())
    units = list(db_session.scalars(select(SyllabusUnit).where(
        SyllabusUnit.org_id == org.org_id)))
    assert sorted({u.title for u in units}) == [
        "Food and Nutrition", "Fractions", "Integers"]
    topics = list(db_session.scalars(select(SyllabusTopic).where(
        SyllabusTopic.org_id == org.org_id)))
    # One topic per chapter, named for the chapter.
    assert {t.title for t in topics} == {
        "Food and Nutrition", "Fractions", "Integers"}


def test_an_unsized_chapter_is_stored_as_null_never_as_one(org, db_session):
    _commit(db_session, org, _pack())
    sizes = {
        t.title: t.est_periods
        for t in db_session.scalars(select(SyllabusTopic).where(
            SyllabusTopic.org_id == org.org_id))
    }
    assert sizes["Integers"] == 4
    assert sizes["Fractions"] is None, "blank means not sized, never 1"


def test_chapters_are_filed_under_the_term_named_on_the_sheet(org, db_session):
    _commit(db_session, org, _pack())
    term1 = db_session.scalar(select(Term).where(
        Term.org_id == org.org_id, Term.name == "Term 1"))
    units = list(db_session.scalars(select(SyllabusUnit).where(
        SyllabusUnit.org_id == org.org_id)))
    assert units and all(u.term_id == term1.id for u in units)


# ── re-uploading (G6) ────────────────────────────────────────────────────────
def test_uploading_the_same_pack_twice_does_not_double_the_school(org, db_session):
    _commit(db_session, org, _pack())
    _commit(db_session, org, _pack())
    oid = org.org_id
    assert _count(db_session, AcademicYear, oid) == 1
    assert _count(db_session, Term, oid) == 2
    assert _count(db_session, SchoolClass, oid) == 2
    assert _count(db_session, Subject, oid) == 2
    assert _count(db_session, ClassSubject, oid) == 3
    assert _count(db_session, Student, oid) == 2
    assert _count(db_session, TimetableSlot, oid) == 2
    assert _count(db_session, CalendarEvent, oid) == 4  # 2 holidays + 2 term exams
    assert _count(db_session, FeeStructure, oid) == 1
    # And no second login for a teacher who already has one.
    assert _count(db_session, Membership, oid) == 3  # operator + two staff


def test_a_later_upload_adds_term_three_without_touching_term_one(org, db_session):
    """D-4: the school sends Terms 1-2 in August and Term 3 in December. The
    chapters teachers have been logging against must survive."""
    _commit(db_session, org, _pack())
    before = {u.title for u in db_session.scalars(select(SyllabusUnit).where(
        SyllabusUnit.org_id == org.org_id))}

    _commit(db_session, org, _pack(syllabus=[
        ["Class", "Section", "Subject", "Term", "Chapter", "Periods"],
        ["6", "", "Mathematics", "Term 3", "Mensuration", 6],
    ]))
    after = {u.title for u in db_session.scalars(select(SyllabusUnit).where(
        SyllabusUnit.org_id == org.org_id))}
    assert before <= after, "Term 1 chapters must not be deleted"
    assert "Mensuration" in after


def test_replace_is_available_but_only_when_asked_for(org, db_session):
    _commit(db_session, org, _pack())
    _commit(db_session, org, _pack(syllabus=[
        ["Class", "Section", "Subject", "Term", "Chapter", "Periods"],
        ["6", "", "Mathematics", "Term 1", "Only This One", 6],
    ]), replace_syllabus=True)
    titles = {u.title for u in db_session.scalars(select(SyllabusUnit).where(
        SyllabusUnit.org_id == org.org_id))}
    # Maths was replaced. Science was NOT in the replacement sheet, so its
    # chapters survive — replace is scoped to the class-subjects the sheet
    # actually names, never a blanket wipe of the school's syllabus.
    assert titles == {"Only This One", "Food and Nutrition"}


def test_a_corrected_pack_updates_rather_than_duplicates(org, db_session):
    _commit(db_session, org, _pack())
    _commit(db_session, org, _pack(assignments=[
        ["Class", "Section", "Subject", "Teacher", "Periods per week"],
        ["6", "", "Mathematics", "Anita Desai", 8],
        ["6", "A", "Science", "Vikram Rao", 5],
    ]))
    maths = db_session.scalar(select(Subject).where(
        Subject.org_id == org.org_id, Subject.name == "Mathematics"))
    rows = list(db_session.scalars(select(ClassSubject).where(
        ClassSubject.org_id == org.org_id, ClassSubject.subject_id == maths.id)))
    assert len(rows) == 2
    assert all(r.periods_per_week == 8 for r in rows)


# ── the optional sheets ──────────────────────────────────────────────────────
def test_holidays_and_exam_blocks_both_remove_teaching_days(org, db_session):
    _commit(db_session, org, _pack())
    events = {
        e.title: (e.type, e.affects_teaching, e.start_date, e.end_date)
        for e in db_session.scalars(select(CalendarEvent).where(
            CalendarEvent.org_id == org.org_id))
    }
    kind, affects, start, end = events["Independence Day"]
    assert kind == "holiday" and affects is True
    # A single-day row with a blank 'To' ends the day it starts.
    assert start == end
    # The exam block came from the Exams sheet, not the Calendar sheet.
    kind, affects, _s, _e = events["Half-yearly"]
    assert kind == "exam_block" and affects is True


def test_the_timetable_points_at_the_right_class_subject(org, db_session):
    _commit(db_session, org, _pack())
    slots = list(db_session.scalars(select(TimetableSlot).where(
        TimetableSlot.org_id == org.org_id)))
    assert {s.weekday for s in slots} == {0}, "Monday is weekday 0"
    assert sorted(s.period_no for s in slots) == [1, 2]
    assert all(s.class_subject_id is not None for s in slots)
    # Slots start when tracking starts, not when the year did.
    assert all(s.effective_from.isoformat() == "2026-08-10" for s in slots)


def test_every_student_is_enrolled_so_collection_has_quarters(org, db_session):
    """A structure says what a CLASS pays; `student_fees` + `installments` say
    what a CHILD owes, quarter by quarter — and only the second pair is what the
    fee screen reads. Without this the admin opens on an empty quarter and
    concludes the import failed."""
    _commit(db_session, org, _pack())
    fees = list(db_session.scalars(select(StudentFee).where(
        StudentFee.org_id == org.org_id)))
    assert len(fees) == 2, "both class-6 students should be enrolled"

    installments = list(db_session.scalars(select(Installment).where(
        Installment.student_fee_id.in_([f.id for f in fees]))))
    # Two templates on the structure → two instalments per child.
    assert len(installments) == 4
    # Due dates are what `core/collection.py` buckets into quarters; an
    # instalment without one is 'unscheduled' and shows in no quarter at all.
    assert all(i.due_date is not None for i in installments)


def test_enrolling_twice_does_not_double_a_child_s_fees(org, db_session):
    _commit(db_session, org, _pack())
    _commit(db_session, org, _pack())
    assert _count(db_session, StudentFee, org.org_id) == 2


def test_fees_land_with_their_installments(org, db_session):
    _commit(db_session, org, _pack())
    structure = db_session.scalar(select(FeeStructure).where(
        FeeStructure.org_id == org.org_id))
    assert structure.class_name == "6"
    assert int(structure.total_amount) == 24000
    assert structure.num_installments == 2


def test_a_pack_with_no_optional_sheets_still_builds_a_school(org, db_session):
    result = _commit(db_session, org, _pack(timetable=[], calendar=[], fees=[]))
    assert _count(db_session, SchoolClass, org.org_id) == 2
    assert _count(db_session, TimetableSlot, org.org_id) == 0
    assert "no periods on My Day" in " ".join(result.sheet("timetable").notes)


# ── a term IS its exam ───────────────────────────────────────────────────────
def test_each_term_ends_on_its_exam_and_the_block_sits_on_those_dates(
        org, db_session):
    """The school gave only the exam window. The term's dates are derived: it
    ends on the exam's last day and starts after the previous term's."""
    _commit(db_session, org, _pack())
    terms = {t.name: (t.start_date.isoformat(), t.end_date.isoformat())
             for t in db_session.scalars(select(Term).where(
                 Term.org_id == org.org_id))}
    assert terms["Term 1"] == ("2026-06-01", "2026-09-27")   # year start → exam end
    assert terms["Term 2"] == ("2026-09-28", "2027-04-25")   # day after → exam end

    blocks = {e.title: (e.start_date.isoformat(), e.end_date.isoformat())
              for e in db_session.scalars(select(CalendarEvent).where(
                  CalendarEvent.org_id == org.org_id,
                  CalendarEvent.type == "exam_block"))}
    assert blocks["Half-yearly"] == ("2026-09-22", "2026-09-27")
    assert blocks["Annual"] == ("2027-04-20", "2027-04-25")


def test_the_exam_block_takes_its_days_out_of_teaching(org, db_session):
    _commit(db_session, org, _pack())
    blocks = list(db_session.scalars(select(CalendarEvent).where(
        CalendarEvent.org_id == org.org_id,
        CalendarEvent.type == "exam_block")))
    assert blocks and all(b.affects_teaching for b in blocks)


def test_the_portion_is_every_chapter_filed_under_that_term(org, db_session):
    """No sheet states the portion. A term IS its exam, so what the exam
    examines is the term's syllabus — asking the school to restate it would be
    asking the same fact twice and inviting the two to disagree."""
    _commit(db_session, org, _pack())
    half = db_session.scalar(select(CalendarEvent).where(
        CalendarEvent.org_id == org.org_id, CalendarEvent.title == "Half-yearly"))
    portions = list(db_session.scalars(select(ExamPortion).where(
        ExamPortion.org_id == org.org_id,
        ExamPortion.exam_event_id == half.id)))
    # 6-A Maths, 6-B Maths and 6-A Science all have Term 1 chapters.
    assert len(portions) == 3

    unit_ids = set(db_session.scalars(select(ExamPortionUnit.unit_id).where(
        ExamPortionUnit.portion_id.in_([p.id for p in portions]))))
    titles = {u.title for u in db_session.scalars(select(SyllabusUnit).where(
        SyllabusUnit.id.in_(unit_ids)))}
    assert titles == {"Integers", "Fractions", "Food and Nutrition"}


def test_a_term_with_no_chapters_gets_no_portion(org, db_session):
    """Term 2 is unplanned here — a state, not a failure."""
    _commit(db_session, org, _pack())
    annual = db_session.scalar(select(CalendarEvent).where(
        CalendarEvent.org_id == org.org_id, CalendarEvent.title == "Annual"))
    assert not list(db_session.scalars(select(ExamPortion).where(
        ExamPortion.org_id == org.org_id,
        ExamPortion.exam_event_id == annual.id)))


# ── the plans: why the dashboard was shouting ────────────────────────────────
def test_the_import_generates_and_approves_the_plans(org, db_session):
    """The step whose absence made a freshly set-up school open on a dashboard
    full of 'has no plan yet'."""
    result = _commit(db_session, org, _pack())
    plans = list(db_session.scalars(select(Plan).where(
        Plan.org_id == org.org_id)))
    assert plans, "every class-subject with a sized syllabus should have a plan"
    assert all(p.status in ("approved", "partial") for p in plans), \
        [p.status for p in plans]
    assert result.sheet("plans").created > 0


def test_a_freshly_imported_school_opens_with_no_pace_alerts(org, db_session):
    """The founder's actual complaint, as a test: after setup the dashboard must
    be quiet. A school told it has no plan on day one has been set up badly."""
    _commit(db_session, org, _pack())
    overview = DashboardService(db_session).overview(org)
    noisy = [a.title for a in overview.alerts
             if "no plan yet" in a.title or "has no plan" in a.title]
    assert noisy == [], noisy


# ── the pack the operator actually sends ─────────────────────────────────────
def test_the_sample_pack_validates_and_commits(org, db_session):
    """End to end on the very file `build_pack(sample=True)` produces."""
    pack = parse_pack(build_pack("Sunrise", sample=True))
    assert validate(pack).ready
    _commit(db_session, org, pack)
    assert _count(db_session, SchoolClass, org.org_id) == 3
    assert _count(db_session, Student, org.org_id) == 3
