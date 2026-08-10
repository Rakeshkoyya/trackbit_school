"""Block capture endpoints (TT-2) — a period that is not a subject.

**Free, deliberately (`D-114`).** `PLAN_TIMETABLE` is free because per-period
attendance cannot resolve a class without the grid; the same reasoning applies to
a games period. Per `D-107` — free buys the act of recording, paid buys the
record over time — scheduling a block and capturing it is free here, while the
hostel week planner and the records board stay on `/sessions` behind
`SESSIONS_HOSTEL` (max).

Every route resolves the meeting through `BlockService.guard`, which asserts the
caller is on the block's staff (or its owner, or an admin) before anything is
read or written. A teacher who is not on the block cannot open it, cannot see its
roster, and cannot check a book — `may_take_block` is the only door.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic
from app.schemas.blocks import BlockHomeworkOut
from app.schemas.classroom import HomeworkCheckIn, HomeworkSheetOut
from app.schemas.sessions import (
    AttendanceRecordIn,
    MediaConfirmIn,
    MediaPresignIn,
    MediaPresignOut,
    MeetingNoteIn,
    MeetingOut,
    SessionStudentCard,
    StudentLogsReplaceIn,
)
from app.services.blocks import BlockService
from app.services.sessions import SessionService

router = APIRouter()


# ── the meeting ───────────────────────────────────────────────────────────────
@router.post("/{block_id}/open", response_model=MeetingOut)
def open_block(block_id: uuid.UUID, on_date: date | None = None,
               m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """Get-or-create this block's meeting for the day, with its roster and card."""
    return BlockService(db).open(m, block_id, on_date)


@router.patch("/meetings/{meeting_id}/attendance", response_model=MeetingOut)
def record_attendance(meeting_id: uuid.UUID, body: AttendanceRecordIn,
                      m: CurrentMember = Depends(require_academic),
                      db: Session = Depends(get_db)):
    """The block's own roll — never the school-day register (`D-91`)."""
    BlockService(db).guard(m, meeting_id)
    return SessionService(db).record(m, meeting_id, body)


@router.put("/meetings/{meeting_id}/note", response_model=MeetingOut)
def set_note(meeting_id: uuid.UUID, body: MeetingNoteIn,
             m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    """The class log, on the kinds that keep one (activity, extra course)."""
    BlockService(db).guard(m, meeting_id)
    return SessionService(db).set_meeting_note(m, meeting_id, body.note)


@router.get("/meetings/{meeting_id}/students/{student_id}", response_model=SessionStudentCard)
def student_card(meeting_id: uuid.UUID, student_id: uuid.UUID,
                 m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    BlockService(db).guard(m, meeting_id)
    return SessionService(db).student_card(m, meeting_id, student_id)


@router.put("/meetings/{meeting_id}/students/{student_id}/logs",
            response_model=SessionStudentCard)
def set_student_logs(meeting_id: uuid.UUID, student_id: uuid.UUID,
                     body: StudentLogsReplaceIn,
                     m: CurrentMember = Depends(require_academic),
                     db: Session = Depends(get_db)):
    BlockService(db).guard(m, meeting_id)
    return SessionService(db).set_student_logs(m, meeting_id, student_id, body.entries)


# ── memories ──────────────────────────────────────────────────────────────────
@router.post("/meetings/{meeting_id}/media/presign", response_model=MediaPresignOut)
def presign_media(meeting_id: uuid.UUID, body: MediaPresignIn,
                  m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    BlockService(db).guard(m, meeting_id)
    return SessionService(db).presign_media(m, meeting_id, body)


@router.post("/meetings/{meeting_id}/media/confirm", response_model=MeetingOut)
def confirm_media(meeting_id: uuid.UUID, body: MediaConfirmIn,
                  m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    BlockService(db).guard(m, meeting_id)
    return SessionService(db).confirm_media(m, meeting_id, body)


@router.post("/meetings/{meeting_id}/media", response_model=MeetingOut)
async def upload_media(
    meeting_id: uuid.UUID,
    file: UploadFile = File(...),
    caption: str | None = Form(default=None),
    student_id: uuid.UUID | None = Form(default=None),
    m: CurrentMember = Depends(require_academic),
    db: Session = Depends(get_db),
):
    BlockService(db).guard(m, meeting_id)
    data = await file.read()
    return SessionService(db).upload_media(
        m, meeting_id, data, file.content_type or "application/octet-stream",
        file.filename or "upload", caption=caption, student_id=student_id)


@router.delete("/media/{media_id}", status_code=204)
def delete_media(media_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    SessionService(db).delete_media(m, media_id)


# ── the homework class: class → subject → the books (TT-2 §3) ────────────────
@router.get("/meetings/{meeting_id}/homework", response_model=BlockHomeworkOut)
def homework(meeting_id: uuid.UUID,
             class_id: uuid.UUID | None = Query(default=None),
             class_subject_id: uuid.UUID | None = Query(default=None),
             m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return BlockService(db).homework(m, meeting_id, class_id, class_subject_id)


@router.get("/meetings/{meeting_id}/homework/{assignment_id}",
            response_model=HomeworkSheetOut)
def homework_sheet(meeting_id: uuid.UUID, assignment_id: uuid.UUID,
                   m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    return BlockService(db).sheet(m, meeting_id, assignment_id)


@router.post("/meetings/{meeting_id}/homework/{assignment_id}/check",
             response_model=HomeworkSheetOut)
def check_homework(meeting_id: uuid.UUID, assignment_id: uuid.UUID, body: HomeworkCheckIn,
                   m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    """Write the verdicts to `homework_results` — the canonical store."""
    return BlockService(db).check(m, meeting_id, assignment_id, body)
