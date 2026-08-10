"""Proof of payment, and the receipt number (FE-1, `D-122`, `D-123`, `D-128`).

The founder asked for *"payment proof like capturing pic or upload the pic or
pdf"*. Two decisions shape the module:

**A proof belongs to the transaction, not to the student.** It is evidence of one
payment; a family with four receipts has four of them. `student_fee_id` is
carried alongside only so the family page can list a child's proofs in one query
rather than joining back through the ledger.

**Deletion is soft** (`D-123`). Law 3 keeps the fact that something was uploaded,
but a cheque photographed into the wrong child's record is a real privacy
problem — so the object is purged from storage and the row survives with
`deleted_at` set.

Storage rides `services/storage.py`, unchanged: presign → client PUT → confirm
when R2 is configured, and a pass-through upload when it is not, so the flow is
testable offline. The row stores the object **key**, never a URL, because
presigned GETs expire and a stored URL rots.
"""

import uuid
from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    FeePaymentProof,
    FeeReceiptCounter,
    StudentFee,
    Transaction,
)
from app.schemas.fees import PresignProofOut, ProofOut
from app.services import fee_events, storage

# HEIC is on the list because it is what an iPhone produces by default, and a
# school that photographs a receipt on an iPhone should not be told its own
# camera is unsupported.
_ALLOWED = {
    "image/jpeg": "photo",
    "image/png": "photo",
    "image/webp": "photo",
    "image/heic": "photo",
    "image/heif": "photo",
    "application/pdf": "pdf",
}
_MAX_BYTES = 15 * 1024 * 1024  # 15 MB — a phone photo of a cheque, with room


def kind_for(content_type: str) -> str:
    kind = _ALLOWED.get((content_type or "").lower().split(";")[0].strip())
    if kind is None:
        raise ValidationError(
            "A payment proof has to be a photo (JPEG, PNG, WebP or HEIC) or a PDF.",
            code="bad_proof_type",
        )
    return kind


def next_receipt_number(
    db: Session, org_id: uuid.UUID, year_id: uuid.UUID
) -> str | None:
    """`D-128` — `FR/2026-27/001`, one sequence per org and academic year.

    Taken under `SELECT … FOR UPDATE` rather than `MAX(receipt_number) + 1`,
    because the school has two clerks at one counter on the first of the month:
    `MAX + 1` hands both of them the same number, and a duplicate receipt number
    is the one thing an auditor always finds.

    Returns None if the year cannot be resolved — a missing receipt number is a
    blank field, never a refused payment.
    """
    year = db.scalar(
        select(AcademicYear).where(
            AcademicYear.id == year_id, AcademicYear.org_id == org_id
        )
    )
    if year is None:
        return None

    counter = db.scalar(
        select(FeeReceiptCounter)
        .where(
            FeeReceiptCounter.org_id == org_id,
            FeeReceiptCounter.academic_year_id == year_id,
        )
        .with_for_update()
    )
    if counter is None:
        counter = FeeReceiptCounter(
            org_id=org_id, academic_year_id=year_id, prefix="FR", next_seq=1
        )
        db.add(counter)
        db.flush()
    seq = counter.next_seq
    counter.next_seq = seq + 1
    label = (year.label or "").replace(" ", "") or str(year_id)[:8]
    return f"{counter.prefix}/{label}/{seq:03d}"


