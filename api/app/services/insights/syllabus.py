"""M2 — is the year's teaching where the plan said it would be (DASH3 §4.2,
reworked by V1-6).

Two axes, and the tab is laid out as a matrix of them.

**Checkpoint (vertical):** whole year · term · per exam. The exam checkpoint is
the one schools actually manage against — `PlannerService.exam_fit` already
computes, per exam, the syllabus each subject must newly cover against the
teaching periods in the gap. `S-50` promotes it from a tab nobody pressed to the
sentence the page opens with, which is why `exam_fit_org` had to be batched.

**Scope (horizontal):** school → class → subject → teacher. Note the shape: one
subject may have several teachers across classes, so **teacher is not a child of
subject** — it is a re-pivot of the same class-subject rows, and `S-43` adds a
fourth re-pivot of those same rows: sections of one grade against each other.

Three things this module refuses to do, all deliberate:

  * **It never renders a state as a colour.** `unplanned`, `unallocated`,
    `unestimated` and now `unknown` mean "nothing is scheduled", "no periods per
    week", "not sized yet" and "nobody recorded anything" — none of them is a
    pace, and V2-P11 exists because treating them as green made an unplanned
    year look healthy.
  * **It never calls a subject behind on no evidence** (`S-42`). The forecast
    can rate a class-subject whose teacher has never written a lesson log — its
    arithmetic is plan against calendar — but saying "3 weeks behind" to a human
    about a class nobody observed states as fact something we never saw. Those
    rows are `unknown`, are excluded from every RAG count and worst list, and
    carry the cause that actually applies: *nothing has been logged*.
  * **It never ranks a node with too little data, and never with a number
    nobody can reconstruct.** The sample guard is unchanged; `S-45` replaces the
    old `on_track_share × 60 + coverage × 40` composite — which could not be
    explained to the teacher it was about — with the sentence it rested on.

And the thing it now always does: **every behind row says why** (`S-41`). Lost
periods, nothing logged, chapters never sized, or genuinely slower. Those are
four different conversations, and only the last one is about teaching.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.coverage import (
    PLANNED,
    SYLLABUS,
    UNKNOWN,
    attribute_cause,
    rated_status,
)
from app.models import (
    AcademicYear,
    ClassPeriod,
    ClassSubject,
    Membership,
    SchoolClass,
    Subject,
    TaskInstance,
    Term,
    User,
)
from app.schemas.insights import (
    CauseTally,
    ExamCheckpoint,
    ExamCheckpointSubject,
    SectionCompare,
    SectionCompareRow,
    SyllabusBoard,
    SyllabusNode,
    SyllabusPulse,
    SyllabusRow,
    SyllabusTrendPoint,
    TermOption,
)
from app.services.coverage import CoverageReader
from app.services.planner import PlannerService
from app.services.school_clock import today_in

MIN_CLASS_SUBJECTS = 3
MIN_LOGGED_PERIODS = 10

# `S-41`'s four causes, in the order they must be read: the first two are not
# about teaching at all, and putting them first is the point of counting them.
# A school looking at "6 subjects behind" acts very differently once it can see
# that four of those six are behind because nobody wrote a lesson log.
CAUSE_META: list[tuple[str, str, str]] = [
    ("not_logged", "Nothing logged",
     "Taught or not, we cannot tell — no lesson was recorded. A capture gap, "
     "not a teaching one."),
    ("periods_lost", "Periods lost",
     "The classes did not run — an exam week, a function, a day out. Nobody's "
     "fault, and it needs a re-plan rather than a conversation."),
    ("never_sized", "Chapters not sized",
     "Chapters with no estimate are never scheduled, so the plan is short "
     "before anybody teaches anything."),
    ("slower", "Behind on teaching",
     "Everything was recorded, the periods ran, and the portion is still "
     "behind. This is the one that is about teaching."),
]


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


def _plural(n: float, word: str) -> str:
    return word if n == 1 else word + "s"


class SyllabusInsights:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_in(m.org.timezone)

    def _year(self, m: CurrentMember, year_id: uuid.UUID | None) -> AcademicYear | None:
        if year_id is not None:
            return self.db.scalar(select(AcademicYear).where(
                AcademicYear.id == year_id, AcademicYear.org_id == m.org_id))
        return self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))

    def board(self, m: CurrentMember, year_id: uuid.UUID | None = None,
              scope: str = "class", checkpoint: str = "year",
              term_id: uuid.UUID | None = None) -> SyllabusBoard:
        today = self._today(m)
        year = self._year(m, year_id)
        board = SyllabusBoard(
            scope=scope, checkpoint=checkpoint, as_of=today,
            academic_year_id=year.id if year else None, term_id=term_id,
            min_class_subjects=MIN_CLASS_SUBJECTS, min_logged_periods=MIN_LOGGED_PERIODS)
        if year is None:
            board.headline = "No academic year is set up yet."
            return board

        scoped_term = term_id if checkpoint == "term" else None
        rows, trend = self._rows(m, year, scoped_term, today)
        board.rows = rows
        board.trend = trend
        board.causes = self._causes(rows)
        board.terms = self._terms(m, year, today)
        board.year_end_date = year.end_date
        if term_id is not None:
            board.term_label = next(
                (t.name for t in board.terms if t.id == term_id), None)

        board.school = self._node("school", None, m.org.name, "whole school", rows,
                                  min_cs=1, min_logged=0)
        board.nodes = self._pivot(scope, rows)
        board.sections = self._sections(rows)

        # Ranked on a number, ordered by a sentence: `score` still sorts, but
        # `rank_reason` is what the screen shows, so nothing appears in a list
        # about a person that they could not reconstruct themselves (`S-45`).
        ranked = [n for n in board.nodes if n.rank_eligible and n.score is not None]
        ranked.sort(key=lambda n: n.score or 0, reverse=True)
        board.ahead = ranked[:3]
        board.needs_support = list(reversed(ranked[-3:])) if len(ranked) > 3 else []

        exams = self._exam_checkpoints(m, year, today)
        board.next_exam = next((e for e in exams if e.days_to_exam >= 0), None)
        if checkpoint == "exam":
            board.exams = exams
        board.headline = self._headline(board, today)
        return board

    # ── the row set (one batch, reused by every pivot) ───────────────────────
    def _rows(self, m: CurrentMember, year: AcademicYear, term_id: uuid.UUID | None,
              today: date) -> tuple[list[SyllabusRow], list[SyllabusTrendPoint]]:
        """Every class-subject in the year: its forecast, what was actually
        taught, why it is behind, and whether a catch-up has been asked for.

        `forecast_org` is one batched pass (PR-6) and `CoverageReader` is three
        more queries for any number of classes; the causes and the catch-up
        state are one grouped query each. **Nothing loops per class** — that was
        the defect PR-6 existed to remove and it would cost more now that four
        screens share this read.
        """
        forecasts = {f.class_subject_id: f
                     for f in PlannerService(self.db).forecast_org(m, year.id)}
        if not forecasts:
            return [], []
        cs_ids = list(forecasts)

        meta = self.db.execute(
            select(ClassSubject.id, ClassSubject.class_id, ClassSubject.subject_id,
                   SchoolClass.name, SchoolClass.section, Subject.name,
                   ClassSubject.teacher_member_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.id.in_(cs_ids))).all()
        teacher_ids = {t for *_rest, t in meta if t}
        teachers = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name).join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(teacher_ids))).all()
        } if teacher_ids else {}

        snap = CoverageReader(self.db).snapshot(
            m.org_id, cs_ids, year, today=today, term_id=term_id)
        not_held = self._not_held(m, cs_ids)
        catchups = self._catchups(m, cs_ids)

        out: list[SyllabusRow] = []
        for cs_id, class_id, subject_id, cname, section, sname, teacher_id in meta:
            f = forecasts[cs_id]
            cov = snap.rows.get(cs_id)
            # `S-42`: the pace is only shown where somebody recorded something.
            status = rated_status(f.status, bool(cov and cov.has_evidence))
            planned = cov.planned_topics if cov else f.planned_topics
            row = SyllabusRow(
                class_subject_id=cs_id, class_id=class_id, class_label=_label(cname, section),
                subject_id=subject_id, subject_name=sname,
                teacher_member_id=teacher_id, teacher_name=teachers.get(teacher_id),
                status=status, total_topics=cov.total_topics if cov else f.total_topics,
                planned_topics=planned,
                taught_topics=cov.taught_weighted if cov else 0.0,
                coverage_pct=cov.figure(PLANNED).pct if cov else None,
                syllabus_pct=cov.figure(SYLLABUS).pct if cov else None,
                syllabus_taught=cov.taught_weighted if cov else 0.0,
                due_topics=cov.due_topics if cov else 0,
                taught_due=cov.taught_due if cov else 0.0,
                behind_topics=cov.behind_topics if cov else 0.0,
                weeks_behind=f.weeks_behind or 0,
                baseline_finish=f.baseline_finish, projected_finish=f.projected_finish,
                unestimated_topics=f.unestimated_topics or 0,
                current_term_unplanned=bool(f.current_term_unplanned),
                logged_periods=f.logged_periods,
                periods_not_held=not_held.get(cs_id, 0),
                taught_full=cov.taught_full if cov else 0,
                taught_partial=cov.taught_partial if cov else 0,
                next_topic_title=cov.next_topic_title if cov else None,
                next_chapter_title=cov.next_chapter_title if cov else None)
            # The plan's marker. Divided here, once, so no screen ever divides
            # a coverage figure for itself (`S-51`).
            if row.planned_topics:
                row.expected_pct = round(row.due_topics / row.planned_topics * 100, 1)
            if row.total_topics:
                row.expected_syllabus_pct = round(
                    row.due_topics / row.total_topics * 100, 1)
            if f.projected_finish and f.baseline_finish:
                row.overrun_days = (f.projected_finish - f.baseline_finish).days
            row.overruns_year = bool(
                f.projected_finish and f.projected_finish > year.end_date)
            self._attribute(row)
            got = catchups.get(cs_id)
            if got is not None:
                row.catchup_task_id, row.catchup_requested_on, row.catchup_outcome = got
            out.append(row)
        out.sort(key=lambda r: (r.class_label, r.subject_name))
        return out, self._trend(snap, out, year, today)

    # ── S-41: why ────────────────────────────────────────────────────────────
    def _not_held(self, m: CurrentMember, cs_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Periods this class-subject was scheduled for and did not happen.

        `class_periods` only exists once a teacher touched the period, so this
        counts periods somebody explicitly called off — an exam week, a function,
        a day the class was out. It is deliberately not "scheduled minus held":
        a period nobody opened is *not captured*, which is a different finding
        and must never be laundered into "we lost it" (rule 2).
        """
        return {
            cs_id: int(n) for cs_id, n in self.db.execute(
                select(ClassPeriod.class_subject_id, func.count(ClassPeriod.id))
                .where(ClassPeriod.org_id == m.org_id,
                       ClassPeriod.class_subject_id.in_(cs_ids),
                       ClassPeriod.status == "not_held")
                .group_by(ClassPeriod.class_subject_id)).all()
        }

    def _attribute(self, row: SyllabusRow) -> None:
        """Give a struggling row its cause and the sentence that goes with it.

        The reasoning lives in `core.coverage.attribute_cause` because the class
        teacher's block asks the same question about the same subject, and two
        implementations of "why is this behind" would drift into two different
        answers about the same teacher on the same day.
        """
        row.cause, row.cause_detail = attribute_cause(
            status=row.status, behind_topics=row.behind_topics,
            weeks_behind=row.weeks_behind, unestimated_topics=row.unestimated_topics,
            planned_topics=row.planned_topics, periods_not_held=row.periods_not_held)

    # ── D-16 / S-60: has a catch-up been asked for? ──────────────────────────
    def _catchups(self, m: CurrentMember,
                  cs_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple]:
        """The newest catch-up request per class-subject, in one query.

        `S-60`: the row clears on the recorded **outcome**, not on the press —
        so a request whose task is still open keeps showing, and one whose task
        was completed carries what was decided. Reads `task_instances` directly
        because the task IS the request; a parallel store would be a second
        source of truth about the same meeting.
        """
        rows = self.db.execute(
            select(TaskInstance.subject_id, TaskInstance.id, TaskInstance.created_at,
                   TaskInstance.status, TaskInstance.outcome)
            .where(TaskInstance.org_id == m.org_id,
                   TaskInstance.subject_type == "class_subject",
                   TaskInstance.subject_id.in_(cs_ids))
            .order_by(TaskInstance.created_at.desc())).all()
        out: dict[uuid.UUID, tuple] = {}
        for cs_id, task_id, created, status, outcome in rows:
            if cs_id in out:
                continue           # ordered newest-first, so the first wins
            done = status != "open"
            out[cs_id] = (task_id, created.date() if created else None,
                          outcome if done else None)
        return out

    # ── S-40: coverage over time ─────────────────────────────────────────────
    def _trend(self, snap, rows: list[SyllabusRow], year: AcademicYear,
               today: date) -> list[SyllabusTrendPoint]:
        """Cumulative taught weight against the plan's cumulative baseline.

        Every other chart on this board is a snapshot, which cannot tell a
        subject that has been slipping for a month from one that had a bad week.
        Built entirely from the snapshot already in memory — no per-week query,
        which is the cost trap `forecast_org` was batched to avoid.
        """
        weekly = snap.weekly()
        in_scope = {r.class_subject_id for r in rows}
        by_week: dict[date, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for cs_id, points in weekly.items():
            if cs_id not in in_scope:
                continue
            for week, taught, planned in points:
                bucket = by_week[week]
                bucket[0] += taught
                bucket[1] += planned
        if not by_week:
            return []

        start = min(by_week)
        end = min(max(max(by_week), today), year.end_date)
        out: list[SyllabusTrendPoint] = []
        actual = baseline = 0.0
        cur = start
        guard = 0
        while cur <= end and guard < 80:
            taught, planned = by_week.get(cur, [0.0, 0.0])
            actual += taught
            baseline += planned
            out.append(SyllabusTrendPoint(
                week_start=cur, actual=round(actual, 1), baseline=int(baseline)))
            cur += timedelta(days=7)
            guard += 1
        return out

    # ── S-43: sections of one grade, against each other ──────────────────────
    def _sections(self, rows: list[SyllabusRow]) -> list[SectionCompare]:
        """6-A Maths against 6-B Maths — same syllabus, same weeks, same exam.

        A pure re-pivot of the rows already computed, so it costs nothing. Only
        grades that genuinely have more than one section teaching the subject
        appear: a comparison of one thing is not a comparison.
        """
        buckets: dict[tuple[str, str], list[SyllabusRow]] = defaultdict(list)
        for r in rows:
            # The label is "<class name>-<section>" and a class name may itself
            # contain a hyphen ("Grade-6"), so split from the RIGHT and only for
            # classes that actually have a section. A sectionless class has no
            # sibling to be compared against, which is the point of the block.
            if "-" not in r.class_label:
                continue
            grade = r.class_label.rsplit("-", 1)[0]
            buckets[(grade, r.subject_name)].append(r)

        out: list[SectionCompare] = []
        for (grade, subject), group in buckets.items():
            if len(group) < 2:
                continue
            pcts = [r.coverage_pct for r in group if r.coverage_pct is not None
                    and r.status != UNKNOWN]
            out.append(SectionCompare(
                grade=grade, subject_name=subject,
                spread_pct=round(max(pcts) - min(pcts), 1) if len(pcts) > 1 else None,
                rows=[SectionCompareRow(
                    class_subject_id=r.class_subject_id, class_label=r.class_label,
                    teacher_name=r.teacher_name, status=r.status,
                    coverage_pct=r.coverage_pct, taught_topics=r.taught_topics,
                    planned_topics=r.planned_topics, behind_topics=r.behind_topics)
                    for r in sorted(group, key=lambda x: x.class_label)]))
        # Widest spread first — that is the pair worth looking at.
        out.sort(key=lambda s: (-(s.spread_pct or 0), s.grade, s.subject_name))
        return out

    # ── pivots ───────────────────────────────────────────────────────────────
    def _pivot(self, scope: str, rows: list[SyllabusRow]) -> list[SyllabusNode]:
        if scope == "school":
            return []
        buckets: dict[tuple, list[SyllabusRow]] = defaultdict(list)
        for r in rows:
            if scope == "class":
                key = (str(r.class_id), r.class_id, r.class_label, None)
            elif scope == "subject":
                key = (str(r.subject_id), r.subject_id, r.subject_name, None)
            else:
                if r.teacher_member_id is None:
                    key = ("unassigned", None, "Unassigned", "no teacher on the class-subject")
                else:
                    key = (str(r.teacher_member_id), r.teacher_member_id,
                           r.teacher_name or "—", None)
            buckets[key].append(r)

        min_logged = MIN_LOGGED_PERIODS if scope == "teacher" else 0
        nodes = [
            self._node(key, node_id, label, sublabel, group,
                       min_cs=MIN_CLASS_SUBJECTS, min_logged=min_logged)
            for (key, node_id, label, sublabel), group in buckets.items()
        ]
        nodes.sort(key=lambda n: n.label)
        return nodes

    def _node(self, key: str, node_id, label: str, sublabel: str | None,
              rows: list[SyllabusRow], *, min_cs: int, min_logged: int) -> SyllabusNode:
        logged_periods = sum(r.logged_periods for r in rows)
        planned = sum(r.planned_topics for r in rows)
        total = sum(r.total_topics for r in rows)
        taught = round(sum(r.taught_topics for r in rows), 1)
        rated = [r for r in rows if r.status in ("green", "amber", "red")]
        node = SyllabusNode(
            key=key, id=node_id, label=label, sublabel=sublabel,
            class_subjects=len(rows),
            on_track=sum(1 for r in rows if r.status == "green"),
            slipping=sum(1 for r in rows if r.status == "amber"),
            behind=sum(1 for r in rows if r.status == "red"),
            unplanned=sum(1 for r in rows if r.status == "unplanned"),
            unallocated=sum(1 for r in rows if r.status in ("unallocated", "none")),
            unknown=sum(1 for r in rows if r.status == UNKNOWN),
            planned_topics=planned, taught_topics=taught, total_topics=total,
            coverage_pct=round(taught / planned * 100, 1) if planned else None,
            syllabus_pct=round(taught / total * 100, 1) if total else None,
            weeks_behind_max=max((r.weeks_behind for r in rated), default=0),
            unestimated_topics=sum(r.unestimated_topics for r in rows),
            logged_periods=logged_periods,
            due_topics=sum(r.due_topics for r in rows),
            taught_due=round(sum(r.taught_due for r in rows), 1),
            # RATED rows only (`S-42`). A class-subject nobody has logged a
            # lesson against has every due topic counted as untaught, so
            # including it here would report a school as "40 topics overdue" on
            # the strength of a record nobody wrote — and this figure orders the
            # worst-first lists, so it would put the unobserved rows on top and
            # describe them as the ones behind.
            behind_topics=round(sum(r.behind_topics for r in rated), 1),
            taught_full=sum(r.taught_full for r in rows),
            taught_partial=sum(r.taught_partial for r in rows),
            untaught_topics=max(0, total - sum(r.taught_full + r.taught_partial
                                               for r in rows)),
            periods_not_held=sum(r.periods_not_held for r in rows),
            classes=len({r.class_id for r in rows}),
            subjects=len({r.subject_id for r in rows if r.subject_id}))
        # The plan's marker, on the same denominator as `coverage_pct` so the
        # two can be drawn on one track: how much of the planned portion was
        # due by today, against how much of it has actually been taught.
        if planned:
            node.expected_pct = round(node.due_topics / planned * 100, 1)
        if total:
            node.expected_syllabus_pct = round(node.due_topics / total * 100, 1)
        node.tone, node.pace_caption = self._pace(node, rated)
        # The guard: below the minimum sample the node carries its numbers but is
        # never ranked, and the UI says "not enough data yet".
        node.rank_eligible = len(rated) >= min_cs and logged_periods >= min_logged
        if node.rank_eligible:
            on_track_share = len([r for r in rated if r.status == "green"]) / len(rated)
            coverage = (node.coverage_pct or 0) / 100
            node.score = round(on_track_share * 60 + min(coverage, 1.0) * 40, 1)
            # `S-45`: `score` orders the list; THIS is what the list shows.
            node.rank_reason = (
                f"{len([r for r in rated if r.status == 'green'])} of {len(rated)} "
                f"on track · {node.coverage_pct:g}% of the plan covered"
                if node.coverage_pct is not None else
                f"{len([r for r in rated if r.status == 'green'])} of {len(rated)} on track")
        return node

    @staticmethod
    def _pace(node: SyllabusNode, rated: list[SyllabusRow]) -> tuple[str, str | None]:
        """A node's tone AND the words that go with it, decided in one place.

        Three surfaces draw these nodes — the overview block, the scope ledger
        and the teacher matrix — so a tone each of them worked out for itself
        would be three verdicts about one teacher on one morning. And it never
        travels without the caption: a colour alone is not allowed to carry a
        verdict here any more than it is on the RAG chips.

        The states come first deliberately. A node where nothing has been logged
        is **neutral**, not green — "we have no evidence" and "it is going well"
        are opposite findings, and only one of them should be a quiet colour.
        """
        if not rated:
            if node.unknown:
                return "neutral", "nothing logged against the plan yet"
            if node.unplanned or node.unallocated:
                return "neutral", "nothing scheduled yet"
            return "neutral", "no syllabus set up"

        # Two different questions, and they can honestly disagree. The forecast
        # answers *will it finish* — plan against remaining calendar — so a
        # subject that has taught nothing in April is still green if the year
        # has room. `behind_topics` answers *is it on schedule today*, and it is
        # the one the marker draws.
        #
        # Painting a visible gap green would make the device lie, so overdue
        # topics take the tone to amber; saying "on track" beside "15 topics
        # overdue" would read as a contradiction, so the caption says which is
        # which. Neither figure is invented and neither overrides the other.
        off = node.behind + node.slipping
        overdue = node.behind_topics
        if node.behind:
            tone = "red"
        elif node.slipping or overdue > 0:
            tone = "amber"
        else:
            tone = "green"
        n = len(rated)
        caption = (f"all {n} on course to finish" if not off
                   else f"{off} of {n} behind the plan")
        if overdue > 0:
            caption += f" · {overdue:g} {_plural(overdue, 'topic')} overdue"
        if node.unknown:
            caption += f" · {node.unknown} not logged"
        return tone, caption

    # ── S-41, counted ────────────────────────────────────────────────────────
    def _causes(self, rows: list[SyllabusRow]) -> list[CauseTally]:
        """The four causes as a tally, in fixed order.

        Counted server-side and not in the browser for the boring reason that
        the same tally has to appear on the tab and in anything that reads this
        board later — but also because the ORDER is a judgement (capture and
        calendar before teaching) and a judgement belongs where it can be read
        and tested, not in a `.sort()` inside a component.

        Causes with nothing in them are still returned: *"nothing lost to
        cancelled periods"* is a finding, and a row that vanishes when it is
        zero makes the remaining ones look like the whole story.
        """
        counts: dict[str, list[float]] = {key: [0, 0.0] for key, *_ in CAUSE_META}
        for r in rows:
            if r.cause not in counts:
                continue
            counts[r.cause][0] += 1
            # The count is always safe — a row IS in this bucket. The topic
            # figure is not: `behind_topics` on an unlogged row is every due
            # topic, so `not_logged` would read *"1 class-subject · 10 topics
            # behind"* about a class nobody observed. `S-42`, exactly: the row
            # is counted, and the thing we cannot know stays unsaid.
            if r.status in ("green", "amber", "red"):
                counts[r.cause][1] += r.behind_topics
        return [
            CauseTally(key=key, label=label, detail=detail,
                       count=int(counts[key][0]),
                       behind_topics=round(counts[key][1], 1))
            for key, label, detail in CAUSE_META
        ]

    def _terms(self, m: CurrentMember, year: AcademicYear,
               today: date) -> list[TermOption]:
        """The year's terms, with the running one flagged against the SCHOOL's
        clock — `today` here is already `today_in(org.timezone)`, so a browser
        in another timezone cannot disagree about which term it is."""
        return [
            TermOption(id=t_id, name=name, start_date=start, end_date=end,
                       is_current=start <= today <= end)
            for t_id, name, start, end in self.db.execute(
                select(Term.id, Term.name, Term.start_date, Term.end_date)
                .where(Term.org_id == m.org_id, Term.academic_year_id == year.id)
                .order_by(Term.start_date)).all()
        ]

    # ── the overview's block ─────────────────────────────────────────────────
    def pulse(self, m: CurrentMember, year_id: uuid.UUID | None = None,
              term_id: uuid.UUID | None = None) -> SyllabusPulse:
        """One ring and two breakdowns, narrowable to a term.

        The same `_rows` batch and the same `_node` roll-up the tab uses, so the
        block on the overview and the board it links to cannot state different
        percentages for the same morning — which is the whole of `S-51`, applied
        between two of our own screens rather than between a parent's and a
        principal's.

        What it deliberately does NOT do is call `exam_fit_org` or build the
        trend: the overview needs neither, and the term switcher re-reads this
        on every press.
        """
        today = self._today(m)
        year = self._year(m, year_id)
        out = SyllabusPulse(as_of=today, term_id=term_id,
                            academic_year_id=year.id if year else None)
        if year is None:
            out.headline = "No academic year is set up yet."
            return out

        out.terms = self._terms(m, year, today)
        # A term id that is not this year's would silently narrow the portion to
        # nothing and read as a school that has taught none of its syllabus.
        if term_id is not None and not any(t.id == term_id for t in out.terms):
            term_id, out.term_id = None, None
        out.term_label = next((t.name for t in out.terms if t.id == term_id), None)

        rows, _ = self._rows(m, year, term_id, today)
        out.school = self._node("school", None, m.org.name, "whole school", rows,
                                min_cs=1, min_logged=0)
        # Worst first — the point of a capped list on a summary block is that the
        # rows nobody would otherwise scroll to are the ones shown.
        out.classes = sorted(self._pivot("class", rows),
                             key=lambda n: (-n.behind_topics, n.label))
        out.subjects = sorted(self._pivot("subject", rows),
                              key=lambda n: (-n.behind_topics, n.label))
        out.headline = self._pulse_headline(out, rows)
        return out

    @staticmethod
    def _pulse_headline(out: SyllabusPulse, rows: list[SyllabusRow]) -> str:
        """The block's own sentence, in the same words the tab uses.

        Scoped to whatever the switcher is on, because a term-scoped ring above
        a year-scoped sentence is the kind of quiet mismatch nobody reports and
        everybody mistrusts.
        """
        where = f"In {out.term_label}" if out.term_label else "Across the year"
        school = out.school
        if school is None or not rows:
            return "No class-subject has a syllabus yet."
        rated = school.on_track + school.slipping + school.behind
        if not rated:
            if school.unknown:
                return (f"{where.lower().capitalize()}, {school.unknown} class-"
                        f"{_plural(school.unknown, 'subject')} "
                        f"{'has' if school.unknown == 1 else 'have'} a plan and no "
                        f"lesson logs — there is nothing to rate yet.")
            return "No plan has been approved yet."
        pct = school.syllabus_pct
        covered = (
            "no topic has been logged as taught yet" if pct == 0
            else f"{pct:g}% of the portion is taught" if pct is not None
            else "no portion is sized yet")
        if school.behind:
            return (f"{where}, {covered} and {school.behind} of {rated} class-"
                    f"{_plural(rated, 'subject')} "
                    f"{'is' if school.behind == 1 else 'are'} behind the plan.")
        if school.slipping:
            return (f"{where}, {covered} — {school.slipping} class-"
                    f"{_plural(school.slipping, 'subject')} slipping, none a "
                    f"week or more behind.")
        # Nothing is behind on the *forecast*, but topics whose week has passed
        # are still untaught. Said plainly, because "everything is on track" over
        # a ring visibly short of its marker is the one sentence this block must
        # never print.
        if school.behind_topics > 0:
            n = school.behind_topics
            return (f"{where}, {covered} — {n:g} {_plural(n, 'topic')} due by "
                    f"today {'has' if n == 1 else 'have'} not been taught, "
                    f"though every subject still has room to finish.")
        return (f"{where}, {covered} and every rated class-subject is on course "
                f"to finish.")

    # ── the headline (S-50, rule 3) ──────────────────────────────────────────
    def _headline(self, board: SyllabusBoard, today: date) -> str:
        """Lead with the exam, because that is what a school manages against.

        Falls back through what is actually knowable: an exam, then pace, then
        the honest statement that nothing has been recorded — never a
        percentage standing on its own with nothing to compare it to.
        """
        ex = board.next_exam
        if ex is not None and ex.short:
            return (f"{ex.title} in {ex.days_to_exam} days · {ex.short} "
                    f"{_plural(ex.short, 'subject')} short of portion.")
        rows = board.rows
        if not rows:
            return "No class-subject has a syllabus yet."
        behind = [r for r in rows if r.status == "red"]
        slipping = [r for r in rows if r.status == "amber"]
        unknown = [r for r in rows if r.status == UNKNOWN]
        rated = len(behind) + len(slipping) + len([r for r in rows if r.status == "green"])

        if behind:
            worst = max(behind, key=lambda r: r.weeks_behind)
            return (f"{len(behind)} of {rated} class-{_plural(rated, 'subject')} "
                    f"{'is' if len(behind) == 1 else 'are'} a week or more behind — "
                    f"worst is {worst.class_label} {worst.subject_name}.")
        if ex is not None:
            return (f"{ex.title} in {ex.days_to_exam} days · "
                    f"every subject is on course for its portion.")
        if not rated and unknown:
            return (f"{len(unknown)} class-{_plural(len(unknown), 'subject')} "
                    f"{'has' if len(unknown) == 1 else 'have'} a plan but no lesson logs yet.")
        if not rated:
            return "No plan has been approved yet."
        return f"Every rated class-subject is on track ({rated} of {len(rows)})."

    # ── the exam checkpoint, school-wide ─────────────────────────────────────
    def _exam_checkpoints(self, m: CurrentMember, year: AcademicYear,
                          today: date) -> list[ExamCheckpoint]:
        """`exam_fit_org` walks every class in the year in one batched pass and
        this merges the result by exam. It used to be a per-class loop, which
        was tolerable only because it ran on one tab; `S-50` puts the nearest
        exam in the headline on every load, so it had to stop being one."""
        classes = {
            cid: _label(name, section) for cid, name, section in self.db.execute(
                select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
                .where(SchoolClass.org_id == m.org_id,
                       SchoolClass.academic_year_id == year.id)).all()
        }
        merged: dict[uuid.UUID, ExamCheckpoint] = {}
        for fit in PlannerService(self.db).exam_fit_org(m, year.id):
            label = classes.get(fit.class_id, "—")
            for ex in fit.exams:
                node = merged.get(ex.exam_event_id)
                if node is None:
                    node = ExamCheckpoint(
                        exam_event_id=ex.exam_event_id, title=ex.title,
                        start_date=ex.start_date, end_date=ex.end_date,
                        days_to_exam=ex.days_to_exam,
                        teaching_days_in_gap=ex.teaching_days_in_gap)
                    merged[ex.exam_event_id] = node
                for s in ex.subjects:
                    if s.verdict == "short":
                        node.short += 1
                    elif s.verdict == "tight":
                        node.tight += 1
                    elif s.verdict in ("fits", "surplus"):
                        node.ok += 1
                    node.subjects.append(ExamCheckpointSubject(
                        class_subject_id=s.class_subject_id, class_label=label,
                        subject_name=s.subject_name, verdict=s.verdict,
                        required_periods=s.required_periods,
                        capacity_periods=s.capacity_periods,
                        unsized_topics=s.unsized_topics))
        out = sorted(merged.values(), key=lambda e: e.start_date)
        for node in out:
            # Worst first inside an exam — the short ones are the whole point.
            order = {"short": 0, "tight": 1, "unallocated": 2, "no_portion": 3,
                     "fits": 4, "surplus": 5}
            node.subjects.sort(key=lambda s: (order.get(s.verdict, 9), s.class_label,
                                              s.subject_name))
        return out
