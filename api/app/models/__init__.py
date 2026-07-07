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
from app.models.auth_token import AuthToken
from app.models.billing import Invoice
from app.models.board import Board, BoardCategory, BoardMember
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
from app.models.sessions import (
    Session,
    SessionAttendance,
    SessionMeeting,
    SessionStudent,
)
from app.models.students import Guardian, Student, StudentCategory
from app.models.task import EVENT_TYPES, Attachment, TaskEvent, TaskInstance, TaskTemplate
from app.models.user import User

__all__ = [
    "AcademicYear",
    "AnalyticsEvent",
    "Attachment",
    "AuthToken",
    "Board",
    "BoardCategory",
    "BoardMember",
    "CalendarEvent",
    "ClassSubject",
    "DeviceToken",
    "EVENT_TYPES",
    "FeeInstallmentTemplate",
    "FeeStructure",
    "Guardian",
    "HomeworkAssignment",
    "HomeworkCheck",
    "Installment",
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
    "Student",
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
    "User",
]
