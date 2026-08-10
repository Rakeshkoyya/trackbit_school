"""Fee endpoints (M6, SPRD §5.6; the desk rebuilt in FE-1).

**Every route here is `require_admin`** — teachers never reach fees, which is one
of the two hard rules that hold on every surface including Lucy. The single
exception is `followup_detail`: `D-83`'s one narrow door, where a teacher who has
been *assigned* a fee follow-up task may read that one student's fee detail
inside that one task, and the service enforces the assignment.

`D-126`: these were `require_office_up`, an admin-only alias left over from the
pre-v2 role set. CLAUDE.md asks that it be consolidated to `require_admin` on
touch, and FE-1 touches all of them. The guard is unchanged in effect — both
resolve to admin — so this renames a thing rather than opening one."""

import uuid

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin
from app.schemas.collection import (
    AssignFollowupIn,
    AssignFollowupOut,
    CollectionBoard,
    FeeFollowupDetail,
    FeeNoteIn,
    FeeNoteOut,
    RemindOut,
)
from app.schemas.fees import (
    AddInstallmentIn,
    ApplyStructureIn,
    ApplyStructureOut,
    CloseFeeIn,
    ConfirmProofIn,
    DueDateUpdate,
    FeeEventOut,
    FeeStructureCreate,
    FeeStructureOut,
    FeeStructureUpdate,
    FeeSummary,
    OverdueStudent,
    PaymentIn,
    PresignProofIn,
    PresignProofOut,
    ProofOut,
    SplitInstallmentIn,
    StructureCoverage,
    StudentFeeCreate,
    StudentFeeDetail,
    StudentFeeListItem,
    StudentFeeUpdate,
    TransactionOut,
)
from app.services import fee_events
from app.services.collection import CollectionService
from app.services.fee_proofs import FeeProofService
from app.services.fee_schedule import FeeScheduleService
from app.services.fee_structures import FeeStructureService
from app.services.fees import FeeService

router = APIRouter()


