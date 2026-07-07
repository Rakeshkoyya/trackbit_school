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
from app.models.fees import (
    FeeInstallmentTemplate,
    FeeStructure,
    Installment,
    StudentFee,
    Transaction,
)
from app.models.notification import DeviceToken, Notification
from app.models.org import Membership, Organization
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
    "Installment",
    "Invoice",
    "Membership",
    "Notification",
    "Organization",
    "SchoolClass",
    "Student",
    "StudentCategory",
    "StudentFee",
    "Subject",
    "Term",
    "Transaction",
    "TaskEvent",
    "TaskInstance",
    "TaskTemplate",
    "User",
]
