"""The one batched read behind every "syllabus covered" figure (V1-6, `S-51`).

`core/coverage.py` owns the *arithmetic* — what a partly-taught topic is worth
and which denominator answers which question. This owns the *read*: given a set
of class-subjects, it joins syllabus × lesson logs × plan entries once and hands
back a row per class-subject that every surface renders its own way.

Four screens used to do this join themselves, and all four disagreed (see
`core/coverage.py`). They now call this:

    admin board          `insights/syllabus.py`   both bases, side by side
    teacher My subjects  `planner` endpoints      pace + what to teach next
    student report card  `growth.py`              per-topic drill-down
    parent progress      `parent_portal.py`       whole-syllabus only (`S-54`)

**Three queries, whatever the school's size.** `forecast_org` was batched in
DASH3 (PR-6) because a per-class loop cost ~80 round-trips for one card; this
must not put them back. There is no per-class-subject query anywhere here, and
adding one would be felt on every screen at once now that they share it.

**Pre-tracking chapters are excluded from the numerator AND the denominator.**
A school that adopts in November never had Term 1 in the system, and a
denominator that counts it makes them read as 60% behind on day one (plan §5).
This is pinned by `test_midyear.py` and is the single easiest thing to break
here: filtering the numerator alone would be *worse* than filtering neither.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.coverage import (
    PLANNED,
    PLANNED_TO_DATE,
    SYLLABUS,
    CoverageFigure,
    better_coverage,
    taught_weight,
)
from app.models import (
    AcademicYear,
    LessonLog,
    PlanEntry,
    SyllabusUnit,
    Term,
)


@dataclass
class CoverageRow:
    """One class-subject's position in its portion, in every basis at once.

    Deliberately holds counts rather than percentages: a caller picks the basis
    that answers its question and gets a `CoverageFigure` that carries the
    denominator with it. Nothing here decides what is *good* — that is pace,
    and pace lives in `PlannerService.forecast`.
    """

    class_subject_id: uuid.UUID
    total_topics: int = 0          # the whole portion, pre-tracking excluded
    planned_topics: int = 0        # topics the approved plan schedules
    due_topics: int = 0            # planned topics whose week has arrived
    unsized_topics: int = 0        # est_periods IS NULL — a state, never a zero

    taught_weighted: float = 0.0   # best log per topic, partial worth a half
    taught_due: float = 0.0        # the same, restricted to what was due
    taught_count: int = 0          # distinct topics with any log at all
    logged_periods: int = 0        # lesson logs written — the sample size

    # `S-46` — the reason a teacher opens the screen at all.
    next_topic_id: uuid.UUID | None = None
    next_topic_title: str | None = None
    next_chapter_title: str | None = None

    # `S-48` — what a parent can ask their child about at dinner.
    last_topic_title: str | None = None
    last_chapter_title: str | None = None
    last_taught_on: date | None = None

    chapters_total: int = 0
    chapters_done: int = 0

    def figure(self, basis: str = SYLLABUS) -> CoverageFigure:
        """The renderable figure for one question. `PLANNED_TO_DATE` is the only
        basis that can say *behind* rather than merely *not finished yet*."""
        if basis == PLANNED:
            return CoverageFigure(self.taught_weighted, self.planned_topics, PLANNED)
        if basis == PLANNED_TO_DATE:
            return CoverageFigure(self.taught_due, self.due_topics, PLANNED_TO_DATE)
        return CoverageFigure(self.taught_weighted, self.total_topics, SYLLABUS)

    @property
    def behind_topics(self) -> float:
        """Topics that were due by today and have not been taught.

        The one pace number a person can check by hand, which is why `S-45`
        replaces the composite score with it. Never negative: a teacher ahead of
        plan is not "minus three behind".
        """
        return round(max(0.0, self.due_topics - self.taught_due), 1)

    @property
    def has_evidence(self) -> bool:
        """Did anybody record anything? `S-42`: a subject with no lesson logs is
        **unknown**, not behind — it is never rated, ranked or reddened."""
        return self.logged_periods > 0


@dataclass
class _Topic:
    id: uuid.UUID
    title: str
    chapter: str
    est_periods: int | None
    order: tuple[int, int]
    planned: bool = False
    week_start: date | None = None
    best: str | None = None
    logs: int = 0
    last_on: date | None = None


@dataclass
class CoverageSnapshot:
    """Everything the three queries found, before anybody decided what to show.

    Holds the roll-up (`rows`) *and* the per-topic detail it was built from, so
    a caller wanting a different shape of the same data — `S-40`'s week-by-week
    series is the reason this exists — derives it in memory instead of going
    back to the database for facts already in hand.
    """

    rows: dict[uuid.UUID, CoverageRow] = field(default_factory=dict)
    topics: dict[uuid.UUID, list["_Topic"]] = field(default_factory=dict)

    def weekly(self) -> dict[uuid.UUID, list[tuple[date, float, int]]]:
        """Per class-subject: (week starting Monday, taught weight, topics the
        plan had scheduled by then) — the raw material for `S-40`.

        A topic is credited to the week it reached its best coverage, so a
        chapter taught across a fortnight lands once, at the end, rather than
        drifting the line upward twice.
        """
        out: dict[uuid.UUID, list[tuple[date, float, int]]] = {}
        for cs_id, topics in self.topics.items():
            points: list[tuple[date, float, int]] = []
            for t in topics:
                if t.best and t.last_on is not None:
                    points.append((_monday(t.last_on), taught_weight(t.best), 0))
                if t.week_start is not None:
                    points.append((_monday(t.week_start), 0.0, 1))
            out[cs_id] = points
        return out


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


@dataclass
class CoverageReader:
    """Batched syllabus × logs × plan reader. Construct once, call `rows`."""

    db: Session

    def rows(self, org_id: uuid.UUID, cs_ids, year: AcademicYear | None = None,
             *, today: date | None = None,
             term_id: uuid.UUID | None = None) -> dict[uuid.UUID, CoverageRow]:
        """One `CoverageRow` per class-subject, keyed by id."""
        return self.snapshot(org_id, cs_ids, year, today=today, term_id=term_id).rows

    def snapshot(self, org_id: uuid.UUID, cs_ids, year: AcademicYear | None = None,
                 *, today: date | None = None,
                 term_id: uuid.UUID | None = None) -> CoverageSnapshot:
        """The roll-up plus the detail behind it, in three queries.

        `year` supplies the tracking floor used to drop pre-adoption terms; pass
        None only when the caller has already scoped the class-subjects itself.
        `term_id` narrows the portion to one term's chapters — the checkpoint
        switcher's "Term" — and narrows the denominator with it, so the figure
        stays a percentage *of that term*.
        """
        cs_ids = list(cs_ids)
        if not cs_ids:
            return CoverageSnapshot()
        today = today or date.today()

        pre_tracking = self._pre_tracking_terms(org_id, year)
        topics_by_cs = self._topics(org_id, cs_ids, pre_tracking, term_id)
        self._apply_plan(org_id, cs_ids, topics_by_cs)
        logged = self._apply_logs(org_id, cs_ids, topics_by_cs)

        return CoverageSnapshot(
            rows={
                cs_id: self._assemble(cs_id, topics_by_cs.get(cs_id, []),
                                      logged.get(cs_id, 0), today)
                for cs_id in cs_ids
            },
            topics={cs_id: topics_by_cs.get(cs_id, []) for cs_id in cs_ids})

    # ── the three queries ────────────────────────────────────────────────────
    def _pre_tracking_terms(self, org_id: uuid.UUID,
                            year: AcademicYear | None) -> set[uuid.UUID]:
        """Terms that ended before this school started using TrackBit.

        Their chapters are before our time: out of every count, never a warning
        (plan §5). Mirrors `PlannerService._forecast_rows`, which is the other
        half of the same rule — the two must agree or the board's coverage and
        its pace would be denominated differently.
        """
        if year is None:
            return set()
        floor = max(year.start_date, year.tracking_start_date) \
            if year.tracking_start_date else year.start_date
        return {
            t_id for t_id, end in self.db.execute(
                select(Term.id, Term.end_date)
                .where(Term.org_id == org_id, Term.academic_year_id == year.id)).all()
            if end < floor
        }

    def _topics(self, org_id: uuid.UUID, cs_ids: list[uuid.UUID],
                pre_tracking: set[uuid.UUID],
                term_id: uuid.UUID | None) -> dict[uuid.UUID, list[_Topic]]:
        by_cs: dict[uuid.UUID, list[_Topic]] = defaultdict(list)
        for unit in self.db.scalars(
            select(SyllabusUnit)
            .where(SyllabusUnit.org_id == org_id,
                   SyllabusUnit.class_subject_id.in_(cs_ids))
            .options(selectinload(SyllabusUnit.topics))
            .order_by(SyllabusUnit.position)
        ):
            if unit.term_id in pre_tracking:
                continue
            if term_id is not None and unit.term_id != term_id:
                continue
            for topic in sorted(unit.topics, key=lambda t: t.position):
                by_cs[unit.class_subject_id].append(_Topic(
                    id=topic.id, title=topic.title, chapter=unit.title,
                    est_periods=topic.est_periods,
                    order=(unit.position, topic.position)))
        for topics in by_cs.values():
            topics.sort(key=lambda t: t.order)
        return by_cs

    def _apply_plan(self, org_id: uuid.UUID, cs_ids: list[uuid.UUID],
                    topics_by_cs: dict[uuid.UUID, list[_Topic]]) -> None:
        """`plan_entries` is UNIQUE on (class_subject, topic), so one row here is
        one planned topic — no dedupe needed."""
        weeks = {
            topic_id: week for topic_id, week in self.db.execute(
                select(PlanEntry.topic_id, PlanEntry.week_start)
                .where(PlanEntry.org_id == org_id,
                       PlanEntry.class_subject_id.in_(cs_ids))).all()
        }
        for topics in topics_by_cs.values():
            for t in topics:
                week = weeks.get(t.id)
                if week is not None:
                    t.planned = True
                    t.week_start = week

    def _apply_logs(self, org_id: uuid.UUID, cs_ids: list[uuid.UUID],
                    topics_by_cs: dict[uuid.UUID, list[_Topic]]) -> dict[uuid.UUID, int]:
        """Best log wins per topic (`better_coverage`) — a topic taught across two
        periods is taught once, at its best state, not 1.5 times."""
        by_topic: dict[uuid.UUID, _Topic] = {
            t.id: t for topics in topics_by_cs.values() for t in topics}
        for topic_id, coverage, on in self.db.execute(
            select(LessonLog.topic_id, LessonLog.coverage, LessonLog.date)
            .where(LessonLog.org_id == org_id,
                   LessonLog.class_subject_id.in_(cs_ids),
                   LessonLog.topic_id.is_not(None))
            .order_by(LessonLog.date)
        ).all():
            t = by_topic.get(topic_id)
            if t is None:          # a log against a pre-tracking or other-term chapter
                continue
            t.best = better_coverage(t.best, coverage)
            t.logs += 1
            t.last_on = on if t.last_on is None or on >= t.last_on else t.last_on

        # The sample size counts EVERY log, including ones against chapters this
        # scope filtered out — "did this teacher record anything" is a question
        # about the teacher, not about the term being looked at.
        return {
            cs_id: int(n) for cs_id, n in self.db.execute(
                select(LessonLog.class_subject_id, func.count(LessonLog.id))
                .where(LessonLog.org_id == org_id,
                       LessonLog.class_subject_id.in_(cs_ids))
                .group_by(LessonLog.class_subject_id)).all()
        }

    # ── assembly ─────────────────────────────────────────────────────────────
    def _assemble(self, cs_id: uuid.UUID, topics: list[_Topic],
                  logged_periods: int, today: date) -> CoverageRow:
        row = CoverageRow(class_subject_id=cs_id, logged_periods=logged_periods)
        chapters: dict[str, list[_Topic]] = defaultdict(list)

        for t in topics:
            row.total_topics += 1
            chapters[t.chapter].append(t)
            if t.est_periods is None:
                row.unsized_topics += 1
            weight = taught_weight(t.best) if t.best else 0.0
            row.taught_weighted += weight
            if t.best:
                row.taught_count += 1
                if row.last_taught_on is None or (
                        t.last_on is not None and t.last_on >= row.last_taught_on):
                    row.last_taught_on = t.last_on
                    row.last_topic_title = t.title
                    row.last_chapter_title = t.chapter
            if t.planned:
                row.planned_topics += 1
                if t.week_start is not None and t.week_start <= today:
                    row.due_topics += 1
                    row.taught_due += weight
            # What to teach next: the first topic in syllabus order that is not
            # finished. `partial` still counts as next — she is mid-way through
            # it, and telling her to skip ahead would be wrong.
            if row.next_topic_id is None and t.best != "full":
                row.next_topic_id = t.id
                row.next_topic_title = t.title
                row.next_chapter_title = t.chapter

        row.taught_weighted = round(row.taught_weighted, 1)
        row.taught_due = round(row.taught_due, 1)
        row.chapters_total = len(chapters)
        row.chapters_done = sum(
            1 for group in chapters.values() if all(t.best == "full" for t in group))
        return row


def coverage_rows(db: Session, org_id: uuid.UUID, cs_ids,
                  year: AcademicYear | None = None, *, today: date | None = None,
                  term_id: uuid.UUID | None = None) -> dict[uuid.UUID, CoverageRow]:
    """Convenience wrapper — the form most callers want."""
    return CoverageReader(db).rows(org_id, cs_ids, year, today=today, term_id=term_id)
