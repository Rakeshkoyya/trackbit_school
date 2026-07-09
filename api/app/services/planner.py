"""Syllabus + plan drafting + forecast (M1, SPRD §5.1).

The forecast is COMPUTED from baseline + current effective periods, never stored
as mutated plan rows (P2). Adding a mid-year event re-blocks days, so re-running
the distribution shifts the projected finish without touching the baseline.
"""

import re
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    LessonLog,
    Membership,
    Plan,
    PlanComment,
    PlanEntry,
    SchoolClass,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    User,
)
from app.schemas.periods import TopicProgressRow
from app.schemas.planner import (
    ForecastOut,
    PlanCommentIn,
    PlanCommentOut,
    PlanEntryOut,
    PlanGenerateOut,
    PlanOut,
    SplitUnit,
    TopicOut,
    UnitOut,
    ViolationOut,
)
from app.services.calendar import effective_periods, expand_blocked_dates
from app.services.plan_validate import (
    validate_capacity,
    validate_coverage,
    validate_ordering,
)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def distribute(
    topic_periods: list[int], *, periods_per_week: int, working_weekdays, blocked: set,
    year_start: date, year_end: date,
) -> list[date]:
    """Greedily place each topic (by est_periods) into successive teaching weeks,
    respecting each week's effective period budget. Returns a week_start per topic.
    Shared by draft (persisted) and forecast (computed)."""
    end_monday = _monday(year_end)
    cur = _monday(year_start)

    def cap(week: date) -> float:
        return effective_periods(
            periods_per_week or 1, week, working_weekdays=working_weekdays, blocked=blocked,
            year_start=year_start, year_end=year_end,
        )

    capacity = cap(cur)
    out: list[date] = []
    for est in topic_periods:
        guard = 0
        while capacity <= 0 and cur < end_monday and guard < 400:
            cur = cur + timedelta(days=7)
            capacity = cap(cur)
            guard += 1
        out.append(cur)
        capacity -= max(est, 1)
    return out


