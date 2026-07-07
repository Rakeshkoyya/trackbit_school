"""After-school sessions (M2, SPRD §5.2) — Flow 6.

The teacher runs their own session; a coordinator/director can view all. Opening
today's meeting is get-or-create; capture upserts attendance so the ≤60s tap flow
is idempotent. The record rolls straight to the dashboard — no report written (P5).
"""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import selectinload

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import Session as SessionModel
from app.models import (
    SessionAttendance,
    SessionMeeting,
    SessionStudent,
    Student,
)
from app.schemas.sessions import (
    AttendanceRecordIn,
    MeetingOut,
    MeetingRosterRow,
    SessionCreate,
    SessionDetail,
    SessionOut,
    SessionRecord,
    SessionStudentOut,
)
from app.services import storage


class SessionService:
    def __init__(self, db: OrmSession):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return datetime.now(ZoneInfo(m.org.timezone)).date()

    def _session(self, org_id: uuid.UUID, session_id: uuid.UUID) -> SessionModel:
        s = self.db.scalar(
            select(SessionModel).where(SessionModel.id == session_id, SessionModel.org_id == org_id)
            .options(selectinload(SessionModel.students))
        )
        if s is None:
            raise NotFoundError("Session")
        return s

    def _own(self, m: CurrentMember, s: SessionModel) -> None:
        if not (m.is_coordinator_up or s.owner_member_id == m.membership.id):
            raise ForbiddenError("This isn't your session.", code="not_your_session")

    def _out(self, s: SessionModel) -> SessionOut:
        return SessionOut(id=s.id, name=s.name, weekdays=s.weekdays, time=s.time,
                          active=s.active, roster_count=len(s.students))

    # ── sessions (SS-1) ──────────────────────────────────────────────────────
    def list_my_sessions(self, m: CurrentMember) -> list[SessionOut]:
        q = select(SessionModel).where(SessionModel.org_id == m.org_id).options(
            selectinload(SessionModel.students)).order_by(SessionModel.name)
        if not m.is_coordinator_up:
            q = q.where(SessionModel.owner_member_id == m.membership.id)
        return [self._out(s) for s in self.db.scalars(q)]

    def create(self, m: CurrentMember, body: SessionCreate) -> SessionDetail:
        s = SessionModel(org_id=m.org_id, name=body.name, owner_member_id=m.membership.id,
                         weekdays=body.weekdays, time=body.time)
        self.db.add(s)
        self.db.flush()
        for sid in dict.fromkeys(body.student_ids):  # dedupe, keep order
            if self.db.scalar(select(Student.id).where(Student.id == sid, Student.org_id == m.org_id)):
                self.db.add(SessionStudent(org_id=m.org_id, session_id=s.id, student_id=sid))
        self.db.flush()
        return self.get(m, s.id)

    def get(self, m: CurrentMember, session_id: uuid.UUID) -> SessionDetail:
        s = self._session(m.org_id, session_id)
        student_map = {
            st.id: st for st in self.db.scalars(
                select(Student).where(Student.id.in_([ss.student_id for ss in s.students]))
            )
        } if s.students else {}
        roster = [
            SessionStudentOut(student_id=ss.student_id,
                              full_name=student_map[ss.student_id].full_name if ss.student_id in student_map else "—",
                              roll_no=student_map[ss.student_id].roll_no if ss.student_id in student_map else None)
            for ss in s.students
        ]
        roster.sort(key=lambda r: r.full_name)
        out = self._out(s)
        return SessionDetail(**out.model_dump(), students=roster)

    def delete(self, m: CurrentMember, session_id: uuid.UUID) -> None:
        s = self._session(m.org_id, session_id)
        self._own(m, s)
        self.db.delete(s)

    # ── capture (SS-2) ───────────────────────────────────────────────────────
    def open_meeting(self, m: CurrentMember, session_id: uuid.UUID,
                     on_date: date | None = None) -> MeetingOut:
        s = self._session(m.org_id, session_id)
        self._own(m, s)
        d = on_date or self._today(m)
        meeting = self.db.scalar(
            select(SessionMeeting).where(
                SessionMeeting.org_id == m.org_id, SessionMeeting.session_id == session_id,
                SessionMeeting.date == d)
        )
        if meeting is None:
            meeting = SessionMeeting(org_id=m.org_id, session_id=session_id, date=d)
            self.db.add(meeting)
            self.db.flush()
        return self._meeting_out(m, s, meeting)

    def _meeting_out(self, m: CurrentMember, s: SessionModel, meeting: SessionMeeting) -> MeetingOut:
        att = {a.student_id: a for a in self.db.scalars(
            select(SessionAttendance).where(SessionAttendance.meeting_id == meeting.id))}
        students = {st.id: st for st in self.db.scalars(
            select(Student).where(Student.id.in_([ss.student_id for ss in s.students])))} \
            if s.students else {}
        roster = []
        for ss in s.students:
            st = students.get(ss.student_id)
            a = att.get(ss.student_id)
            roster.append(MeetingRosterRow(
                student_id=ss.student_id,
                full_name=st.full_name if st else "—", roll_no=st.roll_no if st else None,
                status=a.status if a else None,
                late_minutes=a.late_minutes if a else None,
                homework_done=a.homework_done if a else None))
        roster.sort(key=lambda r: r.full_name)
        return MeetingOut(id=meeting.id, session_id=s.id, date=meeting.date,
                          evidence_url=meeting.evidence_url, roster=roster)

    def record(self, m: CurrentMember, meeting_id: uuid.UUID, body: AttendanceRecordIn) -> MeetingOut:
        meeting = self.db.scalar(
            select(SessionMeeting).where(
                SessionMeeting.id == meeting_id, SessionMeeting.org_id == m.org_id))
        if meeting is None:
            raise NotFoundError("Meeting")
        s = self._session(m.org_id, meeting.session_id)
        self._own(m, s)
        roster_ids = {ss.student_id for ss in s.students}
        existing = {a.student_id: a for a in self.db.scalars(
            select(SessionAttendance).where(SessionAttendance.meeting_id == meeting_id))}
        for row in body.rows:
            if row.student_id not in roster_ids:
                continue
            a = existing.get(row.student_id)
            if a is None:
                a = SessionAttendance(org_id=m.org_id, meeting_id=meeting_id,
                                      student_id=row.student_id)
                self.db.add(a)
            a.status = row.status
            a.late_minutes = row.late_minutes if row.status == "late" else None
            a.homework_done = row.homework_done
        self.db.flush()
        return self._meeting_out(m, s, meeting)

    def set_evidence(self, m: CurrentMember, meeting_id: uuid.UUID, data: bytes,
                     content_type: str, filename: str) -> MeetingOut:
        meeting = self.db.scalar(
            select(SessionMeeting).where(
                SessionMeeting.id == meeting_id, SessionMeeting.org_id == m.org_id))
        if meeting is None:
            raise NotFoundError("Meeting")
        s = self._session(m.org_id, meeting.session_id)
        self._own(m, s)
        key = storage.make_key(org_id=m.org_id, instance_id=meeting.id, filename=filename)
        meeting.evidence_url = storage.save_bytes(key, storage.maybe_downscale(data, content_type),
                                                  content_type)
        self.db.flush()
        return self._meeting_out(m, s, meeting)

    # ── records feed (dashboard precursor) ───────────────────────────────────
    def records(self, m: CurrentMember, on_date: date | None = None) -> list[SessionRecord]:
        d = on_date or self._today(m)
        q = (
            select(SessionMeeting, SessionModel.name, SessionModel.owner_member_id)
            .join(SessionModel, SessionModel.id == SessionMeeting.session_id)
            .where(SessionMeeting.org_id == m.org_id, SessionMeeting.date == d)
            .order_by(SessionModel.name)
        )
        if not m.is_coordinator_up:
            q = q.where(SessionModel.owner_member_id == m.membership.id)
        out: list[SessionRecord] = []
        for meeting, name, _owner in self.db.execute(q).all():
            att = list(self.db.scalars(
                select(SessionAttendance).where(SessionAttendance.meeting_id == meeting.id)))
            out.append(SessionRecord(
                session_id=meeting.session_id, meeting_id=meeting.id, session_name=name,
                date=meeting.date,
                present=sum(1 for a in att if a.status == "present"),
                late=sum(1 for a in att if a.status == "late"),
                absent=sum(1 for a in att if a.status == "absent"),
                homework_done=sum(1 for a in att if a.homework_done),
                total=len(att), evidence_url=meeting.evidence_url))
        return out
