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

    lock    V1-8 `D-53`: verify-and-lock. The locked exam IS the record — for
            the analytics, the report card, and (per `D-54`) as the training
            label. Editing after it is refused until an **admin unlocks with a
            reason**, and the unlock is an appended row, never a mutation
            (`Q-62`, law 3).

Access mirrors attendance: admin any class, a teacher only classes they teach.
Band tests are admin-only (bands are the admin's domain, P4).

V1-8 also gives every exam a **scale** (`minor` | `major`) and, where a school
has configured one, its **own name for the type** (`D-55`). Neither is a display
detail: `core/exams.py` owns what they mean, and no read may pool marks across
scales (`S-114`)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exams import sum_mismatch, type_label
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AssessmentCycle,
    AssessmentScore,
    CalendarEvent,
    ExamLockEvent,
    ExamType,
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
    ExamLockRow,
    ExamRosterRow,
    ExamSaveIn,
    ExamSummary,
    QuestionMark,
)
from app.services import storage
from app.services.exam_types import ExamTypeService
from app.services.periods import assert_can_take_class, visible_class_ids


def _label(k: SchoolClass) -> str:
    return f"{k.name}-{k.section}" if k.section else k.name


class ExamService:
    def __init__(self, db: Session):
        self.db = db

    # ── helpers ──────────────────────────────────────────────────────────────
    def _taught_class_ids(self, m: CurrentMember) -> set[uuid.UUID] | None:
        """None = unrestricted (admin); else the classes this teacher may read.

        `visible_class_ids` is the one definition (founder, 2026-08-05): the
        subjects she teaches PLUS the homeroom she owns. A class teacher who
        takes none of her own class's subjects used to get an empty exam feed
        for her own children.
        """
        return visible_class_ids(self.db, m)

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

    def _papers(self, cycle_id: uuid.UUID) -> dict[uuid.UUID, str]:
        """student → the URL of their own marked script (`S-119`).

        The photos are kept forever as evidence and rendered on the exam page,
        but until V1-8 there was no way back to them from the screen where a
        parent asks *"can I see it?"*. One query for the whole roster."""
        rows = self.db.execute(
            select(ScoreCapturePage.student_id, ScoreCapturePage.object_key)
            .join(ScoreCapture, ScoreCapture.id == ScoreCapturePage.capture_id)
            .where(ScoreCapture.cycle_id == cycle_id,
                   ScoreCapture.status != "discarded",
                   ScoreCapturePage.student_id.is_not(None))
            .order_by(ScoreCapturePage.page_no)).all()
        out: dict[uuid.UUID, str] = {}
        for student_id, key in rows:
            out.setdefault(student_id, storage.url_for(key))
        return out

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
        # The school's own words for the types on screen (`D-55`) — one query,
        # because the feed groups by them.
        type_names = dict(self.db.execute(
            select(ExamType.id, ExamType.name).where(ExamType.org_id == m.org_id)).all())

        out: list[ExamSummary] = []
        for c in cycles:
            scored, tot_s, tot_x, verified = agg.get(c.id, (0, 0.0, 0.0, False))
            roster = (len(c.student_ids) if c.student_ids
                      else roster_sizes.get(c.class_id, scored) if c.class_id
                      else scored)
            out.append(ExamSummary(
                id=c.id, type=c.type,
                exam_type_id=c.exam_type_id,
                exam_type_name=type_names.get(c.exam_type_id),
                type_label=type_names.get(c.exam_type_id) or type_label(c.type),
                scale=c.scale, locked=c.locked_at is not None,
                name=c.name, date=c.date,
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

        papers = self._papers(c.id)
        rows, tot_s, tot_x = [], 0.0, 0.0
        verified = False
        for st in roster:
            sc = scores.get(st.id)
            qm = None
            if sc is not None:
                tot_s += float(sc.score)
                tot_x += float(sc.max_score)
                verified = verified or sc.verified_by is not None
                qm = [QuestionMark(**q) for q in sc.question_marks] if sc.question_marks else None
            rows.append(ExamRosterRow(
                student_id=st.id, full_name=st.full_name, roll_no=st.roll_no,
                score=float(sc.score) if sc else None,
                max_score=float(sc.max_score) if sc else None,
                question_marks=qm,
                paper_url=papers.get(st.id),
                sum_mismatch=sum_mismatch(sc.question_marks if sc else None,
                                          float(sc.score) if sc else None),
                remark=sc.remark if sc else None))

        page_rows = list(self.db.execute(
            select(ScoreCapturePage).join(
                ScoreCapture, ScoreCapture.id == ScoreCapturePage.capture_id)
            .where(ScoreCapture.cycle_id == c.id, ScoreCapture.status != "discarded")
            .order_by(ScoreCapture.created_at, ScoreCapturePage.page_no)).scalars())
        exam_type = self.db.get(ExamType, c.exam_type_id) if c.exam_type_id else None
        event_name = self.db.scalar(select(CalendarEvent.name).where(
            CalendarEvent.id == c.exam_event_id)) if c.exam_event_id else None
        return ExamDetail(
            id=c.id, type=c.type,
            exam_type_id=c.exam_type_id,
            exam_type_name=exam_type.name if exam_type else None,
            type_label=exam_type.name if exam_type else type_label(c.type),
            scale=c.scale,
            exam_event_id=c.exam_event_id, exam_event_name=event_name,
            name=c.name, date=c.date,
            class_id=c.class_id, class_label=_label(klass),
            subject_id=c.subject_id, subject_name=subject.name, topic=c.topic,
            total_marks=float(c.total_marks) if c.total_marks is not None else None,
            student_ids=[uuid.UUID(str(s)) for s in c.student_ids or []] or None,
            verified=verified,
            locked=c.locked_at is not None, locked_at=c.locked_at,
            locked_by_name=self.db.scalar(select(User.name).where(
                User.id == c.locked_by)) if c.locked_by else None,
            lock_history=self._lock_history(m, c.id),
            avg_pct=round(tot_s / tot_x * 100, 1) if tot_x else None,
            rows=rows,
            pages=[CapturePageOut(id=p.id, page_no=p.page_no,
                                  url=storage.url_for(p.object_key),
                                  content_type=p.content_type) for p in page_rows])

    def _lock_history(self, m: CurrentMember, cycle_id: uuid.UUID) -> list[ExamLockRow]:
        rows = self.db.execute(
            select(ExamLockEvent, User.name)
            .outerjoin(Membership, Membership.id == ExamLockEvent.actor_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .where(ExamLockEvent.org_id == m.org_id, ExamLockEvent.cycle_id == cycle_id)
            .order_by(ExamLockEvent.created_at.desc())).all()
        return [ExamLockRow(action=e.action, reason=e.reason, by_name=name,
                            at=e.created_at) for e, name in rows]

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

        exam_type_id, scale = ExamTypeService(self.db).resolve(
            m, body.exam_type_id, body.type)
        if body.exam_event_id is not None and not self.db.scalar(select(CalendarEvent.id).where(
                CalendarEvent.id == body.exam_event_id, CalendarEvent.org_id == m.org_id)):
            raise NotFoundError("Exam block")

        if body.cycle_id is not None:
            cycle = self._cycle(m, body.cycle_id)
            if cycle.class_id != body.class_id:
                raise ValidationError("An exam cannot move to another class.")
            # `D-53`/`S-136`: the whole point of the lock. Without this the full
            # delete-and-reinsert below would silently replace July's confirmed
            # mark in November, with no record that they ever differed.
            self._assert_unlocked(cycle)
            cycle.type = body.type
            cycle.name = body.name
            cycle.date = body.date
            cycle.term_id = term_id
            cycle.subject_id = body.subject_id
            cycle.topic = body.topic
            cycle.total_marks = body.total_marks
            cycle.student_ids = student_ids
            cycle.exam_type_id = exam_type_id
            cycle.scale = scale
            cycle.exam_event_id = body.exam_event_id
        else:
            cycle = AssessmentCycle(
                org_id=m.org_id, term_id=term_id, type=body.type, name=body.name,
                date=body.date, class_id=body.class_id, subject_id=body.subject_id,
                topic=body.topic, total_marks=body.total_marks,
                student_ids=student_ids, created_by_member_id=m.membership.id,
                exam_type_id=exam_type_id, scale=scale,
                exam_event_id=body.exam_event_id)
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
                question_marks=[q.model_dump() for q in r.question_marks]
                               if r.question_marks else None,
                remark=(r.remark or "").strip() or None,
                entered_by=m.user_id))
        self.db.flush()

        if body.capture_id is not None:
            from app.services.score_capture import ScoreCaptureService  # noqa: PLC0415
            # `S-119`: the page↔student map comes from the CONFIRMED grid, so a
            # paper is filed against a child only once a human has said so.
            page_students = {r.page_id: r.student_id for r in body.rows if r.page_id}
            ScoreCaptureService(self.db).finalize_for_exam(
                m, body.capture_id, cycle, page_students)

        return self.detail(m, cycle.id)

    # ── verify & lock (D-53) ─────────────────────────────────────────────────
    @staticmethod
    def _assert_unlocked(cycle: AssessmentCycle) -> None:
        if cycle.locked_at is not None:
            raise ValidationError(
                "This exam is locked. An admin can unlock it with a reason.",
                code="exam_locked")

    def lock(self, m: CurrentMember, cycle_id: uuid.UUID) -> ExamDetail:
        """The teacher verifies the reviewed marks and locks them. After this
        the exam **is** the record — for the analytics, the report card, and (per
        `D-54`) as the training label.

        This is also what finally gives `assessment_scores.verified_by` the
        meaning it has never had: the exam flow never wrote it, so the feed's
        *"· verified"* badge could not light up for any exam recorded through
        SC-5 (module §4.5)."""
        c = self._cycle(m, cycle_id)
        if c.class_id:
            assert_can_take_class(self.db, m, c.class_id, None)
        self._assert_unlocked(c)
        scores = list(self.db.scalars(select(AssessmentScore).where(
            AssessmentScore.org_id == m.org_id, AssessmentScore.cycle_id == c.id)))
        if not scores:
            raise ValidationError("There are no marks to lock yet.", code="no_scores")
        for sc in scores:
            sc.verified_by = m.user_id
        c.locked_at = datetime.now(UTC)
        c.locked_by = m.user_id
        self.db.add(ExamLockEvent(org_id=m.org_id, cycle_id=c.id, action="lock",
                                  actor_member_id=m.membership.id))
        self.db.flush()
        self._write_training_pair(m, c, scores)
        return self.detail(m, cycle_id)

    def unlock(self, m: CurrentMember, cycle_id: uuid.UUID, reason: str | None) -> ExamDetail:
        """Admin-only, with a reason, **appended** (`Q-62`) — the
        `plan_approvals` / `leave_request_events` shape, where status is a
        derived cache of the newest event. The frozen training pair is left
        exactly as it was and flagged by the event, never rewritten (`S-139`):
        a corpus whose labels drift is worse than no corpus, because you cannot
        tell which rows moved."""
        if not m.is_coordinator_up:
            raise ForbiddenError("Only an admin can unlock an exam.", code="admin_only")
        c = self._cycle(m, cycle_id)
        if c.locked_at is None:
            raise ValidationError("This exam is not locked.", code="not_locked")
        if not (reason or "").strip():
            raise ValidationError("Say why this is being unlocked.", code="reason_required")
        c.locked_at = None
        c.locked_by = None
        self.db.add(ExamLockEvent(org_id=m.org_id, cycle_id=c.id, action="unlock",
                                  reason=reason.strip(), actor_member_id=m.membership.id))
        self.db.flush()
        return self.detail(m, cycle_id)

    def _write_training_pair(self, m: CurrentMember, cycle: AssessmentCycle,
                             scores: list[AssessmentScore]) -> None:
        """`D-54`/A-4 — capture in v1, use in v2, **no export path here.**

        Only when the school has opted in (`S-138`), and only at lock, because
        that is the one moment the human's answer stops moving."""
        if not getattr(m.org, "training_data_opt_in", False):
            return
        from app.services.exam_corpus import build_pair  # noqa: PLC0415

        names = dict(self.db.execute(
            select(Student.id, Student.full_name)
            .where(Student.id.in_([s.student_id for s in scores]))).all()) if scores else {}
        final_rows = [{"student_id": s.student_id, "full_name": names.get(s.student_id),
                       "score": float(s.score), "max_score": float(s.max_score),
                       "question_marks": s.question_marks} for s in scores]
        captures = list(self.db.scalars(select(ScoreCapture).where(
            ScoreCapture.cycle_id == cycle.id, ScoreCapture.status != "discarded")))
        for cap in captures:
            locked_rows, corrections = build_pair(
                cap.parsed_rows, cap.parsed_meta, final_rows,
                float(cycle.total_marks) if cycle.total_marks is not None else None)
            cap.locked_rows = locked_rows
            cap.corrections = corrections
        self.db.flush()
