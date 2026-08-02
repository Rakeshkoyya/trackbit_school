"""Assessments & bands (M3, SPRD §5.3).

TrackBit records the school's own paper tests — it never authors them (§8). Bands
are private (P4), append-only. Suggestions come from the scores; a human confirms.
Activating an intervention spins its checklist into class-teacher tasks (M5).
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.exams import normalise_scale, type_label
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AssessmentCycle,
    AssessmentScore,
    ExamType,
    Intervention,
    InterventionItem,
    Membership,
    Organization,
    SchoolClass,
    SkillArea,
    Student,
    StudentBand,
    Subject,
    TaskInstance,
    Term,
    User,
)
from app.schemas.assessments import (
    AnalysisCyclePoint,
    AnalysisMover,
    BandConfig,
    ClassAnalysis,
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


def _tier_for(pct: float, a_min: int = 75, b_min: int = 50) -> str:
    """pct is a 0–1 fraction; thresholds are the org's configured percentages."""
    p = pct * 100
    return "A" if p >= a_min else "B" if p >= b_min else "C"


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
        term_id = body.term_id
        if term_id is None:
            # Quick create (daily tests): derive the term covering the date.
            term_id = self.db.scalar(select(Term.id).where(
                Term.org_id == m.org_id, Term.start_date <= body.date,
                Term.end_date >= body.date).order_by(Term.start_date.desc()).limit(1))
            if term_id is None:
                raise ValidationError("No term covers that date — set up terms first.",
                                      code="no_term")
        elif not self.db.scalar(select(Term.id).where(
                Term.id == term_id, Term.org_id == m.org_id)):
            raise NotFoundError("Term")
        if body.class_id and not self.db.scalar(select(SchoolClass.id).where(
                SchoolClass.id == body.class_id, SchoolClass.org_id == m.org_id)):
            raise NotFoundError("Class")
        if body.subject_id and not self.db.scalar(select(Subject.id).where(
                Subject.id == body.subject_id, Subject.org_id == m.org_id)):
            raise NotFoundError("Subject")
        if not m.is_coordinator_up:
            # A teacher may only quick-create a class-scoped daily test they teach.
            if body.type != "daily_test" or body.class_id is None:
                raise ForbiddenError("Only admins create org-wide cycles.", code="admin_only")
            from app.services.periods import assert_can_take_class  # noqa: PLC0415
            assert_can_take_class(self.db, m, body.class_id, None)
        cycle = AssessmentCycle(org_id=m.org_id, term_id=term_id, type=body.type,
                                name=body.name, date=body.date,
                                class_id=body.class_id, subject_id=body.subject_id)
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
            q = select(Subject).where(Subject.org_id == m.org_id).order_by(Subject.name)
            if cycle.subject_id:  # subject-scoped cycle (daily test): one column
                q = q.where(Subject.id == cycle.subject_id)
            cols = [GridColumn(id=s.id, name=s.name, kind="subject")
                    for s in self.db.scalars(q)]
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
        cycle = self._cycle(m, cycle_id)
        # V1-8 (`D-53`): the lock is the record, on every write path into a
        # cycle — not just the exam screen's. A guard on one door is a door.
        if cycle.locked_at is not None:
            raise ValidationError(
                "This exam is locked. An admin can unlock it with a reason.",
                code="exam_locked")
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
    # `_latest_pcts` / `_current_tiers` are **deleted** (V1-9). Both existed to
    # serve the one-tap re-band and the overall letter: the first took whatever
    # test happened last, and the second filtered for the *overall* band row that
    # `D-75` retires. Per-subject reads live in `BandService.placements` — one
    # implementation, so the directory chip, the class donut, the daily-check
    # generator and the report card cannot disagree about a child's band.

    # ── band config (SC-5) ───────────────────────────────────────────────────
    def band_config(self, m: CurrentMember) -> BandConfig:
        org = self.db.get(Organization, m.org_id)
        return BandConfig(a_min=org.band_a_min, b_min=org.band_b_min)

    def set_band_config(self, m: CurrentMember, body: BandConfig) -> BandConfig:
        if body.b_min >= body.a_min:
            raise ValidationError("The B threshold must be below the A threshold.")
        org = self.db.get(Organization, m.org_id)
        org.band_a_min = body.a_min
        org.band_b_min = body.b_min
        self.db.flush()
        return self.band_config(m)

    def band_board(self, m: CurrentMember, class_id: uuid.UUID, subject_id: uuid.UUID,
                   term_id: uuid.UUID | None = None, cycle_id: uuid.UUID | None = None):
        """Assess a class **for one subject** (`D-75`). Delegates to
        `BandService` so there is exactly one place a band is read."""
        from app.services.bands import BandService  # noqa: PLC0415

        return BandService(self.db).class_board(m, class_id, subject_id, cycle_id, term_id)

    # `S-183`: `apply_band_suggestions` is **deleted**, not deprecated. It
    # re-banded a class from *each child's most recent cycle, whatever it was* —
    # a Tuesday slip test could move eleven children between support tiers. With
    # `D-76`'s explicit promotion there are no longer two paths to one outcome,
    # and the unchosen one was the dangerous one.
    #
    # `categorize_from_cycle` is gone for the same reason: one tap, no preview,
    # one overall letter. Its replacement is `BandService.promote_preview` →
    # `promote` — per subject (`D-75`), locked-only (`S-184`), and showing the
    # moves before they commit (`Q-81`), because `student_bands` is append-only
    # and a child slipping B → C is the most consequential thing this module does.

    def current_band_map(self, m: CurrentMember) -> dict[str, str]:
        """student_id -> **"C · Hindi"** — the lowest band a child holds, named
        with the subject that earned it (`S-186`).

        Staff-only surfaces (directory chips, filters); P4 keeps it off anything
        guardian-facing. There is no overall letter to return any more (`D-75`),
        and a chip that averaged across subjects would be one."""
        from app.services.bands import BandService  # noqa: PLC0415

        return BandService(self.db).chip_map(m)

    def set_band(self, m: CurrentMember, body) -> None:
        # Append-only — a new row per change keeps the movement history (P4).
        if not self.db.scalar(select(Student.id).where(
                Student.id == body.student_id, Student.org_id == m.org_id)):
            raise NotFoundError("Student")
        self.db.add(StudentBand(
            org_id=m.org_id, student_id=body.student_id, term_id=body.term_id, tier=body.tier,
            subject_id=body.subject_id, source=body.source,
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

    def class_analysis(self, m: CurrentMember, class_id: uuid.UUID) -> ClassAnalysis:
        """The class at a glance (SC-4): per-cycle averages, band distribution,
        biggest movers between the last two test cycles, latest-test histogram.
        Everything is computed from scores already captured — no new capture —
        and batched into four queries (remote-DB latency rule)."""
        students = list(self.db.scalars(
            select(Student).where(Student.org_id == m.org_id, Student.class_id == class_id,
                                  Student.status == "active")))
        sids = [s.id for s in students]
        names = {s.id: s.full_name for s in students}

        # V1-9 (`D-75`): there is no overall letter to count. These are band
        # **placements** — one per (child × monitored subject) — and the screen
        # labels them as such. Counting children instead would mean inventing a
        # blend, which is the defect this packet removes.
        from app.services.bands import BandService  # noqa: PLC0415

        places = BandService(self.db).placements(m, sids)
        band_counts = {"A": 0, "B": 0, "C": 0, "unset": 0}
        for sid in sids:
            mine = places.get(sid) or []
            if not mine:
                band_counts["unset"] += 1
            for p in mine:
                band_counts[p.tier] += 1

        rows = []
        if sids:
            rows = self.db.execute(
                select(AssessmentScore.student_id, AssessmentScore.score,
                       AssessmentScore.max_score, AssessmentScore.subject_id,
                       AssessmentCycle.id, AssessmentCycle.name, AssessmentCycle.date,
                       AssessmentCycle.type, AssessmentCycle.scale, ExamType.name)
                .join(AssessmentCycle, AssessmentCycle.id == AssessmentScore.cycle_id)
                .outerjoin(ExamType, ExamType.id == AssessmentCycle.exam_type_id)
                .where(AssessmentScore.org_id == m.org_id,
                       AssessmentScore.student_id.in_(sids),
                       AssessmentScore.subject_id.isnot(None))).all()
        subject_names = {s.id: s.name for s in self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id))}

        # cycle -> {meta, per-subject sums, per-student sums}
        cycles: dict[uuid.UUID, dict] = {}
        for sid, score, mx, subj_id, cid, cname, cdate, ctype, cscale, own_name in rows:
            c = cycles.setdefault(cid, {
                "name": cname, "date": cdate, "type": ctype,
                # V1-8 (`S-114`): the point carries its scale, so the chart can
                # keep a slip test and a term exam on separate lines instead of
                # drawing one trajectory through both.
                "scale": normalise_scale(cscale, ctype),
                "type_label": own_name or type_label(ctype),
                "subj": {}, "students": {}, "tot": [0.0, 0.0]})
            s, x = float(score), float(mx)
            c["tot"][0] += s
            c["tot"][1] += x
            sub = c["subj"].setdefault(subj_id, [0.0, 0.0])
            sub[0] += s
            sub[1] += x
            st = c["students"].setdefault(sid, [0.0, 0.0])
            st[0] += s
            st[1] += x

        def pct(pair: list[float]) -> float | None:
            return round(pair[0] / pair[1] * 100, 1) if pair[1] else None

        ordered = sorted(cycles.items(), key=lambda kv: (kv[1]["date"], str(kv[0])))
        points = [AnalysisCyclePoint(
            cycle_id=cid, name=c["name"], date=c["date"], type=c["type"],
            scale=c["scale"], type_label=c["type_label"],
            avg_pct=pct(c["tot"]),
            subjects=[{"subject_id": str(sub_id), "name": subject_names.get(sub_id, "?"),
                       "avg_pct": pct(pair)}
                      for sub_id, pair in sorted(
                          c["subj"].items(), key=lambda kv: subject_names.get(kv[0], ""))],
        ) for cid, c in ordered]

        movers: list[AnalysisMover] = []
        histogram: list[dict] = []
        latest_name: str | None = None
        if ordered:
            latest = ordered[-1][1]
            latest_name = latest["name"]
            buckets = [0, 0, 0, 0]  # <25, <50, <75, ≤100
            for pair in latest["students"].values():
                p = pct(pair)
                if p is not None:
                    buckets[min(3, int(p // 25))] += 1
            histogram = [{"bucket": b, "count": n} for b, n in
                         zip(["0–25%", "25–50%", "50–75%", "75–100%"], buckets, strict=True)]
            # `S-114`: a "mover" compares like with like. Measuring a term exam
            # against yesterday's slip test produces a dramatic delta about
            # nothing — and it is the delta an admin acts on.
            same_scale = [kv for kv in ordered[:-1] if kv[1]["scale"] == latest["scale"]]
            if same_scale:
                prev = same_scale[-1][1]
                for sid, pair in latest["students"].items():
                    p_now, p_prev = pct(pair), pct(prev["students"].get(sid, [0.0, 0.0]))
                    if p_now is not None and p_prev is not None:
                        movers.append(AnalysisMover(
                            student_id=sid, full_name=names.get(sid, "?"),
                            latest_pct=p_now, prev_pct=p_prev,
                            delta=round(p_now - p_prev, 1)))
                movers.sort(key=lambda mv: mv.delta)

        return ClassAnalysis(class_id=class_id, band_counts=band_counts, cycles=points,
                             movers=movers, histogram=histogram,
                             latest_cycle_name=latest_name)

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
        """A support plan for one child **in one subject** (`D-77`).

        Three V1-9 changes, and each closes a defect the module could not
        function with:

        * **the owner** (`D-71`/`S-168`) — it defaulted to
          `school_classes.class_teacher_member_id`, which no screen set until
          V1-2, so every intervention in every real school was created
          unassigned. It now defaults to the **subject teacher** of the child's
          class and is explicit on the payload.
        * **the exit criterion** (`S-167`) — written when the child enters, not
          judged when the term ends.
        * **the board is optional** (§4.6) — the sheet used to ask a teacher to
          pick a task board from a dropdown of the school's whole data model, in
          the middle of a conversation about a child.
        """
        student = self.db.scalar(select(Student).where(
            Student.id == body.student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        from app.services.bands import BandService  # noqa: PLC0415

        owner_member_id = body.owner_member_id
        if owner_member_id is None and body.subject_id is not None:
            owner_member_id = BandService(self.db)._default_owner(  # noqa: SLF001
                m, student, body.subject_id)
        intervention = Intervention(
            org_id=m.org_id, student_id=body.student_id, term_id=body.term_id,
            subject_id=body.subject_id, owner_member_id=owner_member_id,
            goal_text=body.goal_text, exit_criterion=body.exit_criterion,
            target_tier=body.target_tier)
        self.db.add(intervention)
        self.db.flush()
        # The checklist tasks go to the owner — the person actually answerable
        # for this child in this subject — falling back to the class teacher.
        assignee = None
        if owner_member_id:
            mem = self.db.get(Membership, owner_member_id)
            assignee = mem.user_id if mem else None
        if assignee is None and student.class_id:
            klass = self.db.get(SchoolClass, student.class_id)
            if klass and klass.class_teacher_member_id:
                mem = self.db.get(Membership, klass.class_teacher_member_id)
                assignee = mem.user_id if mem else None
        if body.items and body.board_id:
            task_svc = TaskService(self.db)
            for text in body.items:
                item = InterventionItem(org_id=m.org_id, intervention_id=intervention.id,
                                        text=text)
                self.db.add(item)
                self.db.flush()
                task = task_svc.create(m, TaskCreateRequest(
                    board_id=body.board_id, title=f"{student.full_name}: {text}",
                    description=f"Intervention goal: {body.goal_text}",
                    category="Intervention", assignee_id=assignee))
                item.task_instance_id = task.id
        elif body.items:
            for text in body.items:
                self.db.add(InterventionItem(
                    org_id=m.org_id, intervention_id=intervention.id, text=text))
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
        subject_name = self.db.scalar(select(Subject.name).where(
            Subject.id == iv.subject_id)) if iv.subject_id else None
        owner_name = self.db.scalar(
            select(User.name).join(Membership, Membership.user_id == User.id)
            .where(Membership.id == iv.owner_member_id)) if iv.owner_member_id else None
        return InterventionOut(
            id=iv.id, student_id=iv.student_id, subject_id=iv.subject_id,
            subject_name=subject_name, owner_member_id=iv.owner_member_id,
            owner_name=owner_name, goal_text=iv.goal_text,
            exit_criterion=iv.exit_criterion, target_tier=iv.target_tier,
            status=iv.status, closed_at=iv.closed_at, outcome_note=iv.outcome_note,
            items=items)

    def student_interventions(self, m: CurrentMember, student_id: uuid.UUID) -> list[InterventionOut]:
        ivs = self.db.scalars(select(Intervention.id).where(
            Intervention.org_id == m.org_id, Intervention.student_id == student_id)
            .order_by(Intervention.created_at.desc()))
        return [self._intervention_out(m, iid) for iid in ivs]
