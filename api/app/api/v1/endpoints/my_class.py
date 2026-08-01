"""My Class endpoints — the class teacher's area (V1-3, D-03).

require_academic: the service narrows to the caller's own class (admin: any).
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.schemas.my_class import MyClassOut, RegisterOut
from app.services.my_class import MyClassService

router = APIRouter()


@router.get("", response_model=MyClassOut)
def my_classes(m: CurrentMember = Depends(require_academic),
               db: Session = Depends(get_db)):
    return MyClassService(db).my_classes(m)


@router.get("/{class_id}/register", response_model=RegisterOut)
def register(class_id: uuid.UUID, month: str | None = None,
             m: CurrentMember = Depends(require_academic),
             db: Session = Depends(get_db)):
    """The month attendance grid — student × school day, one status per cell."""
    return MyClassService(db).register(m, class_id, month)
