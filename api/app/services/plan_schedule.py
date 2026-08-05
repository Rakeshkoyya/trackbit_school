"""Moving a chapter (SY-1) — the teacher's own edit to the plan.

`draft` and `generate` lay a whole window out at once, from the syllabus and the
calendar, and are refused while a baseline is locked. That is right for the act
they perform — rewriting everything — and it left no way to do the thing a
teacher actually does in October: *"chapter 3 needs another week, and I will take
it out of chapter 5."*

**Why this is allowed on an approved plan, and why it was not safe before.**
`plan_entries.week_start` used to be both the promise and the schedule, and
`baseline_finish` read it live. Moving a chapter later would therefore have moved
the baseline with it, and every red subject in the school could be cleared by
dragging chapters into December. SY-1 froze the promise at approval
(`baseline_week_start`), so the two are now separate facts: she reschedules the
schedule, the promise stays where the admin locked it, and the distance between
them is exactly the slip the board is supposed to show. The edit is visible, not
silent — the table renders both dates.

What is still refused: scheduling a chapter nobody has sized (you cannot place
what has no estimate), and dates outside the year. What is **reported but
saved**: a range too short for the chapters put in it. The teacher is the one who
knows whether she can go faster, and V2-P5 already settled that over-capacity is
surfaced, never squeezed.
"""

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    PlanEntry,
    SchoolClass,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    Term,
)
from app.schemas.syllabus_board import (
    PlanTimelineOut,
    RescheduleOut,
    RescheduleViolation,
    TimelineChapter,
    TimelineMarker,
)
from app.services.calendar import effective_periods
from app.services.planner import PlannerService, _monday
from app.services.school_clock import today_in
from app.services.syllabus_board import SyllabusBoardService


