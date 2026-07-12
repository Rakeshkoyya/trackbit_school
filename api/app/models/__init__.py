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
    ScoreCapture,
    ScoreCapturePage,
    SkillArea,
    StudentBand,
)
from app.models.auth_token import AuthToken
from app.models.billing import Invoice
from app.models.board import Board, BoardCategory, BoardMember
from app.models.checks import CheckResult, DailyCheck
from app.models.classroom import (
    HomeworkAssignment,
    HomeworkCheck,
    LessonLog,
    LessonObservation,
)
from app.models.exams import ExamPortion
from app.models.fees import (
    FeeInstallmentTemplate,
    FeeStructure,
    Installment,
    StudentFee,
    Transaction,
)
from app.models.lucy import (
    LucyConversation,
    LucyMessage,
    LucyPendingAction,
    LucyWidget,
)
from app.models.notification import DeviceToken, Notification
from app.models.onboarding import OnboardingState
from app.models.org import Membership, Organization
from app.models.periods import AttendanceException, ClassPeriod
from app.models.planner import (
    Plan,
    PlanApproval,
    PlanComment,
    PlanEntry,
    SyllabusTopic,
    SyllabusUnit,
)
from app.models.reports import DailyReport
from app.models.sessions import (
    Session,
    SessionAttendance,
    SessionClass,
    SessionMedia,
    SessionMeeting,
    SessionStudent,
    SessionStudentLog,
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
    "AuthToken",
    "Board",
    "BoardCategory",
    "BoardMember",
    "CalendarEvent",
    "CheckResult",
    "ClassPeriod",
    "ClassSubject",
    "DailyCheck",
    "DailyReport",
    "DeviceToken",
    "EVENT_TYPES",
    "ExamPortion",
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
    "LessonObservation",
    "LucyConversation",
    "LucyMessage",
    "LucyPendingAction",
    "LucyWidget",
    "Membership",
    "Notification",
    "OnboardingState",
    "Organization",
    "Plan",
    "PlanApproval",
    "PlanComment",
    "PlanEntry",
    "SchoolClass",
    "ScoreCapture",
    "ScoreCapturePage",
    "Session",
    "SessionAttendance",
    "SessionClass",
    "SessionMedia",
    "SessionMeeting",
    "SessionStudent",
    "SessionStudentLog",
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
