"""The support programme (V1-9) — bands, promotion, ownership and check-ins.

Guards, and one of them is a deliberate change:

* **Setup, filing a class, ownership and the programme board are admin.** They
  are decisions about how the school runs its programme.
* **Promotion is a teacher's action** (`D-76`: *"it's up to her choice"*). Every
  band write was admin-only before V1-9, and `ExamService.save` still refuses a
  `band_test` from a non-admin — so a promotion guard left as-is would have
  shipped a feature no teacher could use. The service still requires the exam to
  be **locked** (`S-184`), which is the guard that actually matters.
* **The owner's screens are hers**, and an admin's. Never another owner's
  children (`S-170`).

Nothing here reaches a parent, in any shape (P4).
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin
from app.schemas.bands import (
    AllocationBoard,
    AssessmentRecordIn,
    AssignOwnerIn,
    BandAssessmentCreate,
    BandAssessmentList,
    BandAssessmentRow,
    BandAssessmentSheet,
    BandClassBoard,
    BandDescriptorOut,
    BandDistribution,
    BandFileIn,
    BandPromotePreview,
    BandScopeOut,
    BandSubjectSetup,
    CheckpointIn,
    DescriptorUpdate,
    InterventionCloseIn,
    MonitoredIn,
    MyStudentsBoard,
    OwnerSuggestion,
    ProgrammeBoard,
    SupportChild,
    SupportList,
    SupportSummary,
)
from app.schemas.common import MessageResponse
from app.services.band_assessments import BandAssessmentService
from app.services.bands import BandService
from app.services.insights.bands import BandInsights
from app.services.support import SupportService

router = APIRouter()


# ── setup: what a band MEANS in this school (D-68 / D-69 / D-74) ─────────────
@router.get("/setup", response_model=list[BandSubjectSetup])
def band_setup(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """Every subject with its monitored flag and its three descriptors. The nine
    texts are seeded pre-written on first read (`S-175`) — 27 empty boxes get
    filled in by nobody."""
    return BandService(db).setup(m)


@router.put("/setup/monitored", response_model=list[BandSubjectSetup])
def set_monitored(body: MonitoredIn, m: CurrentMember = Depends(require_admin),
                  db: Session = Depends(get_db)):
    return BandService(db).set_monitored(m, body.subject_ids)


@router.patch("/setup/descriptors/{descriptor_id}", response_model=BandDescriptorOut)
def update_descriptor(descriptor_id: uuid.UUID, body: DescriptorUpdate,
                      m: CurrentMember = Depends(require_admin),
                      db: Session = Depends(get_db)):
    return BandService(db).update_descriptor(m, descriptor_id, body.text, body.min_pct)


# ── assess a class, for one subject (D-70 / S-185) ───────────────────────────
@router.get("/class", response_model=BandClassBoard)
def class_board(class_id: uuid.UUID, subject_id: uuid.UUID,
                cycle_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None,
                m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """The test's marks pre-fill every row; she moves only what she disagrees
    with (`Q-79`). A child who did not sit it is **not assessed** — a word."""
    return BandService(db).class_board(m, class_id, subject_id, cycle_id, term_id)


@router.post("/class/file", response_model=MessageResponse)
def file_bands(body: BandFileIn, m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    """**Entry** (`S-185`). Append-only: re-filing appends, it never overwrites.

    Founder 2026-08-04: `require_academic`, not `require_admin`. The subject
    teacher is the person who knows whether this child can read the passage, and
    V1-9's admin-only guard meant she could see a band and never set one. The
    service still refuses a class-subject she does not teach."""
    n = BandService(db).file_bands(m, body)
    return MessageResponse(message=f"{n} band{'' if n == 1 else 's'} filed.")


# ── scope, distribution, allocation (founder 2026-08-04) ─────────────────────
@router.get("/scope", response_model=BandScopeOut)
def band_scope(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """What this member may band — and therefore whether they get the nav item."""
    return BandService(db).scope(m)


@router.get("/distribution", response_model=BandDistribution)
def distribution(term_id: uuid.UUID | None = None,
                 m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    """School · by class · by subject, tallied A/B/C — **under** the movement
    sentence, never instead of it (`S-169`). Scoped to her own class-subjects
    for a teacher, the whole school for an admin."""
    return BandInsights(db).distribution(m, term_id)


@router.get("/allocation", response_model=AllocationBoard)
def allocation(term_id: uuid.UUID | None = None, class_id: uuid.UUID | None = None,
               subject_id: uuid.UUID | None = None,
               m: CurrentMember = Depends(require_admin),
               db: Session = Depends(get_db)):
    """Every Band C placement and its owner — the table the admin allocates from.
    Admin-only: who owns whom is a decision about how the school runs."""
    return BandInsights(db).allocation(m, term_id, class_id, subject_id)


@router.get("/allocation/suggestions", response_model=list[OwnerSuggestion])
def owner_suggestions(student_id: uuid.UUID, subject_id: uuid.UUID,
                      m: CurrentMember = Depends(require_admin),
                      db: Session = Depends(get_db)):
    """Suggested first, **never restricted** — the teachers already in front of
    this child, then everyone, each with a reason and their current load."""
    return BandInsights(db).owner_suggestions(m, student_id, subject_id)


# ── movement: promoting a test (D-76 / S-184 / Q-81) ─────────────────────────
@router.get("/promote/{cycle_id}", response_model=BandPromotePreview)
def promote_preview(cycle_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    """*"Use this as the band test."* The moves are shown **before** anything
    commits — `student_bands` is append-only, so a mistake is permanent."""
    return BandService(db).promote_preview(m, cycle_id)


@router.post("/promote/{cycle_id}", response_model=BandPromotePreview)
def promote(cycle_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
            db: Session = Depends(get_db)):
    return BandService(db).promote(m, cycle_id)


# ── the admin's programme board (D-73 / S-169) ───────────────────────────────
@router.get("/programme", response_model=ProgrammeBoard)
def programme(term_id: uuid.UUID | None = None, m: CurrentMember = Depends(require_admin),
              db: Session = Depends(get_db)):
    """**Movement is the headline.** The distribution is a photograph of a
    decision already made and goes under More (`S-169`)."""
    return BandService(db).programme(m, term_id)


@router.post("/owner", response_model=MessageResponse)
def assign_owner(body: AssignOwnerIn, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    """Give a C child a teacher, by name, for one subject — offered right after
    a class is filed, because that is the only moment anyone is thinking about
    it (`D-71`)."""
    BandService(db).assign_owner(m, body.student_id, body.subject_id, body.member_id,
                                 body.term_id, body.goal_text, body.exit_criterion)
    return MessageResponse(message="Owner assigned.")


# ── the owner's screens (D-87 / S-164 / S-165) ───────────────────────────────
@router.get("/support", response_model=SupportList)
def my_support_students(member_id: uuid.UUID | None = None,
                        m: CurrentMember = Depends(require_academic),
                        db: Session = Depends(get_db)):
    return SupportService(db).my_students(m, member_id)


@router.get("/support/{intervention_id}", response_model=SupportChild)
def support_child(intervention_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    """Opens **already written** (`S-164`): his week as five other teachers
    already recorded it, so she is never asked to type what we already know."""
    return SupportService(db).child(m, intervention_id)


@router.get("/support/{intervention_id}/summary", response_model=SupportSummary)
def support_summary(intervention_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    """The written summary and key insights, over the facts the page already
    shows. AI-off it is the deterministic sentences — never blank, and `source`
    says which one you are reading. Staff-only, like the rest of the module."""
    return SupportService(db).summary(m, intervention_id)


@router.post("/support/{intervention_id}/check-in", response_model=SupportChild)
def check_in(intervention_id: uuid.UUID, body: CheckpointIn,
             m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """Four fields, once a week, append-only (law 3)."""
    return SupportService(db).check_in(m, intervention_id, body)


@router.post("/support/{intervention_id}/close", response_model=SupportChild)
def close_plan(intervention_id: uuid.UUID, body: InterventionCloseIn,
               m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """**The fix the module was waiting on** (`S-180`): until V1-9 nothing could
    finish an intervention, so a goal met in July kept injecting a daily check in
    March."""
    return SupportService(db).close(m, intervention_id, body.status, body.outcome_note)


# ── My students + her own assessments (founder 2026-08-05) ───────────────────
# `require_academic` throughout, and the SERVICE does the narrowing: a teacher
# gets her own assigned children and her own assessments, an admin gets the
# school's. Never another owner's, in either direction (`S-170`).
@router.get("/my-students", response_model=MyStudentsBoard)
def my_students(class_id: uuid.UUID | None = None,
                m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    """The children assigned to her, as a table, filterable by class.

    A teacher with nobody assigned gets a **sentence saying so**, not an empty
    grid she reads as a broken screen."""
    return BandAssessmentService(db).my_students(m, class_id)


@router.get("/assessments", response_model=BandAssessmentList)
def list_assessments(class_id: uuid.UUID | None = None, status: str | None = None,
                     page: int = 1, per_page: int = 20,
                     m: CurrentMember = Depends(require_academic),
                     db: Session = Depends(get_db)):
    """Paginated on purpose: a year of small weekly checks is hundreds of rows.
    `status` is derived from the results, never stored, so it cannot drift."""
    return BandAssessmentService(db).list(m, class_id, status, page, per_page)


@router.post("/assessments", response_model=BandAssessmentRow)
def create_assessment(body: BandAssessmentCreate,
                      m: CurrentMember = Depends(require_academic),
                      db: Session = Depends(get_db)):
    """Set a check for the children she owns in one class — everyone, or the
    ones she picks. The roster of an "everyone" assessment stays **computed**
    (HS-1), so a child assigned next week is on it with no edit."""
    return BandAssessmentService(db).create(m, body)


@router.get("/assessments/{assessment_id}", response_model=BandAssessmentSheet)
def assessment_sheet(assessment_id: uuid.UUID,
                     m: CurrentMember = Depends(require_academic),
                     db: Session = Depends(get_db)):
    """The roster with one input each, in the metric she chose."""
    return BandAssessmentService(db).sheet(m, assessment_id)


@router.put("/assessments/{assessment_id}/results", response_model=BandAssessmentSheet)
def record_results(assessment_id: uuid.UUID, body: AssessmentRecordIn,
                   m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    """**Full replace** — results are capture, and law 3's append-only governs
    decisions. A child omitted goes back to *not evaluated*, never to zero."""
    return BandAssessmentService(db).record(m, assessment_id, body)


@router.delete("/assessments/{assessment_id}", response_model=MessageResponse)
def delete_assessment(assessment_id: uuid.UUID,
                      m: CurrentMember = Depends(require_academic),
                      db: Session = Depends(get_db)):
    """Only while nothing has been recorded against it — after that it is part
    of those children's record."""
    BandAssessmentService(db).delete(m, assessment_id)
    return MessageResponse(message="Assessment removed.")
