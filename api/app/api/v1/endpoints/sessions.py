"""After-school session endpoints (M2, SPRD §5.2 — SS-1/SS-2 + records feed)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.schemas.common import MessageResponse
from app.schemas.sessions import (
    AttendanceRecordIn,
    MeetingOut,
    SessionCreate,
    SessionDetail,
    SessionOut,
    SessionRecord,
)
from app.services.sessions import SessionService

router = APIRouter()


@router.get("", response_model=list[SessionOut])
def list_sessions(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return SessionService(db).list_my_sessions(m)


@router.post("", response_model=SessionDetail)
def create_session(body: SessionCreate, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    return SessionService(db).create(m, body)


# Literal sub-paths BEFORE /{session_id} so they aren't parsed as an id.
@router.get("/records", response_model=list[SessionRecord])
def session_records(on_date: date | None = None, m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    return SessionService(db).records(m, on_date)


@router.patch("/meetings/{meeting_id}/attendance", response_model=MeetingOut)
def record_attendance(meeting_id: uuid.UUID, body: AttendanceRecordIn,
                      m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return SessionService(db).record(m, meeting_id, body)


@router.post("/meetings/{meeting_id}/photo", response_model=MeetingOut)
async def upload_evidence(meeting_id: uuid.UUID, file: UploadFile = File(...),
                          m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    data = await file.read()
    return SessionService(db).set_evidence(
        m, meeting_id, data, file.content_type or "image/jpeg", file.filename or "evidence.jpg")


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    return SessionService(db).get(m, session_id)


@router.delete("/{session_id}", response_model=MessageResponse)
def delete_session(session_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    SessionService(db).delete(m, session_id)
    return MessageResponse(message="Session deleted.")


@router.post("/{session_id}/meetings", response_model=MeetingOut)
def open_meeting(session_id: uuid.UUID, on_date: date | None = None,
                 m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return SessionService(db).open_meeting(m, session_id, on_date)
