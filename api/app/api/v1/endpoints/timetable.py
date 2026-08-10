"""Timetable endpoints (V2-M3, SPRD2 §5.3; the day shape, TT-2).

Reads: academic staff (teachers see grids + their own week).

Writes split in two, deliberately (TT-2, and it revises `D-1`):

* **The initial build stays with the operator** — importing a grid, generating a
  whole year, the legacy period-config, the assisted draft. These are the
  set-up-once acts `require_operator` was written to freeze at handover.
* **The day shape belongs to the school** — the timings, one cell at a time, and
  the blocks. Founder, 2026-08-10: *"timetable can be editable after the
  importing… for additional configurations admin can login and from the UI they
  can change it as required"*, with the worked example of adding hosteller-only
  afternoon classes after Term 1. A school that cannot move its own games period
  without filing a ticket will keep its real timetable on paper, and then the
  register, the day-book and the daily report are all describing a fiction.

`require_admin`, not `require_academic`: a teacher still cannot edit the grid.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin, require_operator
from app.schemas.timetable import (
    BellHistoryOut,
    BellScheduleIn,
    BellScheduleOut,
    BlockIn,
    BlockOut,
    BlockUpdate,
    Clash,
    DraftOut,
    GridOut,
    ImportAnalyzeOut,
    ImportCommitIn,
    OrgGenerateIn,
    OrgGenerateOut,
    PeriodConfigIn,
    PeriodConfigOut,
    SlotBulkIn,
    SlotBulkOut,
    SlotClearIn,
    SlotIn,
    TeacherWeekOut,
)
from app.services.timetable import TimetableService

router = APIRouter()


# ── grid ─────────────────────────────────────────────────────────────────────
@router.get("/grid", response_model=GridOut)
def get_grid(class_id: uuid.UUID, on_date: date | None = None,
             m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return TimetableService(db).get_grid(m, class_id, on_date)


@router.put("/slot", response_model=GridOut)
def set_slot(body: SlotIn, m: CurrentMember = Depends(require_admin),
             db: Session = Depends(get_db)):
    return TimetableService(db).set_slot(m, body)


@router.post("/slot/bulk", response_model=SlotBulkOut)
def set_slots_bulk(body: SlotBulkIn, m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    """One block across many classes and days — "assembly, period 1, everyone"."""
    return TimetableService(db).set_slots_bulk(m, body)


@router.post("/slot/clear", response_model=GridOut)
def clear_slot(body: SlotClearIn, m: CurrentMember = Depends(require_admin),
               db: Session = Depends(get_db)):
    return TimetableService(db).clear_slot(m, body)


@router.get("/validate", response_model=list[Clash])
def validate_grid(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return TimetableService(db).validate_grid(m)


# ── teacher view ──────────────────────────────────────────────────────────────
@router.get("/my-week", response_model=TeacherWeekOut)
def my_week(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return TimetableService(db).teacher_week(m)


@router.get("/teacher/{member_id}/week", response_model=TeacherWeekOut)
def teacher_week(member_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    return TimetableService(db).teacher_week(m, member_id=member_id)


# ── the bell schedule: when the day happens (TT-2) ────────────────────────────
@router.get("/bell", response_model=BellScheduleOut)
def get_bell(year_id: uuid.UUID, on_date: date | None = None,
             m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """The school day as it stands (or stood, with `on_date`)."""
    return TimetableService(db).get_bell(m, year_id, on_date)


@router.put("/bell", response_model=BellScheduleOut)
def set_bell(body: BellScheduleIn, m: CurrentMember = Depends(require_admin),
             db: Session = Depends(get_db)):
    """Reshape the day from `effective_from`. Append-only: the old shape stays
    readable, so last term's timesheets keep last term's clock."""
    return TimetableService(db).set_bell(m, body)


@router.get("/bell/history", response_model=BellHistoryOut)
def bell_history(year_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return TimetableService(db).bell_history(m, year_id)


# ── blocks: a period that is not a subject (TT-2) ─────────────────────────────
@router.get("/blocks", response_model=list[BlockOut])
def list_blocks(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return TimetableService(db).list_blocks(m)


@router.post("/blocks", response_model=BlockOut, status_code=201)
def create_block(body: BlockIn, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    return TimetableService(db).create_block(m, body)


@router.get("/blocks/{block_id}", response_model=BlockOut)
def get_block(block_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
              db: Session = Depends(get_db)):
    return TimetableService(db).get_block(m, block_id)


@router.patch("/blocks/{block_id}", response_model=BlockOut)
def update_block(block_id: uuid.UUID, body: BlockUpdate,
                 m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return TimetableService(db).update_block(m, block_id, body)


@router.delete("/blocks/{block_id}", status_code=204)
def delete_block(block_id: uuid.UUID, m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    TimetableService(db).delete_block(m, block_id)


# ── period timing config (legacy contract — kept, see the service docstring) ──
@router.get("/period-config", response_model=PeriodConfigOut)
def get_period_config(year_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                      db: Session = Depends(get_db)):
    return TimetableService(db).get_period_config(m, year_id)


@router.put("/period-config", response_model=PeriodConfigOut)
def set_period_config(body: PeriodConfigIn, m: CurrentMember = Depends(require_operator),
                      db: Session = Depends(get_db)):
    """Setup-time timings. Stays operator-only and frozen at handover; a live
    school reshapes its day through `PUT /bell`, which keeps the history."""
    return TimetableService(db).set_period_config(m, body)


# ── import (photo/xlsx → parse → confirm) ─────────────────────────────────────
@router.post("/import/analyze", response_model=ImportAnalyzeOut)
async def import_analyze(
    class_id: uuid.UUID = Query(...),
    file: UploadFile | None = File(default=None),
    m: CurrentMember = Depends(require_operator),
    db: Session = Depends(get_db),
):
    data = await file.read() if file is not None else None
    return TimetableService(db).import_analyze(m, class_id, file_bytes=data)


@router.post("/import/commit", response_model=GridOut)
def import_commit(body: ImportCommitIn, m: CurrentMember = Depends(require_operator),
                  db: Session = Depends(get_db)):
    return TimetableService(db).import_commit(m, body)


# ── whole-school generation (deterministic) ───────────────────────────────────
@router.post("/generate", response_model=OrgGenerateOut)
def generate_year_grid(body: OrgGenerateIn, m: CurrentMember = Depends(require_operator),
                       db: Session = Depends(get_db)):
    """Fill every class of the year at once (teacher-clash-aware, honours
    periods_per_week). Preview by default; `apply=true` replaces the live grid."""
    return TimetableService(db).generate_year_grid(m, body)


# ── assisted draft (flag-gated) ───────────────────────────────────────────────
@router.post("/draft", response_model=DraftOut)
def draft(class_id: uuid.UUID = Query(...), m: CurrentMember = Depends(require_operator),
          db: Session = Depends(get_db)):
    return TimetableService(db).assisted_draft(m, class_id)
