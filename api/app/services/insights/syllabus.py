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
    ExamCheckpoint,
    ExamCheckpointSubject,
    SectionCompare,
    SectionCompareRow,
    SyllabusBoard,
    SyllabusNode,
    SyllabusRow,
    SyllabusTrendPoint,
)
from app.services.coverage import CoverageReader
from app.services.planner import PlannerService
from app.services.school_clock import today_in

MIN_CLASS_SUBJECTS = 3
MIN_LOGGED_PERIODS = 10

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
        if term_id is not None:
            board.term_label = self.db.scalar(
                select(Term.name).where(Term.id == term_id, Term.org_id == m.org_id))

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
                next_topic_title=cov.next_topic_title if cov else None,
                next_chapter_title=cov.next_chapter_title if cov else None)
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
            logged_periods=logged_periods)
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
