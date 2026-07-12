"""Exams (SC-5) — the scores screen's exam-first read/write surface.

An "exam" is a class-scoped assessment cycle carrying its own paper metadata
(title, subject, topic, total marks, optional few-students subset). This service
gives the screen its three verbs:

    feed    the landing page's list of previous exams with per-exam summaries
            (batched — the remote DB makes per-cycle queries the dominant cost)
    detail  one exam: the roster (whole class or the picked subset) with each
            student's mark, plus the photo evidence pages
    save    create OR edit in place; creating derives the term from the date,
            attaches a draft photo capture as evidence, and writes the scores
            in the same transaction

Access mirrors attendance: admin any class, a teacher only classes they teach.
Band tests are admin-only (bands are the admin's domain, P4)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AssessmentCycle,
    AssessmentScore,
    ClassSubject,
    Membership,
    SchoolClass,
    ScoreCapture,
    ScoreCapturePage,
    Student,
    Subject,
    Term,
    User,
)
from app.schemas.assessments import (
    CapturePageOut,
    ExamDetail,
    ExamRosterRow,
    ExamSaveIn,
    ExamSummary,
)
from app.services import storage
from app.services.periods import assert_can_take_class


def _label(k: SchoolClass) -> str:
    return f"{k.name}-{k.section}" if k.section else k.name


class ExamService:
    def __init__(self, db: Session):
        self.db = db

    # ── helpers ──────────────────────────────────────────────────────────────
    def _taught_class_ids(self, m: CurrentMember) -> set[uuid.UUID] | None:
        """None = unrestricted (admin); else the classes this teacher teaches."""
        if m.is_coordinator_up:
            return None
        return set(self.db.scalars(select(ClassSubject.class_id).where(
            ClassSubject.org_id == m.org_id,
            ClassSubject.teacher_member_id == m.membership.id)))

    def _roster(self, m: CurrentMember, class_id: uuid.UUID,
                student_ids: list | None) -> list[Student]:
        q = select(Student).where(
            Student.org_id == m.org_id, Student.class_id == class_id,
            Student.status == "active").order_by(Student.full_name)
        if student_ids:
            q = q.where(Student.id.in_([uuid.UUID(str(s)) for s in student_ids]))
        return list(self.db.scalars(q))

    def _cycle(self, m: CurrentMember, cycle_id: uuid.UUID) -> AssessmentCycle:
        c = self.db.scalar(select(AssessmentCycle).where(
            AssessmentCycle.id == cycle_id, AssessmentCycle.org_id == m.org_id))
        if c is None:
            raise NotFoundError("Exam")
        return c

    # ── feed ─────────────────────────────────────────────────────────────────
    def feed(self, m: CurrentMember, class_id: uuid.UUID | None = None,
             limit: int = 30) -> list[ExamSummary]:
        q = (select(AssessmentCycle).where(AssessmentCycle.org_id == m.org_id)
             .order_by(AssessmentCycle.date.desc(), AssessmentCycle.created_at.desc())
             .limit(min(limit, 100)))
        if class_id:
            q = q.where(AssessmentCycle.class_id == class_id)
        taught = self._taught_class_ids(m)
        if taught is not None:
            # A teacher's feed: their classes, plus org-wide cycles (which
            # concern every class).
            q = q.where(AssessmentCycle.class_id.in_(taught)
                        | AssessmentCycle.class_id.is_(None))
        cycles = list(self.db.scalars(q))
        if not cycles:
            return []
        cids = [c.id for c in cycles]

        # One aggregate pass over the scores of every listed cycle.
        agg = {cid: (n, float(s or 0), float(x or 0), verified)
               for cid, n, s, x, verified in self.db.execute(
                   select(AssessmentScore.cycle_id,
                          func.count(func.distinct(AssessmentScore.student_id)),
                          func.sum(AssessmentScore.score),
                          func.sum(AssessmentScore.max_score),
                          func.bool_or(AssessmentScore.verified_by.isnot(None)))
                   .where(AssessmentScore.cycle_id.in_(cids))
                   .group_by(AssessmentScore.cycle_id))}

        class_ids = {c.class_id for c in cycles if c.class_id}
        classes = {k.id: _label(k) for k in self.db.scalars(
            select(SchoolClass).where(SchoolClass.id.in_(class_ids)))} if class_ids else {}
        roster_sizes = dict(self.db.execute(
            select(Student.class_id, func.count()).where(
                Student.org_id == m.org_id, Student.class_id.in_(class_ids),
                Student.status == "active")
            .group_by(Student.class_id)).all()) if class_ids else {}
        subjects = {s.id: s.name for s in self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id))}
        member_ids = {c.created_by_member_id for c in cycles if c.created_by_member_id}
        authors = dict(self.db.execute(
            select(Membership.id, User.name).join(User, User.id == Membership.user_id)
            .where(Membership.id.in_(member_ids))).all()) if member_ids else {}
        pages = dict(self.db.execute(
            select(ScoreCapture.cycle_id, func.count(ScoreCapturePage.id))
            .join(ScoreCapturePage, ScoreCapturePage.capture_id == ScoreCapture.id)
            .where(ScoreCapture.cycle_id.in_(cids), ScoreCapture.status != "discarded")
            .group_by(ScoreCapture.cycle_id)).all())

        out: list[ExamSummary] = []
        for c in cycles:
            scored, tot_s, tot_x, verified = agg.get(c.id, (0, 0.0, 0.0, False))
            roster = (len(c.student_ids) if c.student_ids
                      else roster_sizes.get(c.class_id, scored) if c.class_id
                      else scored)
            out.append(ExamSummary(
                id=c.id, type=c.type, name=c.name, date=c.date,
                class_id=c.class_id, class_label=classes.get(c.class_id),
                subject_id=c.subject_id, subject_name=subjects.get(c.subject_id),
                topic=c.topic,
                total_marks=float(c.total_marks) if c.total_marks is not None else None,
                few_students=bool(c.student_ids),
                roster_count=roster, scored_count=scored,
                avg_pct=round(tot_s / tot_x * 100, 1) if tot_x else None,
                verified=bool(verified),
                created_by_name=authors.get(c.created_by_member_id),
                page_count=pages.get(c.id, 0),
                grid_only=c.type == "diagnostic" or c.class_id is None
                          or c.subject_id is None))
        return out

    # ── detail ───────────────────────────────────────────────────────────────
    def detail(self, m: CurrentMember, cycle_id: uuid.UUID) -> ExamDetail:
        c = self._cycle(m, cycle_id)
        if c.type == "diagnostic" or c.class_id is None or c.subject_id is None:
            raise ValidationError("That cycle opens in the score grid, not the exam page.",
                                  code="use_grid")
        assert_can_take_class(self.db, m, c.class_id, None)
        klass = self.db.get(SchoolClass, c.class_id)
        subject = self.db.get(Subject, c.subject_id)

        roster = self._roster(m, c.class_id, c.student_ids)
        scores = {sc.student_id: sc for sc in self.db.scalars(
            select(AssessmentScore).where(
                AssessmentScore.org_id == m.org_id,
                AssessmentScore.cycle_id == c.id,
                AssessmentScore.subject_id == c.subject_id))}
        # Students who have a score but left the class/subset still show — a
        # saved mark never silently disappears from the review.
        missing = set(scores) - {s.id for s in roster}
        if missing:
            roster += list(self.db.scalars(select(Student).where(
                Student.id.in_(missing)).order_by(Student.full_name)))

        rows, tot_s, tot_x = [], 0.0, 0.0
        verified = False
        for st in roster:
            sc = scores.get(st.id)
            if sc is not None:
                tot_s += float(sc.score)
                tot_x += float(sc.max_score)
                verified = verified or sc.verified_by is not None
            rows.append(ExamRosterRow(
                student_id=st.id, full_name=st.full_name, roll_no=st.roll_no,
                score=float(sc.score) if sc else None,
                max_score=float(sc.max_score) if sc else None))

        page_rows = list(self.db.execute(
            select(ScoreCapturePage).join(
                ScoreCapture, ScoreCapture.id == ScoreCapturePage.capture_id)
            .where(ScoreCapture.cycle_id == c.id, ScoreCapture.status != "discarded")
            .order_by(ScoreCapture.created_at, ScoreCapturePage.page_no)).scalars())
        return ExamDetail(
            id=c.id, type=c.type, name=c.name, date=c.date,
            class_id=c.class_id, class_label=_label(klass),
            subject_id=c.subject_id, subject_name=subject.name, topic=c.topic,
            total_marks=float(c.total_marks) if c.total_marks is not None else None,
            student_ids=[uuid.UUID(str(s)) for s in c.student_ids or []] or None,
            verified=verified,
            avg_pct=round(tot_s / tot_x * 100, 1) if tot_x else None,
            rows=rows,
            pages=[CapturePageOut(id=p.id, page_no=p.page_no,
                                  url=storage.url_for(p.object_key),
                                  content_type=p.content_type) for p in page_rows])

    # ── save (create or edit) ────────────────────────────────────────────────
    def save(self, m: CurrentMember, body: ExamSaveIn) -> ExamDetail:
        if body.type == "diagnostic":
            raise ValidationError("Diagnostics are captured per skill area, not as exams.")
        if body.type == "band_test" and not m.is_coordinator_up:
            raise ForbiddenError("Band tests are recorded by the admin.", code="admin_only")
        if not self.db.scalar(select(SchoolClass.id).where(
                SchoolClass.id == body.class_id, SchoolClass.org_id == m.org_id)):
            raise NotFoundError("Class")
        if not self.db.scalar(select(Subject.id).where(
                Subject.id == body.subject_id, Subject.org_id == m.org_id)):
            raise NotFoundError("Subject")
        assert_can_take_class(self.db, m, body.class_id, None)

        class_roster = {s.id for s in self._roster(m, body.class_id, None)}
        student_ids: list[str] | None = None
        if body.student_ids:
            bad = [s for s in body.student_ids if s not in class_roster]
            if bad:
                raise ValidationError("A picked student is not in this class.",
                                      code="not_in_class")
            student_ids = [str(s) for s in body.student_ids]
        allowed = (set(body.student_ids) if body.student_ids else class_roster)
        seen: set[uuid.UUID] = set()
        for r in body.rows:
            if r.student_id not in allowed:
                raise ValidationError("A score points at a student outside this exam.",
                                      code="not_in_class")
            if r.student_id in seen:
                raise ValidationError("A student appears twice.", code="duplicate_student")
            seen.add(r.student_id)

        term_id = self.db.scalar(select(Term.id).where(
            Term.org_id == m.org_id, Term.start_date <= body.date,
            Term.end_date >= body.date).order_by(Term.start_date.desc()).limit(1))
        if term_id is None:
            raise ValidationError("No term covers that date — set up terms first.",
                                  code="no_term")

        if body.cycle_id is not None:
            cycle = self._cycle(m, body.cycle_id)
            if cycle.class_id != body.class_id:
                raise ValidationError("An exam cannot move to another class.")
            cycle.type = body.type
            cycle.name = body.name
            cycle.date = body.date
            cycle.term_id = term_id
            cycle.subject_id = body.subject_id
            cycle.topic = body.topic
            cycle.total_marks = body.total_marks
            cycle.student_ids = student_ids
        else:
            cycle = AssessmentCycle(
                org_id=m.org_id, term_id=term_id, type=body.type, name=body.name,
                date=body.date, class_id=body.class_id, subject_id=body.subject_id,
                topic=body.topic, total_marks=body.total_marks,
                student_ids=student_ids, created_by_member_id=m.membership.id)
            self.db.add(cycle)
            self.db.flush()

        # Full replace: the reviewed grid IS the exam's marks. Editing later
        # re-sends the whole grid, so a removed row really goes away.
        for sc in self.db.scalars(select(AssessmentScore).where(
                AssessmentScore.org_id == m.org_id,
                AssessmentScore.cycle_id == cycle.id)):
            self.db.delete(sc)
        for r in body.rows:
            self.db.add(AssessmentScore(
                org_id=m.org_id, cycle_id=cycle.id, student_id=r.student_id,
                subject_id=body.subject_id, score=r.score,
                max_score=r.max_score if r.max_score is not None else body.total_marks,
                entered_by=m.user_id))
        self.db.flush()

        if body.capture_id is not None:
            from app.services.score_capture import ScoreCaptureService  # noqa: PLC0415
            ScoreCaptureService(self.db).finalize_for_exam(m, body.capture_id, cycle)

        return self.detail(m, cycle.id)
