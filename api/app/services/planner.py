"""Syllabus + plan drafting + forecast (M1, SPRD §5.1; term scoping V2-P11).

The forecast is COMPUTED from baseline + current effective periods, never stored
as mutated plan rows (P2). Adding a mid-year event re-blocks days, so re-running
the distribution shifts the projected finish without touching the baseline.

**Planning is scoped to a window.** Pass `term_id` and only that term's chapters
are drafted, validated and locked, inside that term's dates; an approved Term 1 is
never rewritten by a Term 2 re-draft. Pass nothing and you get the original
whole-year behaviour. This exists because schools fix the portion for the year up
front but decide how many periods each chapter takes when the term begins.

A topic with `est_periods IS NULL` is **unsized** and is never scheduled — there is
no honest week to put it in. It stays out of `plan_entries`, V6 reports it, and the
forecast refuses to go green while any remain.
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
    ExamPortion,
    LessonLog,
    Membership,
    Plan,
    PlanApproval,
    PlanComment,
    PlanEntry,
    SchoolClass,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    Term,
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
    PlanTermOut,
    SplitUnit,
    TopicOut,
    UnitOut,
    ViolationOut,
)
from app.services.calendar import (
    effective_periods,
    event_rows,
    expand_blocked_dates,
    expand_partial_blocks,
)
from app.services.plan_validate import (
    Violation,
    validate_capacity,
    validate_coverage,
    validate_exam_coverage,
    validate_ordering,
    validate_unsized,
)


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def distribute(
    topic_periods: list[int], *, periods_per_week: int, working_weekdays, blocked: set,
    window_start: date, window_end: date, partial: dict | None = None, periods_per_day: int = 8,
) -> list[date]:
    """Greedily place each topic (by est_periods) into successive teaching weeks,
    respecting each week's effective period budget. Returns a week_start per topic.
    Shared by draft (persisted) and forecast (computed).

    `window_start`/`window_end` bound the planning window — the whole academic year,
    or a single term. Weeks straddling the boundary are clamped to it, so a term's
    first and last weeks are costed at only the days that fall inside the term."""
    end_monday = _monday(window_end)
    cur = _monday(window_start)

    def cap(week: date) -> float:
        return effective_periods(
            periods_per_week or 1, week, working_weekdays=working_weekdays, blocked=blocked,
            year_start=window_start, year_end=window_end, partial=partial,
            periods_per_day=periods_per_day,
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

    # ── term scoping (V2-P11) ────────────────────────────────────────────────
    def _scoped_units(self, units: list[SyllabusUnit],
                      term_id: uuid.UUID | None) -> list[SyllabusUnit]:
        """`term_id=None` means the whole year — every chapter, termed or not."""
        if term_id is None:
            return units
        return [u for u in units if u.term_id == term_id]

    @staticmethod
    def _sized(topics: list[SyllabusTopic]) -> list[SyllabusTopic]:
        return [t for t in topics if t.est_periods is not None]

    @staticmethod
    def _unsized(topics: list[SyllabusTopic]) -> list[SyllabusTopic]:
        return [t for t in topics if t.est_periods is None]

    def _term(self, org_id: uuid.UUID, term_id: uuid.UUID, year: AcademicYear) -> Term:
        term = self.db.scalar(
            select(Term).where(Term.id == term_id, Term.org_id == org_id))
        if term is None:
            raise NotFoundError("Term")
        if term.academic_year_id != year.id:
            raise ValidationError("That term belongs to a different academic year.")
        return term

    def _window(self, org_id: uuid.UUID, year: AcademicYear,
                term_id: uuid.UUID | None) -> tuple[date, date, str]:
        """(start, end, label) of the planning window."""
        if term_id is None:
            return year.start_date, year.end_date, "this year"
        term = self._term(org_id, term_id, year)
        return term.start_date, term.end_date, f"in {term.name}"

    def _approval_state(self, org_id: uuid.UUID,
                        cs_id: uuid.UUID) -> dict[uuid.UUID | None, bool]:
        """Replay the append-only log: the last action on a (cs, term) wins.
        Key `None` is the whole-year approval."""
        rows = self.db.scalars(
            select(PlanApproval)
            .where(PlanApproval.org_id == org_id, PlanApproval.class_subject_id == cs_id)
            .order_by(PlanApproval.created_at, PlanApproval.id)
        )
        state: dict[uuid.UUID | None, bool] = {}
        for r in rows:
            state[r.term_id] = r.action == "approve"
        return state

    def _is_locked(self, state: dict, term_id: uuid.UUID | None) -> bool:
        """A whole-year approval locks every term. A term approval locks only itself,
        and also blocks a whole-year re-plan (which would rewrite it)."""
        if state.get(None):
            return True
        if term_id is None:
            return any(state.values())
        return bool(state.get(term_id))

    def _append_approval(self, m: CurrentMember, cs_id: uuid.UUID,
                         term_id: uuid.UUID | None, action: str) -> None:
        # created_at is set explicitly: the server default is now(), which is the
        # TRANSACTION timestamp, so an approve and a revoke in one request would tie
        # and `_approval_state` could replay them in the wrong order.
        self.db.add(PlanApproval(
            org_id=m.org_id, class_subject_id=cs_id, term_id=term_id, action=action,
            actor_user_id=m.user_id, created_at=datetime.now(UTC)))
        self.db.flush()

    def _recompute_plan_status(self, m: CurrentMember, cs_id: uuid.UUID, plan: Plan) -> None:
        """Derived cache over `plan_approvals` — see the Plan docstring. The log is
        the truth; these columns just let overview/wizard ask "is it locked?"."""
        state = self._approval_state(m.org_id, cs_id)
        term_ids = {u.term_id for u in self._units(m.org_id, cs_id) if u.term_id is not None}

        if state.get(None) or (term_ids and all(state.get(t) for t in term_ids)):
            plan.status = "approved"
        elif any(state.values()):
            plan.status = "partial"
        else:
            plan.status = "draft"

        latest = self.db.scalar(
            select(PlanApproval)
            .where(PlanApproval.org_id == m.org_id, PlanApproval.class_subject_id == cs_id,
                   PlanApproval.action == "approve")
            .order_by(PlanApproval.created_at.desc(), PlanApproval.id.desc()).limit(1))
        locked = plan.status in ("approved", "partial")
        plan.approved_at = latest.created_at if (locked and latest) else None
        plan.approved_by = latest.actor_user_id if (locked and latest) else None
        self.db.flush()

    # ── syllabus CRUD ────────────────────────────────────────────────────────
    def get_syllabus(self, m: CurrentMember, cs_id: uuid.UUID) -> list[UnitOut]:
        self._class_subject(m.org_id, cs_id)
        return [UnitOut.model_validate(u) for u in self._units(m.org_id, cs_id)]

    def add_unit(self, m: CurrentMember, cs_id: uuid.UUID, title: str,
                 term_id: uuid.UUID | None = None) -> UnitOut:
        cs = self._class_subject(m.org_id, cs_id)
        if term_id is not None:
            self._term(m.org_id, term_id, self._year_for_cs(cs))
        pos = len(self._units(m.org_id, cs_id))
        unit = SyllabusUnit(org_id=m.org_id, class_subject_id=cs_id, title=title,
                            term_id=term_id, position=pos)
        self.db.add(unit)
        self.db.flush()
        return UnitOut.model_validate(unit)

    def add_topic(self, m: CurrentMember, unit_id: uuid.UUID, title: str,
                  est: int | None = None) -> TopicOut:
        """`est=None` records the chapter without sizing it — the April state of a
        later term's syllabus. It will not be scheduled until someone sets a number."""
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

    def set_topic_estimate(self, m: CurrentMember, topic_id: uuid.UUID,
                           est: int | None) -> TopicOut:
        """Size (or un-size) a chapter. Refused once the topic's term is locked —
        changing an estimate under an approved baseline would silently invalidate it."""
        topic = self.db.scalar(
            select(SyllabusTopic).where(
                SyllabusTopic.id == topic_id, SyllabusTopic.org_id == m.org_id))
        if topic is None:
            raise NotFoundError("Topic")
        unit = self.db.get(SyllabusUnit, topic.unit_id)
        state = self._approval_state(m.org_id, unit.class_subject_id)
        if self._is_locked(state, unit.term_id):
            raise ValidationError(
                "That chapter's plan is approved. Un-approve it before changing periods.")
        topic.est_periods = est
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
        return self._calendar(org_id, year_id)[0]

    def _calendar(self, org_id: uuid.UUID, year_id: uuid.UUID) -> tuple[set, dict]:
        """(fully blocked dates, date -> periods lost to partial-day events)."""
        rows = event_rows(self.db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.org_id == org_id, CalendarEvent.academic_year_id == year_id)))
        return expand_blocked_dates(rows), expand_partial_blocks(rows)

    def get_plan(self, m: CurrentMember, cs_id: uuid.UUID) -> PlanOut:
        cs = self._class_subject(m.org_id, cs_id)  # same-org guard
        units = self._units(m.org_id, cs_id)
        all_topics = self._ordered_topics(units)
        topics = {t.id: t for t in all_topics}
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
            total_est_periods=sum(t.est_periods or 0 for t in all_topics),
            unestimated_topics=len(self._unsized(all_topics)),
            terms=self._term_rows(m, cs, units),
            entries=out_entries,
        )

    def _term_rows(self, m: CurrentMember, cs: ClassSubject,
                   units: list[SyllabusUnit]) -> list[PlanTermOut]:
        """One row per term that actually has chapters, plus an "Unscheduled" row for
        chapters nobody assigned to a term. Drives the term selector on Plan → Week plan."""
        year = self._year_for_cs(cs)
        state = self._approval_state(m.org_id, cs.id)
        terms = {t.id: t for t in self.db.scalars(
            select(Term).where(Term.org_id == m.org_id, Term.academic_year_id == year.id)
            .order_by(Term.start_date))}

        by_term: dict[uuid.UUID | None, list[SyllabusTopic]] = {}
        for u in units:
            if u.topics:
                by_term.setdefault(u.term_id, []).extend(u.topics)

        out: list[PlanTermOut] = []
        for term_id, term in terms.items():
            if term_id not in by_term:
                continue
            tops = by_term[term_id]
            out.append(PlanTermOut(
                term_id=term_id, name=term.name, start_date=term.start_date,
                end_date=term.end_date, topic_count=len(tops),
                unestimated_topics=len(self._unsized(tops)),
                approved=bool(state.get(term_id)) or bool(state.get(None))))
        if None in by_term:
            tops = by_term[None]
            # With no termed chapters at all, the untermed bucket IS the year — that
            # is the whole-year school, not a pile of chapters someone forgot to file.
            out.append(PlanTermOut(
                term_id=None, name="Whole year" if not out else "Unscheduled",
                start_date=year.start_date, end_date=year.end_date, topic_count=len(tops),
                unestimated_topics=len(self._unsized(tops)),
                approved=bool(state.get(None))))
        return out

    def _lock_guard(self, m: CurrentMember, cs_id: uuid.UUID,
                    term_id: uuid.UUID | None) -> None:
        state = self._approval_state(m.org_id, cs_id)
        if not self._is_locked(state, term_id):
            return
        if term_id is None and any(state.values()) and not state.get(None):
            raise ValidationError(
                "Some terms are already approved. Plan those terms individually, "
                "or un-approve them first.")
        raise ValidationError("Baseline is locked. Un-approve it before re-planning.")

    def _entry_map(self, m: CurrentMember, cs_id: uuid.UUID) -> dict[uuid.UUID, date]:
        return {e.topic_id: e.week_start for e in self.db.scalars(
            select(PlanEntry).where(
                PlanEntry.org_id == m.org_id, PlanEntry.class_subject_id == cs_id))}

    def _replace_entries(self, m: CurrentMember, cs_id: uuid.UUID,
                         scoped: list[SyllabusTopic], sized: list[SyllabusTopic],
                         weeks: list[date]) -> None:
        """Full-replace, but ONLY for the topics in scope. Entries belonging to another
        term's approved baseline are left exactly where they are (P2).

        Deletion spans every scoped topic, not just the sized ones: a topic that was
        sized, planned, and has since been un-sized must lose its entry, or the plan
        keeps scheduling a chapter nobody has estimated."""
        scoped_ids = [t.id for t in scoped]
        if scoped_ids:
            self.db.execute(delete(PlanEntry).where(
                PlanEntry.org_id == m.org_id, PlanEntry.class_subject_id == cs_id,
                PlanEntry.topic_id.in_(scoped_ids)))
        for topic, wk in zip(sized, weeks, strict=True):
            self.db.add(PlanEntry(org_id=m.org_id, class_subject_id=cs_id,
                                  topic_id=topic.id, week_start=wk))

    def _plan_scope(self, m: CurrentMember, cs_id: uuid.UUID, term_id: uuid.UUID | None,
                    ) -> tuple[ClassSubject, AcademicYear, list[SyllabusTopic],
                               list[SyllabusTopic], list[date], str]:
        """Shared body of draft + generate: guard the lock, pick the term's chapters,
        and lay the sized ones out inside the term's dates.
        Returns (cs, year, scoped_topics, sized_topics, weeks, window_label)."""
        cs = self._class_subject(m.org_id, cs_id)
        self._lock_guard(m, cs_id, term_id)
        year = self._year_for_cs(cs)
        units = self._scoped_units(self._units(m.org_id, cs_id), term_id)
        scoped = self._ordered_topics(units)
        if not scoped:
            raise ValidationError(
                "No syllabus chapters in that term yet." if term_id
                else "Add syllabus topics before drafting a plan.")
        sized = self._sized(scoped)
        start, end, label = self._window(m.org_id, year, term_id)
        blocked, partial = self._calendar(m.org_id, year.id)
        weeks = distribute(
            [t.est_periods for t in sized], periods_per_week=cs.periods_per_week,
            working_weekdays=year.working_weekdays, blocked=blocked, partial=partial,
            periods_per_day=year.periods_per_day, window_start=start, window_end=end)
        return cs, year, scoped, sized, weeks, label

    def draft_plan(self, m: CurrentMember, cs_id: uuid.UUID,
                   term_id: uuid.UUID | None = None) -> PlanOut:
        _, _, scoped, sized, weeks, _ = self._plan_scope(m, cs_id, term_id)
        self._replace_entries(m, cs_id, scoped, sized, weeks)
        plan = self.db.scalar(
            select(Plan).where(Plan.org_id == m.org_id, Plan.class_subject_id == cs_id))
        if plan is None:
            self.db.add(Plan(org_id=m.org_id, class_subject_id=cs_id, status="draft"))
        self.db.flush()
        return self.get_plan(m, cs_id)

    def approve_plan(self, m: CurrentMember, cs_id: uuid.UUID,
                     term_id: uuid.UUID | None = None) -> PlanOut:
        cs = self._class_subject(m.org_id, cs_id)
        plan = self.db.scalar(
            select(Plan).where(Plan.org_id == m.org_id, Plan.class_subject_id == cs_id)
        )
        if plan is None:
            raise ValidationError("Draft a plan first.")
        if term_id is not None:
            self._term(m.org_id, term_id, self._year_for_cs(cs))
        state = self._approval_state(m.org_id, cs_id)
        if self._is_locked(state, term_id):
            raise ValidationError("That baseline is already approved.")

        scoped = self._ordered_topics(
            self._scoped_units(self._units(m.org_id, cs_id), term_id))
        if not scoped:
            raise ValidationError("Nothing to approve — that term has no chapters.")
        # Locking a baseline that omits a third of its chapters would make the
        # forecast confidently wrong. Size them first.
        unsized = self._unsized(scoped)
        if unsized:
            raise ValidationError(
                f"{len(unsized)} chapter(s) have no period estimate, so they are not in "
                f"the plan. Set their periods before approving.")

        self._append_approval(m, cs_id, term_id, "approve")
        self._recompute_plan_status(m, cs_id, plan)
        return self.get_plan(m, cs_id)

    def unapprove_plan(self, m: CurrentMember, cs_id: uuid.UUID,
                       term_id: uuid.UUID | None = None) -> PlanOut:
        """Unlock a baseline so it can be re-planned. Appends a compensating row
        (law 3) — the approval history is never rewritten."""
        cs = self._class_subject(m.org_id, cs_id)
        plan = self.db.scalar(
            select(Plan).where(Plan.org_id == m.org_id, Plan.class_subject_id == cs_id))
        if plan is None:
            raise ValidationError("There is no plan to un-approve.")
        if term_id is not None:
            self._term(m.org_id, term_id, self._year_for_cs(cs))
        state = self._approval_state(m.org_id, cs_id)
        # A whole-year approval is what locks each term; revoking one term out of it
        # would leave the year approval standing and the term still locked.
        if term_id is not None and state.get(None) and not state.get(term_id):
            raise ValidationError(
                "This plan is approved for the whole year. Un-approve the year, not a term.")
        if not state.get(term_id):
            raise ValidationError("That baseline is not approved.")

        self._append_approval(m, cs_id, term_id, "revoke")
        self._recompute_plan_status(m, cs_id, plan)
        return self.get_plan(m, cs_id)

    # ── generation pipeline (V2-M2, §5.2): proposer + deterministic validators ─
    def _total_effective_periods(self, cs: ClassSubject, year: AcademicYear, blocked: set,
                                 partial: dict | None = None,
                                 window: tuple[date, date] | None = None) -> float:
        """Teaching periods this class-subject actually has in the window (default:
        the whole year). Term-scoped planning must be costed against the term's own
        capacity, not the year's, or every term looks like it fits."""
        start, end = window or (year.start_date, year.end_date)
        total, cur, last, guard = 0.0, _monday(start), _monday(end), 0
        while cur <= last and guard < 500:
            total += effective_periods(
                cs.periods_per_week or 1, cur, working_weekdays=year.working_weekdays,
                blocked=blocked, partial=partial, periods_per_day=year.periods_per_day,
                year_start=start, year_end=end)
            cur += timedelta(days=7)
            guard += 1
        return total

    def generate_plan(self, m: CurrentMember, cs_id: uuid.UUID,
                      term_id: uuid.UUID | None = None) -> PlanGenerateOut:
        """Proposer (greedy distribute) → deterministic validators. Persists the draft
        so the admin can review — an over-capacity syllabus is flagged (fits=False),
        never silently squeezed. Approval stays a separate, explicit step (P2).

        Scoped to `term_id` when given: only that term's chapters are laid out, inside
        that term's dates, against that term's capacity."""
        cs, year, scoped, sized, weeks, label = self._plan_scope(m, cs_id, term_id)
        blocked, partial = self._calendar(m.org_id, year.id)
        start, end, _ = self._window(m.org_id, year, term_id)
        est = [t.est_periods for t in sized]

        violations = [
            v for v in (
                validate_unsized([t.title for t in self._unsized(scoped)]),
                validate_capacity(
                    sum(est),
                    self._total_effective_periods(cs, year, blocked, partial, (start, end)),
                    label),
                validate_coverage(weeks, _monday(end)),
                validate_ordering(weeks),
            ) if v is not None
        ]
        # Runs BEFORE _replace_entries so the persisted rows still describe the terms
        # we are not touching — that is how a Term-1 exam stays validated against
        # Term 1's locked baseline while we generate Term 2.
        violations.extend(self._exam_violations(m, cs_id, scoped, sized, weeks))

        self._replace_entries(m, cs_id, scoped, sized, weeks)
        plan = self.db.scalar(
            select(Plan).where(Plan.org_id == m.org_id, Plan.class_subject_id == cs_id))
        if plan is None:
            self.db.add(Plan(org_id=m.org_id, class_subject_id=cs_id, status="draft"))
        self.db.flush()
        return PlanGenerateOut(
            # An unsized chapter is not scheduled, so a plan carrying one has not been
            # made to fit — it has been made to look like it fits.
            fits=not any(v.code in ("capacity", "unsized") for v in violations),
            violations=[ViolationOut(code=v.code, message=v.message) for v in violations],
            plan=self.get_plan(m, cs_id))

    def _exam_violations(self, m: CurrentMember, cs_id: uuid.UUID,
                         scoped: list[SyllabusTopic], sized: list[SyllabusTopic],
                         weeks: list[date]) -> list[Violation]:
        """V5: for each exam with a portion on this class-subject, is every topic in
        the portion planned to FINISH before the exam starts? The portion is every
        topic up to and including `upto_topic_id` in syllabus order (V2-P7).

        The portion is indexed against the FULL syllabus, not the slice we just
        planned: a Term-1 exam's portion is defined by the syllabus, and a topic that
        is missing from the plan because nobody sized it is exactly the case worth
        shouting about.

        Placement therefore merges the topics we are about to write with the entries
        already persisted for terms outside this scope. Using only the current slice
        would report a locked, fully-planned Term 1 as "not scheduled at all" the
        moment someone generated Term 2."""
        portions = self.db.execute(
            select(ExamPortion.upto_topic_id, CalendarEvent.title, CalendarEvent.start_date)
            .join(CalendarEvent, CalendarEvent.id == ExamPortion.exam_event_id)
            .where(ExamPortion.org_id == m.org_id, ExamPortion.class_subject_id == cs_id)
        ).all()
        if not portions:
            return []
        all_topics = self._ordered_topics(self._units(m.org_id, cs_id))
        index = {t.id: i for i, t in enumerate(all_topics)}
        scoped_ids = {t.id for t in scoped}
        placement = {tid: wk for tid, wk in self._entry_map(m, cs_id).items()
                     if tid not in scoped_ids}
        placement.update(zip((t.id for t in sized), weeks, strict=True))

        out: list[Violation] = []
        for upto_topic_id, exam_title, exam_start in portions:
            cut = index.get(upto_topic_id)
            if cut is None:
                continue  # the portion's topic was deleted from the syllabus
            portion = all_topics[: cut + 1]
            unplanned = [t for t in portion if t.id not in placement]
            if unplanned:
                out.append(Violation(
                    "exam_coverage",
                    f"{exam_title}: {len(unplanned)} topic(s) in the portion have no period "
                    f'estimate, starting with "{unplanned[0].title}" — they are not '
                    f"scheduled at all."))
            scheduled = [(t.title, placement[t.id]) for t in portion if t.id in placement]
            v = validate_exam_coverage(exam_title, exam_start, scheduled)
            if v is not None:
                out.append(v)
        return out

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
            unsized = self._unsized(topics)
            if not topics or not entries:
                out.append(ForecastOut(
                    class_subject_id=cs.id, subject_name=subject_name, class_label=label,
                    status="none", total_topics=len(topics),
                    unestimated_topics=len(unsized)))
                continue
            if unsized:
                # There is no honest finish date while chapters are unsized. Reporting
                # green here — which is what a NOT NULL DEFAULT 1 used to do — tells the
                # director a year nobody has planned is on track.
                out.append(ForecastOut(
                    class_subject_id=cs.id, subject_name=subject_name, class_label=label,
                    status="unplanned", total_topics=len(topics),
                    unestimated_topics=len(unsized)))
                continue
            year = self.db.get(AcademicYear, klass.academic_year_id)
            baseline_finish = max(e.week_start for e in entries)
            blocked, partial = self._calendar(m.org_id, year.id)
            projected = distribute(
                [t.est_periods for t in topics], periods_per_week=cs.periods_per_week,
                working_weekdays=year.working_weekdays, blocked=blocked, partial=partial,
                periods_per_day=year.periods_per_day,
                window_start=year.start_date, window_end=year.end_date,
            )
            projected_finish = max(projected)
            weeks_behind = max(0, (projected_finish - baseline_finish).days // 7)
            rag = "green" if weeks_behind == 0 else "amber" if weeks_behind <= 2 else "red"
            out.append(ForecastOut(
                class_subject_id=cs.id, subject_name=subject_name, class_label=label,
                status=rag, total_topics=len(topics), baseline_finish=baseline_finish,
                projected_finish=projected_finish, weeks_behind=weeks_behind,
                unestimated_topics=0))
        return out

    def _require_class(self, org_id: uuid.UUID, class_id: uuid.UUID) -> None:
        if not self.db.scalar(
            select(SchoolClass.id).where(SchoolClass.id == class_id, SchoolClass.org_id == org_id)
        ):
            raise NotFoundError("Class")