class FeeProofService:
    def __init__(self, db: Session):
        self.db = db

    # ── loading ──────────────────────────────────────────────────────────────
    def _txn(self, org_id: uuid.UUID, txn_id: uuid.UUID) -> Transaction:
        txn = self.db.scalar(
            select(Transaction).where(
                Transaction.id == txn_id, Transaction.org_id == org_id
            )
        )
        if txn is None:
            raise NotFoundError("Payment")
        return txn

    def _out(self, proof: FeePaymentProof, who: str | None = None) -> ProofOut:
        return ProofOut(
            id=proof.id, transaction_id=proof.transaction_id, kind=proof.kind,
            url=storage.url_for(proof.object_key), content_type=proof.content_type,
            size_bytes=proof.size_bytes, caption=proof.caption,
            uploaded_by_name=who, created_at=proof.created_at,
        )

    # ── upload ───────────────────────────────────────────────────────────────
    def presign(self, m: CurrentMember, txn_id: uuid.UUID, filename: str,
                content_type: str) -> PresignProofOut:
        """Hand back a direct-to-R2 PUT url, or None when R2 is unconfigured."""
        txn = self._txn(m.org_id, txn_id)
        kind_for(content_type)
        key = storage.make_key(org_id=m.org_id, instance_id=txn.id,
                               filename=filename)
        return PresignProofOut(key=key, url=storage.presign_put(key, content_type))

    def upload(self, m: CurrentMember, txn_id: uuid.UUID, file: UploadFile,
               caption: str | None = None) -> ProofOut:
        """Pass-through upload: the bytes come to us and we put them away.

        Used when R2 is unconfigured (dev), and as the fallback for any client
        that cannot PUT directly. Images are downscaled; a PDF passes through
        untouched because `maybe_downscale` no-ops on anything non-image.
        """
        txn = self._txn(m.org_id, txn_id)
        content_type = file.content_type or "application/octet-stream"
        kind = kind_for(content_type)
        data = file.file.read()
        if not data:
            raise ValidationError("That file is empty.", code="empty_file")
        if len(data) > _MAX_BYTES:
            raise ValidationError(
                "That file is larger than 15 MB. A photo of the receipt is "
                "enough — there is no need for the full-resolution original.",
                code="proof_too_large",
            )
        data = storage.maybe_downscale(data, content_type)
        key = storage.make_key(org_id=m.org_id, instance_id=txn.id,
                               filename=file.filename or "proof")
        storage.save_bytes(key, data, content_type)
        return self._record(m, txn, key, kind, content_type, len(data), caption)

    def confirm(self, m: CurrentMember, txn_id: uuid.UUID, key: str,
                caption: str | None = None) -> ProofOut:
        """Second half of the presigned flow: verify the object really landed.

        Without this check a failed browser PUT would leave a proof row pointing
        at nothing, and the family page would render a broken thumbnail as
        evidence — worse than no evidence at all.
        """
        txn = self._txn(m.org_id, txn_id)
        if not key.startswith(f"{m.org_id}/"):
            # Keys are minted per org; one that is not ours is either a bug or
            # somebody reaching into another school's bucket prefix.
            raise ValidationError("That upload does not belong to this school.")
        stat = storage.object_stat(key)
        if stat is None:
            raise ValidationError(
                "That upload did not finish. Try attaching the file again.",
                code="upload_not_found",
            )
        size, content_type = stat
        return self._record(m, txn, key, kind_for(content_type), content_type,
                            size, caption)

    def _record(self, m: CurrentMember, txn: Transaction, key: str, kind: str,
                content_type: str, size: int, caption: str | None) -> ProofOut:
        proof = FeePaymentProof(
            org_id=m.org_id, transaction_id=txn.id,
            student_fee_id=txn.student_fee_id, kind=kind, object_key=key,
            content_type=content_type, size_bytes=size, caption=caption,
            uploaded_by_member_id=m.membership.id,
        )
        self.db.add(proof)
        self.db.flush()
        fee_events.record(
            self.db, m, "proof_added",
            f"A {kind} was attached as proof of the ₹{txn.amount:,.0f} payment"
            + (f" — “{caption}”" if caption else "") + ".",
            student_fee_id=txn.student_fee_id,
            meta={"proof_id": str(proof.id), "transaction_id": str(txn.id),
                  "kind": kind},
        )
        return self._out(proof, m.user.name)

    # ── read / remove ────────────────────────────────────────────────────────
    def list_for_fee(self, m: CurrentMember, sf_id: uuid.UUID) -> list[ProofOut]:
        if not self.db.scalar(
            select(StudentFee.id).where(
                StudentFee.id == sf_id, StudentFee.org_id == m.org_id
            )
        ):
            raise NotFoundError("Fee record")
        rows = self.db.scalars(
            select(FeePaymentProof)
            .where(
                FeePaymentProof.org_id == m.org_id,
                FeePaymentProof.student_fee_id == sf_id,
                FeePaymentProof.deleted_at.is_(None),
            )
            .order_by(FeePaymentProof.created_at.desc())
        )
        return [self._out(p) for p in rows]

    def delete(self, m: CurrentMember, proof_id: uuid.UUID) -> None:
        """`D-123`: purge the object, keep the row.

        The school gets rid of the image — which is the point, because the
        reason to delete one is usually that it is the wrong family's cheque —
        while the record that a proof existed and was removed, and by whom,
        survives (law 3).
        """
        proof = self.db.scalar(
            select(FeePaymentProof).where(
                FeePaymentProof.id == proof_id, FeePaymentProof.org_id == m.org_id
            )
        )
        if proof is None:
            raise NotFoundError("Proof")
        if proof.deleted_at is not None:
            return
        proof.deleted_at = datetime.now(UTC)
        proof.deleted_by_member_id = m.membership.id
        storage.delete_object(proof.object_key)
        fee_events.record(
            self.db, m, "proof_removed",
            f"A {proof.kind} attached as payment proof was removed.",
            student_fee_id=proof.student_fee_id,
            meta={"proof_id": str(proof.id)},
        )
        self.db.flush()
