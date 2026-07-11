"""Student growth report (teacher-view redesign, 2026-07) — a COMPUTED join, no
new capture tables beyond lesson_observations.

Chapter-level analysis is the default reading; the payload nests topic rows under
each chapter so the UI drills to topic level without another call. Everything is
derived from what teachers already capture in the daily flow (P5): attendance
exceptions, lesson logs, homework, check results, deep-log observations, and
verified assessment scores.

Access: admin sees every student; a teacher only students in classes they teach.
Bands appear because this is a staff-only surface — it must never feed any
guardian-facing message (P4).
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AssessmentCycle,
    AssessmentScore,
    AttendanceException,
    CheckResult,
    ClassPeriod,
    ClassSubject,
    DailyCheck,
    HomeworkAssignment,
    LessonLog,
    LessonObservation,
    Membership,
    SchoolClass,
    SkillArea,
    Student,
    StudentBand,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    User,
)
from app.schemas.growth import (
    GrowthAttendance,
    GrowthBandEntry,
    GrowthChapter,
    GrowthObservation,
    GrowthScore,
    GrowthSkill,
    GrowthSubject,
    GrowthTopic,
    StudentGrowthOut,
)

_LOW_ATTENDANCE_PCT = 85.0
_LOW_SCORE_PCT = 40.0


def _pct(part: int, whole: int) -> float | None:
    return round(part * 100.0 / whole, 1) if whole else None


class GrowthService:
    def __init__(self, db: Session):
        self.db = db

    def _assert_can_view(self, m: CurrentMember, student: Student) -> None:
        """Admin, or a teacher with a subject in the student's class (SPRD2 §2)."""
        if m.is_coordinator_up:
            return
        if student.class_id is not None:
            teaches = self.db.scalar(select(ClassSubject.id).where(
                ClassSubject.org_id == m.org_id, ClassSubject.class_id == student.class_id,
                ClassSubject.teacher_member_id == m.membership.id).limit(1))
            if teaches is not None:
                return
        raise ForbiddenError("You can view reports only for students you teach.",
                             code="not_your_student")

    def growth(self, m: CurrentMember, student_id: uuid.UUID) -> StudentGrowthOut:
        student = self.db.scalar(select(Student).where(
            Student.id == student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        self._assert_can_view(m, student)

        klass = self.db.get(SchoolClass, student.class_id) if student.class_id else None
        class_label = (klass.name + (f"-{klass.section}" if klass.section else "")
                       if klass else None)
        band, band_history = self._bands(m.org_id, student.id)
        out = StudentGrowthOut(
            student_id=student.id, full_name=student.full_name, class_label=class_label,
            band=band, band_history=band_history, attendance=GrowthAttendance())
        if klass is None:
            return out

        cs_rows = self.db.execute(
            select(ClassSubject, Subject.name, User.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .outerjoin(Membership, Membership.id == ClassSubject.teacher_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .where(ClassSubject.org_id == m.org_id, ClassSubject.class_id == klass.id)
            .order_by(Subject.name)).all()
        cs_ids = [cs.id for cs, _, _ in cs_rows]

        # ── attendance: every marked period of the class + this student's
        # exceptions, two queries total ─────────────────────────────────────────
        periods = list(self.db.scalars(select(ClassPeriod).where(
            ClassPeriod.org_id == m.org_id, ClassPeriod.class_id == klass.id,
            ClassPeriod.attendance_marked_at.is_not(None))))
        period_ids = [p.id for p in periods]
        exc_by_period: dict[uuid.UUID, str] = dict(self.db.execute(
            select(AttendanceException.period_id, AttendanceException.status)
            .where(AttendanceException.period_id.in_(period_ids),
                   AttendanceException.student_id == student.id)).all()) if period_ids else {}

        def att_for(subset: list[ClassPeriod]) -> GrowthAttendance:
            absent = sum(1 for p in subset if exc_by_period.get(p.id) == "absent")
            late = sum(1 for p in subset if exc_by_period.get(p.id) == "late")
            marked = len(subset)
            present = marked - absent  # late counts as present, like everywhere else
            return GrowthAttendance(marked_periods=marked, present=present, absent=absent,
                                    late=late, pct=_pct(present, marked))

        out.attendance = att_for(periods)
        periods_by_cs: dict[uuid.UUID, list[ClassPeriod]] = defaultdict(list)
        for p in periods:
            if p.class_subject_id is not None:
                periods_by_cs[p.class_subject_id].append(p)

        # ── syllabus + logs (chapter → topic), batched over all subjects ──────
        syl_rows = self.db.execute(
            select(SyllabusUnit, SyllabusTopic)
            .join(SyllabusTopic, SyllabusTopic.unit_id == SyllabusUnit.id, isouter=True)
            .where(SyllabusUnit.org_id == m.org_id,
                   SyllabusUnit.class_subject_id.in_(cs_ids))
            .order_by(SyllabusUnit.position, SyllabusTopic.position)).all() if cs_ids else []
        log_rows = self.db.execute(
            select(LessonLog.topic_id, LessonLog.coverage, LessonLog.date, LessonLog.period_id)
            .where(LessonLog.org_id == m.org_id, LessonLog.class_subject_id.in_(cs_ids),
                   LessonLog.topic_id.is_not(None))
            .order_by(LessonLog.date)).all() if cs_ids else []
        logs_by_topic: dict[uuid.UUID, list] = defaultdict(list)
        for tid, coverage, d, pid in log_rows:
            logs_by_topic[tid].append((coverage, d, pid))
        marked_period_by_id = {p.id: p for p in periods}

        def topic_row(topic: SyllabusTopic) -> GrowthTopic:
            logs = logs_by_topic.get(topic.id, [])
            status = "pending"
            taught_on: date | None = None
            attendance: str | None = None
            if logs:
                status = "done" if any(c == "full" for c, _, _ in logs) else "in_progress"
                taught_on = logs[-1][1]
                for _, _, pid in reversed(logs):
                    if pid in marked_period_by_id:
                        attendance = exc_by_period.get(pid) or "present"
                        break
            return GrowthTopic(topic_id=topic.id, title=topic.title, status=status,
                               taught_on=taught_on, student_attendance=attendance)

        chapters_by_cs: dict[uuid.UUID, list[GrowthChapter]] = defaultdict(list)
        chapter_by_unit: dict[uuid.UUID, GrowthChapter] = {}
        for unit, topic in syl_rows:
            ch = chapter_by_unit.get(unit.id)
            if ch is None:
                ch = GrowthChapter(unit_id=unit.id, title=unit.title,
                                   topics_total=0, topics_taught=0, topics_missed=0)
                chapter_by_unit[unit.id] = ch
                chapters_by_cs[unit.class_subject_id].append(ch)
            if topic is None:
                continue
            row = topic_row(topic)
            ch.topics.append(row)
            ch.topics_total += 1
            if row.status != "pending":
                ch.topics_taught += 1
            if row.student_attendance == "absent":
                ch.topics_missed += 1

        # ── homework, checks, observations, scores — one query each ───────────
        hw_rows = self.db.execute(
            select(HomeworkAssignment.class_subject_id, HomeworkAssignment.student_id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   HomeworkAssignment.class_subject_id.in_(cs_ids),
                   or_(HomeworkAssignment.student_id.is_(None),
                       HomeworkAssignment.student_id == student.id))).all() if cs_ids else []
        hw_assigned: dict[uuid.UUID, int] = defaultdict(int)
        hw_personal: dict[uuid.UUID, int] = defaultdict(int)
        for cs_id, sid in hw_rows:
            hw_assigned[cs_id] += 1
            if sid is not None:
                hw_personal[cs_id] += 1

        check_rows = self.db.execute(
            select(DailyCheck.class_subject_id, DailyCheck.description)
            .join(CheckResult, CheckResult.check_id == DailyCheck.id)
            .where(DailyCheck.org_id == m.org_id, DailyCheck.class_subject_id.in_(cs_ids),
                   CheckResult.student_id == student.id,
                   CheckResult.status == "not_done")).all() if cs_ids else []
        checks_flagged: dict[uuid.UUID, int] = defaultdict(int)
        for cs_id, _desc in check_rows:
            checks_flagged[cs_id] += 1

        obs_rows = list(self.db.scalars(
            select(LessonObservation)
            .where(LessonObservation.org_id == m.org_id,
                   LessonObservation.class_subject_id.in_(cs_ids),
                   LessonObservation.student_id == student.id)
            .order_by(LessonObservation.date))) if cs_ids else []
        obs_by_cs: dict[uuid.UUID, list[GrowthObservation]] = defaultdict(list)
        for o in obs_rows:
            obs_by_cs[o.class_subject_id].append(GrowthObservation(
                date=o.date, section=o.section, concept=o.concept,
                rating=o.rating or "needs_work", note=o.note))

        subject_ids = {cs.subject_id: cs.id for cs, _, _ in cs_rows}
        score_rows = self.db.execute(
            select(AssessmentScore, AssessmentCycle.name, AssessmentCycle.date)
            .join(AssessmentCycle, AssessmentCycle.id == AssessmentScore.cycle_id)
            .where(AssessmentScore.org_id == m.org_id,
                   AssessmentScore.student_id == student.id,
                   AssessmentScore.subject_id.in_(subject_ids))
            .order_by(AssessmentCycle.date)).all() if subject_ids else []
        scores_by_cs: dict[uuid.UUID, list[GrowthScore]] = defaultdict(list)
        for score, cyc_name, cyc_date in score_rows:
            scores_by_cs[subject_ids[score.subject_id]].append(GrowthScore(
                cycle_name=cyc_name, date=cyc_date,
                score=float(score.score), max_score=float(score.max_score)))

        for cs, subject_name, teacher_name in cs_rows:
            out.subjects.append(GrowthSubject(
                class_subject_id=cs.id, subject_name=subject_name, teacher_name=teacher_name,
                attendance=att_for(periods_by_cs.get(cs.id, [])),
                chapters=chapters_by_cs.get(cs.id, []),
                homework_assigned=hw_assigned.get(cs.id, 0),
                homework_personal=hw_personal.get(cs.id, 0),
                checks_flagged=checks_flagged.get(cs.id, 0),
                observations=obs_by_cs.get(cs.id, []),
                scores=scores_by_cs.get(cs.id, [])))

        out.skills = self._skills(m.org_id, student.id)
        out.growth_areas = self._growth_areas(out, obs_rows)
        return out

    def _bands(self, org_id: uuid.UUID, student_id: uuid.UUID,
               ) -> tuple[str | None, list[GrowthBandEntry]]:
        rows = list(self.db.scalars(
            select(StudentBand)
            .where(StudentBand.org_id == org_id, StudentBand.student_id == student_id,
                   StudentBand.scope_skill_area_id.is_(None))
            .order_by(StudentBand.created_at)))
        history = [GrowthBandEntry(tier=b.tier, set_on=b.created_at.date(), note=b.note)
                   for b in rows]
        return (rows[-1].tier if rows else None), history

    def _skills(self, org_id: uuid.UUID, student_id: uuid.UUID) -> list[GrowthSkill]:
        """Latest score per skill area (diagnostics)."""
        rows = self.db.execute(
            select(AssessmentScore, SkillArea.name, AssessmentCycle.name, AssessmentCycle.date)
            .join(SkillArea, SkillArea.id == AssessmentScore.skill_area_id)
            .join(AssessmentCycle, AssessmentCycle.id == AssessmentScore.cycle_id)
            .where(AssessmentScore.org_id == org_id, AssessmentScore.student_id == student_id,
                   AssessmentScore.skill_area_id.is_not(None))
            .order_by(AssessmentCycle.date)).all()
        latest: dict[str, GrowthSkill] = {}
        for score, skill_name, cyc_name, _cyc_date in rows:
            latest[skill_name] = GrowthSkill(
                skill_area=skill_name, score=float(score.score),
                max_score=float(score.max_score), cycle_name=cyc_name)
        return list(latest.values())

    def _growth_areas(self, out: StudentGrowthOut,
                      obs_rows: list[LessonObservation]) -> list[str]:
        """Attention phrases derived from repeated signals — never band tiers."""
        areas: list[str] = []
        if out.attendance.pct is not None and out.attendance.pct < _LOW_ATTENDANCE_PCT:
            areas.append(f"Attendance {out.attendance.pct}% — below {int(_LOW_ATTENDANCE_PCT)}%")
        needs_work: dict[tuple[str, str | None], int] = defaultdict(int)
        for o in obs_rows:
            if o.rating == "needs_work":
                needs_work[(o.section, o.concept)] += 1
        for (section, concept), n in needs_work.items():
            if n >= 2:
                label = f"{section} · {concept}" if concept else section
                areas.append(f"{label} needs work (flagged {n}×)")
        for subj in out.subjects:
            if subj.checks_flagged >= 2:
                areas.append(f"{subj.subject_name}: {subj.checks_flagged} daily checks not done")
            missed = sum(ch.topics_missed for ch in subj.chapters)
            if missed >= 2:
                areas.append(f"{subj.subject_name}: missed {missed} topics while absent")
            if subj.scores:
                last = subj.scores[-1]
                if last.max_score and last.score * 100.0 / last.max_score < _LOW_SCORE_PCT:
                    areas.append(f"{subj.subject_name}: scored {last.score:g}/{last.max_score:g} "
                                 f"in {last.cycle_name}")
        for skill in out.skills:
            if skill.max_score and skill.score * 100.0 / skill.max_score < _LOW_SCORE_PCT:
                areas.append(f"{skill.skill_area}: {skill.score:g}/{skill.max_score:g} "
                             f"in {skill.cycle_name}")
        return areas
