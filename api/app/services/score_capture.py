"""Photo score capture (SC-1) — photo in, confirmed scores out.

The pipeline the teacher sees as "snap → glance → confirm":

    create   an empty capture for (cycle × class × subject-or-skill)
    pages    pass-through photo uploads (downscaled, stored as object keys,
             kept forever as evidence — P5)
    parse    AI transcribes each page (`ai/scores.py`), then the deterministic
             matcher (`score_match.py`) attaches student_ids; the draft lands in
             `parsed_rows`, never in `assessment_scores`
    confirm  the human-edited rows are written as real scores (§8); the existing
             admin `verify` step stays the trust gate above this

Access mirrors attendance: admin any class, a teacher only classes they teach
(`assert_can_take_class`). AI-off keeps everything working: parse reports
`ai_off`, the photos stay as evidence, and the grid remains manually editable.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    AssessmentCycle,
    ScoreCapture,
    ScoreCapturePage,
    SkillArea,
    Student,
    Subject,
)
from app.schemas.assessments import (
    CaptureConfirmIn,
    CaptureCreate,
    CaptureOut,
    CapturePageOut,
    CaptureRosterRow,
    CaptureSummary,
    ScoreIn,
    ScoresBulkIn,
)
from app.services import storage
from app.services.ai.scores import extract_marksheet
from app.services.assessments import AssessmentService
from app.services.periods import assert_can_take_class
from app.services.score_match import match_rows

_MAX_PAGE_BYTES = 25 * 1024 * 1024
_ALLOWED_TYPES = ("image/", "application/pdf")


class ScoreCaptureService:
    def __init__(self, db: Session):
        self.db = db

    # ── helpers ──────────────────────────────────────────────────────────────
    def _capture(self, m: CurrentMember, capture_id: uuid.UUID) -> ScoreCapture:
        cap = self.db.scalar(
            select(ScoreCapture).options(selectinload(ScoreCapture.pages))
            .where(ScoreCapture.id == capture_id, ScoreCapture.org_id == m.org_id))
        if cap is None:
            raise NotFoundError("Capture")
        assert_can_take_class(self.db, m, cap.class_id, None)
        return cap

    def _roster(self, m: CurrentMember, class_id: uuid.UUID) -> list[Student]:
        return list(self.db.scalars(
            select(Student).where(
                Student.org_id == m.org_id, Student.class_id == class_id,
                Student.status == "active")
            .order_by(Student.full_name)))

    def _mutable(self, cap: ScoreCapture) -> None:
        if cap.status in ("confirmed", "discarded"):
            raise ValidationError(f"This capture is already {cap.status}.",
                                  code="capture_closed")

    def _out(self, m: CurrentMember, cap: ScoreCapture) -> CaptureOut:
        roster = [CaptureRosterRow(student_id=s.id, full_name=s.full_name, roll_no=s.roll_no)
                  for s in self._roster(m, cap.class_id)]
        pages = [CapturePageOut(id=p.id, page_no=p.page_no,
                                url=storage.url_for(p.object_key),
                                content_type=p.content_type)
                 for p in cap.pages]
        return CaptureOut(
            id=cap.id, cycle_id=cap.cycle_id, class_id=cap.class_id,
            subject_id=cap.subject_id, skill_area_id=cap.skill_area_id,
            status=cap.status, parse_error=cap.parse_error, pages=pages,
            parsed_rows=cap.parsed_rows, roster=roster, created_at=cap.created_at)

    # ── lifecycle ────────────────────────────────────────────────────────────
    def create(self, m: CurrentMember, body: CaptureCreate) -> CaptureOut:
        if (body.subject_id is None) == (body.skill_area_id is None):
            raise ValidationError("A capture needs exactly one of subject/skill area.")
        cycle = self.db.scalar(select(AssessmentCycle).where(
            AssessmentCycle.id == body.cycle_id, AssessmentCycle.org_id == m.org_id))
        if cycle is None:
            raise NotFoundError("Cycle")
        if body.subject_id and not self.db.scalar(select(Subject.id).where(
                Subject.id == body.subject_id, Subject.org_id == m.org_id)):
            raise NotFoundError("Subject")
        if body.skill_area_id and not self.db.scalar(select(SkillArea.id).where(
                SkillArea.id == body.skill_area_id, SkillArea.org_id == m.org_id)):
            raise NotFoundError("Skill area")
        if cycle.type == "diagnostic" and body.subject_id:
            raise ValidationError("A diagnostic cycle captures skill areas, not subjects.")
        if cycle.type != "diagnostic" and body.skill_area_id:
            raise ValidationError("A test cycle captures subjects, not skill areas.")
        if cycle.class_id and cycle.class_id != body.class_id:
            raise ValidationError("That cycle belongs to a different class.")
        if cycle.subject_id and cycle.subject_id != body.subject_id:
            raise ValidationError("That cycle belongs to a different subject.")
        assert_can_take_class(self.db, m, body.class_id, None)
        if not self._roster(m, body.class_id):
            raise ValidationError("That class has no active students.")

        cap = ScoreCapture(
            org_id=m.org_id, cycle_id=body.cycle_id, class_id=body.class_id,
            subject_id=body.subject_id, skill_area_id=body.skill_area_id,
            created_by_member_id=m.membership.id)
        self.db.add(cap)
        self.db.flush()
        self.db.refresh(cap)
        return self._out(m, cap)

    def add_page(self, m: CurrentMember, capture_id: uuid.UUID, data: bytes,
                 content_type: str, filename: str) -> CaptureOut:
        cap = self._capture(m, capture_id)
        self._mutable(cap)
        if not content_type.startswith(_ALLOWED_TYPES):
            raise ValidationError("Only photos and PDFs can be captured.",
                                  code="bad_page_type")
        if len(data) > _MAX_PAGE_BYTES:
            raise ValidationError("File is too large (max 25 MB).", code="page_too_large")
        key = storage.make_key(org_id=m.org_id, instance_id=cap.id, filename=filename)
        storage.save_bytes(key, storage.maybe_downscale(data, content_type), content_type)
        next_no = (self.db.scalar(select(func.max(ScoreCapturePage.page_no)).where(
            ScoreCapturePage.capture_id == cap.id)) or 0) + 1
        self.db.add(ScoreCapturePage(
            org_id=m.org_id, capture_id=cap.id, page_no=next_no,
            object_key=key, content_type=content_type, size_bytes=len(data)))
        # A new page invalidates any previous parse — back to square one.
        cap.status = "uploaded"
        cap.parsed_rows = None
        cap.parse_error = None
        self.db.flush()
        self.db.refresh(cap)
        return self._out(m, cap)

    def parse(self, m: CurrentMember, capture_id: uuid.UUID) -> CaptureOut:
        cap = self._capture(m, capture_id)
        self._mutable(cap)
        if not cap.pages:
            raise ValidationError("Add at least one photo first.", code="no_pages")

        if not settings.ai_configured:
            cap.parse_error = "ai_off"
            self.db.flush()
            return self._out(m, cap)

        transcribed: list[dict] = []
        for page in cap.pages:
            data = storage.get_bytes(page.object_key)
            filename = page.object_key.rsplit("/", 1)[-1]
            rows = extract_marksheet(filename, data) if data is not None else None
            if rows is None:
                cap.parse_error = "unreadable_page"
                self.db.flush()
                return self._out(m, cap)
            transcribed.extend(rows)

        roster = [{"id": s.id, "full_name": s.full_name, "roll_no": s.roll_no,
                   "admission_no": s.admission_no}
                  for s in self._roster(m, cap.class_id)]
        cap.parsed_rows = match_rows(transcribed, roster)
        cap.parse_error = None
        cap.status = "parsed"
        self.db.flush()
        return self._out(m, cap)

    def confirm(self, m: CurrentMember, capture_id: uuid.UUID,
                body: CaptureConfirmIn) -> CaptureOut:
        cap = self._capture(m, capture_id)
        self._mutable(cap)
        roster_ids = {s.id for s in self._roster(m, cap.class_id)}
        seen: set[uuid.UUID] = set()
        for r in body.rows:
            if r.student_id not in roster_ids:
                raise ValidationError("A row points at a student outside this class.",
                                      code="not_in_class")
            if r.student_id in seen:
                raise ValidationError("A student appears twice in the confirmed rows.",
                                      code="duplicate_student")
            seen.add(r.student_id)

        AssessmentService(self.db).save_scores(m, cap.cycle_id, ScoresBulkIn(rows=[
            ScoreIn(student_id=r.student_id, subject_id=cap.subject_id,
                    skill_area_id=cap.skill_area_id, score=r.score, max_score=r.max_score)
            for r in body.rows]))
        cap.status = "confirmed"
        cap.confirmed_by_member_id = m.membership.id
        cap.confirmed_at = datetime.now(UTC)
        self.db.flush()
        return self._out(m, cap)

    def discard(self, m: CurrentMember, capture_id: uuid.UUID) -> None:
        cap = self._capture(m, capture_id)
        self._mutable(cap)
        cap.status = "discarded"
        self.db.flush()

    def list(self, m: CurrentMember, cycle_id: uuid.UUID | None,
             class_id: uuid.UUID | None) -> list[CaptureSummary]:
        q = (select(ScoreCapture, func.count(ScoreCapturePage.id))
             .outerjoin(ScoreCapturePage, ScoreCapturePage.capture_id == ScoreCapture.id)
             .where(ScoreCapture.org_id == m.org_id)
             .group_by(ScoreCapture.id).order_by(ScoreCapture.created_at.desc()))
        if cycle_id:
            q = q.where(ScoreCapture.cycle_id == cycle_id)
        if class_id:
            q = q.where(ScoreCapture.class_id == class_id)
        return [CaptureSummary(
            id=cap.id, cycle_id=cap.cycle_id, class_id=cap.class_id,
            subject_id=cap.subject_id, skill_area_id=cap.skill_area_id,
            status=cap.status, page_count=count, created_at=cap.created_at)
            for cap, count in self.db.execute(q)]

    def get(self, m: CurrentMember, capture_id: uuid.UUID) -> CaptureOut:
        return self._out(m, self._capture(m, capture_id))
