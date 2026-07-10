"""Post-setup read models (V2-P10) — the screens an admin lands on after ingestion.

All reads, all derived. Academic staff may look; nothing here writes.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.schemas.overview import ClassOverviewOut, SchoolOverviewOut, TeacherLoadRow
from app.services.overview import OverviewService

router = APIRouter()


@router.get("/school", response_model=SchoolOverviewOut)
def school_overview(year_id: uuid.UUID | None = None,
                    m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    """Is this year sound? Every class, its gaps, and its worst forecast."""
    return OverviewService(db).school_overview(m, year_id)


@router.get("/classes/{class_id}", response_model=ClassOverviewOut)
def class_overview(class_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    """One class in full: per subject, teacher, period budget vs the grid, syllabus
    size, plan health."""
    return OverviewService(db).class_overview(m, class_id)


@router.get("/teacher-load", response_model=list[TeacherLoadRow])
def teacher_load(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """Periods per week per teacher, counted off the live timetable grid."""
    return OverviewService(db).teacher_load(m)
