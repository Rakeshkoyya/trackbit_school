"""All models — importing this module registers everything on Base.metadata."""

from app.models.academics import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    SchoolClass,
    Subject,
    Term,
)
from app.models.analytics import AnalyticsEvent
from app.models.assessments import (
    AssessmentCycle,
    AssessmentScore,
    Intervention,
    InterventionItem,
    SkillArea,
    StudentBand,
)
from app.models.attendance import AttendanceException, AttendanceMark
from app.models.auth_token import AuthToken
from app.models.billing import Invoice
from app.models.board import Board, BoardCategory, BoardMember
from app.models.checks import CheckResult, DailyCheck
from app.models.classroom import HomeworkAssignment, HomeworkCheck, LessonLog
from app.models.fees import (
    FeeInstallmentTemplate,
    FeeStructure,
    Installment,
    StudentFee,
    Transaction,
)
from app.models.notification import DeviceToken, Notification
from app.models.org import Membership, Organization
from app.models.planner import Plan, PlanEntry, SyllabusTopic, SyllabusUnit
from app.models.reports import DailyReport
from app.models.sessions import (
    Session,
    SessionAttendance,
    SessionMeeting,
    SessionStudent,
)
from app.models.students import Guardian, Student, StudentCategory
from app.models.task import EVENT_TYPES, Attachment, TaskEvent, TaskInstance, TaskTemplate
from app.models.timetable import TimetableSlot
from app.models.user import User

__all__ = [
    "AcademicYear",
    "AnalyticsEvent",
    "AssessmentCycle",
    "AssessmentScore",
    "Attachment",
    "AttendanceException",
    "AttendanceMark",
    "AuthToken",
    "Board",
    "BoardCategory",
    "BoardMember",
    "CalendarEvent",
    "CheckResult",
    "ClassSubject",
    "DailyCheck",
    "DailyReport",
    "DeviceToken",
    "EVENT_TYPES",
    "FeeInstallmentTemplate",
    "FeeStructure",
    "Guardian",
    "HomeworkAssignment",
    "HomeworkCheck",
    "Installment",
    "Intervention",
    "InterventionItem",
    "Invoice",
    "LessonLog",
    "Membership",
    "Notification",
    "Organization",
    "Plan",
    "PlanEntry",
    "SchoolClass",
    "Session",
    "SessionAttendance",
    "SessionMeeting",
    "SessionStudent",
    "SkillArea",
    "Student",
    "StudentBand",
    "StudentCategory",
    "StudentFee",
    "Subject",
    "SyllabusTopic",
    "SyllabusUnit",
    "Term",
    "Transaction",
    "TaskEvent",
    "TaskInstance",
    "TaskTemplate",
    "TimetableSlot",
    "User",
]
