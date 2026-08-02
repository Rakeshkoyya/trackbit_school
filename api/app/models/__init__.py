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
    BandDescriptor,
    ExamLockEvent,
    ExamType,
    Intervention,
    InterventionItem,
    ScoreCapture,
    ScoreCapturePage,
    SkillArea,
    StudentBand,
    SupportCheckpoint,
)
from app.models.auth_token import AuthToken
from app.models.billing import Invoice
from app.models.board import Board, BoardCategory, BoardMember
from app.models.checks import CheckResult, DailyCheck
from app.models.classroom import (
    HomeworkAssignment,
    HomeworkCheck,
    HomeworkResult,
    LessonLog,
    LessonObservation,
)
from app.models.exams import ExamPortion
from app.models.fees import (
    FEE_NOTE_KINDS,
    FeeInstallmentTemplate,
    FeeNote,
    FeeStructure,
    Installment,
    StudentFee,
    Transaction,
)
from app.models.insights import FOLLOWUP_KINDS, FollowupAction, PeriodSubstitution
from app.models.lucy import (
    LucyConversation,
    LucyMessage,
    LucyPendingAction,
    LucyView,
    LucyWidget,
)
from app.models.marketing import DemoRequest, DemoRequestNote
from app.models.notification import DeviceToken, Notification
from app.models.observances import (
    DECISION_ACTIONS,
    OBSERVANCE_KINDS,
    OBSERVANCE_TIERS,
    EventDecision,
    Observance,
)
from app.models.onboarding import OnboardingState
from app.models.org import Membership, Organization
from app.models.otp import OtpCode
from app.models.parent import GuardianMessage, ParentLoginAttempt
from app.models.periods import AttendanceException, ClassPeriod, StudentAbsenceNote
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
from app.models.staff import (
    LeaveRequest,
    LeaveRequestEvent,
    StaffAbsence,
    StaffAttendanceDay,
    TimesheetEntry,
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
    "BandDescriptor",
    "Board",
    "BoardCategory",
    "BoardMember",
    "CalendarEvent",
    "CheckResult",
    "ClassPeriod",
    "ClassSubject",
    "DailyCheck",
    "DailyReport",
    "DemoRequest",
    "DemoRequestNote",
    "DECISION_ACTIONS",
    "DeviceToken",
    "EVENT_TYPES",
    "EventDecision",
    "ExamLockEvent",
    "ExamPortion",
    "ExamType",
    "FEE_NOTE_KINDS",
    "FeeInstallmentTemplate",
    "FeeNote",
    "FeeStructure",
    "FOLLOWUP_KINDS",
    "FollowupAction",
    "Guardian",
    "HomeworkAssignment",
    "HomeworkCheck",
    "HomeworkResult",
    "Installment",
    "Intervention",
    "InterventionItem",
    "Invoice",
    "LessonLog",
    "LessonObservation",
    "LeaveRequest",
    "LeaveRequestEvent",
    "LucyConversation",
    "LucyMessage",
    "LucyPendingAction",
    "LucyView",
    "LucyWidget",
    "Membership",
    "Notification",
    "OBSERVANCE_KINDS",
    "OBSERVANCE_TIERS",
    "GuardianMessage",
    "Observance",
    "OnboardingState",
    "Organization",
    "OtpCode",
    "ParentLoginAttempt",
    "Plan",
    "PlanApproval",
    "PlanComment",
    "PlanEntry",
    "PeriodSubstitution",
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
    "StaffAbsence",
    "StaffAttendanceDay",
    "Student",
    "StudentAbsenceNote",
    "StudentBand",
    "StudentCategory",
    "StudentFee",
    "Subject",
    "SyllabusTopic",
    "SupportCheckpoint",
    "SyllabusUnit",
    "Term",
    "Transaction",
    "TaskEvent",
    "TaskInstance",
    "TaskTemplate",
    "TimesheetEntry",
    "TimetableSlot",
    "User",
]
