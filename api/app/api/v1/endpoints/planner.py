"""Syllabus + plan + forecast endpoints (M1, SPRD §5.1).

Reads: academic staff. Structural writes: coordinator/director. Plan approval
(baseline lock) is director-only (SPRD §3.3)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import (
    require_academic,
    require_admin,
    require_coordinator_up,
    require_operator,
)
from app.schemas.common import MessageResponse
from app.schemas.ingest import (
    SyllabusAnalyzeOut,
    SyllabusCommitIn,
    SyllabusCommitOut,
    SyllabusTextIn,
)
from app.schemas.my_syllabus import ClassSyllabusOut, MySubjectsOut
from app.schemas.periods import TopicProgressRow
from app.schemas.planner import (
    ExamFitOut,
    ForecastOut,
    PlanCommentIn,
    PlanCommentOut,
    PlanGenerateOut,
    PlanOut,
    SplitIn,
    SplitOut,
    TopicCreate,
    TopicEstimateIn,
    TopicOut,
    UnitCreate,
    UnitOut,
    WeekScheduleOut,
)
from app.schemas.syllabus_board import (
    ChapterPatchIn,
    ExamMapOut,
    ExamPortionSetIn,
    PlanTimelineOut,
    RescheduleIn,
    RescheduleOut,
    SyllabusBoardOut,
)
from app.services import templates
from app.services.exam_map import ExamMapService
from app.services.my_syllabus import MySyllabusService
from app.services.plan_schedule import PlanScheduleService
from app.services.planner import PlannerService
from app.services.syllabus_board import SyllabusBoardService
from app.services.syllabus_import import SyllabusImporter, analyze_file, analyze_text
from app.services.week_schedule import WeekScheduleService

router = APIRouter()


# ── the teacher's own syllabus (V1-6, S-46 / D-15) ───────────────────────────
@router.get("/my-subjects", response_model=MySubjectsOut)
def my_subjects(year_id: uuid.UUID | None = None,
                m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    """`S-46` — one row per class-subject she teaches, with what to teach next.

    Scoped to the caller inside the service (`D-15`): the rows are chosen by
    `teacher_member_id`, never filtered afterwards, so no other teacher's
    subject is ever loaded in the first place.
    """
    return MySyllabusService(db).my_subjects(m, year_id)


@router.get("/class-syllabus/{class_id}", response_model=ClassSyllabusOut)
def class_syllabus(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    """`D-15` — every subject for ONE class, for that class's teacher or an admin.

    A teacher who is not this class's class teacher gets 403 `not_your_class`;
    there is no school-wide form of this endpoint by design.
    """
    return MySyllabusService(db).class_syllabus(m, class_id)


# ── the syllabus board (SY-1) ────────────────────────────────────────────────
@router.get("/syllabus/board", response_model=SyllabusBoardOut)
def syllabus_board(year_id: uuid.UUID | None = None,
                   class_id: uuid.UUID | None = None,
                   class_subject_id: uuid.UUID | None = None,
                   term_id: uuid.UUID | None = None,
                   m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    """Every chapter in the school as one table, grouped by class.

    Scope is decided inside the service and is a **block, not a filter**: an
    admin gets every class, a teacher gets the subjects she teaches plus the
    homeroom she owns, and no other row is ever loaded. The `class_*` params
    narrow what she may already see; they cannot widen it."""
    return SyllabusBoardService(db).board(
        m, year_id, class_id=class_id, class_subject_id=class_subject_id,
        term_id=term_id)


@router.patch("/syllabus/units/{unit_id}", response_model=UnitOut)
def patch_unit(unit_id: uuid.UUID, body: ChapterPatchIn,
               m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    """Difficulty, remarks, title, term — the chapter's own columns.

    `require_academic` rather than admin: the person who knows a chapter is hard
    is the person teaching it, and the service narrows the write to her own
    subjects (or her homeroom's)."""
    return SyllabusBoardService(db).patch_chapter(m, unit_id, body)


# ── syllabus ─────────────────────────────────────────────────────────────────
@router.get("/syllabus", response_model=list[UnitOut])
def get_syllabus(class_subject_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return PlannerService(db).get_syllabus(m, class_subject_id)


# SY-2 — the five writes below were `require_operator`, which freezes them the
# day a school is handed over (D-1). That is the right rule for the school's
# STRUCTURE — its classes, its subjects, who teaches what — and the wrong one
# for the syllabus, which is a live teaching record: a chapter added in
# September, a chapter sized when its term begins, and a chapter dropped from
# the board are all things the teacher standing in front of the class does.
# Freezing them left the Syllabus grid offering an "Add chapter" control that
# every handed-over school would be refused.
#
# So they are `require_academic`, and the narrower question — *is this subject
# yours* — is asked by `assert_can_edit_class_subject` inside the SERVICE.
# That placement is deliberate and load-bearing: an in-process service call
# (Lucy's tools, the setup importer, a future MCP write) does not run a route
# guard, so a rule living only here would not be a rule at all.
@router.post("/syllabus/units", response_model=UnitOut)
def add_unit(body: UnitCreate, m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    return PlannerService(db).add_unit(m, body.class_subject_id, body.title, body.term_id)


@router.post("/syllabus/topics", response_model=TopicOut)
def add_topic(body: TopicCreate, m: CurrentMember = Depends(require_academic),
              db: Session = Depends(get_db)):
    return PlannerService(db).add_topic(m, body.unit_id, body.title, body.est_periods)


@router.put("/syllabus/topics/{topic_id}/estimate", response_model=TopicOut)
def set_topic_estimate(topic_id: uuid.UUID, body: TopicEstimateIn,
                       m: CurrentMember = Depends(require_academic),
                       db: Session = Depends(get_db)):
    """Size a chapter when its term begins — the whole point of term-wise planning."""
    return PlannerService(db).set_topic_estimate(m, topic_id, body.est_periods)


@router.delete("/syllabus/units/{unit_id}", response_model=MessageResponse)
def delete_unit(unit_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    PlannerService(db).delete_unit(m, unit_id)
    return MessageResponse(message="Chapter removed.")


@router.delete("/syllabus/topics/{topic_id}", response_model=MessageResponse)
def delete_topic(topic_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    PlannerService(db).delete_topic(m, topic_id)
    return MessageResponse(message="Topic removed.")


@router.post("/syllabus/split", response_model=SplitOut)
def split_syllabus(body: SplitIn, _: CurrentMember = Depends(require_operator),
                   db: Session = Depends(get_db)):
    return SplitOut(units=PlannerService(db).split_text(body.text))


# ── syllabus document import (V2-P7, SPRD2 §5.1) ─────────────────────────────
@router.get("/syllabus/import/template")
def syllabus_import_template(_: CurrentMember = Depends(require_operator)):
    """V1-2 §6 ②: blank syllabus template (one sheet per class-subject),
    generated from the importer's SPECS — blank Periods = not sized, never 1."""
    return Response(
        content=templates.syllabus_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="syllabus-template.xlsx"'})


@router.post("/syllabus/import/analyze", response_model=SyllabusAnalyzeOut)
async def syllabus_import_analyze(file: UploadFile = File(...),
                                  _: CurrentMember = Depends(require_operator)):
    """xlsx/csv grid, a typed-out list, or a PDF/photo of a printed syllabus (read by
    the multimodal model). All three come back as the same editable draft."""
    return analyze_file(await file.read(), file.filename or "syllabus.xlsx")


@router.post("/syllabus/import/text", response_model=SyllabusAnalyzeOut)
def syllabus_import_text(body: SyllabusTextIn,
                         _: CurrentMember = Depends(require_operator)):
    """Paste path. Same draft shape as the file path, so the UI has one review screen."""
    return analyze_text(body.text)


@router.post("/syllabus/import/commit", response_model=SyllabusCommitOut)
def syllabus_import_commit(body: SyllabusCommitIn,
                           m: CurrentMember = Depends(require_operator),
                           db: Session = Depends(get_db)):
    return SyllabusImporter(db).commit(
        m, class_subject_id=body.class_subject_id,
        units=[u.model_dump() for u in body.units], replace=body.replace)


# ── plan ─────────────────────────────────────────────────────────────────────
@router.get("/plan", response_model=PlanOut)
def get_plan(class_subject_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    return PlannerService(db).get_plan(m, class_subject_id)


@router.get("/plan/forecast", response_model=list[ForecastOut])
def plan_forecast(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    return PlannerService(db).forecast(m, class_id)


@router.get("/plan/exam-fit", response_model=ExamFitOut)
def exam_fit(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    """Per exam: the portion each subject must newly cover vs the teaching periods
    in the gap before it. Recomputed on every call — the calendar's live check."""
    return PlannerService(db).exam_fit(m, class_id)


@router.get("/plan/week-schedule", response_model=WeekScheduleOut)
def week_schedule(class_id: uuid.UUID, week_start: date | None = None,
                  m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    """The class's week, period by period: actuals where a log exists, remaining
    syllabus projected onto the slots from today forward. Computed, never stored."""
    return WeekScheduleService(db).week(m, class_id, week_start)


@router.post("/plan/{cs_id}/draft", response_model=PlanOut)
def draft_plan(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
               m: CurrentMember = Depends(require_operator),
               db: Session = Depends(get_db)):
    """`term_id` scopes the draft to one term; omit it to plan the whole year."""
    return PlannerService(db).draft_plan(m, cs_id, term_id)


@router.get("/plan/{cs_id}/progress", response_model=list[TopicProgressRow])
def topic_progress(cs_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    """Chapter/topic progress computed from lesson logs (P2) — what the period card
    shows as done / in progress / pending."""
    return PlannerService(db).topic_progress(m, cs_id)


@router.get("/plan/{cs_id}/timeline", response_model=PlanTimelineOut)
def plan_timeline(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
                  m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    """The reschedule dialog's read (SY-1): the chapters she can move, and the
    exams, term ends and today she is moving them against."""
    return PlanScheduleService(db).timeline(m, cs_id, term_id)


@router.put("/plan/{cs_id}/schedule", response_model=RescheduleOut)
def reschedule_plan(cs_id: uuid.UUID, body: RescheduleIn,
                    m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    """Move chapters to new date ranges.

    Deliberately NOT admin-only and deliberately allowed on an approved plan:
    the promise is frozen at approval (`plan_entries.baseline_week_start`), so
    the slip stays visible on every board no matter where she moves the
    chapter. A range too small for what she put in it is reported and still
    saved — she is the one who knows whether she can go faster (V2-P5)."""
    return PlanScheduleService(db).reschedule(m, cs_id, body)


@router.post("/plan/{cs_id}/extend", response_model=PlanOut)
def extend_plan(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
                m: CurrentMember = Depends(require_operator),
                db: Session = Depends(get_db)):
    """Schedule newly sized chapters after the existing (possibly locked) entries —
    the partial-plan growth path. Never reshuffles what is already planned (P2)."""
    return PlannerService(db).extend_plan(m, cs_id, term_id)


@router.post("/plan/{cs_id}/generate", response_model=PlanGenerateOut)
def generate_plan(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
                  m: CurrentMember = Depends(require_operator),
                  db: Session = Depends(get_db)):
    """Proposer + deterministic validators (V2-M2 §5.2). Over-capacity is reported.
    `term_id` scopes generation to one term, leaving other terms' baselines alone."""
    return PlannerService(db).generate_plan(m, cs_id, term_id)


@router.post("/plan/{cs_id}/approve", response_model=PlanOut)
def approve_plan(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
                 m: CurrentMember = Depends(require_operator),
                 db: Session = Depends(get_db)):
    """Lock a baseline (P2). `term_id` locks just that term; omit it to lock the year."""
    return PlannerService(db).approve_plan(m, cs_id, term_id)


@router.post("/plan/{cs_id}/unapprove", response_model=PlanOut)
def unapprove_plan(cs_id: uuid.UUID, term_id: uuid.UUID | None = None,
                   m: CurrentMember = Depends(require_operator),
                   db: Session = Depends(get_db)):
    """Unlock a baseline so it can be re-planned. Appends a compensating row to
    `plan_approvals` — the approval history is never rewritten (law 3)."""
    return PlannerService(db).unapprove_plan(m, cs_id, term_id)


# ── exam ↔ syllabus mapping (SY-1) ───────────────────────────────────────────
@router.get("/exam-map", response_model=ExamMapOut)
def exam_map(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    """Which chapters each exam examines, per subject, with the fit verdict
    beside it — the verdict read from `PlannerService.exam_fit`, never
    recomputed, so this screen and the Year tab's panel agree."""
    return ExamMapService(db).map(m, class_id)


@router.put("/exam-map/portion", response_model=ExamMapOut)
def set_exam_map_portion(body: ExamPortionSetIn,
                         m: CurrentMember = Depends(require_admin),
                         db: Session = Depends(get_db)):
    """Full replace of one (exam, class-subject) portion, as a chapter SET.

    Admin-only, unlike the chapter's own remarks: what an exam examines is the
    school's decision and changing it re-scopes every fit verdict and every
    coverage warning that hangs off it."""
    return ExamMapService(db).set_portion(m, body)


# ── teacher change-requests (comment threads on the plan, §5.2) ───────────────
@router.get("/plan/{cs_id}/comments", response_model=list[PlanCommentOut])
def list_comments(cs_id: uuid.UUID, include_resolved: bool = False,
                  m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return PlannerService(db).list_comments(m, cs_id, include_resolved)


@router.post("/plan/{cs_id}/comments", response_model=PlanCommentOut)
def add_comment(cs_id: uuid.UUID, body: PlanCommentIn,
                m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return PlannerService(db).add_comment(m, cs_id, body)


@router.post("/plan/comments/{comment_id}/resolve", response_model=PlanCommentOut)
def resolve_comment(comment_id: uuid.UUID, m: CurrentMember = Depends(require_coordinator_up),
                    db: Session = Depends(get_db)):
    return PlannerService(db).resolve_comment(m, comment_id)
