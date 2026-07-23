"""Lucy's read tools — thin wrappers over the existing services.

Every handler passes the real `CurrentMember` through, so the services' own
scoping does the guarding: growth limits teachers to their students, attendance
to their classes, the exam feed to taught classes; fee/dashboard/report tools
are `role="admin"` so a teacher's model never sees them. No handler builds a
query of its own — if a read needs new SQL it belongs in the owning service.

Descriptions are written FOR THE MODEL: what the tool answers, when to prefer
it, and what the ids it needs look like.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.services.academics import AcademicService
from app.services.assessments import AssessmentService
from app.services.attendance import AttendanceService
from app.services.classroom import ClassroomService
from app.services.daily_report import DailyReportService
from app.services.dashboard import DashboardService
from app.services.exams import ExamService
from app.services.fees import FeeService
from app.services.growth import GrowthService
from app.services.lucy.registry import tool
from app.services.overview import OverviewService
from app.services.planner import PlannerService
from app.services.sessions import SessionService
from app.services.students import StudentService
from app.services.timeline import StudentTimelineService

_UUID = {"type": "string", "format": "uuid"}
_DATE = {"type": "string", "format": "date",
         "description": "ISO date YYYY-MM-DD; omit for today"}


# --- orientation: ids and structure --------------------------------------

@tool("get_school_structure",
      "Academic years (with terms), classes and subjects of the school, with their ids. "
      "Call this FIRST whenever you need a class_id, subject_id, year_id or term_id — "
      "never guess ids.",
      widgets=("table", "markdown"))
def get_school_structure(m: CurrentMember, db: Session):
    svc = AcademicService(db)
    years = [y.model_dump(mode="json") for y in svc.list_years(m)]
    for y in years:
        y["terms"] = [t.model_dump(mode="json") for t in svc.list_terms(m, uuid.UUID(y["id"]))]
    active = next((y for y in years if y.get("is_active")), years[0] if years else None)
    classes = []
    if active:
        classes = [c.model_dump(mode="json")
                   for c in svc.list_classes(m, uuid.UUID(active["id"]))]
        for c in classes:
            c["label"] = f"{c['name']}-{c['section']}" if c.get("section") else c["name"]
    return {
        "years": years,
        "classes_in_active_year": classes,
        "subjects": [s.model_dump(mode="json") for s in svc.list_subjects(m)],
    }


@tool("get_class_subjects",
      "The subject allocations of one class: class_subject_id, subject and teacher for "
      "each subject taught in that class. Needed before topic-progress or plan lookups.",
      params={"class_id": {**_UUID, "required": True}})
def get_class_subjects(m: CurrentMember, db: Session, class_id: uuid.UUID):
    return AcademicService(db).list_class_subjects(m, class_id)


@tool("search_students",
      "Find students by name or admission number, optionally within one class. "
      "Returns id, name, roll no and class. Use this to resolve a student the user "
      "named before calling a per-student tool.",
      params={"query": {"type": "string", "description": "part of a name or admission no"},
              "class_id": _UUID},
      widgets=("table",))
def search_students(m: CurrentMember, db: Session,
                    query: str | None = None, class_id: uuid.UUID | None = None):
    return StudentService(db).list_students(m, class_id=class_id, query=query)


@tool("get_student",
      "One student's profile: personal details, class, category, status and guardians.",
      params={"student_id": {**_UUID, "required": True}},
      widgets=("student_card", "table"))
def get_student(m: CurrentMember, db: Session, student_id: uuid.UUID):
    return StudentService(db).get_student(m, student_id)


# --- whole-school reads (admin) -------------------------------------------

@tool("get_school_overview",
      "Whole-school health for one academic year: per-class student counts, subjects "
      "missing teachers or syllabus, timetable coverage, plan approval and worst "
      "syllabus forecast. The go-to for 'how is the school doing'.",
      params={"year_id": _UUID}, role="admin",
      widgets=("table", "stat_group"))
def get_school_overview(m: CurrentMember, db: Session, year_id: uuid.UUID | None = None):
    return OverviewService(db).school_overview(m, year_id)


@tool("get_teacher_load",
      "Every teacher's weekly load: periods per week, classes and subjects taught.",
      role="admin", widgets=("table", "bar_chart"))
def get_teacher_load(m: CurrentMember, db: Session):
    return OverviewService(db).teacher_load(m)


@tool("get_dashboard",
      "The director dashboard: syllabus RAG counts, fee summary, today's session "
      "records, homework health and the live alert feed (pace/compliance/homework "
      "problems). Best single source for 'what needs attention right now'.",
      params={"year_id": _UUID}, role="admin",
      widgets=("alert_list", "stat_group", "rag_board", "area_chart", "meter"),
      default_widget="alert_list")
def get_dashboard(m: CurrentMember, db: Session, year_id: uuid.UUID | None = None):
    return DashboardService(db).overview(m, year_id)


@tool("get_daily_report",
      "The school's generated daily report for a date: narrative sections plus "
      "highlighted risks, ambiguities and wins. This is the day already written up — "
      "prefer it for 'summarize today/yesterday'.",
      params={"on_date": _DATE}, role="admin",
      widgets=("report_card",), default_widget="report_card")
def get_daily_report(m: CurrentMember, db: Session, on_date: date | None = None):
    return DailyReportService(db).get_or_create(m, on_date)


@tool("get_compliance",
      "Which class-subjects have a lesson log today (per teacher). Use for 'who has "
      "not logged yet'.",
      params={"on_date": _DATE}, role="admin",
      widgets=("table", "progress"))
def get_compliance(m: CurrentMember, db: Session, on_date: date | None = None):
    return ClassroomService(db).compliance(m, on_date)


# --- fees (admin only — teachers never see fees) ---------------------------

@tool("get_fee_summary",
      "Fee collection totals for a year: total, collected, pending installments and "
      "overdue amount.",
      params={"year_id": _UUID}, role="admin",
      widgets=("stat_group", "donut", "meter"), default_widget="stat_group")
def get_fee_summary(m: CurrentMember, db: Session, year_id: uuid.UUID | None = None):
    return FeeService(db).summary(m, year_id)


@tool("get_overdue_fees",
      "Students with overdue fee installments: name, class, overdue amount, earliest "
      "due date. Sorted worst-first.",
      params={"year_id": _UUID,
              "limit": {"type": "integer", "description": "max rows, default 20"}},
      role="admin", widgets=("table", "alert_list"))
def get_overdue_fees(m: CurrentMember, db: Session,
                     year_id: uuid.UUID | None = None, limit: int = 20):
    return FeeService(db).overdue_students(m, year_id=year_id, limit=limit)


# --- attendance -------------------------------------------------------------

@tool("get_attendance_roster",
      "One class-period's attendance sheet: every student with present/absent/late "
      "status plus summary counts. Teachers can read only classes they teach. "
      "period_no is 1-based within the school day.",
      params={"class_id": {**_UUID, "required": True},
              "period_no": {"type": "integer", "required": True},
              "on_date": _DATE},
      widgets=("roster_grid", "stat_group", "table"), default_widget="roster_grid")
def get_attendance_roster(m: CurrentMember, db: Session, class_id: uuid.UUID,
                          period_no: int, on_date: date | None = None):
    return AttendanceService(db).roster(m, class_id, period_no, on_date)


@tool("get_attendance_day",
      "A class's whole-day attendance state: per period, whether attendance was "
      "taken and the present/absent/late counts. Good for 'class 6 attendance today' "
      "before drilling into one period.",
      params={"class_id": {**_UUID, "required": True}, "on_date": _DATE},
      widgets=("table", "stat_group"))
def get_attendance_day(m: CurrentMember, db: Session, class_id: uuid.UUID,
                       on_date: date | None = None):
    states = AttendanceService(db).period_states(m.org_id, [class_id],
                                                 on_date or date.today())
    return [{"period_no": pno, **vals}
            for (_cid, pno), vals in sorted(states.items(), key=lambda kv: kv[0][1])]


# --- per-student depth ------------------------------------------------------

@tool("get_student_growth",
      "The full growth report for one student: attendance %, per-subject chapters "
      "taught/missed-while-absent, homework, check flags, observations, test scores, "
      "skill profile, current band with history, and derived growth areas. Teachers "
      "can read only students they teach. THE tool for 'how is <student> doing'.",
      params={"student_id": {**_UUID, "required": True}},
      widgets=("stat_group", "drilldown", "table", "line_chart"),
      default_widget="stat_group")
def get_student_growth(m: CurrentMember, db: Session, student_id: uuid.UUID):
    return GrowthService(db).growth(m, student_id)


@tool("get_student_timeline",
      "What one student did on a date, period by period: subject, presence, topic "
      "logged, homework, checks and hostel sessions. Absent periods appear as gaps.",
      params={"student_id": {**_UUID, "required": True}, "on_date": _DATE},
      widgets=("timeline", "table"), default_widget="timeline")
def get_student_timeline(m: CurrentMember, db: Session, student_id: uuid.UUID,
                         on_date: date | None = None):
    return StudentTimelineService(db).timeline(m, student_id, on_date)


# --- assessments, bands, trends ---------------------------------------------

@tool("get_assessment_trends",
      "Per-subject average-% trend across assessment cycles for one class, with weak "
      "subjects flagged. Renders naturally as a line chart.",
      params={"class_id": {**_UUID, "required": True}},
      widgets=("line_chart", "table"), default_widget="line_chart")
def get_assessment_trends(m: CurrentMember, db: Session, class_id: uuid.UUID):
    return AssessmentService(db).trends(m, class_id)


@tool("get_weak_subjects",
      "Org-wide list of subjects trending weak (declining or low averages) across "
      "classes.",
      widgets=("table", "alert_list"))
def get_weak_subjects(m: CurrentMember, db: Session):
    return AssessmentService(db).weak_subjects(m)


@tool("get_band_board",
      "The A/B/C intervention-band board for a class: each student's current and "
      "suggested tier with latest %. STAFF-ONLY data — never include band tiers in "
      "anything meant for parents or guardians.",
      params={"class_id": {**_UUID, "required": True}, "term_id": _UUID},
      widgets=("table", "donut"))
def get_band_board(m: CurrentMember, db: Session, class_id: uuid.UUID,
                   term_id: uuid.UUID | None = None):
    return AssessmentService(db).band_board(m, class_id, term_id)


@tool("get_band_history",
      "One student's band tier changes over time (append-only history). Staff-only.",
      params={"student_id": {**_UUID, "required": True}},
      widgets=("table", "timeline"))
def get_band_history(m: CurrentMember, db: Session, student_id: uuid.UUID):
    return AssessmentService(db).band_history(m, student_id)


@tool("get_skill_profile",
      "One student's per-skill scores across assessment cycles (e.g. Reading, "
      "Problem solving).",
      params={"student_id": {**_UUID, "required": True}},
      widgets=("radar", "bar_chart", "table"), default_widget="radar")
def get_skill_profile(m: CurrentMember, db: Session, student_id: uuid.UUID):
    return AssessmentService(db).skill_profile(m, student_id)


@tool("get_class_analysis",
      "Per-cycle average % by subject for one class — the class's academic heatmap "
      "across tests.",
      params={"class_id": {**_UUID, "required": True}},
      widgets=("table", "bar_chart"))
def get_class_analysis(m: CurrentMember, db: Session, class_id: uuid.UUID):
    return AssessmentService(db).class_analysis(m, class_id)


@tool("get_exam_feed",
      "Recent exams/tests (newest first): name, type, class, subject, topic, average "
      "%, how many of the roster were scored, evidence pages. Teachers see only "
      "their taught classes. Optionally filter to one class.",
      params={"class_id": _UUID,
              "limit": {"type": "integer", "description": "max rows, default 30"}},
      widgets=("table",))
def get_exam_feed(m: CurrentMember, db: Session,
                  class_id: uuid.UUID | None = None, limit: int = 30):
    return ExamService(db).feed(m, class_id, limit)


@tool("get_exam_detail",
      "One exam's full result sheet: every student's score and %, plus exam meta.",
      params={"cycle_id": {**_UUID, "required": True,
                           "description": "the exam id from get_exam_feed"}},
      widgets=("table", "stat_group", "bar_chart"))
def get_exam_detail(m: CurrentMember, db: Session, cycle_id: uuid.UUID):
    return ExamService(db).detail(m, cycle_id)


# --- planner / syllabus ------------------------------------------------------

@tool("get_plan_forecast",
      "Syllabus RAG forecast for every subject of a class: green/amber/red status, "
      "baseline vs projected finish, weeks behind. 'Is class 7 on track?' lives here.",
      params={"class_id": {**_UUID, "required": True}},
      widgets=("rag_board", "table"), default_widget="rag_board")
def get_plan_forecast(m: CurrentMember, db: Session, class_id: uuid.UUID):
    return PlannerService(db).forecast(m, class_id)


@tool("get_exam_fit",
      "Whether each subject's plan finishes its exam portions before each exam of "
      "the class (exam-readiness view).",
      params={"class_id": {**_UUID, "required": True}},
      widgets=("rag_board", "table"))
def get_exam_fit(m: CurrentMember, db: Session, class_id: uuid.UUID):
    return PlannerService(db).exam_fit(m, class_id)


@tool("get_topic_progress",
      "Chapter/topic-level progress for ONE class-subject: each topic's planned "
      "week vs taught date. Needs a class_subject_id from get_class_subjects.",
      params={"class_subject_id": {**_UUID, "required": True}},
      widgets=("progress", "table"), default_widget="progress")
def get_topic_progress(m: CurrentMember, db: Session, class_subject_id: uuid.UUID):
    return PlannerService(db).topic_progress(m, class_subject_id)


# --- day-to-day capture ------------------------------------------------------

@tool("get_my_day",
      "The calling teacher's own day: their periods with attendance/log state, plus "
      "pending homework checks. For teachers asking 'what's left today'.",
      params={"on_date": _DATE},
      widgets=("timeline", "table"), default_widget="timeline")
def get_my_day(m: CurrentMember, db: Session, on_date: date | None = None):
    return ClassroomService(db).my_day(m, on_date)


@tool("get_session_records",
      "Hostel/activity session records for a date: attendance counts, homework-done "
      "counts and media evidence per session meeting.",
      params={"on_date": _DATE},
      widgets=("table", "stat_group"))
def get_session_records(m: CurrentMember, db: Session, on_date: date | None = None):
    return SessionService(db).records(m, on_date)