# ── fee structures (FE-1) ────────────────────────────────────────────────────
@router.get("/structures", response_model=list[FeeStructureOut])
def list_structures(class_name: str | None = None, year_id: uuid.UUID | None = None,
                    m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return FeeService(db).list_structures(m, class_name=class_name, year_id=year_id)


# ⚠️ BEFORE `/structures/{fs_id}`. FastAPI matches in declaration order, so a
# literal path declared after a UUID parameter route is unreachable — the
# router would try to parse "coverage" as a UUID and 422 every request.
@router.get("/structures/coverage", response_model=StructureCoverage)
def structure_coverage(year_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                       db: Session = Depends(get_db)):
    """`D-117`: every class of the year, priced or not.

    The founder's completeness check — *"once all the classes and fee structure
    is done"* — cannot be answered by a list of the structures that exist,
    because the class that is missing is exactly the row such a list omits."""
    return FeeStructureService(db).coverage(m, year_id)


@router.post("/structures", response_model=FeeStructureOut)
def create_structure(body: FeeStructureCreate, m: CurrentMember = Depends(require_admin),
                     db: Session = Depends(get_db)):
    return FeeStructureService(db).create(m, body)


@router.get("/structures/{fs_id}", response_model=FeeStructureOut)
def get_structure(fs_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                  db: Session = Depends(get_db)):
    return FeeService(db).get_structure(m, fs_id)


@router.put("/structures/{fs_id}", response_model=FeeStructureOut)
def update_structure(fs_id: uuid.UUID, body: FeeStructureUpdate,
                     m: CurrentMember = Depends(require_admin),
                     db: Session = Depends(get_db)):
    """`D-118`: an edit to the admin, an archive-and-replace underneath.

    **Students already set up keep the amount they were set up on.** A family
    part-way through paying ₹62,000 does not silently owe ₹68,000 because
    somebody corrected the price; the Students tab surfaces the divergence and
    re-applying is a separate, deliberate act."""
    return FeeStructureService(db).update(m, fs_id, body)


@router.post("/structures/{fs_id}/apply", response_model=ApplyStructureOut)
def apply_structure(fs_id: uuid.UUID, body: ApplyStructureIn,
                    m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """`D-120`: set a whole class up in one action.

    Empty `student_ids` means every active student in the class. Students who
    already have a record for the year are skipped and **counted in the reply** —
    a school told "22 set up" when it selected 24 must be able to see why."""
    return FeeStructureService(db).apply(m, fs_id, body)


# ── the actor log (`D-124`) ──────────────────────────────────────────────────
@router.get("/activity", response_model=list[FeeEventOut])
def year_activity(year_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                  db: Session = Depends(get_db)):
    """Everything that happened at the fee desk this year, newest first.

    The founder's case: three admins share this desk, one of them changes
    something, and another needs to find out who to ask. That is a read across
    the whole year, not one child — the per-student feed is separate."""
    return fee_events.for_year(db, m.org_id, year_id)


@router.get("/student-fees/{sf_id}/activity", response_model=list[FeeEventOut])
def student_fee_activity(sf_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                         db: Session = Depends(get_db)):
    """One child's history — what the family page shows beside the ledger."""
    FeeService(db).get_student_fee(m, sf_id)  # same-org guard, 404s otherwise
    return fee_events.for_student_fee(db, m.org_id, sf_id)


# ── student fees ─────────────────────────────────────────────────────────────
@router.get("/student-fees", response_model=list[StudentFeeListItem])
def list_student_fees(
    year_id: uuid.UUID | None = None, class_name: str | None = None,
    status: str | None = None, search: str | None = Query(default=None, max_length=80),
    m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db),
):
    return FeeService(db).list_student_fees(
        m, year_id=year_id, class_name=class_name, status=status, search=search)


@router.post("/student-fees", response_model=StudentFeeDetail)
def enroll(body: StudentFeeCreate, m: CurrentMember = Depends(require_admin),
           db: Session = Depends(get_db)):
    return FeeService(db).enroll(m, body)


@router.get("/student-fees/{sf_id}", response_model=StudentFeeDetail)
def get_student_fee(sf_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    return FeeService(db).get_student_fee(m, sf_id)


@router.patch("/student-fees/{sf_id}", response_model=StudentFeeDetail)
def update_discount(sf_id: uuid.UUID, body: StudentFeeUpdate,
                    m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return FeeService(db).update_discount(m, sf_id, body)


# ── D-127: the transfer (founder Q-2) ────────────────────────────────────────
@router.post("/student-fees/{sf_id}/close", response_model=StudentFeeDetail)
def close_record(sf_id: uuid.UUID, body: CloseFeeIn,
                 m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    """The student transferred out. Unpaid instalments are voided (never
    deleted), the remaining balance comes off the total, and the record goes
    `closed`. Reversible — see `/reopen`."""
    return FeeService(db).close_record(m, sf_id, body)


@router.post("/student-fees/{sf_id}/reopen", response_model=StudentFeeDetail)
def reopen_record(sf_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                  db: Session = Depends(get_db)):
    """Undo the transfer, restoring the schedule from the snapshot the close
    wrote into the append-only log."""
    return FeeService(db).reopen_record(m, sf_id)


@router.get("/student-fees/{sf_id}/transactions", response_model=list[TransactionOut])
def list_transactions(sf_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                      db: Session = Depends(get_db)):
    return FeeService(db).list_transactions(m, sf_id)


# ── installment actions ──────────────────────────────────────────────────────
@router.post("/installments/{inst_id}/pay", response_model=StudentFeeDetail)
def pay(inst_id: uuid.UUID, body: PaymentIn, m: CurrentMember = Depends(require_admin),
        db: Session = Depends(get_db)):
    return FeeService(db).pay(m, inst_id, body)


@router.post("/installments/{inst_id}/mark-paid", response_model=StudentFeeDetail)
def mark_paid(inst_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
              db: Session = Depends(get_db)):
    return FeeService(db).mark_paid(m, inst_id)


@router.post("/installments/{inst_id}/undo", response_model=StudentFeeDetail)
def undo(inst_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
         db: Session = Depends(get_db)):
    return FeeService(db).undo(m, inst_id)


# ── the mutable schedule (FE-1, `D-121`) ─────────────────────────────────────
# All three preserve `sum(instalments) == net payable`, asserted in one place.
# Changing what a family OWES is a discount, not a schedule edit.
@router.post("/installments/{inst_id}/split", response_model=StudentFeeDetail)
def split_installment(inst_id: uuid.UUID, body: SplitInstallmentIn,
                      m: CurrentMember = Depends(require_admin),
                      db: Session = Depends(get_db)):
    """The founder's *"some parent wants more installments"* case.

    Reach for this before `add`: the sum is preserved by construction, so it
    cannot change what the family owes however it is called."""
    return FeeScheduleService(db).split(m, inst_id, body)


@router.post("/student-fees/{sf_id}/installments", response_model=StudentFeeDetail)
def add_installment(sf_id: uuid.UUID, body: AddInstallmentIn,
                    m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """Append an instalment, funded proportionally out of the unpaid ones."""
    return FeeScheduleService(db).add(m, sf_id, body)


@router.delete("/installments/{inst_id}", response_model=StudentFeeDetail)
def remove_installment(inst_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                       db: Session = Depends(get_db)):
    """Remove an UNPAID instalment; its amount returns to the others."""
    return FeeScheduleService(db).remove(m, inst_id)


@router.patch("/installments/{inst_id}/due-date", response_model=StudentFeeDetail)
def update_due_date(inst_id: uuid.UUID, body: DueDateUpdate,
                    m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return FeeService(db).update_due_date(m, inst_id, body)


# ── proof of payment (FE-1, `D-122`/`D-123`) ─────────────────────────────────
# Two ways in, one storage path. `presign` + `confirm` when R2 is configured,
# and the pass-through `upload` when it is not — the HS-1 shape, so the flow is
# testable offline and works in dev with no credentials.
@router.post("/transactions/{txn_id}/proofs/presign", response_model=PresignProofOut)
def presign_proof(txn_id: uuid.UUID, body: PresignProofIn,
                  m: CurrentMember = Depends(require_admin),
                  db: Session = Depends(get_db)):
    return FeeProofService(db).presign(m, txn_id, body.filename, body.content_type)


@router.post("/transactions/{txn_id}/proofs/confirm", response_model=ProofOut)
def confirm_proof(txn_id: uuid.UUID, body: ConfirmProofIn,
                  m: CurrentMember = Depends(require_admin),
                  db: Session = Depends(get_db)):
    """Verifies the object actually landed before writing the row — a failed
    browser PUT would otherwise leave a proof pointing at nothing, and a broken
    thumbnail rendered as evidence is worse than no evidence."""
    return FeeProofService(db).confirm(m, txn_id, body.key, body.caption)


@router.post("/transactions/{txn_id}/proofs", response_model=ProofOut)
def upload_proof(txn_id: uuid.UUID, file: UploadFile = File(...),
                 caption: str | None = Form(default=None),
                 m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    """Pass-through upload — the camera capture on a phone lands here."""
    return FeeProofService(db).upload(m, txn_id, file, caption)


@router.get("/student-fees/{sf_id}/proofs", response_model=list[ProofOut])
def list_proofs(sf_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                db: Session = Depends(get_db)):
    return FeeProofService(db).list_for_fee(m, sf_id)


@router.delete("/proofs/{proof_id}", status_code=204)
def delete_proof(proof_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    """`D-123`: purges the object, keeps the row. A cheque photographed into the
    wrong child's record has to be removable; that it existed is history."""
    FeeProofService(db).delete(m, proof_id)


# ── dashboard card (M4 read-only) ────────────────────────────────────────────
@router.get("/summary", response_model=FeeSummary)
def summary(year_id: uuid.UUID | None = None, m: CurrentMember = Depends(require_admin),
            db: Session = Depends(get_db)):
    return FeeService(db).summary(m, year_id)


@router.get("/overdue-students", response_model=list[OverdueStudent])
def overdue_students(
    year_id: uuid.UUID | None = None, limit: int = Query(20, le=100), offset: int = Query(0, ge=0),
    m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db),
):
    return FeeService(db).overdue_students(m, year_id=year_id, limit=limit, offset=offset)


# ── V1-10 · the collection board (D-64) ──────────────────────────────────────
# Every one of these is `require_admin` — an **admin-only alias** since the
# v2 role collapse — except `followup_detail`, which is the single narrow
# exception `D-83` opened and guards inside the service.
@router.get("/collection", response_model=CollectionBoard)
def collection_board(year_id: uuid.UUID | None = None, quarter: str | None = None,
                     m: CurrentMember = Depends(require_admin),
                     db: Session = Depends(get_db)):
    """The one computation every fee screen renders (`S-152`): quarter strip,
    collection curve, class table with both denominators, and the named
    defaulter list that has existed since P0-D and was called by nothing."""
    return CollectionService(db).board(m, year_id, quarter)


@router.get("/student-fees/{sf_id}/notes", response_model=list[FeeNoteOut])
def fee_notes(sf_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
              db: Session = Depends(get_db)):
    return CollectionService(db).notes(m, sf_id)


@router.post("/student-fees/{sf_id}/notes", response_model=FeeNoteOut)
def add_fee_note(sf_id: uuid.UUID, body: FeeNoteIn,
                 m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    """`D-84`: append-only. What the family SAID is the point — "spoke to the
    mother, paying after the 15th" is what makes a row go away."""
    return CollectionService(db).add_note(m, sf_id, body)


@router.post("/student-fees/{sf_id}/remind", response_model=RemindOut)
def remind(sf_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
           db: Session = Depends(get_db)):
    """One human press per reminder — no automatic dunning. The service holds
    the manners: one per week, quiet hours, primary guardian only, and it stops
    the moment the payment lands."""
    return CollectionService(db).remind(m, sf_id)


@router.post("/student-fees/{sf_id}/assign", response_model=AssignFollowupOut)
def assign_followup(sf_id: uuid.UUID, body: AssignFollowupIn,
                    m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """`D-83`: the task carries the amount, the date and the conversation log —
    the person making the call cannot make it usefully while blind to them."""
    task_id = CollectionService(db).assign_followup(m, sf_id, body.member_id, body.board_id)
    return AssignFollowupOut(task_id=task_id, message="Follow-up assigned.")


# `D-83`: the ONE fee payload a teacher may receive — this student, inside this
# task. `require_academic`, because the guard that matters is the assignment,
# and the service enforces it.
@router.get("/followup/{task_id}", response_model=FeeFollowupDetail)
def followup_detail(task_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    return CollectionService(db).followup_detail(m, task_id)
