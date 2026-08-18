"""Class-period lifecycle (V2-P6) — open, close, mark not-held.

Open-on-action: the row is created by the teacher's first real action on the card,
which the UI hides behind the "Start attendance" button. The timetable already
records that the period was *scheduled*, so a missing `class_periods` row means
"nothing was captured" with no ambiguity — and no write happens on the read path.

Card assembly (attendance + plan + homework) lives in ClassroomService, which is
the surface that owns My Day; this module is lifecycle only, so `attendance.py`
can import the guard and the get-or-create without a cycle.
"""

import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import CalendarEvent, ClassPeriod, ClassSubject, SchoolClass


def today_for(m: CurrentMember) -> date:
    return datetime.now(ZoneInfo(m.org.timezone)).date()


def visible_class_ids(db: Session, m: CurrentMember) -> set[uuid.UUID] | None:
    """The classes this member may read. `None` = unrestricted (admin).

    A teacher's set is **the subjects she teaches ∪ the homeroom she owns**, and
    the second half is the fix (founder, 2026-08-05). Every class-scoped read in
    the app derived its own version of this from `class_subjects` alone, so a
    class teacher who takes none of her own class's subjects — a warden, a
    primary homeroom teacher whose subjects sit under someone else — was locked
    out of her own class's exam feed and report cards while the register, the
    syllabus block and the homework load all let her in. One rule, here, so the
    two halves of My Class cannot answer the question differently.
    """
    if m.is_coordinator_up:
        return None
    from app.models import SchoolClass as _SchoolClass  # noqa: PLC0415

    taught = set(db.scalars(select(ClassSubject.class_id).where(
        ClassSubject.org_id == m.org_id,
        ClassSubject.teacher_member_id == m.membership.id)))
    return taught | set(db.scalars(select(_SchoolClass.id).where(
        _SchoolClass.org_id == m.org_id,
        _SchoolClass.class_teacher_member_id == m.membership.id)))


def is_class_teacher_of(db: Session, m: CurrentMember, class_id: uuid.UUID) -> bool:
    """Is this member the class teacher of THIS class? (`D-89`.)

    The homeroom half of `visible_class_ids`, asked about one class instead of
    all of them, so the two can never drift apart — the whole reason a class
    teacher is derived from `school_classes.class_teacher_member_id` and never
    stored as a third `org_role` is that the same fact in two stores diverges on
    the first reassignment, and two copies of the same *query* diverge the same
    way. Admin is deliberately not short-circuited here: callers answer that
    themselves, and this stays a plain fact about the roster.
    """
    if m.membership is None:
        return False
    from app.models import SchoolClass as _SchoolClass  # noqa: PLC0415

    return db.scalar(select(_SchoolClass.id).where(
        _SchoolClass.id == class_id, _SchoolClass.org_id == m.org_id,
        _SchoolClass.class_teacher_member_id == m.membership.id)) is not None


def assert_can_edit_class_subject(
    db: Session, m: CurrentMember, class_subject_id: uuid.UUID,
) -> ClassSubject:
    """May this member change THIS subject's syllabus? Returns it if so.

    Narrower than `assert_can_take_class`, which answers *may she stand in front
    of this class* and is therefore true for every subject of a class she
    teaches one subject of — the right rule for attendance and the wrong one for
    a syllabus, where it would let the Hindi teacher rewrite the Maths chapters
    (the same distinction `main_exams.assert_can_record_subject` draws for
    marks).

    Admin anywhere; otherwise the subject's own teacher, or the class teacher of
    its homeroom — she is answerable for her class's record and is the person
    who keeps the syllabus current for a colleague who has left.

    Lives here rather than on either service because both `PlannerService` and
    `SyllabusBoardService` need it and `syllabus_board` already imports
    `planner`; a helper on either would close an import cycle.
    """
    cs = db.scalar(select(ClassSubject).where(
        ClassSubject.id == class_subject_id, ClassSubject.org_id == m.org_id))
    if cs is None:
        raise NotFoundError("Class-subject")
    if m.is_coordinator_up:
        return cs
    if cs.teacher_member_id == m.membership.id:
        return cs
    klass = db.get(SchoolClass, cs.class_id)
    if klass is not None and klass.class_teacher_member_id == m.membership.id:
        return cs
    raise ForbiddenError("This subject is not yours to edit.",
                         code="not_your_subject")


