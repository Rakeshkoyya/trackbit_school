"""Timetable endpoints (V2-M3, SPRD2 §5.3).

Reads: academic staff (teachers see grids + their own week). Writes (grid edits,
import, period config, draft): admin only."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin
from app.schemas.timetable import (
    Clash,
    DraftOut,
    GridOut,
    ImportAnalyzeOut,
    ImportCommitIn,
    PeriodConfigIn,
    PeriodConfigOut,
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


# ── period timing config ──────────────────────────────────────────────────────
@router.get("/period-config", response_model=PeriodConfigOut)
def get_period_config(year_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                      db: Session = Depends(get_db)):
    return TimetableService(db).get_period_config(m, year_id)


@router.put("/period-config", response_model=PeriodConfigOut)
def set_period_config(body: PeriodConfigIn, m: CurrentMember = Depends(require_admin),
                      db: Session = Depends(get_db)):
    return TimetableService(db).set_period_config(m, body)


# ── import (photo/xlsx → parse → confirm) ─────────────────────────────────────
@router.post("/import/analyze", response_model=ImportAnalyzeOut)
async def import_analyze(
    class_id: uuid.UUID = Query(...),
    file: UploadFile | None = File(default=None),
    m: CurrentMember = Depends(require_admin),
    db: Session = Depends(get_db),
):
    data = await file.read() if file is not None else None
    return TimetableService(db).import_analyze(m, class_id, file_bytes=data)


@router.post("/import/commit", response_model=GridOut)
def import_commit(body: ImportCommitIn, m: CurrentMember = Depends(require_admin),
                  db: Session = Depends(get_db)):
    return TimetableService(db).import_commit(m, body)


# ── assisted draft (flag-gated) ───────────────────────────────────────────────
@router.post("/draft", response_model=DraftOut)
def draft(class_id: uuid.UUID = Query(...), m: CurrentMember = Depends(require_admin),
          db: Session = Depends(get_db)):
    return TimetableService(db).assisted_draft(m, class_id)
