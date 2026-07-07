"""Director Dashboard endpoints (M4, SPRD §5.4).

Whole-school view for director + coordinator. The fee card inside the overview is
populated for the director only (§3.3). Alert→task lands work on an existing board.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_coordinator_up
from app.schemas.dashboard import CreateTaskFromAlert, DashboardOverview, DigestOut
from app.schemas.task import TaskDetailOut
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get("/overview", response_model=DashboardOverview)
def overview(year_id: uuid.UUID | None = None, m: CurrentMember = Depends(require_coordinator_up),
             db: Session = Depends(get_db)):
    return DashboardService(db).overview(m, year_id)


@router.get("/digest", response_model=DigestOut)
def digest(year_id: uuid.UUID | None = None, m: CurrentMember = Depends(require_coordinator_up),
           db: Session = Depends(get_db)):
    return DashboardService(db).digest(m, year_id)


@router.post("/alerts/create-task", response_model=TaskDetailOut)
def create_task_from_alert(body: CreateTaskFromAlert,
                           m: CurrentMember = Depends(require_coordinator_up),
                           db: Session = Depends(get_db)):
    return DashboardService(db).create_task_from_alert(m, body.board_id, body.title, body.description)
