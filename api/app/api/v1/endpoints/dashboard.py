"""Director Dashboard endpoints (M4, SPRD §5.4).

Whole-school view for director + coordinator. The fee card inside the overview is
populated for the director only (§3.3). Alert→task lands work on an existing board.
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import feature_gate, require_coordinator_up
from app.core.features import Feature
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


# Gated like every other door into the Tasks module (`D-109`: it is whole and
# unmetered — `/tasks`, `/boards` and `/recurring` all carry this at the router).
# This route did not, which made "Create task" on the dashboard's alert feed a
# way past that gate: a school without task management could still land work on
# a board it is not allowed to open. The 402 is what the button's upgrade dialog
# now says out loud rather than discovering on submit.
@router.post("/alerts/create-task", response_model=TaskDetailOut,
             dependencies=[Depends(feature_gate(Feature.TASKS_BOARDS))])
def create_task_from_alert(body: CreateTaskFromAlert,
                           m: CurrentMember = Depends(require_coordinator_up),
                           db: Session = Depends(get_db)):
    return DashboardService(db).create_task_from_alert(m, body.board_id, body.title, body.description)
