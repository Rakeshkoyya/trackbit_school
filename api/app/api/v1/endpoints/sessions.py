"""After-school & hostel session endpoints (M2 + HS-1, SPRD §5.2)."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.schemas.common import MessageResponse
from app.schemas.sessions import (
    AttendanceRecordIn,
    HomeworkBoardOut,
    MediaConfirmIn,
    MediaPresignIn,
    MediaPresignOut,
    MeetingOut,
    SessionCreate,
    SessionDetail,
    SessionOut,
    SessionRecord,
    SessionUpdate,
    StudentLogsIn,
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


# ── per-student study logs (HS-1) ────────────────────────────────────────────
@router.put("/meetings/{meeting_id}/logs", response_model=MeetingOut)
def set_student_logs(meeting_id: uuid.UUID, body: StudentLogsIn,
                     m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return SessionService(db).set_logs(m, meeting_id, body)


# ── homework board (HS-1) ────────────────────────────────────────────────────
@router.get("/meetings/{meeting_id}/homework", response_model=HomeworkBoardOut)
def homework_board(meeting_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    return SessionService(db).homework_board(m, meeting_id)


# ── media / memories (HS-1) ──────────────────────────────────────────────────
@router.post("/meetings/{meeting_id}/media/presign", response_model=MediaPresignOut)
def presign_media(meeting_id: uuid.UUID, body: MediaPresignIn,
                  m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return SessionService(db).presign_media(m, meeting_id, body)


@router.post("/meetings/{meeting_id}/media/confirm", response_model=MeetingOut)
def confirm_media(meeting_id: uuid.UUID, body: MediaConfirmIn,
                  m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return SessionService(db).confirm_media(m, meeting_id, body)


@router.post("/meetings/{meeting_id}/media", response_model=MeetingOut)
async def upload_media(meeting_id: uuid.UUID, file: UploadFile = File(...),
                       caption: str | None = Form(default=None),
                       m: CurrentMember = Depends(require_academic),
                       db: Session = Depends(get_db)):
    data = await file.read()
    return SessionService(db).upload_media(
        m, meeting_id, data, file.content_type or "image/jpeg",
        file.filename or "media.jpg", caption)


@router.delete("/media/{media_id}", response_model=MessageResponse)
def delete_media(media_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    SessionService(db).delete_media(m, media_id)
    return MessageResponse(message="Media removed.")


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


@router.patch("/{session_id}", response_model=SessionDetail)
def update_session(session_id: uuid.UUID, body: SessionUpdate,
                   m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return SessionService(db).update(m, session_id, body)


@router.delete("/{session_id}", response_model=MessageResponse)
def delete_session(session_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    SessionService(db).delete(m, session_id)
    return MessageResponse(message="Session deleted.")


@router.post("/{session_id}/meetings", response_model=MeetingOut)
def open_meeting(session_id: uuid.UUID, on_date: date | None = None,
                 m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return SessionService(db).open_meeting(m, session_id, on_date)
