"""FE-1d — proof of payment, and the receipt number (`D-122`, `D-123`, `D-128`).

⚠️ Every test here forces the **local-disk** storage backend by blanking the R2
settings. `api/.env` has real Cloudflare credentials in it, and a test suite that
uploaded a few hundred synthetic receipts into the school's live bucket would be
a nasty thing to discover later.
"""

import uuid

import pytest

from app.core.config import settings
from app.services import storage

# A one-pixel PNG and a minimal PDF — real bytes with real magic numbers, so the
# content-type checks and any downscaling are exercised rather than side-stepped.
_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
    "de0000000c4944415408d763f8cfc000000301010018dd8db00000000049454e"
    "44ae426082"
)
_PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"


@pytest.fixture(autouse=True)
def local_storage(tmp_path, monkeypatch):
    """Never touch the real bucket. `storage_configured` is a property over
    these four, so blanking them selects the local-disk path for everything."""
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "", raising=False)
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "", raising=False)
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "", raising=False)
    monkeypatch.setattr(settings, "R2_BUCKET", "", raising=False)
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path), raising=False)
    assert not settings.storage_configured
    return tmp_path


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _setup(client, cleanup):
    email = f"admin-{uuid.uuid4().hex[:12]}@example.com"
    reg = client.post("/api/v1/auth/register-org",
                      json={"org_name": "Proof Org", "name": "Director",
                            "email": email, "password": "supersecret1",
                            "timezone": "Asia/Kolkata"}).json()
    cleanup["orgs"].append(uuid.UUID(reg["org"]["id"]))
    cleanup["users"].append(uuid.UUID(reg["user"]["id"]))
    h = _h(reg["access_token"])
    year = client.post("/api/v1/academics/years", headers=h,
                       json={"label": "2026-27", "start_date": "2026-04-01",
                             "end_date": "2027-03-31"}).json()
    klass = client.post("/api/v1/academics/classes", headers=h,
                        json={"academic_year_id": year["id"], "name": "6",
                              "section": "A"}).json()
    client.post("/api/v1/students", headers=h,
                json={"admission_no": "P1", "full_name": "Aarav",
                      "class_id": klass["id"]})
    fs = client.post("/api/v1/fees/structures", headers=h, json={
        "class_name": "6", "academic_year_id": year["id"],
        "total_amount": "60000", "num_installments": 2,
        "installments": [
            {"installment_number": 1, "amount": "30000", "due_date": "2026-04-10"},
            {"installment_number": 2, "amount": "30000",
             "due_date": "2026-09-10"}]}).json()
    client.post(f"/api/v1/fees/structures/{fs['id']}/apply", headers=h, json={})
    sf = client.get("/api/v1/fees/student-fees", headers=h,
                    params={"year_id": year["id"]}).json()[0]
    detail = client.get(f"/api/v1/fees/student-fees/{sf['id']}", headers=h).json()
    return h, year, detail


def _pay(client, h, detail, amount="10000"):
    r = client.post(f"/api/v1/fees/installments/{detail['installments'][0]['id']}/pay",
                    headers=h, json={"amount": amount, "mode": "cash"})
    assert r.status_code == 200, r.text
    txns = client.get(f"/api/v1/fees/student-fees/{detail['id']}/transactions",
                      headers=h).json()
    return next(t for t in txns if t["type"] == "payment")


# ── D-128: generated receipt numbers ─────────────────────────────────────────
def test_receipt_numbers_are_generated_sequentially(client, cleanup):
    """`FR/2026-27/001`, then 002. Sequential per org and year, from a locked
    counter — `MAX + 1` would hand two clerks the same number."""
    h, _year, detail = _setup(client, cleanup)
    _pay(client, h, detail, "10000")
    _pay(client, h, detail, "5000")

    txns = client.get(f"/api/v1/fees/student-fees/{detail['id']}/transactions",
                      headers=h).json()
    receipts = sorted(t["receipt_number"] for t in txns
                      if t["type"] == "payment" and t["receipt_number"])
    assert receipts == ["FR/2026-27/001", "FR/2026-27/002"], receipts


def test_a_typed_receipt_number_is_never_overwritten(client, cleanup):
    """A school reconciling against a pre-printed book types the number on the
    paper in front of it, and that has to win."""
    h, _year, detail = _setup(client, cleanup)
    client.post(f"/api/v1/fees/installments/{detail['installments'][0]['id']}/pay",
                headers=h, json={"amount": "1000", "mode": "cash",
                                 "receipt_number": "BOOK-42"})
    txns = client.get(f"/api/v1/fees/student-fees/{detail['id']}/transactions",
                      headers=h).json()
    assert any(t["receipt_number"] == "BOOK-42" for t in txns)


def test_the_payment_date_lands_on_the_transaction(client, cleanup):
    """`paid_on` was accepted and then dropped: it was written to the instalment,
    so a second payment overwrote the first one's date."""
    h, _year, detail = _setup(client, cleanup)
    client.post(f"/api/v1/fees/installments/{detail['installments'][0]['id']}/pay",
                headers=h, json={"amount": "1000", "mode": "cash",
                                 "paid_on": "2026-05-02"})
    txns = client.get(f"/api/v1/fees/student-fees/{detail['id']}/transactions",
                      headers=h).json()
    paid = next(t for t in txns if t["type"] == "payment")
    assert paid["paid_on"] == "2026-05-02"


