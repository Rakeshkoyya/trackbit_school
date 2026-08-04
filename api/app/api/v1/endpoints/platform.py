"""Platform endpoints (super-admin only): the layer above orgs.

The operator creates each school, enters it to run setup from the data the
school handed over, and only then gives the school admin their credentials.
"""

import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_super_admin
from app.core.rate_limit import limiter
from app.schemas.auth import SessionResponse
from app.schemas.events import (
    ObservanceBulkIn,
    ObservanceBulkOut,
    ObservanceImportCommitIn,
    ObservanceImportCommitOut,
    ObservanceImportPreview,
    ObservanceIn,
    ObservanceOut,
)
from app.schemas.platform import (
    CreateSchoolRequest,
    CreateSchoolResult,
    PlatformOrgOut,
    ReadinessOut,
)
from app.services import observance_import
from app.services.observance_import import ObservanceImportService
from app.services.observances import ObservanceService
from app.services.platform import PlatformService
from app.services.readiness import ReadinessService

router = APIRouter()


@router.get("/orgs", response_model=list[PlatformOrgOut])
def list_orgs(
    member=Depends(require_super_admin), db: Session = Depends(get_db)
) -> list[PlatformOrgOut]:
    return PlatformService(db).list_orgs()


@router.post("/orgs", response_model=CreateSchoolResult)
@limiter.limit("10/minute")
def create_school(
    request: Request,
    body: CreateSchoolRequest,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> CreateSchoolResult:
    return PlatformService(db).create_school(member, body)


@router.post("/orgs/{org_id}/enter", response_model=SessionResponse)
@limiter.limit("30/minute")
def enter_org(
    request: Request,
    org_id: uuid.UUID,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> SessionResponse:
    return SessionResponse(**PlatformService(db).enter_org(member, org_id))


# ── the readiness report (V1-2, §6 ⑤) ────────────────────────────────────────
@router.get("/orgs/{org_id}/readiness", response_model=ReadinessOut)
def org_readiness(
    org_id: uuid.UUID,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> ReadinessOut:
    """The page the operator reads before giving the school its password."""
    return ReadinessService(db).report(org_id)


@router.post("/orgs/{org_id}/handover", response_model=ReadinessOut)
def mark_handed_over(
    org_id: uuid.UUID,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> ReadinessOut:
    return ReadinessService(db).mark_handed_over(org_id)


# ── the observance catalogue (V1-7, D-60 / S-149) ────────────────────────────
# Platform data: no org_id, no RLS, super-admin on every write. One curation
# serves every school and one correction fixes every school — which is the whole
# reason it is not a file in the repo.
@router.get("/observances", response_model=list[ObservanceOut])
def list_observances(
    year: int | None = None,
    state: str | None = None,
    q: str | None = None,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> list[ObservanceOut]:
    return ObservanceService(db).list(year=year, state=state, q=q)


@router.post("/observances", response_model=ObservanceOut)
def create_observance(
    body: ObservanceIn,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> ObservanceOut:
    return ObservanceService(db).create(body, member.user.id)


@router.put("/observances/{observance_id}", response_model=ObservanceOut)
def update_observance(
    observance_id: uuid.UUID,
    body: ObservanceIn,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> ObservanceOut:
    return ObservanceService(db).update(observance_id, body)


@router.delete("/observances/{observance_id}", status_code=204)
def retire_observance(
    observance_id: uuid.UUID,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> None:
    """Retire, never delete — a school may already have approved against it."""
    ObservanceService(db).retire(observance_id)


@router.post("/observances/bulk", response_model=ObservanceBulkOut)
def bulk_observances(
    body: ObservanceBulkIn,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> ObservanceBulkOut:
    """A year's import from one source, upserted on (key, date)."""
    return ObservanceService(db).bulk(body, member.user.id)


# ── the annual xlsx import (V1-20) ───────────────────────────────────────────
# `S-151`'s "a small importer per source plus one annual human review", made
# real. This is how 2028 gets into the catalogue without a deploy.
@router.post("/observances/import/analyze", response_model=ObservanceImportPreview)
async def observance_import_analyze(
    file: UploadFile = File(...),
    source: str = "",
    year_hint: int | None = None,
    _=Depends(require_super_admin),
) -> ObservanceImportPreview:
    """Read the sheet, propose a column mapping, and resolve every row.

    The model is asked only about columns the keyword heuristic could not place,
    and it never sees or decides a date (`ingest.py`'s division of labour, and
    `S-123`: asking a model when Diwali is would be the rejected row). Rows that
    cannot be read come back WITH their problems rather than being dropped.
    """
    data = await file.read()
    analysis = observance_import.analyze(data)
    rows = observance_import.preview(
        mapping=analysis["mapping"], rows=analysis["rows"],
        default_source=source.strip() or "Imported spreadsheet", year_hint=year_hint)
    return ObservanceImportPreview(
        columns=analysis["columns"], mapping=analysis["mapping"],
        unmapped_columns=analysis["unmapped_columns"],
        missing_required=analysis["missing_required"],
        low_confidence=analysis["low_confidence"], source=analysis["source"],
        rows=rows,
        ready=sum(1 for r in rows if r.importable),
        blocked=sum(1 for r in rows if not r.importable))


@router.post("/observances/import/commit", response_model=ObservanceImportCommitOut)
def observance_import_commit(
    body: ObservanceImportCommitIn,
    member=Depends(require_super_admin),
    db: Session = Depends(get_db),
) -> ObservanceImportCommitOut:
    """Write what the operator confirmed. Upserts on (key, date), so re-running
    a corrected file FIXES every school rather than double-suggesting."""
    return ObservanceImportService(db).commit(
        mapping=body.mapping, rows=body.rows, default_source=body.source,
        year_hint=body.year_hint, user_id=member.user.id)
