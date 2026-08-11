"""The syllabus board (SY-1) — every chapter in the school, as one table.

**This service COMPOSES. It does not compute a single figure of its own.**

    coverage, plan dates, lesson logs   `services/coverage.py::CoverageReader`
    pace                                `PlannerService.forecast_org`
    the chapter's status word           `core/coverage.py::chapter_status`
    working days                        `services/calendar.py`

That is `S-51` applied for the seventh time in this module: *"syllabus covered"*
was computed in five places before V1-6 put it in one, and a board that walked
the syllabus itself to build a table would be the sixth. Every number here can be
traced to the roll-up the tab it links to already renders.

Scope is the only thing that differs between the admin's board and the
teacher's, and it is a **block, not a filter** (`D-15`): her rows are chosen by
`teacher_member_id`, so another teacher's subject is never loaded and then
dropped.

**Founder 2026-08-05: the homeroom is NOT in that set here.** It used to be —
`visible_class_ids`' subjects ∪ homeroom — which put every subject of her own
class on the board she opens to plan *her teaching*, mixed in with her own rows
and outnumbering them five to one. Her class's other subjects are somebody
else's plan; what she needs from them is a read of how her children are doing,
and that read now has its own door in **My Class → Syllabus**, which asks for
this same board with `whole_class=True` after checking she owns the homeroom.
One computation, two scopes, and each screen answers one question.

Query budget: six, for any number of classes.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.coverage import (
    CHAPTER_COMPLETED,
    CHAPTER_IN_PROGRESS,
    CHAPTER_NOT_SCHEDULED,
    CHAPTER_NOT_STARTED,
    PLANNED,
    chapter_status,
    coverage_pct,
    rated_status,
    shown_chapter_status,
    taught_weight,
)
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    Membership,
    SchoolClass,
    Subject,
    SyllabusUnit,
    Term,
    User,
)
from app.schemas.syllabus_board import (
    SyllabusBoardOut,
    SyllabusChapterRow,
    SyllabusClassGroup,
    SyllabusSubjectGroup,
    SyllabusTermOut,
    SyllabusTopicRow,
)
from app.services.calendar import (
    event_rows,
    expand_blocked_dates,
    is_teaching_day,
    teaching_days,
)
from app.services.coverage import CoverageReader, _Topic
from app.services.periods import visible_class_ids
from app.services.planner import PlannerService
from app.services.school_clock import today_in


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


def _norm(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalnum())


class SyllabusBoardService:
    def __init__(self, db: Session):
        self.db = db

    # ── scope ────────────────────────────────────────────────────────────────
    def _year(self, m: CurrentMember, year_id: uuid.UUID | None) -> AcademicYear | None:
        q = select(AcademicYear).where(AcademicYear.org_id == m.org_id)
        if year_id:
            return self.db.scalar(q.where(AcademicYear.id == year_id))
        # The column is `is_active`, and the first load arrives with no year_id
        # at all (the year context resolves a moment later), so this path is the
        # one a real browser hits first — not an edge case.
        return self.db.scalar(q.where(AcademicYear.is_active.is_(True))) or self.db.scalar(
            q.order_by(AcademicYear.start_date.desc()))

    def board(self, m: CurrentMember, year_id: uuid.UUID | None = None,
              *, class_id: uuid.UUID | None = None,
              class_subject_id: uuid.UUID | None = None,
              term_id: uuid.UUID | None = None,
              whole_class: bool = False) -> SyllabusBoardOut:
        """The whole board. `class_id`/`class_subject_id`/`term_id` narrow it;
        none of them widen it past what this member may see.

        `whole_class` is the ONE exception and it is deliberately not reachable
        from the HTTP route: it lifts the own-subjects filter for the class
        already named in `class_id`, and only `MyClassService` sets it, after
        `_klass` has established that this member is that homeroom's teacher.
        Putting the flag on the endpoint would let any teacher ask for any
        class's board by guessing an id.
        """
        today = today_in(m.org.timezone)
        year = self._year(m, year_id)
        allowed = visible_class_ids(self.db, m)
        scope = ("school" if allowed is None
                 else "class" if whole_class else "mine")
        if year is None:
            return SyllabusBoardOut(as_of=today, scope=scope,
                                    headline="No academic year is set up yet.")

        # ① classes × subjects × teacher, in one join.
        q = (select(ClassSubject, SchoolClass, Subject.name, User.name)
             .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
             .join(Subject, Subject.id == ClassSubject.subject_id)
             .outerjoin(Membership, Membership.id == ClassSubject.teacher_member_id)
             .outerjoin(User, User.id == Membership.user_id)
             .where(ClassSubject.org_id == m.org_id,
                    SchoolClass.academic_year_id == year.id)
             .order_by(SchoolClass.name, SchoolClass.section, Subject.name))
        if class_id is not None:
            q = q.where(SchoolClass.id == class_id)
        if class_subject_id is not None:
            q = q.where(ClassSubject.id == class_subject_id)
        rows = self.db.execute(q).all()
        if allowed is not None and not whole_class:
            # Her own subjects, and nothing else. The homeroom she owns is a
            # different question with its own screen (My Class → Syllabus).
            rows = [r for r in rows if r[0].teacher_member_id == m.membership.id]
        if not rows:
            return SyllabusBoardOut(
                academic_year_id=year.id, as_of=today, scope=scope,
                headline=("No classes in this year yet." if scope == "school"
                          else "This class has no subjects set up yet."
                          if scope == "class"
                          else "You are not assigned to any class-subject yet."))

        cs_ids = [cs.id for cs, _k, _s, _t in rows]

        # ② the terms of the year, and which of them predate adoption.
        terms = list(self.db.scalars(
            select(Term).where(Term.org_id == m.org_id,
                               Term.academic_year_id == year.id)
            .order_by(Term.start_date)))
        floor = year.tracking_start_date or year.start_date
        term_out = [SyllabusTermOut(id=t.id, name=t.name, start_date=t.start_date,
                                    end_date=t.end_date, pre_tracking=t.end_date < floor)
                    for t in terms]
        term_name = {t.id: t.name for t in terms}

        # ③④⑤ coverage: the syllabus × plan × logs join, batched. This is the one
        # place any of those three facts is read.
        snap = CoverageReader(self.db).snapshot(m.org_id, cs_ids, year, today=today,
                                                term_id=term_id)

        # ⑥ chapter metadata — the two columns the coverage reader has no reason
        # to carry, plus position and the chapters that hold no topics at all
        # (which the topic-keyed snapshot cannot see).
        units_q = (select(SyllabusUnit)
                   .where(SyllabusUnit.org_id == m.org_id,
                          SyllabusUnit.class_subject_id.in_(cs_ids))
                   .order_by(SyllabusUnit.position))
        if term_id is not None:
            units_q = units_q.where(SyllabusUnit.term_id == term_id)
        units_by_cs: dict[uuid.UUID, list[SyllabusUnit]] = defaultdict(list)
        for u in self.db.scalars(units_q):
            units_by_cs[u.class_subject_id].append(u)

        # The calendar, for turning a plan week into the dates a human reads: a
        # chapter starting "the week of the 6th" starts on the first day the
        # school is actually open that week, not on a Monday it is shut.
        blocked = self._blocked(m.org_id, year.id)
        working = set(year.working_weekdays or [0, 1, 2, 3, 4])

        # Pace comes from the forecast (`S-51`), never recomputed here — and
        # narrowed to the rows this board is actually showing, so a teacher
        # opening one subject does not pace the whole school to draw it.
        pace_by_cs = {f.class_subject_id: f
                      for f in PlannerService(self.db).forecast_org(
                          m, year.id, cs_ids=cs_ids)}

        by_class: dict[uuid.UUID, SyllabusClassGroup] = {}
        tally = {CHAPTER_COMPLETED: 0, CHAPTER_IN_PROGRESS: 0,
                 CHAPTER_NOT_STARTED: 0, CHAPTER_NOT_SCHEDULED: 0}
        overdue = 0

        for cs, klass, subject_name, teacher_name in rows:
            topics = snap.topics.get(cs.id, [])
            row = snap.rows.get(cs.id)
            chapters = self._chapters(cs, units_by_cs.get(cs.id, []), topics,
                                      term_name, working, blocked, today)
            for ch in chapters:
                tally[ch.status] = tally.get(ch.status, 0) + 1
                if ch.overdue:
                    overdue += 1

            fc = pace_by_cs.get(cs.id)
            group = by_class.setdefault(
                klass.id, SyllabusClassGroup(class_id=klass.id,
                                             label=_label(klass.name, klass.section)))
            group.subjects.append(SyllabusSubjectGroup(
                class_subject_id=cs.id, class_id=klass.id,
                class_label=_label(klass.name, klass.section),
                subject_id=cs.subject_id, subject_name=subject_name,
                teacher_name=teacher_name, periods_per_week=cs.periods_per_week or 0,
                plan_status=self._plan_status(fc),
                pace=rated_status(fc.status, (row.has_evidence if row else False))
                if fc else "unknown",
                coverage_pct=(row.figure(PLANNED).pct if row else None),
                chapters=chapters))

        classes = list(by_class.values())
        total = sum(tally.values())
        return SyllabusBoardOut(
            academic_year_id=year.id, as_of=today, scope=scope,
            headline=self._headline(total, tally, overdue, scope),
            terms=term_out, classes=classes,
            chapters_total=total,
            completed=tally[CHAPTER_COMPLETED], in_progress=tally[CHAPTER_IN_PROGRESS],
            not_started=tally[CHAPTER_NOT_STARTED],
            not_scheduled=tally[CHAPTER_NOT_SCHEDULED], overdue=overdue)

    @staticmethod
    def _plan_status(fc) -> str:
        if fc is None:
            return "none"
        if fc.status in ("none", "unplanned"):
            return "none"
        return "planned"

    @staticmethod
    def _headline(total: int, tally: dict, overdue: int, scope: str) -> str:
        """Lead with a sentence, not a number (ux rule 3).

        `overdue` leads when there is any, because it is the only figure on the
        board somebody has to *do* something about. A board with nothing overdue
        says what has been finished — never "0 overdue", which reads as a
        warning that failed to fire.
        """
        who = ("Your subjects" if scope == "mine"
               else "This class" if scope == "class" else "The school")
        if not total:
            return "No chapters recorded yet — import a syllabus to fill this in."
        done = tally[CHAPTER_COMPLETED]
        if overdue:
            return (f"{overdue} chapter{'' if overdue == 1 else 's'} planned to finish by "
                    f"now {'has' if overdue == 1 else 'have'} not — "
                    f"{done} of {total} finished overall.")
        unscheduled = tally[CHAPTER_NOT_SCHEDULED]
        if unscheduled and done == 0:
            return (f"{who.lower()} has {total} chapters recorded and {unscheduled} "
                    f"not scheduled yet — nothing is behind, nothing is planned.")
        tail = (f" · {unscheduled} not scheduled yet" if unscheduled else "")
        return f"{done} of {total} chapters finished, nothing overdue{tail}."

    # ── one class-subject's chapters ─────────────────────────────────────────
    def _chapters(self, cs: ClassSubject, units: list[SyllabusUnit],
                  topics: list[_Topic], term_name: dict, working: set[int],
                  blocked: set[date], today: date) -> list[SyllabusChapterRow]:
        by_unit: dict[uuid.UUID, list[_Topic]] = defaultdict(list)
        for t in topics:
            if t.unit_id is not None:
                by_unit[t.unit_id].append(t)

        out: list[SyllabusChapterRow] = []
        for u in units:
            group = sorted(by_unit.get(u.id, []), key=lambda t: t.order)
            out.append(self._chapter(cs, u, group, term_name, working, blocked, today))
        return out

    def _chapter(self, cs: ClassSubject, u: SyllabusUnit, group: list[_Topic],
                 term_name: dict, working: set[int], blocked: set[date],
                 today: date) -> SyllabusChapterRow:
        sized = [t.est_periods for t in group if t.est_periods is not None]
        full = sum(1 for t in group if t.best == "full")
        partial = sum(1 for t in group if t.best == "partial")
        planned_weeks = [t.week_start for t in group if t.week_start is not None]
        baseline_weeks = [t.baseline_week_start for t in group
                          if t.baseline_week_start is not None]
        taught_on = [t.last_on for t in group if t.last_on is not None]
        started_on = [t.first_on for t in group if t.first_on is not None]

        planned_start = (self._first_working(min(planned_weeks), working, blocked)
                         if planned_weeks else None)
        planned_end = (self._last_working(max(planned_weeks), working, blocked)
                       if planned_weeks else None)
        baseline_start = (self._first_working(min(baseline_weeks), working, blocked)
                          if baseline_weeks else None)
        baseline_end = (self._last_working(max(baseline_weeks), working, blocked)
                        if baseline_weeks else None)
        actual_end = max(taught_on) if taught_on else None

        derived = chapter_status(topics=len(group), taught_full=full,
                                 taught_partial=partial, planned=len(planned_weeks),
                                 excluded=u.not_planned)
        # SY-2 — the shown word. The rule lives in `core/coverage.py` so this
        # board and the exam map cannot answer it differently; the derived word
        # travels beside it either way.
        status = shown_chapter_status(u.manual_status, u.not_planned, derived)
        weighted = sum(taught_weight(t.best) for t in group if t.best)

        # Overdue = the plan said it would be finished by now and it is not.
        # Never true without a planned end: an unscheduled chapter has not been
        # missed, and reddening it would put every school that plans term by term
        # permanently in the wrong (rule 2 / V2-P11).
        #
        # `not_scheduled` is excluded explicitly rather than left to follow from
        # "no planned end". That used to be equivalent — the only ways to be
        # not_scheduled were to have no topics or no plan, and both leave
        # `planned_end` None. A chapter the school marks `not_planned` breaks
        # that: it can carry plan entries from before the decision, so it had a
        # planned end in the past and rendered **Overdue** while reading "Not
        # planned". The rule is the state, not the absence of a date.
        overdue = bool(planned_end and planned_end < today
                       and status not in (CHAPTER_COMPLETED, CHAPTER_NOT_SCHEDULED))
        # Drift compares two OBSERVED dates — when it was actually last taught
        # against when the plan said it would finish. A typed "completed" has no
        # actual_end behind it, so `status` here is deliberately the shown word
        # (a teacher who marked it done and logged nothing simply gets no
        # drift), and the figure can never be computed from a claim alone.
        drift = ((actual_end - planned_end).days
                 if actual_end and planned_end and status == CHAPTER_COMPLETED else None)

        return SyllabusChapterRow(
            unit_id=u.id, class_subject_id=cs.id, title=u.title, position=u.position,
            term_id=u.term_id, term_name=term_name.get(u.term_id) if u.term_id else None,
            difficulty=u.difficulty, remarks=u.remarks, not_planned=u.not_planned,
            # None, not 0: a chapter with nothing sized has no estimate at all.
            est_periods=sum(sized) if sized else None,
            topics_total=len(group),
            unsized_topics=sum(1 for t in group if t.est_periods is None),
            has_topic_detail=self._has_topic_detail(u.title, group),
            planned_start=planned_start, planned_end=planned_end,
            baseline_start=baseline_start, baseline_end=baseline_end,
            actual_start=min(started_on) if started_on else None,
            actual_end=actual_end,
            status=status, derived_status=derived, manual_status=u.manual_status,
            completion_pct=coverage_pct(weighted, len(group)),
            expected_pct=self._expected_pct(planned_start, planned_end, today,
                                            working, blocked),
            taught_full=full, taught_partial=partial,
            overdue=overdue, finish_drift_days=drift,
            topics=[self._topic_row(t, working, blocked) for t in group])

    @staticmethod
    def _expected_pct(start: date | None, end: date | None, today: date,
                      working: set[int], blocked: set[date]) -> float | None:
        """How much of this chapter's own window has gone by, in TEACHING days.

        Teaching days rather than calendar days, so a chapter straddling a
        fortnight of holidays is not reported as half-elapsed when the school
        was shut for most of it — the same denominator the plan was built on.
        """
        if start is None or end is None:
            return None
        total = teaching_days(start, end, working, blocked)
        if not total:
            return None
        if today < start:
            return 0.0
        gone = teaching_days(start, min(today, end), working, blocked)
        return round(min(100.0, gone / total * 100), 1)

    @staticmethod
    def _has_topic_detail(chapter_title: str, group: list[_Topic]) -> bool:
        """Does this chapter expand?

        Two topics or more, always. Exactly one topic only when its title says
        something the chapter's does not — which is how a chapter-only school's
        row (one topic mirroring its chapter) stays a single line, without the
        importer having to record which kind of school it is.
        """
        if len(group) > 1:
            return True
        if len(group) == 1:
            return _norm(group[0].title) != _norm(chapter_title)
        return False

    def _topic_row(self, t: _Topic, working: set[int],
                   blocked: set[date]) -> SyllabusTopicRow:
        status = chapter_status(
            topics=1, taught_full=1 if t.best == "full" else 0,
            taught_partial=1 if t.best == "partial" else 0,
            planned=1 if t.week_start else 0)
        return SyllabusTopicRow(
            id=t.id, title=t.title, position=t.order[1], est_periods=t.est_periods,
            status=status, coverage=t.best,
            planned_start=(self._first_working(t.week_start, working, blocked)
                           if t.week_start else None),
            planned_end=(self._last_working(t.week_start, working, blocked)
                         if t.week_start else None),
            actual_start=t.first_on, actual_end=t.last_on, logs=t.logs)

    # ── a plan week is a Monday; a person reads dates ────────────────────────
    def _blocked(self, org_id: uuid.UUID, year_id: uuid.UUID) -> set[date]:
        return expand_blocked_dates(event_rows(self.db.scalars(
            select(CalendarEvent).where(CalendarEvent.org_id == org_id,
                                        CalendarEvent.academic_year_id == year_id))))

    @staticmethod
    def _first_working(week_start: date, working: set[int], blocked: set[date]) -> date:
        for i in range(7):
            d = week_start + timedelta(days=i)
            if is_teaching_day(d, working, blocked):
                return d
        return week_start

    @staticmethod
    def _last_working(week_start: date, working: set[int], blocked: set[date]) -> date:
        for i in range(6, -1, -1):
            d = week_start + timedelta(days=i)
            if is_teaching_day(d, working, blocked):
                return d
        return week_start + timedelta(days=6)

    # ── the chapter's own two columns ────────────────────────────────────────
    def patch_chapter(self, m: CurrentMember, unit_id: uuid.UUID,
                      body) -> SyllabusUnit:
        """Title, difficulty, remarks, term, scope, status and periods.

        The chapter's whole editable row (SY-2) — everything the grid's cells
        write goes through here, so there is one place that decides who may
        change a chapter and one place that validates the words.

        Written in place: law 3's append-only is for decisions about a PERSON,
        and a chapter's remark, difficulty or period count is corrected, not
        superseded.

        Who: an admin anywhere, or the subject's own teacher (or the class
        teacher of its homeroom). A chapter remark that only an admin may write
        is a remark nobody writes."""
        u = self.db.scalar(select(SyllabusUnit).where(
            SyllabusUnit.id == unit_id, SyllabusUnit.org_id == m.org_id))
        if u is None:
            raise NotFoundError("Chapter")
        self._assert_can_edit(m, u.class_subject_id)

        if body.title is not None:
            u.title = body.title.strip()
        if body.difficulty is not None:
            if body.difficulty == "unset":
                u.difficulty = None
            elif body.difficulty in ("easy", "moderate", "hard"):
                u.difficulty = body.difficulty
            else:
                raise ValidationError(
                    "Difficulty must be easy, moderate or hard.")
        if body.remarks is not None:
            # "" clears it: an emptied box is the teacher deleting a remark, and
            # keeping the old text would make the field impossible to retract.
            u.remarks = body.remarks.strip() or None
        if body.not_planned is not None:
            # In scope or not — the one stored word on a board of derived ones.
            # Corrected in place like difficulty and remarks beside it: law 3's
            # append-only is for decisions about a PERSON, and this is a
            # decision about a chapter, reversed by ticking the box back.
            u.not_planned = body.not_planned
        if body.status is not None:
            # SY-2. "unset" hands the row back to the lesson logs — the same
            # escape `difficulty` has, and the reason this can be an override
            # rather than a replacement: a school that never touches the cell is
            # on exactly the behaviour it had before.
            if body.status == "unset":
                u.manual_status = None
            elif body.status in (CHAPTER_NOT_STARTED, CHAPTER_IN_PROGRESS,
                                 CHAPTER_COMPLETED):
                u.manual_status = body.status
            else:
                raise ValidationError(
                    "Status must be not started, in progress or completed.",
                    code="bad_status")
        if body.clear_est_periods or body.est_periods is not None:
            self._set_chapter_periods(
                u, None if body.clear_est_periods else body.est_periods)
        if body.clear_term:
            u.term_id = None
        elif body.term_id is not None:
            term = self.db.scalar(select(Term).where(
                Term.id == body.term_id, Term.org_id == m.org_id))
            if term is None:
                raise NotFoundError("Term")
            u.term_id = term.id
        self.db.flush()
        return u

    def _set_chapter_periods(self, u: SyllabusUnit, periods: int | None) -> None:
        """Size a chapter from its own row.

        Only for the chapter-only shape — one chapter, one topic — which is what
        every importer produces and what the grid draws as a single line. There
        the chapter's estimate IS its topic's, and making the row editable saves
        opening a drawer to type one number.

        A chapter genuinely split into topics is refused rather than guessed at:
        spreading 8 periods over three topics means choosing 3/3/2 or 2/3/3, and
        a service inventing that would put an estimate nobody made into the
        forecast. Those are sized topic by topic, where the person doing it can
        see what she is dividing.
        """
        topics = sorted(u.topics, key=lambda t: (t.position, t.title))
        if len(topics) != 1:
            raise ValidationError(
                f"“{u.title}” has {len(topics)} topics, so its periods are set "
                "on the topics themselves — open the chapter to size them."
                if topics else
                f"“{u.title}” has no topics yet, so there is nothing to size.",
                code="chapter_not_single_topic")
        topics[0].est_periods = periods

    def _assert_can_edit(self, m: CurrentMember, cs_id: uuid.UUID) -> None:
        if m.is_coordinator_up:
            return
        cs = self.db.scalar(select(ClassSubject).where(
            ClassSubject.id == cs_id, ClassSubject.org_id == m.org_id))
        if cs is None:
            raise NotFoundError("Class subject")
        if cs.teacher_member_id == m.membership.id:
            return
        klass = self.db.get(SchoolClass, cs.class_id)
        if klass is not None and klass.class_teacher_member_id == m.membership.id:
            return
        raise ForbiddenError("This subject is not yours to edit.",
                             code="not_your_subject")
