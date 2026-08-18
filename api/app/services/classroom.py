"""Classroom capture (M2, SPRD §5.2) — My Day, quick log, homework, compliance.

Every capture is org-scoped and either by the teacher who owns the class-subject
or a coordinator/director. Posting homework notifies guardians immediately (the
teacher's payback, P3) with plain homework text only — never band/tier info (P4).
"""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core import day_shape
from app.core import homework_verdict as verdicts
from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    AssessmentCycle,
    AssessmentScore,
    ClassPeriod,
    ClassSubject,
    Guardian,
    HomeworkAssignment,
    HomeworkCheck,
    HomeworkResult,
    LessonLog,
    LessonObservation,
    Membership,
    PlanEntry,
    SchoolClass,
    ScoreCapture,
    ScoreCapturePage,
    Student,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    TimetableSlot,
    User,
)
from app.schemas.assessments import ExamSummary
from app.schemas.classroom import (
    ClassLogBookOut,
    ClassLogEntryOut,
    ClassLogIn,
    ComplianceOut,
    ComplianceRow,
    HomeworkBookOut,
    HomeworkCheckIn,
    HomeworkIn,
    HomeworkLogEntryOut,
    HomeworkOut,
    HomeworkPending,
    HomeworkSheetOut,
    HomeworkSheetRow,
    LessonLogIn,
    LessonLogOut,
    MyDayClass,
    MyDayOut,
    MyDayPeriod,
    ObservationConceptOut,
    ObservationSectionIn,
    ObservationSectionOut,
    ObservationsOut,
    ObservationStudentOut,
)
from app.schemas.periods import (
    CombinedClassCard,
    PeriodCardOut,
    PeriodEventOut,
    PeriodHomeworkOut,
    PeriodLogOut,
    PeriodPlanOut,
)
from app.schemas.timetable import TeacherSlot
from app.services.attendance import AttendanceService, day_absence_maps, is_day_absent
from app.services.calendar import day_lock
from app.services.notify_guardian import notify_guardians
from app.services.periods import assert_can_take_class, find_period, get_or_create_period
from app.services.planner import PlannerService
from app.services.timetable import TimetableService

# How far back the check sheet looks to show a child's miss streak (S-89).
SHEET_STREAK_DAYS = 30


def _label(klass: SchoolClass) -> str:
    return klass.name + (f"-{klass.section}" if klass.section else "")