class PlanScheduleService:
    def __init__(self, db: Session):
        self.db = db
        self.planner = PlannerService(db)

    # ── access ───────────────────────────────────────────────────────────────
    def _cs(self, m: CurrentMember, cs_id: uuid.UUID) -> ClassSubject:
        cs = self.db.scalar(select(ClassSubject).where(
            ClassSubject.id == cs_id, ClassSubject.org_id == m.org_id))
        if cs is None:
            raise NotFoundError("Class-subject")
        return cs

    def _assert_can_plan(self, m: CurrentMember, cs: ClassSubject) -> None:
        """Admin anywhere; otherwise the subject's own teacher, or the class
        teacher of that class. Blocked with a sentence rather than filtered to an
        empty timeline (`S-46`) — nothing showing reads as a subject with no
        chapters."""
        if m.is_coordinator_up:
            return
        if cs.teacher_member_id == m.membership.id:
            return
        klass = self.db.get(SchoolClass, cs.class_id)
        if klass is not None and klass.class_teacher_member_id == m.membership.id:
            return
        raise ForbiddenError("This subject is not yours to plan.",
                             code="not_your_subject")

    # ── the dialog's read ────────────────────────────────────────────────────
    def timeline(self, m: CurrentMember, cs_id: uuid.UUID,
                 term_id: uuid.UUID | None = None) -> PlanTimelineOut:
        """The chapters she can move, and the fixed points she is moving them
        against: exams, term boundaries and today.

        Everything movable is a chapter; everything unmovable is a marker. The
        dialog needs no rule of its own to tell them apart."""
        cs = self._cs(m, cs_id)
        self._assert_can_plan(m, cs)
        klass = self.db.get(SchoolClass, cs.class_id)
        year = self.db.get(AcademicYear, klass.academic_year_id) if klass else None
        if year is None:
            raise ValidationError("This class has no academic year.")
        subject = self.db.get(Subject, cs.subject_id)
        start, end, _lbl = self.planner._window(m.org_id, year, term_id)

        board = SyllabusBoardService(self.db)
        rows = board.board(m, year.id, class_subject_id=cs_id, term_id=term_id)
        chapters: list[TimelineChapter] = []
        for group in rows.classes:
            for sub in group.subjects:
                for ch in sub.chapters:
                    chapters.append(TimelineChapter(
                        unit_id=ch.unit_id, title=ch.title, position=ch.position,
                        est_periods=ch.est_periods,
                        planned_start=ch.planned_start, planned_end=ch.planned_end,
                        actual_start=ch.actual_start, actual_end=ch.actual_end,
                        status=ch.status, difficulty=ch.difficulty,
                        # A finished chapter is history. Moving its dates would
                        # rewrite what already happened, and the logs beside it
                        # would immediately contradict the new plan.
                        locked=ch.status == "completed"))

        markers: list[TimelineMarker] = [
            TimelineMarker(kind="today", label="Today", date=today_in(m.org.timezone))]
        for ev in self.db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.org_id == m.org_id,
                CalendarEvent.academic_year_id == year.id,
                CalendarEvent.type == "exam_block")
            .order_by(CalendarEvent.start_date)
        ):
            if ev.end_date >= start and ev.start_date <= end:
                markers.append(TimelineMarker(
                    kind="exam", label=ev.title, date=ev.start_date,
                    end_date=ev.end_date))
        for t in self.db.scalars(
            select(Term).where(Term.org_id == m.org_id,
                               Term.academic_year_id == year.id)
            .order_by(Term.start_date)
        ):
            if t.end_date >= start and t.start_date <= end:
                markers.append(TimelineMarker(kind="term_end", label=t.name,
                                              date=t.end_date))

        state = self.planner._approval_state(m.org_id, cs_id)
        approved = self.planner._is_locked(state, term_id)
        return PlanTimelineOut(
            class_subject_id=cs_id,
            class_label=klass.name + (f"-{klass.section}" if klass.section else ""),
            subject_name=subject.name if subject else "",
            window_start=start, window_end=end,
            periods_per_week=cs.periods_per_week or 0,
            # `locked` here means "you cannot move anything", which approval does
            # NOT cause — the baseline is frozen separately, so the schedule stays
            # editable and the slip stays visible. The only true block is having
            # no periods to plan into.
            locked=not cs.periods_per_week,
            lock_reason=("This subject has no periods a week on the class, so there "
                         "is no pace to plan against. Set its weekly periods first."
                         if not cs.periods_per_week else
                         "The baseline is approved. Moving a chapter now is recorded "
                         "as a change against it, not a new promise."
                         if approved else None),
            chapters=chapters, markers=markers)

    # ── the write ────────────────────────────────────────────────────────────
    def reschedule(self, m: CurrentMember, cs_id: uuid.UUID, body) -> RescheduleOut:
        cs = self._cs(m, cs_id)
        self._assert_can_plan(m, cs)
        if not cs.periods_per_week:
            raise ValidationError(
                "This subject has no periods/week on the class, so a date range "
                "means nothing yet. Set its weekly periods first.")
        klass = self.db.get(SchoolClass, cs.class_id)
        year = self.db.get(AcademicYear, klass.academic_year_id) if klass else None
        if year is None:
            raise ValidationError("This class has no academic year.")

        units = {u.id: u for u in self.planner._units(m.org_id, cs_id)}
        floor = self.planner._tracking_floor(year)
        blocked, partial = self.planner._calendar(m.org_id, year.id)
        entries = {e.topic_id: e for e in self.db.scalars(select(PlanEntry).where(
            PlanEntry.org_id == m.org_id, PlanEntry.class_subject_id == cs_id))}

        violations: list[RescheduleViolation] = []
        touched: set[uuid.UUID] = set()
        spans: list[tuple[date, date, uuid.UUID, str]] = []

        for req in body.chapters:
            unit = units.get(req.unit_id)
            if unit is None:
                raise NotFoundError("Chapter")
            if req.end_date < req.start_date:
                raise ValidationError(
                    f"“{unit.title}” ends before it starts.")
            start = max(req.start_date, floor)
            end = req.end_date
            if start < floor or end > year.end_date:
                violations.append(RescheduleViolation(
                    unit_id=unit.id, code="outside_year",
                    message=(f"“{unit.title}” runs outside the academic year — "
                             f"clamped to it.")))
                end = min(end, year.end_date)
            if end < start:
                raise ValidationError(
                    f"“{unit.title}” has no days inside the academic year.")

            topics = sorted(unit.topics, key=lambda t: t.position)
            sized = [t for t in topics if t.est_periods is not None]
            unsized = len(topics) - len(sized)
            if unsized:
                violations.append(RescheduleViolation(
                    unit_id=unit.id, code="unsized",
                    message=(f"{unsized} topic{'' if unsized == 1 else 's'} in "
                             f"“{unit.title}” {'has' if unsized == 1 else 'have'} no "
                             f"period estimate, so {'it is' if unsized == 1 else 'they are'} "
                             f"not scheduled.")))
            if not sized:
                continue

            required = sum(t.est_periods for t in sized)
            capacity = self.planner._total_effective_periods(
                cs, year, blocked, partial, window=(start, end))
            if required > capacity + 0.01:
                violations.append(RescheduleViolation(
                    unit_id=unit.id, code="too_short",
                    message=(f"“{unit.title}” needs {required} periods and those dates "
                             f"hold about {capacity:g}. Saved as you asked — widen the "
                             f"range or trim the chapter.")))

            self._place(m, cs, year, unit, sized, entries, start, end, blocked, partial)
            touched.add(unit.id)
            spans.append((start, end, unit.id, unit.title))

        # Two chapters sharing days is legal — a school finishing one while
        # starting the next does it every term — but the weekly budget is then
        # split between them and neither range holds what it claims. Say so.
        spans.sort()
        for (_s1, e1, _u1, t1), (s2, _e2, u2, t2) in zip(spans, spans[1:], strict=False):
            if s2 <= e1:
                violations.append(RescheduleViolation(
                    unit_id=u2, code="overlaps",
                    message=(f"“{t1}” and “{t2}” share days ({s2:%d %b} – {e1:%d %b}), "
                             f"so they are competing for the same periods.")))

        self.db.flush()
        board = SyllabusBoardService(self.db).board(
            m, year.id, class_subject_id=cs_id)
        chapters = [ch for g in board.classes for s in g.subjects for ch in s.chapters
                    if ch.unit_id in touched]
        return RescheduleOut(fits=not any(v.code in ("too_short", "overlaps")
                                          for v in violations),
                             violations=violations, chapters=chapters)

    def _teaching_weeks(self, cs: ClassSubject, year: AcademicYear, start: date,
                        end: date, blocked: set, partial: dict) -> list[date]:
        """The weeks inside the range the school actually teaches in.

        A week the school is shut has no capacity, so placing a topic in it
        would schedule a chapter for a fortnight nobody is in the building.
        """
        out: list[date] = []
        cur = _monday(start)
        last = _monday(end)
        while cur <= last and len(out) < 400:
            if effective_periods(
                cs.periods_per_week or 1, cur, working_weekdays=year.working_weekdays,
                blocked=blocked, year_start=start, year_end=end, partial=partial,
                periods_per_day=year.periods_per_day,
            ) > 0:
                out.append(cur)
            cur = cur + timedelta(days=7)
        return out or [_monday(start)]

    def _place(self, m: CurrentMember, cs: ClassSubject, year: AcademicYear,
               unit: SyllabusUnit, sized: list[SyllabusTopic],
               entries: dict[uuid.UUID, PlanEntry], start: date, end: date,
               blocked: set, partial: dict) -> None:
        """Lay this chapter's topics ACROSS its own date range.

        Deliberately **not** the drafter's greedy `distribute`. Greedy fills
        from the front and stops as soon as the periods are used up, which is
        right when it is laying out a whole term against a calendar and wrong
        here: the teacher just dragged the chapter's end out by a fortnight to
        say *"this needs longer"*, and greedy quietly ignored her — the dates
        went in, the plan came back identical, and the control looked broken.

        So the range she drew IS the chapter's span: the first topic opens it,
        the last topic lands in its final teaching week, and the ones between
        are spread in proportion to the periods they were sized at. Whether the
        periods actually fit is a separate question, already answered by the
        `too_short` violation — a warning, not a silent re-layout.

        `baseline_week_start` is never written here: the promise is stamped at
        approval and this is not one.
        """
        weeks = self._teaching_weeks(cs, year, start, end, blocked, partial)
        total = sum(t.est_periods for t in sized)
        # The denominator is "everything before the last topic", so the last
        # topic's fraction is exactly 1 and it lands in the final week.
        span = max(1, total - (sized[-1].est_periods if sized else 0))
        cumulative = 0
        for topic in sized:
            if len(sized) == 1 or len(weeks) == 1:
                idx = 0
            else:
                idx = round(cumulative / span * (len(weeks) - 1))
            cumulative += topic.est_periods
            wk = weeks[min(max(idx, 0), len(weeks) - 1)]
            existing = entries.get(topic.id)
            if existing is not None:
                existing.week_start = wk
            else:
                fresh = PlanEntry(org_id=m.org_id, class_subject_id=cs.id,
                                  topic_id=topic.id, week_start=wk)
                self.db.add(fresh)
                entries[topic.id] = fresh
