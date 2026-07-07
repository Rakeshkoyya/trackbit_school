"""Assessments & bands (M3, SPRD §5.3).

TrackBit records the school's own paper tests — it never authors them (§8). Bands
are private (P4), append-only. Suggestions come from the scores; a human confirms.
Activating an intervention spins its checklist into class-teacher tasks (M5).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    AssessmentCycle,
    AssessmentScore,
    Intervention,
    InterventionItem,
    Membership,
    SchoolClass,
    SkillArea,
    Student,
    StudentBand,
    Subject,
    TaskInstance,
    Term,
)
from app.schemas.assessments import (
    BandBoard,
    BandRow,
    CycleCreate,
    CycleOut,
    GridCell,
    GridColumn,
    InterventionCreate,
    InterventionItemOut,
    InterventionOut,
    ScoreGrid,
    ScoresBulkIn,
    SkillAreaOut,
    SkillProfile,
    SkillProfileCycle,
    SubjectTrend,
)
from app.schemas.task import TaskCreateRequest
from app.services.task import TaskService

DEFAULT_SKILLS = ("Reading", "Writing", "Speaking", "Math")
WEAK_DROP = 0.10  # a >10pt class-average drop across cycles flags a weak subject


def _tier_for(pct: float) -> str:
    return "A" if pct >= 0.75 else "B" if pct >= 0.5 else "C"


class AssessmentService:
    def __init__(self, db: Session):
        self.db = db

    # ── skill areas ──────────────────────────────────────────────────────────
    def list_skills(self, m: CurrentMember) -> list[SkillAreaOut]:
        rows = self.db.scalars(
            select(SkillArea).where(SkillArea.org_id == m.org_id, SkillArea.active.is_(True))
            .order_by(SkillArea.position, SkillArea.name))
        return [SkillAreaOut.model_validate(r) for r in rows]

    def ensure_default_skills(self, m: CurrentMember) -> list[SkillAreaOut]:
        existing = {s.name for s in self.db.scalars(
            select(SkillArea).where(SkillArea.org_id == m.org_id))}
        for i, name in enumerate(DEFAULT_SKILLS):
            if name not in existing:
                self.db.add(SkillArea(org_id=m.org_id, name=name, position=i))
        self.db.flush()
        return self.list_skills(m)

    def create_skill(self, m: CurrentMember, name: str) -> SkillAreaOut:
        if self.db.scalar(select(SkillArea.id).where(
                SkillArea.org_id == m.org_id, SkillArea.name == name)):
            raise ValidationError(f"“{name}” already exists.")
        pos = self.db.scalar(select(func.count()).select_from(SkillArea).where(
            SkillArea.org_id == m.org_id)) or 0
        sa = SkillArea(org_id=m.org_id, name=name, position=pos)
        self.db.add(sa)
        self.db.flush()
        return SkillAreaOut.model_validate(sa)

    def delete_skill(self, m: CurrentMember, skill_id: uuid.UUID) -> None:
        sa = self.db.scalar(select(SkillArea).where(
            SkillArea.id == skill_id, SkillArea.org_id == m.org_id))
        if sa is None:
            raise NotFoundError("Skill area")
        self.db.delete(sa)

    # ── cycles ───────────────────────────────────────────────────────────────
    def list_cycles(self, m: CurrentMember, term_id: uuid.UUID | None) -> list[CycleOut]:
        q = select(AssessmentCycle).where(AssessmentCycle.org_id == m.org_id).order_by(
            AssessmentCycle.date.desc())
        if term_id:
            q = q.where(AssessmentCycle.term_id == term_id)
        return [CycleOut.model_validate(c) for c in self.db.scalars(q)]

    def create_cycle(self, m: CurrentMember, body: CycleCreate) -> CycleOut:
        if not self.db.scalar(select(Term.id).where(
                Term.id == body.term_id, Term.org_id == m.org_id)):
            raise NotFoundError("Term")
        cycle = AssessmentCycle(org_id=m.org_id, term_id=body.term_id, type=body.type,
                                name=body.name, date=body.date)
        self.db.add(cycle)
        self.db.flush()
        return CycleOut.model_validate(cycle)

    def delete_cycle(self, m: CurrentMember, cycle_id: uuid.UUID) -> None:
        c = self.db.scalar(select(AssessmentCycle).where(
            AssessmentCycle.id == cycle_id, AssessmentCycle.org_id == m.org_id))
        if c is None:
            raise NotFoundError("Cycle")
        self.db.delete(c)

    def _cycle(self, m: CurrentMember, cycle_id: uuid.UUID) -> AssessmentCycle:
        c = self.db.scalar(select(AssessmentCycle).where(
            AssessmentCycle.id == cycle_id, AssessmentCycle.org_id == m.org_id))
        if c is None:
            raise NotFoundError("Cycle")
        return c

    # ── score grid / intake / verify ─────────────────────────────────────────
    def grid(self, m: CurrentMember, cycle_id: uuid.UUID, class_id: uuid.UUID) -> ScoreGrid:
        cycle = self._cycle(m, cycle_id)
        if cycle.type == "diagnostic":
            cols = [GridColumn(id=s.id, name=s.name, kind="skill") for s in self.list_skills(m)]
        else:
            subs = self.db.scalars(select(Subject).where(Subject.org_id == m.org_id)
                                   .order_by(Subject.name))
            cols = [GridColumn(id=s.id, name=s.name, kind="subject") for s in subs]
        students = list(self.db.scalars(
            select(Student).where(Student.org_id == m.org_id, Student.class_id == class_id)
            .order_by(Student.full_name)))
        sids = [s.id for s in students]
        cells: list[GridCell] = []
        if sids:
            for sc in self.db.scalars(select(AssessmentScore).where(
                    AssessmentScore.org_id == m.org_id, AssessmentScore.cycle_id == cycle_id,
                    AssessmentScore.student_id.in_(sids))):
                col = sc.subject_id or sc.skill_area_id
                cells.append(GridCell(student_id=sc.student_id, column_id=col,
                                      score=float(sc.score), max_score=float(sc.max_score)))
        verified = self.db.scalar(select(AssessmentScore.verified_by).where(
            AssessmentScore.cycle_id == cycle_id, AssessmentScore.verified_by.isnot(None)).limit(1))
        return ScoreGrid(
            cycle_id=cycle_id, cycle_type=cycle.type, verified=verified is not None,
            columns=cols, students=[{"student_id": str(s.id), "full_name": s.full_name} for s in students],
            cells=cells)

    def save_scores(self, m: CurrentMember, cycle_id: uuid.UUID, body: ScoresBulkIn) -> ScoreGrid | None:
        self._cycle(m, cycle_id)
        for r in body.rows:
            if (r.subject_id is None) == (r.skill_area_id is None):
                raise ValidationError("Each score needs exactly one of subject/skill.")
            existing = self.db.scalar(select(AssessmentScore).where(
                AssessmentScore.org_id == m.org_id, AssessmentScore.cycle_id == cycle_id,
                AssessmentScore.student_id == r.student_id,
                (AssessmentScore.subject_id == r.subject_id) if r.subject_id
                else AssessmentScore.subject_id.is_(None),
                (AssessmentScore.skill_area_id == r.skill_area_id) if r.skill_area_id
                else AssessmentScore.skill_area_id.is_(None)))
            if existing:
                existing.score = r.score
                existing.max_score = r.max_score
            else:
                self.db.add(AssessmentScore(
                    org_id=m.org_id, cycle_id=cycle_id, student_id=r.student_id,
                    subject_id=r.subject_id, skill_area_id=r.skill_area_id,
                    score=r.score, max_score=r.max_score, entered_by=m.user_id))
        self.db.flush()
        return None

    def verify(self, m: CurrentMember, cycle_id: uuid.UUID) -> ScoreGrid | None:
        self._cycle(m, cycle_id)
        for sc in self.db.scalars(select(AssessmentScore).where(
                AssessmentScore.org_id == m.org_id, AssessmentScore.cycle_id == cycle_id)):
            sc.verified_by = m.user_id
        self.db.flush()
        return None

    # ── bands ────────────────────────────────────────────────────────────────
    def _latest_pct(self, m: CurrentMember, student_id: uuid.UUID) -> float | None:
        """Average pct across the student's most recent cycle with scores."""
        latest = self.db.execute(
            select(AssessmentCycle.id).join(
                AssessmentScore, AssessmentScore.cycle_id == AssessmentCycle.id)
            .where(AssessmentCycle.org_id == m.org_id, AssessmentScore.student_id == student_id)
            .order_by(AssessmentCycle.date.desc()).limit(1)).scalar_one_or_none()
        if latest is None:
            return None
        rows = list(self.db.execute(
            select(AssessmentScore.score, AssessmentScore.max_score).where(
                AssessmentScore.cycle_id == latest, AssessmentScore.student_id == student_id)).all())
        tot = sum(float(mx) for _, mx in rows)
        return round(sum(float(s) for s, _ in rows) / tot, 4) if tot else None

    def band_board(self, m: CurrentMember, class_id: uuid.UUID, term_id: uuid.UUID | None) -> BandBoard:
        students = list(self.db.scalars(
            select(Student).where(Student.org_id == m.org_id, Student.class_id == class_id)
            .order_by(Student.full_name)))
        rows: list[BandRow] = []
        for st in students:
            current = self.db.scalar(
                select(StudentBand.tier).where(
                    StudentBand.org_id == m.org_id, StudentBand.student_id == st.id,
                    StudentBand.scope_skill_area_id.is_(None),
                    *([StudentBand.term_id == term_id] if term_id else []))
                .order_by(StudentBand.created_at.desc()).limit(1))
            pct = self._latest_pct(m, st.id)
            rows.append(BandRow(
                student_id=st.id, full_name=st.full_name, current_tier=current,
                suggested_tier=_tier_for(pct) if pct is not None else None,
                latest_pct=round(pct * 100, 1) if pct is not None else None))
        return BandBoard(class_id=class_id, term_id=term_id, rows=rows)

    def set_band(self, m: CurrentMember, body) -> None:
        # Append-only — a new row per change keeps the movement history (P4).
        if not self.db.scalar(select(Student.id).where(
                Student.id == body.student_id, Student.org_id == m.org_id)):
            raise NotFoundError("Student")
        self.db.add(StudentBand(
            org_id=m.org_id, student_id=body.student_id, term_id=body.term_id, tier=body.tier,
            scope_skill_area_id=body.scope_skill_area_id, set_by=m.user_id, note=body.note))
        self.db.flush()

    def band_history(self, m: CurrentMember, student_id: uuid.UUID) -> list[StudentBand]:
        return list(self.db.scalars(
            select(StudentBand).where(
                StudentBand.org_id == m.org_id, StudentBand.student_id == student_id)
            .order_by(StudentBand.created_at.desc())))

    # ── skill profile + trends ───────────────────────────────────────────────
    def skill_profile(self, m: CurrentMember, student_id: uuid.UUID) -> SkillProfile:
        skills = {s.id: s.name for s in self.db.scalars(
            select(SkillArea).where(SkillArea.org_id == m.org_id))}
        cycles = list(self.db.scalars(
            select(AssessmentCycle).where(
                AssessmentCycle.org_id == m.org_id, AssessmentCycle.type == "diagnostic")
            .order_by(AssessmentCycle.date)))
        out_cycles: list[SkillProfileCycle] = []
        for c in cycles:
            scores = {}
            for sc in self.db.scalars(select(AssessmentScore).where(
                    AssessmentScore.cycle_id == c.id, AssessmentScore.student_id == student_id,
                    AssessmentScore.skill_area_id.isnot(None))):
                name = skills.get(sc.skill_area_id)
                if name and float(sc.max_score):
                    scores[name] = round(float(sc.score) / float(sc.max_score) * 100, 1)
            if scores:
                out_cycles.append(SkillProfileCycle(cycle_id=c.id, name=c.name, date=c.date, scores=scores))
        return SkillProfile(student_id=student_id, skills=list(skills.values()), cycles=out_cycles)

    def trends(self, m: CurrentMember, class_id: uuid.UUID) -> list[SubjectTrend]:
        sids = [s for s in self.db.scalars(select(Student.id).where(
            Student.org_id == m.org_id, Student.class_id == class_id))]
        subjects = {s.id: s.name for s in self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id))}
        out: list[SubjectTrend] = []
        if not sids:
            return out
        for subj_id, subj_name in subjects.items():
            rows = self.db.execute(
                select(AssessmentCycle.name, AssessmentCycle.date,
                       func.sum(AssessmentScore.score), func.sum(AssessmentScore.max_score))
                .join(AssessmentScore, AssessmentScore.cycle_id == AssessmentCycle.id)
                .where(AssessmentScore.org_id == m.org_id, AssessmentScore.subject_id == subj_id,
                       AssessmentScore.student_id.in_(sids))
                .group_by(AssessmentCycle.id, AssessmentCycle.name, AssessmentCycle.date)
                .order_by(AssessmentCycle.date)).all()
            points = [{"cycle_name": name, "date": str(d),
                       "avg_pct": round(float(sc) / float(mx) * 100, 1) if mx else 0}
                      for name, d, sc, mx in rows]
            weak = len(points) >= 2 and points[-1]["avg_pct"] < points[-2]["avg_pct"] - WEAK_DROP * 100
            if points:
                out.append(SubjectTrend(subject_id=subj_id, subject_name=subj_name,
                                        points=points, weak=weak))
        return out

    def weak_subjects(self, m: CurrentMember) -> list[SubjectTrend]:
        """Weak subjects across all classes (fed to the director dashboard)."""
        out: list[SubjectTrend] = []
        for cid in self.db.scalars(select(SchoolClass.id).where(SchoolClass.org_id == m.org_id)):
            out.extend(t for t in self.trends(m, cid) if t.weak)
        return out

    # ── interventions (spawn M5 tasks) ───────────────────────────────────────
    def create_intervention(self, m: CurrentMember, body: InterventionCreate) -> InterventionOut:
        student = self.db.scalar(select(Student).where(
            Student.id == body.student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        intervention = Intervention(
            org_id=m.org_id, student_id=body.student_id, term_id=body.term_id,
            goal_text=body.goal_text, target_tier=body.target_tier)
        self.db.add(intervention)
        self.db.flush()
        # Assign the checklist tasks to the class teacher (if set).
        assignee = None
        if student.class_id:
            klass = self.db.get(SchoolClass, student.class_id)
            if klass and klass.class_teacher_member_id:
                mem = self.db.get(Membership, klass.class_teacher_member_id)
                assignee = mem.user_id if mem else None
        task_svc = TaskService(self.db)
        for text in body.items:
            item = InterventionItem(org_id=m.org_id, intervention_id=intervention.id, text=text)
            self.db.add(item)
            self.db.flush()
            task = task_svc.create(m, TaskCreateRequest(
                board_id=body.board_id, title=f"{student.full_name}: {text}",
                description=f"Intervention goal: {body.goal_text}", category="Intervention",
                assignee_id=assignee))
            item.task_instance_id = task.id
        self.db.flush()
        return self._intervention_out(m, intervention.id)

    def _intervention_out(self, m: CurrentMember, intervention_id: uuid.UUID) -> InterventionOut:
        iv = self.db.scalar(select(Intervention).where(
            Intervention.id == intervention_id, Intervention.org_id == m.org_id)
            .options(selectinload(Intervention.items)))
        if iv is None:
            raise NotFoundError("Intervention")
        done_ids = set(self.db.scalars(select(TaskInstance.id).where(
            TaskInstance.id.in_([i.task_instance_id for i in iv.items if i.task_instance_id]),
            TaskInstance.status == "done"))) if iv.items else set()
        items = [InterventionItemOut(id=i.id, text=i.text, task_instance_id=i.task_instance_id,
                                     done=i.task_instance_id in done_ids) for i in iv.items]
        return InterventionOut(id=iv.id, student_id=iv.student_id, goal_text=iv.goal_text,
                               target_tier=iv.target_tier, status=iv.status, items=items)

    def student_interventions(self, m: CurrentMember, student_id: uuid.UUID) -> list[InterventionOut]:
        ivs = self.db.scalars(select(Intervention.id).where(
            Intervention.org_id == m.org_id, Intervention.student_id == student_id)
            .order_by(Intervention.created_at.desc()))
        return [self._intervention_out(m, iid) for iid in ivs]