class ClassroomService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return datetime.now(ZoneInfo(m.org.timezone)).date()

    def _cs(self, org_id: uuid.UUID, cs_id: uuid.UUID) -> ClassSubject:
        cs = self.db.scalar(
            select(ClassSubject).where(ClassSubject.id == cs_id, ClassSubject.org_id == org_id)
        )
        if cs is None:
            raise NotFoundError("Class-subject")
        return cs

    def _can_capture(self, m: CurrentMember, cs: ClassSubject) -> None:
        if not (m.is_coordinator_up or cs.teacher_member_id == m.membership.id):
            raise ForbiddenError("You don't teach this class.", code="not_your_class")

    def _active_year(self, org_id: uuid.UUID) -> AcademicYear | None:
        return self.db.scalar(
            select(AcademicYear).where(
                AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True)
            )
        )

    def _marks_attendance(self, m: CurrentMember, period_no: int,
                          class_id: uuid.UUID | None = None,
                          d: date | None = None) -> tuple[bool, bool | None]:
        """(is the ask owed here, has the day been captured) — V1-3 `D-01`.

        `first_period` makes this a question about the DAY, not the period
        (founder, 2026-08-05): the register is owed until somebody takes it, and
        then it is owed nowhere. Passing the class and date is what lets a
        period card in the afternoon say *"the register was taken this
        morning"* rather than either asking again or silently dropping the
        section — and what lets period 3 take it when period 1 never happened.
        """
        from app.services import bell  # noqa: PLC0415
        from app.services.school_clock import marking_period_nos  # noqa: PLC0415
        year = self._active_year(m.org_id)
        att = AttendanceService(self.db)
        if att.once_per_day(m) and class_id is not None and d is not None:
            held = att.day_register_period(m.org_id, class_id, d)
            if held is None:
                return True, False
            return held.period_no == period_no, True
        # TT-2: the shape of the day is effective-dated, so which periods mark
        # attendance is a question about a DATE, not about the year.
        shape = bell.resolve(self.db, year, d or self._today(m))
        marking = marking_period_nos(shape.entries, m.org.attendance_mode)
        return (not marking or period_no in marking), None

    # ── My Day (CL-1) ────────────────────────────────────────────────────────
    def my_day(self, m: CurrentMember, on_date: date | None = None) -> MyDayOut:
        today = on_date or self._today(m)
        monday = today - timedelta(days=today.weekday())
        year = self._active_year(m.org_id)
        if year is None:
            tasks, older = self._my_day_tasks(m, today, None)
            return MyDayOut(date=today, classes=[], periods=[], homework_pending=[],
                            tasks=tasks, older_task_count=older)

        rows = self.db.execute(
            select(ClassSubject, Subject.name, SchoolClass)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .where(ClassSubject.org_id == m.org_id,
                   ClassSubject.teacher_member_id == m.membership.id,
                   SchoolClass.academic_year_id == year.id)
            .order_by(SchoolClass.name, Subject.name)
        ).all()

        classes: list[MyDayClass] = []
        for cs, subject_name, klass in rows:
            logged_ids = set(self.db.scalars(
                select(LessonLog.topic_id).where(LessonLog.class_subject_id == cs.id)))
            planned = self.db.execute(
                select(PlanEntry.topic_id, SyllabusTopic.title)
                .join(SyllabusTopic, SyllabusTopic.id == PlanEntry.topic_id)
                .where(PlanEntry.org_id == m.org_id, PlanEntry.class_subject_id == cs.id,
                       PlanEntry.week_start == monday)
            ).all()
            topic, topic_id = None, None
            for tid, title in planned:
                if tid not in logged_ids:
                    topic, topic_id = title, tid
                    break
            if topic is None and planned:
                topic_id, topic = planned[0]
            logged_today = self.db.scalar(
                select(LessonLog.id).where(
                    LessonLog.class_subject_id == cs.id, LessonLog.date == today).limit(1)
            ) is not None
            hw_today = self.db.scalar(
                select(HomeworkAssignment.id).where(
                    HomeworkAssignment.class_subject_id == cs.id,
                    HomeworkAssignment.date == today).limit(1)
            ) is not None
            classes.append(MyDayClass(
                class_subject_id=cs.id, class_label=_label(klass), subject_name=subject_name,
                planned_topic=topic, planned_topic_id=topic_id,
                logged=logged_today, homework_set=hw_today))

        pending: list[HomeworkPending] = []
        cs_ids = [cs.id for cs, _, _ in rows]
        if cs_ids:
            # D-85 / V1-0e: EVERYTHING unchecked, oldest first — the old
            # `date == yesterday` filter made Friday's homework vanish on Monday,
            # and the admin's "overdue, unchecked" column then blamed teachers
            # for work this queue had never offered them. 60-day floor bounds
            # the payload; the full backlog lives on the homework screen (V1-5).
            hw_rows = self.db.execute(
                select(HomeworkAssignment, Subject.name, SchoolClass)
                .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
                .join(Subject, Subject.id == ClassSubject.subject_id)
                .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
                .where(HomeworkAssignment.org_id == m.org_id,
                       HomeworkAssignment.class_subject_id.in_(cs_ids),
                       HomeworkAssignment.date < today,
                       HomeworkAssignment.date >= today - timedelta(days=60))
                .order_by(HomeworkAssignment.date)
            ).all()
            checked_ids = set(self.db.scalars(
                select(HomeworkCheck.assignment_id).where(
                    HomeworkCheck.assignment_id.in_([hw.id for hw, _, _ in hw_rows])))
            ) if hw_rows else set()
            for hw, sname, klass in hw_rows:
                if hw.id in checked_ids:
                    continue
                pending.append(HomeworkPending(
                    assignment_id=hw.id, class_label=_label(klass),
                    subject_name=sname, text=hw.text))
                if len(pending) >= 20:
                    break

        # Today's periods straight from the timetable (V2-P1 §5.4), each resolved on
        # its OWN period row (V2-P6) — two Maths periods on one day are independent
        # cards with independent topics, not two views of one class-subject.
        day_slots = TimetableService(self.db).teacher_day(m, today)
        # V1-7 `S-145`: a period the school itself locked is no longer EXPECTED,
        # so it leaves her surface entirely rather than sitting there unlogged.
        # Leaving it would invent work on a holiday and make the capture rate
        # lie. What was already recorded against it is untouched (`Q-65`) — this
        # drops the ask, never the record.
        lock = day_lock(self.db, m.org_id, today, year.id)
        if lock.closed:
            day_slots = []
        elif lock.periods:
            day_slots = [ts for ts in day_slots if ts.period_no not in lock.periods]
        # …plus any period I'm covering for someone who is away (DASH3 PR-2). The
        # grid says who *usually* takes it; today's cover says who is taking it.
        # Skipped when a slot for the same (class, period) is already mine — a
        # substitution can never displace my own timetable.
        covering = self._substituted_slots(m, today, day_slots)
        day_slots = day_slots + [ts for ts, _who in covering]
        covering_by_slot = {(ts.class_id, ts.period_no): who for ts, who in covering}

        # TT-2: blocks leave the subject pipeline here. A games period has no
        # class-subject, so it has no topic, no lesson log and no homework — and
        # feeding it through `period_states` / `_assign_topics` would either
        # crash on the null id or, worse, invent an empty Maths card for it.
        block_slots = [ts for ts in day_slots if ts.slot_type == "block"]
        day_slots = [ts for ts in day_slots if ts.slot_type != "block"]

        att_service = AttendanceService(self.db)
        # TT-4: a combined row is one meeting over several classes, and every
        # class in it still keeps its own register — so the state lookup has to
        # cover the whole room, not just the class the row is keyed on.
        members_of = {
            (ts.class_id, ts.period_no): (list(ts.class_ids) or [ts.class_id])
            for ts in day_slots}
        class_ids = list({cid for ids in members_of.values() for cid in ids})
        att = att_service.period_states(m.org_id, class_ids, today)
        roster_sizes = att_service.roster_sizes(m.org_id, class_ids)

        period_ids = [s["period_id"] for s in att.values() if s.get("period_id")]
        logs_by_period = {
            log.period_id: log for log in self.db.scalars(
                select(LessonLog).where(
                    LessonLog.org_id == m.org_id, LessonLog.period_id.in_(period_ids)))
        } if period_ids else {}

        hw_cs = set(self.db.scalars(
            select(HomeworkAssignment.class_subject_id).where(
                HomeworkAssignment.org_id == m.org_id, HomeworkAssignment.date == today)))
        test_cs = self._tests_recorded_today(
            m.org_id, [ts.class_subject_id for ts in day_slots if ts.class_subject_id],
            today)

        assignment = self._assign_topics(
            m.org_id, monday, day_slots,
            {(ts.class_id, ts.period_no): att.get((ts.class_id, ts.period_no), {}).get("period_id")
             for ts in day_slots},
            logs_by_period)

        # V1-3 (D-01/Q-02a): which periods the org's mode takes attendance in.
        # The card itself stays for every period — only the attendance ask moves.
        from app.services import bell  # noqa: PLC0415
        from app.services.school_clock import marking_period_nos  # noqa: PLC0415
        shape = bell.resolve(self.db, year, today)
        marking = set(marking_period_nos(shape.entries, m.org.attendance_mode))

        # Founder, 2026-08-05 — **once a day means once a day, and the ask
        # follows the gap.** In `first_period` the register belongs to the DAY,
        # so:
        #   · a class whose register is already taken shows the ask on NO period
        #     (a Science teacher in period 4 is not being asked to re-take the
        #     morning roll — that is the noise this rule removes);
        #   · a class whose register is NOT taken shows it on EVERY period,
        #     because period 1 may not have happened, or its teacher may be
        #     away, and the register still has to get taken by somebody.
        # A static "period 1 only" rule gets the first case wrong all afternoon
        # and the second case wrong all day.
        once = att_service.once_per_day(m)
        day_taken = {cid for cid in class_ids
                     if any(s.get("marked")
                            for (c, _p), s in att.items() if c == cid)}

        periods: list[MyDayPeriod] = []
        for ts in day_slots:
            state = att.get((ts.class_id, ts.period_no), {})
            topic_id, topic_title, _unit, logged = assignment[(ts.class_id, ts.period_no)]
            members = members_of.get((ts.class_id, ts.period_no)) or [ts.class_id]
            # TT-4 — one row for the whole room. Every count is the sum, and
            # every "done" is an ALL: a lesson where 5-A's register is in and
            # 6-A's is not has not been captured, and a green tick there would
            # lose a class's day quietly, which is the one thing this row must
            # never do. Absent numbers stay absent (`present_count=None`) until
            # the whole room is marked — a half-marked room has no honest
            # present count to show.
            states = [att.get((cid, ts.period_no), {}) for cid in members]
            combined = len(members) > 1
            marked_all = all(s.get("marked", False) for s in states)
            if combined:
                # Same ALL rule for the topic: each class keeps its own syllabus,
                # so the room is logged only when every class in it is.
                logged = all(
                    s.get("period_id") is not None and s["period_id"] in logs_by_period
                    for s in states)
            roster_count = sum(
                s.get("roster_count", roster_sizes.get(cid, 0))
                for cid, s in zip(members, states, strict=True))
            periods.append(MyDayPeriod(
                period_no=ts.period_no, class_subject_id=ts.class_subject_id,
                class_id=ts.class_id,
                class_label=" + ".join(ts.class_labels) if combined else ts.class_label,
                subject_name=ts.subject_name,
                combined_id=ts.combined_id,
                combined_class_ids=members if combined else [],
                combined_class_labels=list(ts.class_labels) if combined else [],
                planned_topic=topic_title, planned_topic_id=topic_id, logged=logged,
                period_id=state.get("period_id"),
                status=state.get("status", "held"),
                opened=state.get("period_id") is not None,
                closed=state.get("closed", False),
                attendance_marked=marked_all,
                marks_attendance=(
                    # Once a day: ask wherever it is still owed, nowhere once it
                    # is done. The period holding the register keeps the row so
                    # the person who took it can still correct it.
                    (any(cid not in day_taken for cid in members) or marked_all)
                    if once else (not marking or ts.period_no in marking)),
                day_attendance_taken=(
                    all(cid in day_taken for cid in members)) if once else None,
                roster_count=roster_count,
                present_count=sum(s.get("present_count") or 0
                                  for s in states) if marked_all else None,
                absent_count=sum(s.get("absent_count") or 0
                                 for s in states) if marked_all else None,
                late_count=sum(s.get("late_count") or 0
                               for s in states) if marked_all else None,
                homework_set=ts.class_subject_id in hw_cs,
                test_recorded=ts.class_subject_id in test_cs,
                substituting=(ts.class_id, ts.period_no) in covering_by_slot,
                covering_for=covering_by_slot.get((ts.class_id, ts.period_no)),
                start=ts.start, end=ts.end))

        # TT-2 blocks. Deliberately thin: the roll, the log and the memories all
        # live on the block's own meeting, which does not exist until she opens
        # it, so there is nothing to count here and nothing to pre-create. The
        # row is a doorway, and `block_kind` is what the doorway leads to.
        block_state = self._block_states(
            m, [ts.session_id for ts in block_slots if ts.session_id], today)
        for ts in block_slots:
            block_classes = list(ts.class_labels) or [ts.class_label]
            state = block_state.get(ts.session_id, (False, None))
            cap = day_shape.capture_for(ts.block_kind)
            # TT-6: assembly is the exception to D-91. Every child in the school
            # is standing in it, so the roll taken there IS each class's register
            # — and this row therefore reports the HALL's state, read back from
            # the class registers themselves rather than from the meeting. A
            # block whose register is in for ten classes and missing for the
            # eleventh is not done, which is why `marked` is an ALL.
            room = (att_service.assembly_state(
                m.org_id, list(ts.class_ids) or [ts.class_id], ts.period_no, today)
                if cap.school_roll else None)
            room_marked = bool(room and room["marked"])
            periods.append(MyDayPeriod(
                period_no=ts.period_no, slot_type="block", class_subject_id=None,
                class_id=ts.class_id, class_label=" + ".join(block_classes),
                combined_class_ids=(list(ts.class_ids)
                                    if len(block_classes) > 1 else []),
                combined_class_labels=block_classes if len(block_classes) > 1 else [],
                session_id=ts.session_id, block_name=ts.block_name,
                block_kind=ts.block_kind,
                block_kind_label=day_shape.label_for(ts.block_kind),
                start=ts.start, end=ts.end,
                # TT-5: pooled, so the row says whether a colleague has already
                # covered it — and says it is optional either way. Except the
                # school register, which is owed: the day's attendance hangs off
                # it, and a school that skips it has no record of who came in.
                captured=room_marked if room else state[0],
                captured_by=state[1], optional=not cap.school_roll,
                school_roll=cap.school_roll,
                # A block normally never carries the school-day register (D-91):
                # its roll is its own, taken against its own roster on its own
                # meeting. `school_roll` is the one kind that does.
                marks_attendance=cap.school_roll,
                attendance_marked=room_marked,
                roster_count=room["roster_count"] if room else 0,
                present_count=(room["roster_count"] - (room["absent_count"] or 0)
                               if room_marked else None),
                absent_count=room["absent_count"] if room_marked else None,
                late_count=room["late_count"] if room_marked else None))
        periods.sort(key=lambda p: p.period_no)
        tasks, older = self._my_day_tasks(m, today, year)
        return MyDayOut(date=today, classes=classes, periods=periods,
                        homework_pending=pending, tasks=tasks, older_task_count=older,
                        day_closed=lock.closed,
                        locked_periods=sorted(lock.periods),
                        lock_reason=lock.title)

    def _block_states(
        self, m: CurrentMember, session_ids: list[uuid.UUID], d: date,
    ) -> dict[uuid.UUID, tuple[bool, str | None]]:
        """session_id → (has anything been recorded today, by whom) — TT-5.

        A block is staffed by everyone who MAY take it, so the same row appears
        on four teachers' My Day. Without this, each of them has to open it to
        discover a colleague already did it at six o'clock — and a row that has
        to be opened to be dismissed is not an optional row.

        **Captured is derived from content, never from the meeting existing.**
        `open_meeting` creates that row the moment somebody taps the card, so
        reading it as done would tick a block off for merely being looked at.
        Attendance, a class log, a per-student log or a photo are the things
        that mean somebody actually ran it.
        """
        from app.models import (  # noqa: PLC0415
            SessionAttendance,
            SessionMedia,
            SessionMeeting,
            SessionStudentLog,
        )

        if not session_ids:
            return {}
        meetings = list(self.db.scalars(
            select(SessionMeeting).where(
                SessionMeeting.org_id == m.org_id,
                SessionMeeting.session_id.in_(set(session_ids)),
                SessionMeeting.date == d)))
        if not meetings:
            return {}
        ids = [mt.id for mt in meetings]
        with_content: set[uuid.UUID] = set()
        for model in (SessionAttendance, SessionMedia, SessionStudentLog):
            with_content |= set(self.db.scalars(
                select(model.meeting_id).where(model.meeting_id.in_(ids)).distinct()))
        names = self._member_names(
            m.org_id, {mt.taken_by_member_id for mt in meetings if mt.taken_by_member_id})
        return {
            mt.session_id: (
                # `taken_by_member_id` is stamped by every WRITE and by none of
                # the reads, so it carries the case content cannot: a block whose
                # roster is empty that evening was still taken by somebody, and
                # her colleagues should be told so.
                mt.id in with_content or bool(mt.note)
                or mt.taken_by_member_id is not None,
                names.get(mt.taken_by_member_id),
            )
            for mt in meetings
        }

    def _member_names(self, org_id: uuid.UUID,
                      member_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not member_ids:
            return {}
        return dict(self.db.execute(
            select(Membership.id, User.name)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org_id, Membership.id.in_(member_ids))).all())

    def _my_day_tasks(self, m: CurrentMember, today: date, year: AcademicYear | None):
        """D-41/D-43: the narrow task window under the periods — rail follow-ups
        from the last 3 WORKING days (a Friday follow-up must survive the
        weekend, D-43's build note) ∪ anything due today, whatever board it came
        from. Capped at 5 (S-109); everything else lives on /tasks, and the
        returned count keeps the window honest ("4 older tasks →")."""
        from app.core.timeutil import org_day_bounds  # noqa: PLC0415
        from app.models import Board, CalendarEvent, TaskInstance  # noqa: PLC0415
        from app.services.calendar import (  # noqa: PLC0415
            DEFAULT_WORKING_WEEKDAYS,
            event_rows,
            expand_blocked_dates,
        )
        from app.services.insights.actions import FOLLOWUPS_BOARD_NAME  # noqa: PLC0415
        from app.services.task import TaskService  # noqa: PLC0415

        start_utc, end_utc, _ = org_day_bounds(m.org.timezone)
        ww = (set(year.working_weekdays) if year is not None and year.working_weekdays
              else set(DEFAULT_WORKING_WEEKDAYS))
        blocked: set[date] = set()
        if year is not None:
            events = list(self.db.scalars(select(CalendarEvent).where(
                CalendarEvent.org_id == m.org_id,
                CalendarEvent.academic_year_id == year.id,
                CalendarEvent.end_date >= today - timedelta(days=30),
                CalendarEvent.start_date <= today)))
            blocked = expand_blocked_dates(event_rows(events))
        # Walk back until 3 working days are collected (today counts if working).
        cutoff, d, seen = today, today, 0
        while seen < 3:
            if d.weekday() in ww and d not in blocked:
                seen += 1
                cutoff = d
            d -= timedelta(days=1)
            if (today - d).days > 30:  # a broken calendar must not loop forever
                break
        cutoff_utc = datetime.combine(
            cutoff, datetime.min.time(), tzinfo=ZoneInfo(m.org.timezone)).astimezone(UTC)

        followups_board_id = self.db.scalar(select(Board.id).where(
            Board.org_id == m.org_id, Board.name == FOLLOWUPS_BOARD_NAME,
            Board.archived_at.is_(None)))
        # Recurring rows: only today's occurrence, and missed ones expire quietly
        # (same rule as HomeService.my_tasks).
        recurring_ok = or_(
            TaskInstance.template_id.is_(None),
            and_(TaskInstance.occurrence_date == today, TaskInstance.status == "open"))
        window = [and_(TaskInstance.due_at >= start_utc, TaskInstance.due_at < end_utc)]
        if followups_board_id is not None:
            window.append(and_(TaskInstance.board_id == followups_board_id,
                               TaskInstance.created_at >= cutoff_utc))
        rows = list(self.db.scalars(select(TaskInstance).where(
            TaskInstance.org_id == m.org_id,
            TaskInstance.assignee_id == m.user_id,
            TaskInstance.status.in_(("open", "missed")),
            recurring_ok, or_(*window))))
        rows.sort(key=lambda t: (t.due_at is None, t.due_at or t.created_at))
        shown = rows[:5]

        total_open = int(self.db.scalar(
            select(func.count()).select_from(TaskInstance).where(
                TaskInstance.org_id == m.org_id,
                TaskInstance.assignee_id == m.user_id,
                TaskInstance.status.in_(("open", "missed")),
                recurring_ok)) or 0)
        older = max(0, total_open - len(shown))
        return TaskService(self.db)._serialize_many(m, shown), older

    def _substituted_slots(self, m: CurrentMember, today: date, mine) -> list[tuple]:
        """Periods I'm covering today, shaped as timetable slots so the rest of
        My Day treats them identically. Returns (TeacherSlot, covering_for_name)."""
        from app.services.substitution import SubstitutionService  # noqa: PLC0415

        subs = SubstitutionService(self.db).for_teacher(m.org_id, m.membership.id, today)
        subs = [s for s in subs if s.class_subject_id is not None]
        if not subs:
            return []
        taken = {(ts.class_id, ts.period_no) for ts in mine}
        rows = {
            cs_id: (label, sname) for cs_id, cname, section, sname in self.db.execute(
                select(ClassSubject.id, SchoolClass.name, SchoolClass.section, Subject.name)
                .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
                .join(Subject, Subject.id == ClassSubject.subject_id)
                .where(ClassSubject.id.in_([s.class_subject_id for s in subs])))
            for label in [cname + (f"-{section}" if section else "")]
        }
        absent_ids = [s.absent_member_id for s in subs if s.absent_member_id]
        absent_names = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name).join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(absent_ids))).all()
        } if absent_ids else {}

        out: list[tuple] = []
        for s in subs:
            if (s.class_id, s.period_no) in taken:
                continue
            label, sname = rows.get(s.class_subject_id, ("?", None))
            out.append((TeacherSlot(
                weekday=today.weekday(), period_no=s.period_no, class_id=s.class_id,
                class_label=label, subject_name=sname,
                class_subject_id=s.class_subject_id),
                absent_names.get(s.absent_member_id)))
        return out

    # ── per-period topic resolution (V2-P6) ──────────────────────────────────
    def _week_topics(self, org_id: uuid.UUID, cs_id: uuid.UUID, monday: date):
        """This week's planned topics for a class-subject, in syllabus order."""
        return self.db.execute(
            select(SyllabusTopic.id, SyllabusTopic.title, SyllabusUnit.title)
            .join(SyllabusUnit, SyllabusUnit.id == SyllabusTopic.unit_id)
            .join(PlanEntry, PlanEntry.topic_id == SyllabusTopic.id)
            .where(PlanEntry.org_id == org_id, PlanEntry.class_subject_id == cs_id,
                   PlanEntry.week_start == monday)
            .order_by(SyllabusUnit.position, SyllabusTopic.position)
        ).all()

    def _assign_topics(self, org_id: uuid.UUID, monday: date, slots, period_ids, logs_by_period):
        """(class_id, period_no) → (topic_id, topic_title, unit_title, logged).

        A period that already has a lesson log shows what was actually taught. The
        rest consume this week's remaining planned topics in period order, so a
        second period of the same subject gets the NEXT topic, not a repeat of the
        first. Topics logged on any earlier date are already excluded."""
        out: dict[tuple[uuid.UUID, int], tuple] = {}
        by_cs: dict[uuid.UUID, list] = {}
        for s in slots:
            by_cs.setdefault(s.class_subject_id, []).append(s)

        for cs_id, cs_slots in by_cs.items():
            logged_ids = set(self.db.scalars(
                select(LessonLog.topic_id).where(
                    LessonLog.org_id == org_id, LessonLog.class_subject_id == cs_id,
                    LessonLog.topic_id.is_not(None))))
            titles = {tid: (title, unit) for tid, title, unit in
                      self._week_topics(org_id, cs_id, monday)}
            remaining = [(tid, t, u) for tid, (t, u) in titles.items() if tid not in logged_ids]
            cursor = 0
            for s in sorted(cs_slots, key=lambda x: x.period_no):
                pid = period_ids.get((s.class_id, s.period_no))
                log = logs_by_period.get(pid) if pid else None
                if log is not None:
                    title, unit = titles.get(log.topic_id, (None, None))
                    if title is None and log.topic_id is not None:
                        title = self.db.scalar(
                            select(SyllabusTopic.title).where(SyllabusTopic.id == log.topic_id))
                    out[(s.class_id, s.period_no)] = (log.topic_id, title, unit, True)
                    continue
                if cursor < len(remaining):
                    tid, title, unit = remaining[cursor]
                    cursor += 1
                    out[(s.class_id, s.period_no)] = (tid, title, unit, False)
                else:
                    # Week's plan exhausted — the card shows no suggestion rather
                    # than re-proposing a topic the class already covered.
                    out[(s.class_id, s.period_no)] = (None, None, None, False)
        return out

    # ── quick log (CL-2) ─────────────────────────────────────────────────────
    def _slots_for_cs(self, org_id: uuid.UUID, cs_id: uuid.UUID, d: date) -> list[TimetableSlot]:
        """That class-subject's timetabled periods on `d`, per the grid effective then."""
        return list(self.db.scalars(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id, TimetableSlot.class_subject_id == cs_id,
                TimetableSlot.weekday == d.weekday(), TimetableSlot.effective_from <= d,
                or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > d))
            .order_by(TimetableSlot.period_no)))

    def _resolve_log_period(
        self, m: CurrentMember, cs: ClassSubject, d: date, body: LessonLogIn,
    ) -> ClassPeriod | None:
        """Which period occurrence does this log belong to?

        Explicit `period_id` or `period_no` wins. Otherwise fall back to the grid:
        attach to the earliest of today's slots for this class-subject that has no
        log yet — so a plain quick log still lands on a period, and a teacher
        quick-logging a double period fills period 1 then period 2. With no slot at
        all (nothing timetabled) the log stays period-less, as it did before V2-P6."""
        if body.period_id is not None:
            period = self.db.scalar(select(ClassPeriod).where(
                ClassPeriod.id == body.period_id, ClassPeriod.org_id == m.org_id))
            if period is None:
                raise NotFoundError("Period")
            return period
        if body.period_no is not None:
            return get_or_create_period(self.db, m, cs.class_id, d, body.period_no, cs.id)

        slots = self._slots_for_cs(m.org_id, cs.id, d)
        if not slots:
            return None
        taken = set(self.db.scalars(
            select(ClassPeriod.period_no)
            .join(LessonLog, LessonLog.period_id == ClassPeriod.id)
            .where(ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == cs.class_id,
                   ClassPeriod.date == d)))
        for s in slots:
            if s.period_no not in taken:
                return get_or_create_period(self.db, m, cs.class_id, d, s.period_no, cs.id)
        return get_or_create_period(self.db, m, cs.class_id, d, slots[-1].period_no, cs.id)

    def log(self, m: CurrentMember, body: LessonLogIn) -> LessonLogOut:
        cs = self._cs(m.org_id, body.class_subject_id)
        self._can_capture(m, cs)
        d = body.date or self._today(m)
        period = self._resolve_log_period(m, cs, d, body)

        # Dedupe within the period when there is one, else within the day (the
        # pre-V2-P6 key). Mirrors the two partial unique indexes on lesson_logs.
        cond = ([LessonLog.period_id == period.id] if period is not None
                else [LessonLog.class_subject_id == cs.id, LessonLog.date == d,
                      LessonLog.period_id.is_(None)])
        cond.append(LessonLog.topic_id.is_(None) if body.topic_id is None
                    else LessonLog.topic_id == body.topic_id)
        existing = self.db.scalar(select(LessonLog).where(*cond))
        if existing:
            existing.coverage = body.coverage
            existing.note = body.note
            existing.member_id = m.membership.id
            self.db.flush()
            return LessonLogOut.model_validate(existing)
        log = LessonLog(org_id=m.org_id, class_subject_id=cs.id, date=d, member_id=m.membership.id,
                        topic_id=body.topic_id, coverage=body.coverage, note=body.note,
                        period_id=period.id if period is not None else None)
        self.db.add(log)
        self.db.flush()
        return LessonLogOut.model_validate(log)

    def delete_log(self, m: CurrentMember, log_id: uuid.UUID) -> None:
        """Remove a mis-tapped topic log. Same permission as writing it."""
        log = self.db.scalar(select(LessonLog).where(
            LessonLog.id == log_id, LessonLog.org_id == m.org_id))
        if log is None:
            raise NotFoundError("Lesson log")
        self._can_capture(m, self._cs(m.org_id, log.class_subject_id))
        self.db.delete(log)
        self.db.flush()

    # ── the class log book (founder, 2026-08-05) ─────────────────────────────
    def _may_write(self, m: CurrentMember, cs: ClassSubject) -> bool:
        try:
            self._can_capture(m, cs)
        except ForbiddenError:
            return False
        return True

    def _book_scope(self, m: CurrentMember, class_subject_id: uuid.UUID,
                    since: date | None, until: date | None):
        """Resolve one class-subject's book: the row, its labels, and the window.

        Reading is `assert_can_take_class`, which is deliberately wider than
        writing: a teacher who covered this class last Tuesday, and the class
        teacher who owns the homeroom, both need to see the register even when
        they may not add to it. A class that isn't theirs is refused with a
        sentence rather than returned empty (`S-46`) — an empty book reads as
        "nothing was ever taught here".
        """
        cs = self._cs(m.org_id, class_subject_id)
        assert_can_take_class(self.db, m, cs.class_id, cs.id)
        until = until or self._today(m)
        since = since or (until - timedelta(days=89))
        klass = self.db.get(SchoolClass, cs.class_id)
        subject = self.db.scalar(select(Subject.name).where(Subject.id == cs.subject_id))
        return cs, klass, subject or "—", since, until

    def class_log_book(self, m: CurrentMember, class_subject_id: uuid.UUID,
                       since: date | None = None,
                       until: date | None = None) -> ClassLogBookOut:
        """Every log line for one class-subject over a window, newest first.

        Two row shapes in one register, and the `kind` field is what keeps them
        honest: `class` rows are `lesson_logs` and are what the syllabus board
        counts; `student` rows are `lesson_observations` of kind `log` — a line
        about one child — and count towards nothing at all.
        """
        cs, klass, subject, since, until = self._book_scope(m, class_subject_id, since, until)
        entries: list[ClassLogEntryOut] = []

        for log, topic_title, unit_title, teacher, period_no in self.db.execute(
                select(LessonLog, SyllabusTopic.title, SyllabusUnit.title,
                       User.name, ClassPeriod.period_no)
                .outerjoin(SyllabusTopic, SyllabusTopic.id == LessonLog.topic_id)
                .outerjoin(SyllabusUnit, SyllabusUnit.id == SyllabusTopic.unit_id)
                .outerjoin(Membership, Membership.id == LessonLog.member_id)
                .outerjoin(User, User.id == Membership.user_id)
                .outerjoin(ClassPeriod, ClassPeriod.id == LessonLog.period_id)
                .where(LessonLog.org_id == m.org_id,
                       LessonLog.class_subject_id == cs.id,
                       LessonLog.date >= since, LessonLog.date <= until)).all():
            # `note` carries the free text when no topic was picked — that text
            # IS the entry, so it renders as the title and not twice.
            free_text = log.topic_id is None
            entries.append(ClassLogEntryOut(
                id=log.id, kind="class", date=log.date, topic_id=log.topic_id,
                topic_title=topic_title, unit_title=unit_title,
                title=log.note if free_text else None,
                coverage=log.coverage, note=None if free_text else log.note,
                teacher_name=teacher, period_no=period_no))

        for obs, student_name, teacher in self.db.execute(
                select(LessonObservation, Student.full_name, User.name)
                .outerjoin(Student, Student.id == LessonObservation.student_id)
                .outerjoin(Membership, Membership.id == LessonObservation.member_id)
                .outerjoin(User, User.id == Membership.user_id)
                .where(LessonObservation.org_id == m.org_id,
                       LessonObservation.class_subject_id == cs.id,
                       LessonObservation.entry_kind == "log",
                       LessonObservation.student_id.is_not(None),
                       LessonObservation.date >= since,
                       LessonObservation.date <= until)).all():
            entries.append(ClassLogEntryOut(
                id=obs.id, kind="student", date=obs.date, title=obs.section,
                note=obs.note, teacher_name=teacher,
                student_id=obs.student_id, student_name=student_name))

        entries.sort(key=lambda e: (e.date, e.period_no or 0), reverse=True)
        return ClassLogBookOut(
            class_subject_id=cs.id, class_id=cs.class_id, class_label=_label(klass),
            subject_name=subject, since=since, until=until, entries=entries,
            can_write=self._may_write(m, cs))

    def add_class_log(self, m: CurrentMember, body: ClassLogIn) -> ClassLogBookOut:
        """One entry, for the class or for named children.

        With no `student_ids` this is the existing `log()` path — a `lesson_logs`
        row, which moves the syllabus. With names on it, it writes
        `lesson_observations` of kind `log` instead and **no lesson log at all**:
        a lesson that reached three children is not coverage, and recording it
        as coverage would inflate every pace figure the school reads.
        """
        cs = self._cs(m.org_id, body.class_subject_id)
        self._can_capture(m, cs)
        d = body.date or self._today(m)
        title = (body.title or "").strip()
        if body.topic_id is None and not title:
            raise ValidationError("Pick a topic or write what the class did.")

        if not body.student_ids:
            if body.topic_id is not None:
                # Same dedupe as the period card: a topic logged twice in a day
                # updates its coverage rather than doubling it (`better_coverage`).
                self.log(m, LessonLogIn(
                    class_subject_id=cs.id, topic_id=body.topic_id,
                    coverage=body.coverage, date=d, note=body.note))
            else:
                # Free text is appended, never deduped: two things a teacher
                # wrote about one afternoon are two entries, and collapsing them
                # would silently overwrite the first.
                self.db.add(LessonLog(
                    org_id=m.org_id, class_subject_id=cs.id, date=d,
                    member_id=m.membership.id, coverage=body.coverage, note=title))
                self.db.flush()
            return self.class_log_book(m, cs.id)

        ids = list(dict.fromkeys(body.student_ids))
        in_class = set(self.db.scalars(select(Student.id).where(
            Student.id.in_(ids), Student.org_id == m.org_id,
            Student.class_id == cs.class_id)))
        if in_class != set(ids):
            raise NotFoundError("Student")
        section = title or self.db.scalar(
            select(SyllabusTopic.title).where(SyllabusTopic.id == body.topic_id)) or "Note"
        for sid in ids:
            self.db.add(LessonObservation(
                org_id=m.org_id, class_subject_id=cs.id, date=d,
                member_id=m.membership.id, section=section, student_id=sid,
                note=body.note, entry_kind="log"))
        self.db.flush()
        return self.class_log_book(m, cs.id)

    def delete_class_log(self, m: CurrentMember, entry_id: uuid.UUID) -> None:
        """Remove one entry of either shape. Same permission as writing it."""
        log = self.db.scalar(select(LessonLog).where(
            LessonLog.id == entry_id, LessonLog.org_id == m.org_id))
        if log is not None:
            self._can_capture(m, self._cs(m.org_id, log.class_subject_id))
            self.db.delete(log)
            self.db.flush()
            return
        obs = self.db.scalar(select(LessonObservation).where(
            LessonObservation.id == entry_id, LessonObservation.org_id == m.org_id,
            LessonObservation.entry_kind == "log"))
        if obs is None:
            raise NotFoundError("Log entry")
        self._can_capture(m, self._cs(m.org_id, obs.class_subject_id))
        self.db.delete(obs)
        self.db.flush()

    def homework_book(self, m: CurrentMember, class_subject_id: uuid.UUID,
                      since: date | None = None,
                      until: date | None = None) -> HomeworkBookOut:
        """Every homework set for one class-subject over a window, newest first.

        Completion comes from `core/homework_verdict`, so `late` is worth here
        exactly what it is worth on the check sheet and the report card. An
        unchecked homework returns `completion=None` — never 0%, on any surface
        (HW-1): nobody has looked at it, which is the teacher's gap and not a
        statement about forty children.
        """
        cs, klass, subject, since, until = self._book_scope(m, class_subject_id, since, until)
        rows = self.db.execute(
            select(HomeworkAssignment, Student.full_name)
            .outerjoin(Student, Student.id == HomeworkAssignment.student_id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   HomeworkAssignment.class_subject_id == cs.id,
                   HomeworkAssignment.date >= since,
                   HomeworkAssignment.date <= until)
            .order_by(HomeworkAssignment.date.desc())).all()
        ids = [hw.id for hw, _ in rows]
        checks = {
            c.assignment_id: c for c in self.db.scalars(
                select(HomeworkCheck).where(HomeworkCheck.assignment_id.in_(ids)))
        } if ids else {}
        checker_names = dict(self.db.execute(
            select(Membership.id, User.name).join(User, User.id == Membership.user_id)
            .where(Membership.id.in_([c.checked_by_member_id for c in checks.values()
                                      if c.checked_by_member_id]))).all()) if checks else {}
        results: dict[uuid.UUID, list[str]] = defaultdict(list)
        if ids:
            for r in self.db.scalars(select(HomeworkResult).where(
                    HomeworkResult.assignment_id.in_(ids))):
                results[r.assignment_id].append(r.status)
        class_size = self.db.scalar(select(func.count(Student.id)).where(
            Student.org_id == m.org_id, Student.class_id == cs.class_id,
            Student.status == "active")) or 0

        entries: list[HomeworkLogEntryOut] = []
        for hw, student_name in rows:
            check = checks.get(hw.id)
            roster = 1 if hw.student_id else class_size
            exceptions = results.get(hw.id, [])
            entry = HomeworkLogEntryOut(
                id=hw.id, date=hw.date, due_date=hw.due_date, text=hw.text,
                student_id=hw.student_id, student_name=student_name,
                checked=check is not None,
                checked_at=check.checked_at if check else None,
                checked_by=checker_names.get(check.checked_by_member_id) if check else None,
                roster=roster)
            if check is not None:
                # Everyone with no exception row did it — capture-by-exception,
                # so the done set is the roster minus these (P1v2).
                counts = verdicts.tally(
                    exceptions + [verdicts.DONE] * max(0, roster - len(exceptions)))
                entry.completion = verdicts.completion(counts)
                entry.not_done, entry.partial = counts["not_done"], counts["partial"]
                entry.late, entry.carried = counts["late"], counts["carried"]
                entry.waived = counts["waived"]
            entries.append(entry)
        return HomeworkBookOut(
            class_subject_id=cs.id, class_id=cs.class_id, class_label=_label(klass),
            subject_name=subject, since=since, until=until, entries=entries,
            can_write=self._may_write(m, cs))

    # ── the period card (V2-P6) ──────────────────────────────────────────────
    def _subject_name(self, cs_id: uuid.UUID | None) -> str | None:
        if cs_id is None:
            return None
        return self.db.scalar(
            select(Subject.name).join(ClassSubject, ClassSubject.subject_id == Subject.id)
            .where(ClassSubject.id == cs_id))

    def _tests_recorded_today(self, org_id: uuid.UUID,
                              cs_ids: list[uuid.UUID], d: date) -> set[uuid.UUID]:
        """Which of the day's class-subjects already have a test on the record.

        One query for the whole day — the My Day row only has to answer "is
        there one?", the same shallow question the topic and homework chips
        answer. What those tests ARE is the period card's job (`tests`).

        "On the record" means a mark or a photographed paper. Starting a
        capture creates its cycle before either exists, so counting the cycle
        alone would put a green chip on a test that was opened and abandoned.
        """
        if not cs_ids:
            return set()
        has_score = select(AssessmentScore.id).where(
            AssessmentScore.cycle_id == AssessmentCycle.id).exists()
        has_page = (select(ScoreCapturePage.id)
                    .join(ScoreCapture, ScoreCapture.id == ScoreCapturePage.capture_id)
                    .where(ScoreCapture.cycle_id == AssessmentCycle.id,
                           ScoreCapture.status != "discarded").exists())
        return set(self.db.scalars(
            select(ClassSubject.id)
            .join(AssessmentCycle,
                  and_(AssessmentCycle.class_id == ClassSubject.class_id,
                       AssessmentCycle.subject_id == ClassSubject.subject_id))
            .where(ClassSubject.id.in_(cs_ids),
                   AssessmentCycle.org_id == org_id,
                   AssessmentCycle.date == d,
                   or_(has_score, has_page))))

    def _tests_today(self, m: CurrentMember, class_id: uuid.UUID,
                     cs_id: uuid.UUID | None, d: date) -> list[ExamSummary]:
        """The tests recorded for this class-subject on this date.

        Founder, 2026-08-18: a test photographed from the period card vanished
        the moment the review sheet closed, so the teacher could neither see
        what she had just recorded nor get back to the papers. This is the way
        back — the same rows the exams feed builds, so the two screens cannot
        disagree about how many were scored.

        Only exams carrying something are listed. Starting a capture creates
        its cycle up front, and discarding leaves that empty cycle behind; an
        exam with no mark and no photographed paper is that ghost, not a
        record, and offering it would be a row that opens onto nothing.
        """
        if cs_id is None:
            return []
        subject_id = self.db.scalar(
            select(ClassSubject.subject_id).where(ClassSubject.id == cs_id))
        if subject_id is None:
            return []
        from app.services.exams import ExamService  # noqa: PLC0415
        rows = ExamService(self.db).feed(
            m, class_id, limit=20, subject_id=subject_id, on_date=d)
        return [r for r in rows if r.scored_count > 0 or r.page_count > 0]

    def _plan_and_homework(
        self, m: CurrentMember, class_id: uuid.UUID, cs_id: uuid.UUID | None,
        period_no: int, d: date, monday: date, period: ClassPeriod | None,
    ) -> tuple[PeriodPlanOut, list[PeriodHomeworkOut]]:
        """One class's plan and homework for one period.

        Lifted out of `period_card` unchanged so a combined period can render the
        same two things for every class in the room (TT-4) without a second copy
        of the topic-assignment rules — which is exactly how two definitions of
        "what was planned here" would have got into the codebase.
        """
        if cs_id is None:
            return PeriodPlanOut(), []
        slots = self._slots_for_cs(m.org_id, cs_id, d)
        period_ids = {
            (p.class_id, p.period_no): p.id for p in self.db.scalars(
                select(ClassPeriod).where(
                    ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == class_id,
                    ClassPeriod.date == d))}
        day_logs = list(self.db.scalars(
            select(LessonLog).where(
                LessonLog.org_id == m.org_id, LessonLog.class_subject_id == cs_id,
                LessonLog.date == d, LessonLog.period_id.is_not(None))
            .order_by(LessonLog.created_at)))
        logs_by_period = {log.period_id: log for log in day_logs}
        assignment = self._assign_topics(m.org_id, monday, slots, period_ids, logs_by_period)
        topic_id, title, unit, logged = assignment.get(
            (class_id, period_no), (None, None, None, False))
        log = logs_by_period.get(period.id) if period else None
        progress = PlannerService(self.db).topic_progress(m, cs_id)
        titles = {r.topic_id: r.topic_title for r in progress}
        # ALL topics taught this period — a period can hold several, and a
        # topic continued from yesterday shows up again here (partial → full).
        period_logs = [x for x in day_logs if period and x.period_id == period.id]
        plan = PeriodPlanOut(
            planned_topic_id=None if logged else topic_id,
            planned_topic_title=None if logged else title,
            planned_unit_title=None if logged else unit,
            logged_topic_id=log.topic_id if log else None,
            logged_coverage=log.coverage if log else None,
            logged=[PeriodLogOut(
                id=x.id, topic_id=x.topic_id,
                topic_title=titles.get(x.topic_id) if x.topic_id else None,
                coverage=x.coverage, note=x.note) for x in period_logs],
            progress=progress)
        homework = [
            PeriodHomeworkOut(id=h.id, text=h.text, student_id=h.student_id,
                              due_date=h.due_date)
            for h in self.db.scalars(
                select(HomeworkAssignment).where(
                    HomeworkAssignment.org_id == m.org_id,
                    HomeworkAssignment.class_subject_id == cs_id,
                    HomeworkAssignment.date == d).order_by(HomeworkAssignment.created_at))]
        return plan, homework

    def period_card(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
                    on_date: date | None = None) -> PeriodCardOut:
        """Everything the period-detail page needs, in one call. Purely a read —
        the period row is created by "Start attendance", not by opening the page."""
        d = on_date or self._today(m)
        assert_can_take_class(self.db, m, class_id, None, d, period_no)
        monday = d - timedelta(days=d.weekday())
        period = find_period(self.db, m.org_id, class_id, d, period_no)

        cs_id = period.class_subject_id if period else None
        if cs_id is None:
            cs_id = self.db.scalar(
                select(TimetableSlot.class_subject_id).where(
                    TimetableSlot.org_id == m.org_id, TimetableSlot.class_id == class_id,
                    TimetableSlot.weekday == d.weekday(), TimetableSlot.period_no == period_no,
                    TimetableSlot.effective_from <= d,
                    or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > d)))

        sheet = AttendanceService(self.db).roster(m, class_id, period_no, d, combined=False)
        marks_attendance, day_taken = self._marks_attendance(m, period_no, class_id, d)
        subject_name = self._subject_name(cs_id)
        plan, homework = self._plan_and_homework(
            m, class_id, cs_id, period_no, d, monday, period)

        # TT-4 — the rest of the room. Built from the same two helpers as this
        # class's own half, so a combined card cannot drift from an ordinary one.
        combo = TimetableService(self.db).combined_meeting(m, class_id, period_no, d)
        combined_cards: list[CombinedClassCard] = []
        if combo is not None:
            att = AttendanceService(self.db)
            for c in combo.classes:
                other = find_period(self.db, m.org_id, c.class_id, d, period_no)
                one_sheet = att.roster(m, c.class_id, period_no, d, combined=False)
                c_plan, c_hw = self._plan_and_homework(
                    m, c.class_id, c.class_subject_id, period_no, d, monday, other)
                combined_cards.append(CombinedClassCard(
                    class_id=c.class_id, class_label=c.class_label,
                    class_subject_id=c.class_subject_id, subject_name=c.subject_name,
                    period_id=other.id if other else None,
                    attendance_marked=one_sheet.marked,
                    roster_count=len(one_sheet.roster),
                    present_count=one_sheet.present_count if one_sheet.marked else None,
                    absent_count=one_sheet.absent_count if one_sheet.marked else None,
                    late_count=one_sheet.late_count if one_sheet.marked else None,
                    plan=c_plan, homework=c_hw))

        # V1-7 `S-147`/`S-145`: the day's approved events, which are both the
        # reason picker behind "not held, because" and the answer to whether
        # this period is still being asked for at all.
        lock = day_lock(self.db, m.org_id, d)
        day_events = [PeriodEventOut(
            id=e.id, title=e.title, type=e.type,
            affects_teaching=e.affects_teaching, blocks_periods=e.blocks_periods)
            for e in lock.events]
        locked = not lock.expects(period_no)

        return PeriodCardOut(
            class_id=class_id, class_label=sheet.class_label, period_no=period_no, date=d,
            class_subject_id=cs_id, subject_name=subject_name,
            combined_id=combo.id if combo else None,
            combined_label=combo.label if combo else None,
            combined=combined_cards,
            period_id=period.id if period else None,
            status=period.status if period else "held",
            not_held_reason=period.not_held_reason if period else None,
            not_held_event_id=period.not_held_event_id if period else None,
            day_events=day_events,
            locked=locked,
            lock_reason=lock.title if locked else None,
            opened=period is not None,
            closed=period is not None and period.closed_at is not None,
            attendance_marked=sheet.marked,
            marks_attendance=marks_attendance,
            day_attendance_taken=day_taken,
            roster=sheet.roster,
            roster_count=len(sheet.roster),
            present_count=sheet.present_count if sheet.marked else None,
            absent_count=sheet.absent_count if sheet.marked else None,
            late_count=sheet.late_count if sheet.marked else None,
            plan=plan, homework=homework,
            # Per class, not per room: the capture surface photographs ONE
            # class's papers, so a combined period lists the tests of the class
            # whose card this is. The other half's own card lists its own.
            tests=self._tests_today(m, class_id, cs_id, d))

    # ── deep log — lesson observations (optional, exception-only) ────────────
    def _observation_scope(self, m: CurrentMember, body: ObservationSectionIn,
                           d: date) -> ClassPeriod | None:
        """Resolve which period occurrence the section belongs to (same rules as
        the lesson log): explicit id, explicit number, else day-scoped."""
        if body.period_id is not None:
            period = self.db.scalar(select(ClassPeriod).where(
                ClassPeriod.id == body.period_id, ClassPeriod.org_id == m.org_id))
            if period is None:
                raise NotFoundError("Period")
            return period
        if body.period_no is not None:
            cs = self._cs(m.org_id, body.class_subject_id)
            return get_or_create_period(self.db, m, cs.class_id, d, body.period_no, cs.id)
        return None

    def save_observation_section(self, m: CurrentMember,
                                 body: ObservationSectionIn) -> ObservationsOut:
        """Full-replace one section's rows — concept rows plus only the tapped
        per-student deviations. An empty `concepts` list keeps just the section
        row ("we did Vocabulary", nothing deeper)."""
        cs = self._cs(m.org_id, body.class_subject_id)
        self._can_capture(m, cs)
        d = body.date or self._today(m)
        period = self._observation_scope(m, body, d)
        period_id = period.id if period is not None else None

        # Per-student rows must be students of this class.
        student_ids = {s.student_id for c in body.concepts for s in c.students}
        if student_ids:
            in_class = set(self.db.scalars(select(Student.id).where(
                Student.id.in_(student_ids), Student.org_id == m.org_id,
                Student.class_id == cs.class_id)))
            if in_class != student_ids:
                raise NotFoundError("Student")

        # `entry_kind` scopes the full-replace: a class-log line a teacher wrote
        # about one child is not part of this section's observation set, and
        # re-saving "Vocabulary" from the period card must not delete it.
        for row in self.db.scalars(select(LessonObservation).where(
                LessonObservation.org_id == m.org_id,
                LessonObservation.class_subject_id == cs.id,
                LessonObservation.date == d,
                LessonObservation.entry_kind == "observation",
                LessonObservation.period_id.is_(None) if period_id is None
                else LessonObservation.period_id == period_id,
                LessonObservation.section == body.section)):
            self.db.delete(row)
        self.db.flush()

        common = {"org_id": m.org_id, "class_subject_id": cs.id, "date": d,
                  "period_id": period_id, "member_id": m.membership.id,
                  "section": body.section, "entry_kind": "observation"}
        if not body.concepts:
            self.db.add(LessonObservation(**common))
        for c in body.concepts:
            self.db.add(LessonObservation(**common, concept=c.concept))
            for s in c.students:
                self.db.add(LessonObservation(**common, concept=c.concept,
                                              student_id=s.student_id, rating=s.rating,
                                              note=s.note))
        self.db.flush()
        return self.observations(m, cs.id, d, period_id)

    def delete_observation_section(self, m: CurrentMember, class_subject_id: uuid.UUID,
                                   section: str, on_date: date | None = None,
                                   period_id: uuid.UUID | None = None) -> None:
        """Remove a named section from the day. Omitting period_id removes it
        wherever it sits (period-scoped or day-scoped) — the teacher is deleting
        "the Vocabulary section", not a storage detail."""
        cs = self._cs(m.org_id, class_subject_id)
        self._can_capture(m, cs)
        d = on_date or self._today(m)
        cond = [LessonObservation.org_id == m.org_id,
                LessonObservation.class_subject_id == cs.id,
                LessonObservation.date == d,
                LessonObservation.entry_kind == "observation",
                LessonObservation.section == section]
        if period_id is not None:
            cond.append(LessonObservation.period_id == period_id)
        for row in self.db.scalars(select(LessonObservation).where(*cond)):
            self.db.delete(row)
        self.db.flush()

    def observations(self, m: CurrentMember, class_subject_id: uuid.UUID,
                     on_date: date | None = None,
                     period_id: uuid.UUID | None = None) -> ObservationsOut:
        """The deep log for one class-subject day (or one period of it), grouped
        section → concept → tapped students."""
        cs = self._cs(m.org_id, class_subject_id)
        assert_can_take_class(self.db, m, cs.class_id, None)
        d = on_date or self._today(m)
        cond = [LessonObservation.org_id == m.org_id,
                LessonObservation.class_subject_id == cs.id,
                LessonObservation.date == d,
                LessonObservation.entry_kind == "observation"]
        if period_id is not None:
            cond.append(LessonObservation.period_id == period_id)
        rows = list(self.db.execute(
            select(LessonObservation, Student.full_name)
            .outerjoin(Student, Student.id == LessonObservation.student_id)
            .where(*cond).order_by(LessonObservation.created_at)).all())

        sections: dict[tuple[uuid.UUID | None, str], ObservationSectionOut] = {}
        concepts: dict[tuple[uuid.UUID | None, str, str | None], ObservationConceptOut] = {}
        for obs, student_name in rows:
            skey = (obs.period_id, obs.section)
            if skey not in sections:
                sections[skey] = ObservationSectionOut(
                    section=obs.section, period_id=obs.period_id)
            if obs.concept is None and obs.student_id is None:
                continue  # bare section row — nothing deeper recorded
            ckey = (*skey, obs.concept)
            if ckey not in concepts:
                concepts[ckey] = ObservationConceptOut(concept=obs.concept)
                sections[skey].concepts.append(concepts[ckey])
            if obs.student_id is not None:
                concepts[ckey].students.append(ObservationStudentOut(
                    student_id=obs.student_id, full_name=student_name or "?",
                    rating=obs.rating or "needs_work", note=obs.note))
        return ObservationsOut(class_subject_id=cs.id, date=d,
                               sections=list(sections.values()))

    # ── homework (CL-2) + guardian notify (P3) ───────────────────────────────
    def add_homework(self, m: CurrentMember, body: HomeworkIn) -> HomeworkOut:
        """Set homework for the class, for one child, or for several.

        `student_ids` writes **one assignment row per child**, never one row with
        a list on it. Every existing reader — the check sheet, the streak, the
        parent portal, the report card — keys on (assignment, student), so a
        shared row would have needed all of them taught a second shape, and a
        child's history would stop being one row per piece of work.

        TT-4: `also_class_subject_ids` sets the SAME homework in the other
        classes of a combined period — one form, one act, one assignment row per
        class. Same reasoning as `student_ids` above: the rows stay ordinary, so
        the check sheet, the parent portal and the syllabus board learn nothing
        new. A per-student note never fans out; those children are in one class.
        """
        also = [cs_id for cs_id in dict.fromkeys(body.also_class_subject_ids)
                if cs_id != body.class_subject_id]
        if also and not (body.student_id or body.student_ids):
            first = self._add_homework_one(m, body)
            notified = first.notified_count
            created = list(first.created_ids)
            for cs_id in also:
                extra = self._add_homework_one(
                    m, body.model_copy(update={
                        "class_subject_id": cs_id, "also_class_subject_ids": []}))
                notified += extra.notified_count
                created.extend(extra.created_ids)
            return first.model_copy(update={
                "notified_count": notified, "created_ids": created})
        return self._add_homework_one(m, body)

    def _add_homework_one(self, m: CurrentMember, body: HomeworkIn) -> HomeworkOut:
        cs = self._cs(m.org_id, body.class_subject_id)
        self._can_capture(m, cs)
        d = body.date or self._today(m)
        # A per-student addition must be a student of this class (V2-P3 §5.5).
        targets: list[uuid.UUID | None] = (
            list(dict.fromkeys(body.student_ids)) if body.student_ids
            else [body.student_id])
        named = [t for t in targets if t is not None]
        if named:
            in_class = set(self.db.scalars(
                select(Student.id).where(
                    Student.id.in_(named), Student.org_id == m.org_id,
                    Student.class_id == cs.class_id)))
            if in_class != set(named):
                raise NotFoundError("Student")

        klass = self.db.get(SchoolClass, cs.class_id)
        subject = self.db.scalar(select(Subject.name).where(Subject.id == cs.subject_id))
        due = f" (due {body.due_date})" if body.due_date else ""
        message = f"Homework for {_label(klass)} {subject}: {body.text}{due}"

        created: list[HomeworkAssignment] = []
        count = 0
        for target in targets:
            hw = HomeworkAssignment(
                org_id=m.org_id, class_subject_id=cs.id, date=d, text=body.text,
                due_date=body.due_date, student_id=target)
            self.db.add(hw)
            self.db.flush()
            created.append(hw)

            # Notify the one student's guardians for a per-student note, else
            # the class (P3 — the teacher's payback for logging it).
            guardian_q = (
                select(Student.id, Guardian)
                .join(Guardian, Guardian.student_id == Student.id)
                .where(Student.org_id == m.org_id))
            guardian_q = (guardian_q.where(Student.id == target) if target
                          else guardian_q.where(Student.class_id == cs.class_id))
            # Grouped by child: with siblings on one login, a homework note that
            # doesn't say whose it is is unreadable.
            by_student: dict[uuid.UUID, list[Guardian]] = {}
            for sid, guardian in self.db.execute(guardian_q).all():
                by_student.setdefault(sid, []).append(guardian)
            for sid, guardians in by_student.items():
                count += notify_guardians(
                    self.db, org_id=m.org_id, student_id=sid, guardians=guardians,
                    kind="homework_set", title=f"Homework · {subject}", body=message,
                    dedupe_key=f"homework_set:{hw.id}:{sid}").notified
            hw.notified_at = datetime.now(UTC)
        self.db.flush()

        first = created[0]
        return HomeworkOut(id=first.id, class_subject_id=cs.id, date=d, text=first.text,
                           due_date=first.due_date, student_id=first.student_id,
                           notified_count=count,
                           created_ids=[h.id for h in created])

    # ── homework checking (HW-1) — capture-by-exception, like attendance ─────
    def _homework(self, m: CurrentMember, assignment_id: uuid.UUID) -> HomeworkAssignment:
        hw = self.db.scalar(
            select(HomeworkAssignment).where(
                HomeworkAssignment.id == assignment_id, HomeworkAssignment.org_id == m.org_id)
        )
        if hw is None:
            raise NotFoundError("Homework")
        return hw

    def _block_covers_homework(self, m: CurrentMember, block_id: uuid.UUID,
                               class_id: uuid.UUID) -> bool:
        """May this member check this class's homework from inside a block?

        TT-2: the evening homework class is run by a warden who very likely
        teaches none of the subjects she is supervising. Three things must all
        hold, and the narrowness is the point — this is the one path by which
        somebody who does not teach a class can write its homework verdicts:

        1. the block's kind actually does homework checking (`day_shape`);
        2. she is on that block's staff (or its owner, or an admin);
        3. the class is genuinely in the block — it has a live timetable cell
           for it, or is linked to it directly.
        """
        from app.models import Session as SessionModel  # noqa: PLC0415
        from app.models import SessionClass, TimetableSlot  # noqa: PLC0415
        from app.services.timetable import TimetableService  # noqa: PLC0415

        block = self.db.scalar(select(SessionModel).where(
            SessionModel.id == block_id, SessionModel.org_id == m.org_id))
        if block is None or not day_shape.capture_for(block.kind).homework_check:
            return False
        if not TimetableService(self.db).may_take_block(m, block_id):
            return False
        on_grid = self.db.scalar(select(TimetableSlot.id).where(
            TimetableSlot.org_id == m.org_id, TimetableSlot.session_id == block_id,
            TimetableSlot.class_id == class_id,
            TimetableSlot.effective_to.is_(None)).limit(1))
        if on_grid is not None:
            return True
        return self.db.scalar(select(SessionClass.id).where(
            SessionClass.session_id == block_id,
            SessionClass.class_id == class_id).limit(1)) is not None

    def _can_touch_homework(self, m: CurrentMember, cs, hw,
                            block_id: uuid.UUID | None = None) -> None:
        """S-93: a substitute who covered this class since the homework was set
        may open and check it — `homework_checks.checked_by_member_id` exists
        precisely to record that it was someone else. TT-2 adds the same
        widening for the staff of a homework block."""
        try:
            self._can_capture(m, cs)
            return
        except ForbiddenError:
            if block_id is not None and self._block_covers_homework(m, block_id, cs.class_id):
                return
            from app.models import PeriodSubstitution  # noqa: PLC0415
            covered = self.db.scalar(
                select(PeriodSubstitution.id).where(
                    PeriodSubstitution.org_id == m.org_id,
                    PeriodSubstitution.class_id == cs.class_id,
                    PeriodSubstitution.substitute_member_id == m.membership.id,
                    PeriodSubstitution.cancelled_at.is_(None),
                    PeriodSubstitution.date >= hw.date).limit(1))
            if covered is None:
                raise

    def _homework_roster(self, org_id: uuid.UUID, hw: HomeworkAssignment,
                         class_id: uuid.UUID) -> list[Student]:
        """Who this homework is for. A per-student assignment has a roster of one
        — checking it must not present the whole class."""
        q = select(Student).where(Student.org_id == org_id, Student.status == "active")
        q = (q.where(Student.id == hw.student_id) if hw.student_id
             else q.where(Student.class_id == class_id))
        return list(self.db.scalars(q.order_by(Student.roll_no, Student.full_name)))

    def homework_sheet(self, m: CurrentMember, assignment_id: uuid.UUID,
                       block_id: uuid.UUID | None = None) -> HomeworkSheetOut:
        hw = self._homework(m, assignment_id)
        cs = self._cs(m.org_id, hw.class_subject_id)
        self._can_touch_homework(m, cs, hw, block_id)
        klass = self.db.get(SchoolClass, cs.class_id)
        subject = self.db.scalar(select(Subject.name).where(Subject.id == cs.subject_id))
        check = self.db.scalar(
            select(HomeworkCheck).where(HomeworkCheck.assignment_id == assignment_id))
        results = {
            r.student_id: r for r in self.db.scalars(
                select(HomeworkResult).where(HomeworkResult.assignment_id == assignment_id))
        }
        checked_by = None
        if check is not None and check.checked_by_member_id:
            checked_by = self.db.scalar(
                select(User.name).join(Membership, Membership.user_id == User.id)
                .where(Membership.id == check.checked_by_member_id))

        students = self._homework_roster(m.org_id, hw, cs.class_id)
        context = self._sheet_context(m, hw, cs.class_id, [st.id for st in students])

        rows: list[HomeworkSheetRow] = []
        for st in students:
            hit = results.get(st.id)
            absent, carried, streak = context.get(st.id, (False, 0, 0))
            rows.append(HomeworkSheetRow(
                student_id=st.id, full_name=st.full_name, roll_no=st.roll_no,
                # S-85: an absent child is SHOWN, never preselected. `done` stays
                # the default until a human says otherwise — the sheet reports
                # what it knows and lets the teacher decide.
                status=hit.status if hit else "done", note=hit.note if hit else None,
                absent_when_set=absent, carried_pending=carried, miss_streak=streak))
        counts = verdicts.tally(r.status for r in rows)
        return HomeworkSheetOut(
            assignment_id=hw.id, class_label=_label(klass), subject_name=subject,
            text=hw.text, date=hw.date, due_date=hw.due_date,
            checked=check is not None, checked_at=check.checked_at if check else None,
            checked_by=checked_by, student_id=hw.student_id, roster=rows,
            done_count=counts["done"], not_done_count=counts["not_done"],
            partial_count=counts["partial"], late_count=counts["late"],
            carried_count=counts["carried"], waived_count=counts["waived"])

    def _sheet_context(self, m: CurrentMember, hw: HomeworkAssignment,
                       class_id: uuid.UUID, student_ids: list[uuid.UUID],
                       ) -> dict[uuid.UUID, tuple[bool, int, int]]:
        """student → (absent when it was set, carried items still pending, streak).

        The three things the teacher needs while she is holding the notebooks,
        in three queries for the whole class rather than three per child.

        Everything here is a READ over capture that already happened — attendance
        knows who was in the room, `homework_results` knows what is still carried,
        and the streak is the same one the admin board computes. None of it is a
        second copy: a "was absent when set" column would drift from attendance
        the first time a register was corrected.
        """
        if not student_ids:
            return {}
        # 1 · Who was day-absent on the day it was set (THE shared rule).
        marked, absents = day_absence_maps(self.db, m.org_id, hw.date, hw.date)
        taken = marked.get((class_id, hw.date), 0)

        # 2 · This class's earlier homework, so the streak is computed over ALL
        # of it. Reading only the exception rows would count every day in the
        # window as a bad one — "done" has no row, which is the whole design.
        since = hw.date - timedelta(days=SHEET_STREAK_DAYS)
        past = self.db.execute(
            select(HomeworkAssignment.id, HomeworkAssignment.date,
                   HomeworkAssignment.student_id)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   ClassSubject.class_id == class_id,
                   HomeworkAssignment.date >= since,
                   HomeworkAssignment.date < hw.date)).all()
        past_ids = [aid for aid, _d, _s in past]
        checked_ids = set(self.db.scalars(
            select(HomeworkCheck.assignment_id)
            .where(HomeworkCheck.assignment_id.in_(past_ids)))) if past_ids else set()
        rows = self.db.execute(
            select(HomeworkResult.assignment_id, HomeworkResult.student_id,
                   HomeworkResult.status)
            .where(HomeworkResult.assignment_id.in_(past_ids),
                   HomeworkResult.student_id.in_(student_ids))).all() if past_ids else []
        verdict_at: dict[tuple[uuid.UUID, uuid.UUID], str] = {
            (aid, sid): status for aid, sid, status in rows
        }

        wanted = set(student_ids)
        dated: dict[uuid.UUID, list[tuple[date, str]]] = defaultdict(list)
        carried: dict[uuid.UUID, int] = defaultdict(int)
        for aid, on, only_for in past:
            targets = wanted if only_for is None else ({only_for} & wanted)
            for sid in targets:
                if aid not in checked_ids:
                    status = "not_checked"
                else:
                    status = verdict_at.get((aid, sid), "done")
                dated[sid].append((on, status))
                # S-97: still waiting to be resolved from while they were away.
                if status == "carried":
                    carried[sid] += 1

        return {
            sid: (is_day_absent(taken, absents.get(sid, {}).get(hw.date, 0)),
                  carried.get(sid, 0),
                  verdicts.miss_streak(dated.get(sid, [])))
            for sid in student_ids
        }

    def check_homework(self, m: CurrentMember, assignment_id: uuid.UUID,
                       body: HomeworkCheckIn,
                       block_id: uuid.UUID | None = None) -> HomeworkSheetOut:
        """Record who didn't do it. An empty list means everyone did.

        Full replace of the exception set (P1v2, same contract as
        `AttendanceService.mark`), and it recomputes `done_count`/`total_count`
        so every existing reader of those columns stays correct.
        """
        hw = self._homework(m, assignment_id)
        cs = self._cs(m.org_id, hw.class_subject_id)
        self._can_touch_homework(m, cs, hw, block_id)

        check = self.db.scalar(
            select(HomeworkCheck).where(HomeworkCheck.assignment_id == assignment_id))
        if check is None:
            check = HomeworkCheck(org_id=m.org_id, assignment_id=assignment_id)
            self.db.add(check)
            self.db.flush()

        # Only students this homework was actually set for can be flagged — the
        # ids arrive from a client, and org_id comes from the token (law 1).
        roster = {st.id for st in self._homework_roster(m.org_id, hw, cs.class_id)}
        wanted = {r.student_id: r for r in body.results if r.student_id in roster}

        existing = {
            r.student_id: r for r in self.db.scalars(
                select(HomeworkResult).where(HomeworkResult.assignment_id == assignment_id))
        }
        for student_id, row in existing.items():
            if student_id not in wanted:
                self.db.delete(row)
        for student_id, incoming in wanted.items():
            if student_id in existing:
                existing[student_id].status = incoming.status
                existing[student_id].note = incoming.note
                continue
            self.db.add(HomeworkResult(
                org_id=m.org_id, check_id=check.id, assignment_id=assignment_id,
                student_id=student_id, status=incoming.status, note=incoming.note))

        check.total_count = len(roster)
        check.done_count = len(roster) - len(wanted)
        check.checked_at = datetime.now(UTC)
        check.checked_by_member_id = m.membership.id
        self.db.flush()
        # Carry the block through: the re-read runs the same guard, and a warden
        # who may write these verdicts must be able to read back what she wrote.
        return self.homework_sheet(m, assignment_id, block_id)

    # ── compliance (CL-4) — coordinator/director ─────────────────────────────
    def compliance(self, m: CurrentMember, on_date: date | None = None) -> ComplianceOut:
        today = on_date or self._today(m)
        year = self._active_year(m.org_id)
        rows: list[ComplianceRow] = []
        if year is not None:
            data = self.db.execute(
                select(ClassSubject, Subject.name, SchoolClass, User.name)
                .join(Subject, Subject.id == ClassSubject.subject_id)
                .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
                .outerjoin(Membership, Membership.id == ClassSubject.teacher_member_id)
                .outerjoin(User, User.id == Membership.user_id)
                .where(ClassSubject.org_id == m.org_id, SchoolClass.academic_year_id == year.id)
                .order_by(SchoolClass.name, Subject.name)
            ).all()
            for cs, sname, klass, teacher in data:
                logged = self.db.scalar(
                    select(LessonLog.id).where(
                        LessonLog.class_subject_id == cs.id, LessonLog.date == today).limit(1)
                ) is not None
                rows.append(ComplianceRow(
                    class_subject_id=cs.id, class_label=_label(klass), subject_name=sname,
                    teacher_name=teacher, logged=logged))
        return ComplianceOut(date=today, logged_count=sum(1 for r in rows if r.logged),
                             total=len(rows), rows=rows)
