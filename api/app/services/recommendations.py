"""Recommendations engine (V2-M5, SPRD2 §5.5) — daily checks from plan × bands.

Lazily (on first My Day read of a class-subject×date) the system materialises a
few `daily_checks` from the planned topic and the class's band distribution — with
zero teacher setup. Volume is capped so the period card stays a one-minute job:
  * ≤ 2 class-wide checks,
  * + 1 richer check for the C-band (when C-band students are in the class),
  * + ≤ 1 targeted check per intervention student.
AI drafts the wording; deterministic templates run when AI is off (§8). The teacher
confirms "class did it ✓" and taps only deviations (P1v2 exception capture).
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    CheckResult,
    ClassSubject,
    DailyCheck,
    Intervention,
    LessonLog,
    PlanEntry,
    Student,
    StudentBand,
    SyllabusTopic,
)
from app.schemas.checks import (
    CheckConfirmIn,
    CheckResultOut,
    ChecksOut,
    DailyCheckOut,
)
from app.services.ai import draft_checks

MAX_CLASS_WIDE = 2  # §5.5 volume cap


class RecommendationsService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return datetime.now(ZoneInfo(m.org.timezone)).date()

    def _cs(self, org_id: uuid.UUID, cs_id: uuid.UUID) -> ClassSubject:
        cs = self.db.scalar(
            select(ClassSubject).where(ClassSubject.id == cs_id, ClassSubject.org_id == org_id))
        if cs is None:
            raise NotFoundError("Class-subject")
        return cs

    def _can_capture(self, m: CurrentMember, cs: ClassSubject) -> None:
        if not (m.is_coordinator_up or cs.teacher_member_id == m.membership.id):
            raise ForbiddenError("You don't teach this class.", code="not_your_class")

    # ── inputs to the generator ──────────────────────────────────────────────
    def _planned_topic_title(self, org_id: uuid.UUID, cs_id: uuid.UUID, on_date: date) -> str | None:
        """The week's next un-logged planned topic for this class-subject (mirrors
        My Day's topic pick); falls back to the first planned topic."""
        monday = on_date - timedelta(days=on_date.weekday())
        planned = self.db.execute(
            select(PlanEntry.topic_id, SyllabusTopic.title)
            .join(SyllabusTopic, SyllabusTopic.id == PlanEntry.topic_id)
            .where(PlanEntry.org_id == org_id, PlanEntry.class_subject_id == cs_id,
                   PlanEntry.week_start == monday)
        ).all()
        if not planned:
            return None
        logged_ids = set(self.db.scalars(
            select(LessonLog.topic_id).where(LessonLog.class_subject_id == cs_id)))
        for tid, title in planned:
            if tid not in logged_ids:
                return title
        return planned[0][1]

    def _class_students(self, org_id: uuid.UUID, class_id: uuid.UUID) -> list[Student]:
        return list(self.db.scalars(
            select(Student).where(
                Student.org_id == org_id, Student.class_id == class_id,
                Student.status == "active")))

    def _current_tier(self, org_id: uuid.UUID, student_id: uuid.UUID) -> str | None:
        return self.db.scalar(
            select(StudentBand.tier).where(
                StudentBand.org_id == org_id, StudentBand.student_id == student_id,
                StudentBand.scope_skill_area_id.is_(None))
            .order_by(StudentBand.created_at.desc()).limit(1))

    def _intervention_students(
        self, org_id: uuid.UUID, students: list[Student],
    ) -> list[tuple[Student, str]]:
        """(student, goal_text) for students in this class with an active intervention."""
        by_id = {s.id: s for s in students}
        if not by_id:
            return []
        rows = self.db.execute(
            select(Intervention.student_id, Intervention.goal_text)
            .where(Intervention.org_id == org_id, Intervention.status == "active",
                   Intervention.student_id.in_(list(by_id)))
            .order_by(Intervention.created_at)
        ).all()
        out: list[tuple[Student, str]] = []
        seen: set[uuid.UUID] = set()
        for sid, goal in rows:  # ≤ 1 per intervention student (first active wins)
            if sid in seen:
                continue
            seen.add(sid)
            out.append((by_id[sid], goal))
        return out

    # ── generate-if-absent, then read ────────────────────────────────────────
    def ensure(self, m: CurrentMember, cs_id: uuid.UUID, on_date: date | None = None) -> ChecksOut:
        cs = self._cs(m.org_id, cs_id)
        self._can_capture(m, cs)
        d = on_date or self._today(m)

        existing = self.db.scalar(
            select(DailyCheck.id).where(
                DailyCheck.org_id == m.org_id, DailyCheck.class_subject_id == cs_id,
                DailyCheck.date == d).limit(1))
        if existing is None:
            self._generate(m, cs, d)
        return self._read(m, cs_id, d)

    def _generate(self, m: CurrentMember, cs: ClassSubject, d: date) -> None:
        students = self._class_students(m.org_id, cs.class_id)
        c_band = {s.id for s in students if self._current_tier(m.org_id, s.id) == "C"}
        topic = self._planned_topic_title(m.org_id, cs.id, d)
        source, drafted = draft_checks(topic, c_band_present=bool(c_band))

        # All generated checks are system-authored (source='ai'), whether the wording
        # came from a live model ('ai') or the deterministic fallback ('fixture').
        _ = source
        class_wide = 0
        for dc in drafted:
            if dc.band_scope == "all":
                if class_wide >= MAX_CLASS_WIDE:  # cap class-wide volume (§5.5)
                    continue
                class_wide += 1
            self.db.add(DailyCheck(
                org_id=m.org_id, class_subject_id=cs.id, date=d, description=dc.description,
                source="ai", band_scope=dc.band_scope))

        # ≤ 1 targeted check per intervention student in this class.
        for student, goal in self._intervention_students(m.org_id, students):
            tier = self._current_tier(m.org_id, student.id)
            self.db.add(DailyCheck(
                org_id=m.org_id, class_subject_id=cs.id, date=d,
                description=f"{student.full_name}: {goal}", source="ai",
                band_scope=tier if tier in ("A", "B", "C") else "all",
                student_id=student.id))
        self.db.flush()

    def _read(self, m: CurrentMember, cs_id: uuid.UUID, d: date) -> ChecksOut:
        checks = list(self.db.scalars(
            select(DailyCheck).where(
                DailyCheck.org_id == m.org_id, DailyCheck.class_subject_id == cs_id,
                DailyCheck.date == d)
            .options(selectinload(DailyCheck.results))
            .order_by(DailyCheck.created_at)))
        # Resolve names for targeted checks + all result rows in one pass.
        need_ids: set[uuid.UUID] = set()
        for c in checks:
            if c.student_id:
                need_ids.add(c.student_id)
            need_ids.update(r.student_id for r in c.results)
        names = dict(self.db.execute(
            select(Student.id, Student.full_name).where(Student.id.in_(need_ids))).all()
        ) if need_ids else {}

        out = [
            DailyCheckOut(
                id=c.id, description=c.description, source=c.source, band_scope=c.band_scope,
                student_id=c.student_id, student_name=names.get(c.student_id) if c.student_id else None,
                confirmed=c.confirmed_at is not None,
                results=[CheckResultOut(
                    student_id=r.student_id, full_name=names.get(r.student_id, "—"),
                    status=r.status, note=r.note) for r in c.results])
            for c in checks
        ]
        return ChecksOut(class_subject_id=cs_id, date=d, checks=out)

    # ── confirm "class did it ✓" + exceptions ────────────────────────────────
    def confirm(self, m: CurrentMember, check_id: uuid.UUID, body: CheckConfirmIn) -> DailyCheckOut:
        check = self.db.scalar(
            select(DailyCheck).where(DailyCheck.id == check_id, DailyCheck.org_id == m.org_id)
            .options(selectinload(DailyCheck.results)))
        if check is None:
            raise NotFoundError("Check")
        cs = self._cs(m.org_id, check.class_subject_id)
        self._can_capture(m, cs)
        roster_ids = {s.id for s in self._class_students(m.org_id, cs.class_id)}

        check.confirmed_at = datetime.now(UTC)
        check.confirmed_by = m.membership.id
        # Full-replace the exception set via the relationship so the in-memory
        # (identity-mapped) collection stays correct for the read below.
        check.results.clear()  # cascade delete-orphan removes the old rows
        for e in body.exceptions:
            if e.student_id not in roster_ids:
                continue
            check.results.append(CheckResult(
                org_id=m.org_id, student_id=e.student_id, status=e.status, note=e.note))
        self.db.flush()
        checks = self._read(m, check.class_subject_id, check.date).checks
        return next(c for c in checks if c.id == check.id)
