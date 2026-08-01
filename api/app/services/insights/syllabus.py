"""M2 — is the year's teaching where the plan said it would be (DASH3 §4.2).

Two axes, and the tab is laid out as a matrix of them.

**Checkpoint (vertical):** whole year · term · per exam. The exam checkpoint is
the one schools actually manage against — `PlannerService.exam_fit` already
computes, per exam, the syllabus each subject must newly cover against the
teaching periods in the gap. This surfaces it school-wide instead of per class.

**Scope (horizontal):** school → class → subject → teacher. Note the shape: one
subject may have several teachers across classes, so **teacher is not a child of
subject** — it is a re-pivot of the same class-subject rows. The UI is a scope
switcher, not a nested tree, and this service returns whichever pivot was asked
for over one identical row set.

Two things this module refuses to do, both deliberate:

  * **It never renders a state as a colour.** `unplanned`, `unallocated` and
    `unestimated` mean "nothing is scheduled", "no periods per week" and "not
    sized yet" — none of them is a pace, and V2-P11 exists because treating them
    as green made an unplanned year look healthy.
  * **It never ranks a node with too little data.** A class needs ≥3 planned
    class-subjects and a teacher ≥3 plus ≥10 logged periods, or the node reads
    "not enough data yet". A pace number carries timetable disruption and class
    composition at least as much as teaching, so the framing is *needs support /
    ahead of plan*, with the underlying numbers always beside it — never a league
    table of people.
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.coverage import taught_weight
from app.models import (
    AcademicYear,
    ClassSubject,
    LessonLog,
    Membership,
    PlanEntry,
    SchoolClass,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    Term,
    User,
)
from app.schemas.insights import (
    ExamCheckpoint,
    ExamCheckpointSubject,
    SyllabusBoard,
    SyllabusNode,
    SyllabusRow,
)
from app.services.planner import PlannerService
from app.services.school_clock import today_in

MIN_CLASS_SUBJECTS = 3
MIN_LOGGED_PERIODS = 10


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


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
            return board

        rows = self._rows(m, year, term_id if checkpoint == "term" else None)
        board.rows = rows
        if term_id is not None:
            board.term_label = self.db.scalar(
                select(Term.name).where(Term.id == term_id, Term.org_id == m.org_id))

        board.school = self._node("school", None, m.org.name, "whole school", rows,
                                  min_cs=1, min_logged=0)
        board.nodes = self._pivot(scope, rows)
        ranked = [n for n in board.nodes if n.rank_eligible and n.score is not None]
        ranked.sort(key=lambda n: n.score or 0, reverse=True)
        board.ahead = ranked[:3]
        board.needs_support = list(reversed(ranked[-3:])) if len(ranked) > 3 else []

        if checkpoint == "exam":
            board.exams = self._exam_checkpoints(m, year)
        return board

    # ── the row set (one batch, reused by every pivot) ───────────────────────
    def _rows(self, m: CurrentMember, year: AcademicYear,
              term_id: uuid.UUID | None) -> list[SyllabusRow]:
        """Every class-subject in the year: its forecast, plus what was actually
        taught. `forecast_org` is one batched pass (PR-6); the taught counts are
        two more grouped queries. Nothing loops per class."""
        forecasts = {f.class_subject_id: f
                     for f in PlannerService(self.db).forecast_org(m, year.id)}
        if not forecasts:
            return []

        meta = self.db.execute(
            select(ClassSubject.id, ClassSubject.class_id, ClassSubject.subject_id,
                   SchoolClass.name, SchoolClass.section, Subject.name,
                   ClassSubject.teacher_member_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.id.in_(forecasts.keys()))).all()
        teacher_ids = {t for *_rest, t in meta if t}
        teachers = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name).join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(teacher_ids))).all()
        } if teacher_ids else {}

        # Topics actually taught: distinct topics with a lesson log, weighted by
        # coverage. Restricted to the term's chapters when a term is in scope.
        term_topics: set[uuid.UUID] | None = None
        if term_id is not None:
            term_topics = set(self.db.scalars(
                select(SyllabusTopic.id)
                .join(SyllabusUnit, SyllabusUnit.id == SyllabusTopic.unit_id)
                .where(SyllabusUnit.org_id == m.org_id, SyllabusUnit.term_id == term_id)))

        taught: dict[uuid.UUID, float] = defaultdict(float)
        best: dict[tuple[uuid.UUID, uuid.UUID], str] = {}
        for cs_id, topic_id, coverage in self.db.execute(
            select(LessonLog.class_subject_id, LessonLog.topic_id, LessonLog.coverage)
            .where(LessonLog.org_id == m.org_id,
                   LessonLog.class_subject_id.in_(forecasts.keys()),
                   LessonLog.topic_id.is_not(None))).all():
            if term_topics is not None and topic_id not in term_topics:
                continue
            key = (cs_id, topic_id)
            if best.get(key) != "full":
                best[key] = coverage
        for (cs_id, _topic_id), coverage in best.items():
            taught[cs_id] += taught_weight(coverage)

        logged = {
            cs_id: int(n) for cs_id, n in self.db.execute(
                select(LessonLog.class_subject_id, func.count(LessonLog.id))
                .where(LessonLog.org_id == m.org_id,
                       LessonLog.class_subject_id.in_(forecasts.keys()))
                .group_by(LessonLog.class_subject_id)).all()
        }
        term_planned: dict[uuid.UUID, int] = {}
        if term_topics is not None:
            term_planned = {
                cs_id: int(n) for cs_id, n in self.db.execute(
                    select(PlanEntry.class_subject_id, func.count(PlanEntry.id))
                    .where(PlanEntry.org_id == m.org_id,
                           PlanEntry.class_subject_id.in_(forecasts.keys()),
                           PlanEntry.topic_id.in_(term_topics or [uuid.uuid4()]))
                    .group_by(PlanEntry.class_subject_id)).all()
            }

        out: list[SyllabusRow] = []
        for cs_id, class_id, subject_id, cname, section, sname, teacher_id in meta:
            f = forecasts[cs_id]
            planned = term_planned.get(cs_id, f.planned_topics) if term_topics is not None \
                else f.planned_topics
            done = round(taught.get(cs_id, 0.0), 1)
            out.append(SyllabusRow(
                class_subject_id=cs_id, class_id=class_id, class_label=_label(cname, section),
                subject_id=subject_id, subject_name=sname,
                teacher_member_id=teacher_id, teacher_name=teachers.get(teacher_id),
                status=f.status, total_topics=f.total_topics, planned_topics=planned,
                taught_topics=done,
                coverage_pct=round(done / planned * 100, 1) if planned else None,
                weeks_behind=f.weeks_behind or 0,
                baseline_finish=f.baseline_finish, projected_finish=f.projected_finish,
                unestimated_topics=f.unestimated_topics or 0,
                current_term_unplanned=bool(f.current_term_unplanned),
                logged_periods=logged.get(cs_id, 0)))
        out.sort(key=lambda r: (r.class_label, r.subject_name))
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
            planned_topics=planned, taught_topics=taught,
            coverage_pct=round(taught / planned * 100, 1) if planned else None,
            weeks_behind_max=max((r.weeks_behind for r in rows), default=0),
            unestimated_topics=sum(r.unestimated_topics for r in rows),
            logged_periods=logged_periods)
        # The guard: below the minimum sample the node carries its numbers but is
        # never ranked, and the UI says "not enough data yet".
        node.rank_eligible = len(rated) >= min_cs and logged_periods >= min_logged
        if node.rank_eligible:
            on_track_share = len([r for r in rated if r.status == "green"]) / len(rated)
            coverage = (node.coverage_pct or 0) / 100
            node.score = round(on_track_share * 60 + min(coverage, 1.0) * 40, 1)
        return node

    # ── the exam checkpoint, school-wide ─────────────────────────────────────
    def _exam_checkpoints(self, m: CurrentMember, year: AcademicYear) -> list[ExamCheckpoint]:
        """`exam_fit` is per class; this runs it for every class and merges by
        exam. It is the one place the module accepts a per-class loop — exam fit
        walks each class's own syllabus ordering and cannot be expressed as a
        single grouped query — so the result is capped to the classes of one year
        and only computed when the exam checkpoint is actually selected."""
        classes = self.db.execute(
            select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
            .where(SchoolClass.org_id == m.org_id, SchoolClass.academic_year_id == year.id)
            .order_by(SchoolClass.name, SchoolClass.section)).all()
        planner = PlannerService(self.db)
        merged: dict[uuid.UUID, ExamCheckpoint] = {}
        for cid, cname, section in classes:
            label = _label(cname, section)
            fit = planner.exam_fit(m, cid)
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