def assert_can_take_class(
    db: Session, m: CurrentMember, class_id: uuid.UUID, class_subject_id: uuid.UUID | None,
    on_date: date | None = None, period_no: int | None = None,
) -> None:
    """Admin takes any class; a teacher takes a class they teach a subject in.
    A given class-subject must belong to that class.

    A teacher covering the period today also passes (DASH3 PR-2). Without this a
    substitute would see the period in My Day and be refused when they tapped it,
    which is worse than never showing it — so the date is threaded through from
    the period card.

    **The class teacher of the homeroom passes too.** She is the person the
    school's own rule names first — *the class teacher takes the register at
    period one* — and until now this function was the one place that did not
    know her. `visible_class_ids` has read "the subjects she teaches ∪ the
    homeroom she owns" since 2026-08-05, so her class appeared on the attendance
    board, in My Day and in the exam feed, and then every one of those screens
    refused her the moment she tapped it. A class whose subjects are not mapped
    yet — a new senior class, a school still mid-setup — has NO `class_subjects`
    at all, so its class teacher failed every branch below and was locked out of
    her own register with a 403 the UI showed as an endless spinner.

    This is the same rule `assert_can_edit_class_subject` and
    `MainExamService.assert_can_record_subject` already state in their own
    words: she is answerable for her class's record. It stays narrower than it
    looks — this function answers *may she stand in front of this class*, and
    recording another subject's marks is still gated by the narrower guard.
    """
    if class_subject_id is not None:
        cs = db.scalar(select(ClassSubject).where(
            ClassSubject.id == class_subject_id, ClassSubject.org_id == m.org_id))
        if cs is None:
            raise NotFoundError("Class-subject")
        if cs.class_id != class_id:
            raise ValidationError("That subject is not taught in this class.")
    if m.is_coordinator_up:
        return
    teaches = db.scalar(select(ClassSubject.id).where(
        ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id,
        ClassSubject.teacher_member_id == m.membership.id).limit(1))
    if teaches is not None:
        return
    if is_class_teacher_of(db, m, class_id):
        return
    if on_date is not None:
        from app.services.substitution import SubstitutionService  # noqa: PLC0415

        if SubstitutionService(db).covers(m.org_id, m.membership.id, class_id,
                                          on_date, period_no):
            return
    raise ForbiddenError("You don't teach this class.", code="not_your_class")


def find_period(
    db: Session, org_id: uuid.UUID, class_id: uuid.UUID, d: date, period_no: int,
) -> ClassPeriod | None:
    return db.scalar(select(ClassPeriod).where(
        ClassPeriod.org_id == org_id, ClassPeriod.class_id == class_id,
        ClassPeriod.date == d, ClassPeriod.period_no == period_no))


def get_or_create_period(
    db: Session, m: CurrentMember, class_id: uuid.UUID, d: date, period_no: int,
    class_subject_id: uuid.UUID | None,
) -> ClassPeriod:
    """Idempotent open. `teacher_member_id` records who actually took this
    occurrence — a substitution is simply a period whose teacher differs from the
    class-subject's year-long assignment."""
    period = find_period(db, m.org_id, class_id, d, period_no)
    if period is None:
        period = ClassPeriod(
            org_id=m.org_id, class_id=class_id, date=d, period_no=period_no,
            class_subject_id=class_subject_id, teacher_member_id=m.membership.id,
            opened_at=datetime.now(UTC), status="held")
        db.add(period)
        db.flush()
    elif class_subject_id is not None and period.class_subject_id is None:
        period.class_subject_id = class_subject_id
        db.flush()
    return period


class PeriodService:
    def __init__(self, db: Session):
        self.db = db

    def _class(self, org_id: uuid.UUID, class_id: uuid.UUID) -> SchoolClass:
        klass = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == class_id, SchoolClass.org_id == org_id))
        if klass is None:
            raise NotFoundError("Class")
        return klass

    def _period(self, m: CurrentMember, period_id: uuid.UUID) -> ClassPeriod:
        period = self.db.scalar(select(ClassPeriod).where(
            ClassPeriod.id == period_id, ClassPeriod.org_id == m.org_id))
        if period is None:
            raise NotFoundError("Period")
        assert_can_take_class(self.db, m, period.class_id, None,
                              period.date, period.period_no)
        return period

    def open(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
             class_subject_id: uuid.UUID | None, on_date: date | None = None) -> ClassPeriod:
        self._class(m.org_id, class_id)
        d = on_date or today_for(m)
        assert_can_take_class(self.db, m, class_id, class_subject_id, d, period_no)
        return get_or_create_period(self.db, m, class_id, d, period_no, class_subject_id)

    def close(self, m: CurrentMember, period_id: uuid.UUID) -> ClassPeriod:
        """Close-out is the teacher's "done with this period" signal. It does not
        require attendance — a not-held period closes too — so the 16:00 reminder
        job and the daily report can both read `closed_at` as ground truth."""
        period = self._period(m, period_id)
        if period.closed_at is None:
            period.closed_at = datetime.now(UTC)
            self.db.flush()
        return period

    def reopen(self, m: CurrentMember, period_id: uuid.UUID) -> ClassPeriod:
        period = self._period(m, period_id)
        period.closed_at = None
        self.db.flush()
        return period

    def not_held(self, m: CurrentMember, period_id: uuid.UUID, reason: str,
                 event_id: uuid.UUID | None = None) -> ClassPeriod:
        """The class did not happen. Keeps the period row (so the day's coverage
        arithmetic still balances) and closes it out with a reason.

        V1-7 `S-147`: when the reason is an approved calendar event, it is
        RECORDED as that event rather than as one of forty spellings of
        "independance day rehersal" — which is what makes "what did Diwali cost
        us in periods?" a query. `S-146`: this is the per-class block (8-A went
        to the rehearsal, 8-B carried on). If the ADMIN locked the period
        school-wide, the teacher is never asked in the first place — the day is
        already out of the capacity calculation, and recording it here too would
        subtract it twice.
        """
        period = self._period(m, period_id)
        period.status = "not_held"
        period.not_held_reason = reason
        if event_id is not None:
            event = self.db.scalar(select(CalendarEvent).where(
                CalendarEvent.id == event_id, CalendarEvent.org_id == m.org_id))
            if event is None:
                raise NotFoundError("Event")
            period.not_held_event_id = event.id
            period.not_held_reason = reason or event.title
        else:
            period.not_held_event_id = None
        if period.closed_at is None:
            period.closed_at = datetime.now(UTC)
        self.db.flush()
        return period