class PlannerService:
    def __init__(self, db: Session):
        self.db = db

    # ── scoped loaders ───────────────────────────────────────────────────────
    def _class_subject(self, org_id: uuid.UUID, cs_id: uuid.UUID) -> ClassSubject:
        cs = self.db.scalar(
            select(ClassSubject).where(ClassSubject.id == cs_id, ClassSubject.org_id == org_id)
        )
        if cs is None:
            raise NotFoundError("Class-subject")
        return cs

    def _units(self, org_id: uuid.UUID, cs_id: uuid.UUID) -> list[SyllabusUnit]:
        return list(self.db.scalars(
            select(SyllabusUnit)
            .where(SyllabusUnit.org_id == org_id, SyllabusUnit.class_subject_id == cs_id)
            .options(selectinload(SyllabusUnit.topics))
            .order_by(SyllabusUnit.position)
        ))

    def _ordered_topics(self, units: list[SyllabusUnit]) -> list[SyllabusTopic]:
        topics: list[SyllabusTopic] = []
        for u in units:
            topics.extend(sorted(u.topics, key=lambda t: t.position))
        return topics

    # ── syllabus CRUD ────────────────────────────────────────────────────────
    def get_syllabus(self, m: CurrentMember, cs_id: uuid.UUID) -> list[UnitOut]:
        self._class_subject(m.org_id, cs_id)
        return [UnitOut.model_validate(u) for u in self._units(m.org_id, cs_id)]

    def add_unit(self, m: CurrentMember, cs_id: uuid.UUID, title: str) -> UnitOut:
        self._class_subject(m.org_id, cs_id)
        pos = len(self._units(m.org_id, cs_id))
        unit = SyllabusUnit(org_id=m.org_id, class_subject_id=cs_id, title=title, position=pos)
        self.db.add(unit)
        self.db.flush()
        return UnitOut.model_validate(unit)

    def add_topic(self, m: CurrentMember, unit_id: uuid.UUID, title: str, est: int) -> TopicOut:
        unit = self.db.scalar(
            select(SyllabusUnit).where(SyllabusUnit.id == unit_id, SyllabusUnit.org_id == m.org_id)
            .options(selectinload(SyllabusUnit.topics))
        )
        if unit is None:
            raise NotFoundError("Unit")
        topic = SyllabusTopic(org_id=m.org_id, unit_id=unit_id, title=title,
                              est_periods=est, position=len(unit.topics))
        self.db.add(topic)
        self.db.flush()
        return TopicOut.model_validate(topic)

    def delete_unit(self, m: CurrentMember, unit_id: uuid.UUID) -> None:
        unit = self.db.scalar(
            select(SyllabusUnit).where(SyllabusUnit.id == unit_id, SyllabusUnit.org_id == m.org_id)
        )
        if unit is None:
            raise NotFoundError("Unit")
        self.db.delete(unit)

    def delete_topic(self, m: CurrentMember, topic_id: uuid.UUID) -> None:
        topic = self.db.scalar(
            select(SyllabusTopic).where(
                SyllabusTopic.id == topic_id, SyllabusTopic.org_id == m.org_id
            )
        )
        if topic is None:
            raise NotFoundError("Topic")
        self.db.delete(topic)

    def split_text(self, text: str) -> list[SplitUnit]:
        """AI-stub syllabus splitter (SPRD §8: heuristic fallback when no key).
        A line ending with ':' or in ALL CAPS starts a unit; other lines are topics."""
        units: list[SplitUnit] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            is_heading = line.endswith(":") or (line.isupper() and len(line) > 2) or \
                bool(re.match(r"^(unit|chapter)\b", line, re.I))
            # A heading like "Chapter 1: Plants" titles the unit "Plants".
            if is_heading and ":" in line:
                title = line.split(":", 1)[1].strip() or line.rstrip(":").strip()
            else:
                title = line.rstrip(":").strip()
            if is_heading or not units:
                units.append(SplitUnit(title=title, topics=[]))
                if is_heading:
                    continue
            units[-1].topics.append(title)
        return [u for u in units if u.topics or u.title]

    # ── plan ─────────────────────────────────────────────────────────────────
    def _year_for_cs(self, cs: ClassSubject) -> AcademicYear:
        klass = self.db.get(SchoolClass, cs.class_id)
        year = self.db.get(AcademicYear, klass.academic_year_id) if klass else None
        if year is None:
            raise ValidationError("This class has no academic year.")
        return year

    def _blocked(self, org_id: uuid.UUID, year_id: uuid.UUID) -> set:
        events = self.db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.org_id == org_id, CalendarEvent.academic_year_id == year_id
            )
        )
        return expand_blocked_dates([(e.start_date, e.end_date, e.affects_teaching) for e in events])

    def get_plan(self, m: CurrentMember, cs_id: uuid.UUID) -> PlanOut:
        self._class_subject(m.org_id, cs_id)  # same-org guard
        units = self._units(m.org_id, cs_id)
        topics = {t.id: t for t in self._ordered_topics(units)}
        unit_titles = {t.id: u.title for u in units for t in u.topics}
        plan = self.db.scalar(
            select(Plan).where(Plan.org_id == m.org_id, Plan.class_subject_id == cs_id)
        )
        entries = self.db.scalars(
            select(PlanEntry).where(
                PlanEntry.org_id == m.org_id, PlanEntry.class_subject_id == cs_id
            ).order_by(PlanEntry.week_start)
        )
        out_entries = [
            PlanEntryOut(
                topic_id=e.topic_id,
                topic_title=topics[e.topic_id].title if e.topic_id in topics else "—",
                unit_title=unit_titles.get(e.topic_id, ""),
                week_start=e.week_start,
            )
            for e in entries if e.topic_id in topics
        ]
        return PlanOut(
            class_subject_id=cs_id,
            status=plan.status if plan else "none",
            approved_at=plan.approved_at if plan else None,
            total_est_periods=sum(t.est_periods for t in topics.values()),
            entries=out_entries,
        )

    def draft_plan(self, m: CurrentMember, cs_id: uuid.UUID) -> PlanOut:
        cs = self._class_subject(m.org_id, cs_id)
        plan = self.db.scalar(
            select(Plan).where(Plan.org_id == m.org_id, Plan.class_subject_id == cs_id)
        )
        if plan and plan.status == "approved":
            raise ValidationError("Baseline is locked. Un-approving is a separate action.")
        topics = self._ordered_topics(self._units(m.org_id, cs_id))
        if not topics:
            raise ValidationError("Add syllabus topics before drafting a plan.")
        year = self._year_for_cs(cs)
        weeks = distribute(
            [t.est_periods for t in topics], periods_per_week=cs.periods_per_week,
            working_weekdays=year.working_weekdays, blocked=self._blocked(m.org_id, year.id),
            year_start=year.start_date, year_end=year.end_date,
        )
        # Replace any existing (draft) entries — never mutate an approved baseline.
        self.db.execute(delete(PlanEntry).where(
            PlanEntry.org_id == m.org_id, PlanEntry.class_subject_id == cs_id))
        for topic, wk in zip(topics, weeks, strict=True):
            self.db.add(PlanEntry(org_id=m.org_id, class_subject_id=cs_id,
                                  topic_id=topic.id, week_start=wk))
        if plan is None:
            self.db.add(Plan(org_id=m.org_id, class_subject_id=cs_id, status="draft"))
        self.db.flush()
        return self.get_plan(m, cs_id)

    def approve_plan(self, m: CurrentMember, cs_id: uuid.UUID) -> PlanOut:
        self._class_subject(m.org_id, cs_id)
        plan = self.db.scalar(
            select(Plan).where(Plan.org_id == m.org_id, Plan.class_subject_id == cs_id)
        )
        if plan is None:
            raise ValidationError("Draft a plan first.")
        plan.status = "approved"
        plan.approved_by = m.user_id
        plan.approved_at = datetime.now(UTC)
        self.db.flush()
        return self.get_plan(m, cs_id)

    # ── generation pipeline (V2-M2, §5.2): proposer + deterministic validators ─
    def _total_effective_periods(self, cs: ClassSubject, year: AcademicYear, blocked: set) -> float:
        total, cur, end, guard = 0.0, _monday(year.start_date), _monday(year.end_date), 0
        while cur <= end and guard < 500:
            total += effective_periods(
                cs.periods_per_week or 1, cur, working_weekdays=year.working_weekdays,
                blocked=blocked, year_start=year.start_date, year_end=year.end_date)
            cur += timedelta(days=7)
            guard += 1
        return total

    def generate_plan(self, m: CurrentMember, cs_id: uuid.UUID) -> PlanGenerateOut:
        """Proposer (greedy distribute) → deterministic validators. Persists the draft
        so the admin can review — an over-capacity syllabus is flagged (fits=False),
        never silently squeezed. Approval stays a separate, explicit step (P2)."""
        cs = self._class_subject(m.org_id, cs_id)
        plan = self.db.scalar(
            select(Plan).where(Plan.org_id == m.org_id, Plan.class_subject_id == cs_id))
        if plan and plan.status == "approved":
            raise ValidationError("Baseline is locked. Un-approving is a separate action.")
        topics = self._ordered_topics(self._units(m.org_id, cs_id))
        if not topics:
            raise ValidationError("Add syllabus topics before generating a plan.")
        year = self._year_for_cs(cs)
        blocked = self._blocked(m.org_id, year.id)
        est = [t.est_periods for t in topics]
        weeks = distribute(
            est, periods_per_week=cs.periods_per_week, working_weekdays=year.working_weekdays,
            blocked=blocked, year_start=year.start_date, year_end=year.end_date)

        violations = [
            v for v in (
                validate_capacity(sum(est), self._total_effective_periods(cs, year, blocked)),
                validate_coverage(weeks, _monday(year.end_date)),
                validate_ordering(weeks),
            ) if v is not None
        ]
        # Persist the proposer's draft (review surface); never touch an approved baseline.
        self.db.execute(delete(PlanEntry).where(
            PlanEntry.org_id == m.org_id, PlanEntry.class_subject_id == cs_id))
        for topic, wk in zip(topics, weeks, strict=True):
            self.db.add(PlanEntry(org_id=m.org_id, class_subject_id=cs_id,
                                  topic_id=topic.id, week_start=wk))
        if plan is None:
            self.db.add(Plan(org_id=m.org_id, class_subject_id=cs_id, status="draft"))
        self.db.flush()
        return PlanGenerateOut(
            fits=not any(v.code == "capacity" for v in violations),
            violations=[ViolationOut(code=v.code, message=v.message) for v in violations],
            plan=self.get_plan(m, cs_id))

    # ── topic progress (V2-P6): plan is baseline, logs are actual (P2) ───────
    def topic_progress(self, m: CurrentMember, cs_id: uuid.UUID) -> list[TopicProgressRow]:
        """Every syllabus topic with how far the class actually got.

        Derived from lesson_logs, never stored: a topic with any full-coverage log
        is done; one with only partial logs is in progress; the rest are pending."""
        self._class_subject(m.org_id, cs_id)
        units = self._units(m.org_id, cs_id)
        coverages: dict[uuid.UUID, set[str]] = {}
        for topic_id, coverage in self.db.execute(
            select(LessonLog.topic_id, LessonLog.coverage).where(
                LessonLog.org_id == m.org_id, LessonLog.class_subject_id == cs_id,
                LessonLog.topic_id.is_not(None))
        ).all():
            coverages.setdefault(topic_id, set()).add(coverage)

        out: list[TopicProgressRow] = []
        for unit in units:
            for topic in sorted(unit.topics, key=lambda t: t.position):
                seen = coverages.get(topic.id, set())
                status = "done" if "full" in seen else "in_progress" if seen else "pending"
                out.append(TopicProgressRow(
                    topic_id=topic.id, topic_title=topic.title, unit_title=unit.title,
                    est_periods=topic.est_periods, status=status))
        return out

    # ── teacher change-requests (comment threads on the plan) ─────────────────
    def _comment_out(self, c: PlanComment) -> PlanCommentOut:
        author = None
        if c.author_member_id is not None:
            author = self.db.scalar(
                select(User.name).join(Membership, Membership.user_id == User.id)
                .where(Membership.id == c.author_member_id))
        return PlanCommentOut(
            id=c.id, class_subject_id=c.class_subject_id, topic_id=c.topic_id,
            author_name=author, text=c.text, status=c.status, created_at=c.created_at)

    def add_comment(self, m: CurrentMember, cs_id: uuid.UUID, body: PlanCommentIn) -> PlanCommentOut:
        self._class_subject(m.org_id, cs_id)
        c = PlanComment(org_id=m.org_id, class_subject_id=cs_id, topic_id=body.topic_id,
                        author_member_id=m.membership.id, text=body.text)
        self.db.add(c)
        self.db.flush()
        return self._comment_out(c)

    def list_comments(self, m: CurrentMember, cs_id: uuid.UUID,
                      include_resolved: bool = False) -> list[PlanCommentOut]:
        self._class_subject(m.org_id, cs_id)
        q = select(PlanComment).where(
            PlanComment.org_id == m.org_id, PlanComment.class_subject_id == cs_id)
        if not include_resolved:
            q = q.where(PlanComment.status == "open")
        return [self._comment_out(c) for c in self.db.scalars(q.order_by(PlanComment.created_at))]

    def resolve_comment(self, m: CurrentMember, comment_id: uuid.UUID) -> PlanCommentOut:
        c = self.db.scalar(
            select(PlanComment).where(PlanComment.id == comment_id, PlanComment.org_id == m.org_id))
        if c is None:
            raise NotFoundError("Comment")
        c.status = "resolved"
        self.db.flush()
        return self._comment_out(c)

    # ── forecast (computed) ──────────────────────────────────────────────────
    def forecast(self, m: CurrentMember, class_id: uuid.UUID) -> list[ForecastOut]:
        self._require_class(m.org_id, class_id)
        rows = self.db.execute(
            select(ClassSubject, Subject.name, SchoolClass)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .where(ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id)
        ).all()
        out: list[ForecastOut] = []
        for cs, subject_name, klass in rows:
            label = klass.name + (f"-{klass.section}" if klass.section else "")
            units = self._units(m.org_id, cs.id)
            topics = self._ordered_topics(units)
            entries = list(self.db.scalars(
                select(PlanEntry).where(
                    PlanEntry.org_id == m.org_id, PlanEntry.class_subject_id == cs.id)
            ))
            if not topics or not entries:
                out.append(ForecastOut(
                    class_subject_id=cs.id, subject_name=subject_name, class_label=label,
                    status="none", total_topics=len(topics)))
                continue
            year = self.db.get(AcademicYear, klass.academic_year_id)
            baseline_finish = max(e.week_start for e in entries)
            projected = distribute(
                [t.est_periods for t in topics], periods_per_week=cs.periods_per_week,
                working_weekdays=year.working_weekdays, blocked=self._blocked(m.org_id, year.id),
                year_start=year.start_date, year_end=year.end_date,
            )
            projected_finish = max(projected)
            weeks_behind = max(0, (projected_finish - baseline_finish).days // 7)
            rag = "green" if weeks_behind == 0 else "amber" if weeks_behind <= 2 else "red"
            out.append(ForecastOut(
                class_subject_id=cs.id, subject_name=subject_name, class_label=label,
                status=rag, total_topics=len(topics), baseline_finish=baseline_finish,
                projected_finish=projected_finish, weeks_behind=weeks_behind))
        return out

    def _require_class(self, org_id: uuid.UUID, class_id: uuid.UUID) -> None:
        if not self.db.scalar(
            select(SchoolClass.id).where(SchoolClass.id == class_id, SchoolClass.org_id == org_id)
        ):
            raise NotFoundError("Class")