# ── D-122: a photo or a PDF ──────────────────────────────────────────────────
def test_a_photo_round_trips(client, cleanup):
    h, _year, detail = _setup(client, cleanup)
    txn = _pay(client, h, detail)

    r = client.post(f"/api/v1/fees/transactions/{txn['id']}/proofs", headers=h,
                    files={"file": ("receipt.png", _PNG, "image/png")})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "photo"

    listed = client.get(f"/api/v1/fees/student-fees/{detail['id']}/proofs",
                        headers=h).json()
    assert len(listed) == 1
    assert listed[0]["url"]


def test_a_pdf_round_trips(client, cleanup):
    h, _year, detail = _setup(client, cleanup)
    txn = _pay(client, h, detail)
    r = client.post(f"/api/v1/fees/transactions/{txn['id']}/proofs", headers=h,
                    files={"file": ("receipt.pdf", _PDF, "application/pdf")})
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "pdf"


def test_a_word_document_is_refused(client, cleanup):
    h, _year, detail = _setup(client, cleanup)
    txn = _pay(client, h, detail)
    r = client.post(f"/api/v1/fees/transactions/{txn['id']}/proofs", headers=h,
                    files={"file": ("notes.docx", b"PK\x03\x04",
                                    "application/msword")})
    assert r.status_code == 422, r.text


def test_presign_falls_back_when_r2_is_unconfigured(client, cleanup):
    """`url is None` is the signal the client uses to POST the bytes instead.
    Dev has no R2, and the flow must still work there."""
    h, _year, detail = _setup(client, cleanup)
    txn = _pay(client, h, detail)
    r = client.post(f"/api/v1/fees/transactions/{txn['id']}/proofs/presign",
                    headers=h,
                    json={"filename": "r.png", "content_type": "image/png"})
    assert r.status_code == 200, r.text
    assert r.json()["url"] is None
    assert r.json()["key"]


def test_confirm_refuses_an_upload_that_never_landed(client, cleanup):
    """A failed browser PUT must not leave a proof row pointing at nothing — a
    broken thumbnail rendered as evidence is worse than no evidence."""
    h, _year, detail = _setup(client, cleanup)
    txn = _pay(client, h, detail)
    presigned = client.post(f"/api/v1/fees/transactions/{txn['id']}/proofs/presign",
                            headers=h,
                            json={"filename": "r.png",
                                  "content_type": "image/png"}).json()
    r = client.post(f"/api/v1/fees/transactions/{txn['id']}/proofs/confirm",
                    headers=h, json={"key": presigned["key"]})
    assert r.status_code == 422, r.text
    assert "did not finish" in r.text


def test_confirm_refuses_another_schools_key(client, cleanup):
    h, _year, detail = _setup(client, cleanup)
    txn = _pay(client, h, detail)
    r = client.post(f"/api/v1/fees/transactions/{txn['id']}/proofs/confirm",
                    headers=h, json={"key": f"{uuid.uuid4()}/x/y.png"})
    assert r.status_code == 422, r.text
    assert "does not belong to this school" in r.text


# ── D-123: soft delete ───────────────────────────────────────────────────────
def test_deleting_a_proof_purges_the_file_but_keeps_the_record(
    client, cleanup, local_storage
):
    """The image goes — the usual reason to delete one is that it is the wrong
    family's cheque — but that it existed, and who removed it, survives."""
    h, _year, detail = _setup(client, cleanup)
    txn = _pay(client, h, detail)
    proof = client.post(f"/api/v1/fees/transactions/{txn['id']}/proofs", headers=h,
                        files={"file": ("r.png", _PNG, "image/png")}).json()

    assert list(local_storage.rglob("*.png")), "upload should have written a file"

    r = client.delete(f"/api/v1/fees/proofs/{proof['id']}", headers=h)
    assert r.status_code == 204, r.text
    assert not list(local_storage.rglob("*.png")), "the object must be purged"

    assert client.get(f"/api/v1/fees/student-fees/{detail['id']}/proofs",
                      headers=h).json() == []
    events = client.get(f"/api/v1/fees/student-fees/{detail['id']}/activity",
                        headers=h).json()
    kinds = [e["kind"] for e in events]
    assert "proof_added" in kinds and "proof_removed" in kinds


def test_paying_with_a_proof_key_attaches_in_one_round_trip(client, cleanup):
    """`proof_key` on the payment body: the clerk presses Record payment once."""
    h, _year, detail = _setup(client, cleanup)
    txn = _pay(client, h, detail)
    presigned = client.post(f"/api/v1/fees/transactions/{txn['id']}/proofs/presign",
                            headers=h,
                            json={"filename": "r.png",
                                  "content_type": "image/png"}).json()
    # Put the bytes where the key says they should be — the local-disk analogue
    # of the browser's PUT to the presigned URL.
    storage.save_bytes(presigned["key"], _PNG, "image/png")

    second = detail["installments"][1]
    r = client.post(f"/api/v1/fees/installments/{second['id']}/pay", headers=h,
                    json={"amount": "1000", "mode": "online",
                          "proof_key": presigned["key"]})
    assert r.status_code == 200, r.text
    proofs = client.get(f"/api/v1/fees/student-fees/{detail['id']}/proofs",
                        headers=h).json()
    assert len(proofs) == 1
