"""After-school & hostel sessions (M2 + HS-1, SPRD §5.2) — Flow 6 + the evening.

The teacher runs their own session; an admin plans the hostel week and can view
all. Opening today's meeting is get-or-create; capture upserts attendance so the
≤60s tap flow is idempotent. The record rolls straight to the dashboard — no
report written (P5).

HS-1 promotes a session into the hostel-timetable unit:
- roster is *computed*: linked classes (optionally Hosteller-category only) ∪
  explicit session_students — a newly admitted hosteller appears with zero work;
- a deterministic teacher-clash check guards the week grid (no solver, §11);
- `kind` picks the capture surface: study (optional per-student logs), homework
  (computed board over homework_assignments — a read view, no new capture),
  activity (photo/video memories in R2, attached to the meeting only — P5).
"""

import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import selectinload

from app.core.context import CurrentMember
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.models import (
    ClassSubject,
    HomeworkAssignment,
    Membership,
    SchoolClass,
    SessionAttendance,
    SessionClass,
    SessionMedia,
    SessionMeeting,
    SessionStudent,
    SessionStudentLog,
    Student,
    StudentCategory,
    Subject,
)
from app.models import Session as SessionModel
from app.schemas.sessions import (
    AttendanceRecordIn,
    HomeworkBoardOut,
    HomeworkBoardRow,
    HomeworkItem,
    MediaConfirmIn,
    MediaOut,
    MediaPresignIn,
    MediaPresignOut,
    MeetingOut,
    MeetingRosterRow,
    SessionCreate,
    SessionDetail,
    SessionOut,
    SessionRecord,
    SessionStudentCard,
    SessionStudentOut,
    SessionUpdate,
    StudentLogEntry,
)
from app.services import storage

# Media limits (HS-1). Direct uploads pass through the API worker's memory, so
# they stay small; anything bigger goes presigned straight to R2.
_MAX_DIRECT_BYTES = 25 * 1024 * 1024
_MAX_MEDIA_BYTES = 300 * 1024 * 1024
# A session with a start but no end still occupies the grid; assume this length
# for the clash check so two open-ended blocks at the same time still collide.
_DEFAULT_MINUTES = 45


def _minutes(hhmm: str) -> int | None:
    try:
        h, m = hhmm.split(":")
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _media_kind(content_type: str) -> str:
    if content_type.startswith("image/"):
        return "photo"
    if content_type.startswith("video/"):
        return "video"
    raise ValidationError("Only photos and videos can be attached.",
                          code="unsupported_media_type")


class SessionService:
    def __init__(self, db: OrmSession):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return datetime.now(ZoneInfo(m.org.timezone)).date()

    def _session(self, org_id: uuid.UUID, session_id: uuid.UUID) -> SessionModel:
        s = self.db.scalar(
            select(SessionModel).where(SessionModel.id == session_id, SessionModel.org_id == org_id)
            .options(selectinload(SessionModel.students), selectinload(SessionModel.classes))
        )
        if s is None:
            raise NotFoundError("Session")
        return s

    def _own(self, m: CurrentMember, s: SessionModel) -> None:
        if not (m.is_coordinator_up or s.owner_member_id == m.membership.id):
            raise ForbiddenError("This isn't your session.", code="not_your_session")

    # ── computed roster (HS-1) ───────────────────────────────────────────────
    def _roster(self, org_id: uuid.UUID, s: SessionModel) -> list[tuple[Student, bool]]:
        """Effective roster: linked-class students ∪ explicit rows. Returns
        (student, explicit) sorted by name. Computed, never materialized."""
        explicit_ids = [ss.student_id for ss in s.students]
        by_id: dict[uuid.UUID, tuple[Student, bool]] = {}
        class_ids = [sc.class_id for sc in s.classes]
        if class_ids:
            q = select(Student).where(
                Student.org_id == org_id, Student.class_id.in_(class_ids),
                Student.status == "active")
            if s.hostellers_only:
                # Category is org-editable data; the convention is the seeded
                # "Hosteller" name (case-insensitive).
                q = q.join(StudentCategory, StudentCategory.id == Student.category_id).where(
                    func.lower(StudentCategory.name) == "hosteller")
            for st in self.db.scalars(q):
                by_id[st.id] = (st, False)
        if explicit_ids:
            for st in self.db.scalars(
                    select(Student).where(Student.org_id == org_id,
                                          Student.id.in_(explicit_ids))):
                by_id[st.id] = (st, True)
        return sorted(by_id.values(), key=lambda t: t[0].full_name)

    # ── teacher-clash check (HS-1, deterministic — §11: no solver) ──────────
    def _check_clash(self, org_id: uuid.UUID, s: SessionModel) -> None:
        start = _minutes(s.time) if s.time else None
        if start is None or not s.weekdays or s.owner_member_id is None:
            return  # nothing concrete enough to collide
        end = (_minutes(s.end_time) if s.end_time else None) or start + _DEFAULT_MINUTES
        others = self.db.scalars(
            select(SessionModel).where(
                SessionModel.org_id == org_id, SessionModel.active.is_(True),
                SessionModel.owner_member_id == s.owner_member_id,
                SessionModel.id != s.id)
        )
        days = set(s.weekdays)
        for o in others:
            o_start = _minutes(o.time) if o.time else None
            if o_start is None or not days.intersection(o.weekdays):
                continue
            o_end = (_minutes(o.end_time) if o.end_time else None) or o_start + _DEFAULT_MINUTES
            if start < o_end and o_start < end:
                raise ConflictError(
                    f"The teacher already runs “{o.name}” at that time.",
                    code="teacher_clash", details={"session_id": str(o.id), "name": o.name})

    def _out_many(self, m: CurrentMember, sessions: list[SessionModel]) -> list[SessionOut]:
        """SessionOut rows with roster counts, class labels and teacher names —
        batched (one query per lookup, not per session): the DB is remote."""
        class_ids = {sc.class_id for s in sessions for sc in s.classes}
        classes = {c.id: c for c in self.db.scalars(
            select(SchoolClass).where(SchoolClass.id.in_(class_ids)))} if class_ids else {}
        owner_ids = {s.owner_member_id for s in sessions if s.owner_member_id}
        owners = {mem.id: mem.user.name for mem in self.db.scalars(
            select(Membership).where(Membership.id.in_(owner_ids))
            .options(selectinload(Membership.user)))} if owner_ids else {}

        # Per-class active-student id sets (both filters), then union per session.
        per_class: dict[uuid.UUID, set[uuid.UUID]] = {}
        per_class_hostel: dict[uuid.UUID, set[uuid.UUID]] = {}
        if class_ids:
            for class_id, student_id, cat in self.db.execute(
                    select(Student.class_id, Student.id, StudentCategory.name)
                    .outerjoin(StudentCategory, StudentCategory.id == Student.category_id)
                    .where(Student.org_id == m.org_id, Student.class_id.in_(class_ids),
                           Student.status == "active")):
                per_class.setdefault(class_id, set()).add(student_id)
                if (cat or "").lower() == "hosteller":
                    per_class_hostel.setdefault(class_id, set()).add(student_id)

        out = []
        for s in sessions:
            ids = {ss.student_id for ss in s.students}
            source = per_class_hostel if s.hostellers_only else per_class
            for sc in s.classes:
                ids |= source.get(sc.class_id, set())
            labels = []
            for sc in s.classes:
                c = classes.get(sc.class_id)
                if c:
                    labels.append(f"{c.name}{c.section or ''}")
            out.append(SessionOut(
                id=s.id, name=s.name, weekdays=s.weekdays, time=s.time, end_time=s.end_time,
                kind=s.kind, hostellers_only=s.hostellers_only, active=s.active,
                roster_count=len(ids), class_labels=sorted(labels),
                teacher_name=owners.get(s.owner_member_id),
                owner_member_id=s.owner_member_id))
        return out

    # ── sessions (SS-1) ──────────────────────────────────────────────────────
    def list_my_sessions(self, m: CurrentMember) -> list[SessionOut]:
        q = select(SessionModel).where(SessionModel.org_id == m.org_id).options(
            selectinload(SessionModel.students), selectinload(SessionModel.classes)
        ).order_by(SessionModel.time, SessionModel.name)
        if not m.is_coordinator_up:
            q = q.where(SessionModel.owner_member_id == m.membership.id)
        return self._out_many(m, list(self.db.scalars(q)))

    def _resolve_owner(self, m: CurrentMember, owner_member_id: uuid.UUID | None) -> uuid.UUID:
        if owner_member_id is None or owner_member_id == m.membership.id:
            return m.membership.id
        if not m.is_coordinator_up:
            raise ForbiddenError("Only an admin can assign a session to someone else.",
                                 code="not_admin")
        owner = self.db.scalar(select(Membership).where(
            Membership.id == owner_member_id, Membership.org_id == m.org_id,
            Membership.status == "active"))
        if owner is None:
            raise NotFoundError("Member")
        return owner.id

    def _set_links(self, m: CurrentMember, s: SessionModel,
                   student_ids: list[uuid.UUID] | None,
                   class_ids: list[uuid.UUID] | None) -> None:
        if student_ids is not None:
            s.students.clear()
            self.db.flush()
            for sid in dict.fromkeys(student_ids):  # dedupe, keep order
                if self.db.scalar(select(Student.id).where(
                        Student.id == sid, Student.org_id == m.org_id)):
                    self.db.add(SessionStudent(org_id=m.org_id, session_id=s.id, student_id=sid))
        if class_ids is not None:
            s.classes.clear()
            self.db.flush()
            for cid in dict.fromkeys(class_ids):
                if self.db.scalar(select(SchoolClass.id).where(
                        SchoolClass.id == cid, SchoolClass.org_id == m.org_id)):
                    self.db.add(SessionClass(org_id=m.org_id, session_id=s.id, class_id=cid))

    def create(self, m: CurrentMember, body: SessionCreate) -> SessionDetail:
        s = SessionModel(org_id=m.org_id, name=body.name,
                         owner_member_id=self._resolve_owner(m, body.owner_member_id),
                         weekdays=body.weekdays, time=body.time, end_time=body.end_time,
                         kind=body.kind, hostellers_only=body.hostellers_only)
        self.db.add(s)
        self.db.flush()
        self._set_links(m, s, body.student_ids, body.class_ids)
        self.db.flush()
        self.db.refresh(s)
        self._check_clash(m.org_id, s)
        return self.get(m, s.id)

    def update(self, m: CurrentMember, session_id: uuid.UUID, body: SessionUpdate) -> SessionDetail:
        s = self._session(m.org_id, session_id)
        self._own(m, s)
        if body.owner_member_id is not None:
            s.owner_member_id = self._resolve_owner(m, body.owner_member_id)
        for field in ("name", "weekdays", "time", "end_time", "kind", "hostellers_only", "active"):
            v = getattr(body, field)
            if v is not None:
                setattr(s, field, v)
        self._set_links(m, s, body.student_ids, body.class_ids)
        self.db.flush()
        self.db.refresh(s)
        self._check_clash(m.org_id, s)
        return self.get(m, s.id)

    def get(self, m: CurrentMember, session_id: uuid.UUID) -> SessionDetail:
        s = self._session(m.org_id, session_id)
        roster = [
            SessionStudentOut(student_id=st.id, full_name=st.full_name, roll_no=st.roll_no,
                              explicit=explicit)
            for st, explicit in self._roster(m.org_id, s)
        ]
        out = self._out_many(m, [s])[0]
        return SessionDetail(**out.model_dump(), students=roster,
                             class_ids=[sc.class_id for sc in s.classes])

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

    def _media_rows(self, meeting_id: uuid.UUID) -> list[SessionMedia]:
        return list(self.db.scalars(
            select(SessionMedia).where(SessionMedia.meeting_id == meeting_id)
            .order_by(SessionMedia.created_at)))

    @staticmethod
    def _media_out(rows: list[SessionMedia]) -> list[MediaOut]:
        return [
            MediaOut(id=md.id, kind=md.kind, url=storage.url_for(md.object_key),
                     content_type=md.content_type, caption=md.caption,
                     student_id=md.student_id, created_at=md.created_at)
            for md in rows
        ]

    def _class_labels(self, class_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not class_ids:
            return {}
        return {c.id: f"{c.name}{c.section or ''}" for c in self.db.scalars(
            select(SchoolClass).where(SchoolClass.id.in_(class_ids)))}

    def _meeting_out(self, m: CurrentMember, s: SessionModel, meeting: SessionMeeting) -> MeetingOut:
        att = {a.student_id: a for a in self.db.scalars(
            select(SessionAttendance).where(SessionAttendance.meeting_id == meeting.id))}
        logs_by_student: dict[uuid.UUID, list[SessionStudentLog]] = {}
        for log in self.db.scalars(
                select(SessionStudentLog).where(SessionStudentLog.meeting_id == meeting.id)
                .order_by(SessionStudentLog.created_at)):
            logs_by_student.setdefault(log.student_id, []).append(log)
        media = self._media_rows(meeting.id)
        media_counts: dict[uuid.UUID, int] = {}
        for md in media:
            if md.student_id:
                media_counts[md.student_id] = media_counts.get(md.student_id, 0) + 1
        full = self._roster(m.org_id, s)
        classes = self._class_labels({st.class_id for st, _ in full if st.class_id})
        roster = []
        for st, _explicit in full:
            a = att.get(st.id)
            st_logs = logs_by_student.get(st.id, [])
            preview = " · ".join(
                (f"{log.section}: {log.note}" if log.section else log.note) for log in st_logs
            ) or None
            roster.append(MeetingRosterRow(
                student_id=st.id, full_name=st.full_name, roll_no=st.roll_no,
                class_label=classes.get(st.class_id),
                status=a.status if a else None,
                late_minutes=a.late_minutes if a else None,
                homework_done=a.homework_done if a else None,
                log_count=len(st_logs), log_note=preview,
                media_count=media_counts.get(st.id, 0)))
        # The meeting's media strip is the whole-class memories; per-student media
        # lives on the student page (SessionStudentCard).
        return MeetingOut(id=meeting.id, session_id=s.id, date=meeting.date, kind=s.kind,
                          evidence_url=meeting.evidence_url, roster=roster,
                          media=self._media_out([md for md in media if md.student_id is None]))

    def _meeting(self, m: CurrentMember,
                 meeting_id: uuid.UUID) -> tuple[SessionMeeting, SessionModel]:
        meeting = self.db.scalar(
            select(SessionMeeting).where(
                SessionMeeting.id == meeting_id, SessionMeeting.org_id == m.org_id))
        if meeting is None:
            raise NotFoundError("Meeting")
        s = self._session(m.org_id, meeting.session_id)
        self._own(m, s)
        return meeting, s

    def record(self, m: CurrentMember, meeting_id: uuid.UUID,
               body: AttendanceRecordIn) -> MeetingOut:
        meeting, s = self._meeting(m, meeting_id)
        roster_ids = {st.id for st, _ in self._roster(m.org_id, s)}
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

    # ── per-student study logs (HS-2: named sections; optional — P1v2) ──────
    def set_student_logs(self, m: CurrentMember, meeting_id: uuid.UUID,
                         student_id: uuid.UUID, entries: list[StudentLogEntry]) -> SessionStudentCard:
        """Full-replace this student's log sections for the meeting (save = replace,
        like attendance and observation sections). Empty list clears everything."""
        meeting, s = self._meeting(m, meeting_id)
        if student_id not in {st.id for st, _ in self._roster(m.org_id, s)}:
            raise NotFoundError("Student")
        for log in self.db.scalars(select(SessionStudentLog).where(
                SessionStudentLog.meeting_id == meeting_id,
                SessionStudentLog.student_id == student_id)):
            self.db.delete(log)
        self.db.flush()
        seen: set[str] = set()
        for e in entries:
            section = e.section.strip()
            note = e.note.strip()
            if not note or section.lower() in seen:
                continue
            seen.add(section.lower())
            self.db.add(SessionStudentLog(
                org_id=m.org_id, meeting_id=meeting_id, student_id=student_id,
                section=section, note=note, member_id=m.membership.id))
        self.db.flush()
        return self.student_card(m, meeting_id, student_id)

    # ── homework items (HS-1) — a read view over homework_assignments ───────
    def _homework_map(self, org_id: uuid.UUID, d: date,
                      roster: list[tuple[Student, bool]]) -> dict[uuid.UUID, list[HomeworkItem]]:
        """Per-student open homework for the meeting date, one batched query set."""
        class_ids = {st.class_id for st, _ in roster if st.class_id}
        if not class_ids:
            return {}
        cs_by_class: dict[uuid.UUID, set[uuid.UUID]] = {}
        subject_of_cs: dict[uuid.UUID, str] = {}
        for cs_id, class_id, subject_name in self.db.execute(
                select(ClassSubject.id, ClassSubject.class_id, Subject.name)
                .join(Subject, Subject.id == ClassSubject.subject_id)
                .where(ClassSubject.class_id.in_(class_ids))):
            cs_by_class.setdefault(class_id, set()).add(cs_id)
            subject_of_cs[cs_id] = subject_name
        if not subject_of_cs:
            return {}
        # "Open tonight": set on/before the meeting day and either not yet due,
        # or (no due date) set within the last 3 days.
        assignments = list(self.db.scalars(
            select(HomeworkAssignment).where(
                HomeworkAssignment.org_id == org_id,
                HomeworkAssignment.class_subject_id.in_(subject_of_cs.keys()),
                HomeworkAssignment.date <= d,
                (HomeworkAssignment.due_date >= d)
                | (HomeworkAssignment.due_date.is_(None)
                   & (HomeworkAssignment.date >= d - timedelta(days=3))))
            .order_by(HomeworkAssignment.date.desc())))
        out: dict[uuid.UUID, list[HomeworkItem]] = {}
        for st, _explicit in roster:
            out[st.id] = [
                HomeworkItem(assignment_id=a.id, subject=subject_of_cs[a.class_subject_id],
                             text=a.text, assigned_on=a.date, due_date=a.due_date,
                             personal=a.student_id is not None)
                for a in assignments
                if a.class_subject_id in cs_by_class.get(st.class_id, set())
                and (a.student_id is None or a.student_id == st.id)
            ]
        return out

    def homework_board(self, m: CurrentMember, meeting_id: uuid.UUID) -> HomeworkBoardOut:
        meeting, s = self._meeting(m, meeting_id)
        roster = self._roster(m.org_id, s)
        att = {a.student_id: a for a in self.db.scalars(
            select(SessionAttendance).where(SessionAttendance.meeting_id == meeting.id))}
        classes = self._class_labels({st.class_id for st, _ in roster if st.class_id})
        items = self._homework_map(m.org_id, meeting.date, roster)
        rows = []
        for st, _explicit in roster:
            a_row = att.get(st.id)
            rows.append(HomeworkBoardRow(
                student_id=st.id, full_name=st.full_name,
                class_label=classes.get(st.class_id),
                homework_done=a_row.homework_done if a_row else None,
                items=items.get(st.id, [])))
        return HomeworkBoardOut(meeting_id=meeting.id, date=meeting.date, rows=rows)

    # ── per-student card (HS-2) — everything the student page needs at once ─
    def student_card(self, m: CurrentMember, meeting_id: uuid.UUID,
                     student_id: uuid.UUID) -> SessionStudentCard:
        meeting, s = self._meeting(m, meeting_id)
        roster = self._roster(m.org_id, s)
        target = next((st for st, _ in roster if st.id == student_id), None)
        if target is None:
            raise NotFoundError("Student")
        a = self.db.scalar(select(SessionAttendance).where(
            SessionAttendance.meeting_id == meeting_id,
            SessionAttendance.student_id == student_id))
        logs = list(self.db.scalars(
            select(SessionStudentLog).where(
                SessionStudentLog.meeting_id == meeting_id,
                SessionStudentLog.student_id == student_id)
            .order_by(SessionStudentLog.created_at)))
        media = [md for md in self._media_rows(meeting_id) if md.student_id == student_id]
        classes = self._class_labels({target.class_id} if target.class_id else set())
        items = self._homework_map(m.org_id, meeting.date, [(target, False)])
        return SessionStudentCard(
            meeting_id=meeting.id, date=meeting.date, session_id=s.id, session_name=s.name,
            kind=s.kind, student_id=target.id, full_name=target.full_name,
            roll_no=target.roll_no, class_label=classes.get(target.class_id),
            status=a.status if a else None, late_minutes=a.late_minutes if a else None,
            homework_done=a.homework_done if a else None,
            homework=items.get(target.id, []),
            logs=[StudentLogEntry(section=log.section, note=log.note) for log in logs],
            media=self._media_out(media))

    # ── media / memories (HS-1/HS-2) ─────────────────────────────────────────
    def _check_media_student(self, m: CurrentMember, s: SessionModel,
                             student_id: uuid.UUID | None) -> None:
        if student_id is not None and student_id not in {
                st.id for st, _ in self._roster(m.org_id, s)}:
            raise NotFoundError("Student")

    def presign_media(self, m: CurrentMember, meeting_id: uuid.UUID,
                      body: MediaPresignIn) -> MediaPresignOut:
        meeting, s = self._meeting(m, meeting_id)
        self._check_media_student(m, s, body.student_id)
        _media_kind(body.content_type)  # validates the type
        if body.size_bytes > _MAX_MEDIA_BYTES:
            raise ValidationError("File is too large (max 300 MB).", code="media_too_large")
        key = storage.make_key(org_id=m.org_id, instance_id=meeting.id, filename=body.filename)
        return MediaPresignOut(key=key, upload_url=storage.presign_put(key, body.content_type))

    def confirm_media(self, m: CurrentMember, meeting_id: uuid.UUID,
                      body: MediaConfirmIn) -> MeetingOut:
        meeting, s = self._meeting(m, meeting_id)
        self._check_media_student(m, s, body.student_id)
        # make_key binds the key to org and meeting; refuse anything else so a
        # caller can't attach (or probe) another org's objects.
        if not body.key.startswith(f"{m.org_id}/{meeting.id}/"):
            raise ValidationError("Unknown upload key.", code="bad_media_key")
        stat = storage.object_stat(body.key)
        if stat is None:
            raise ValidationError("Upload not found — it may have failed; try again.",
                                  code="media_not_uploaded")
        size, content_type = stat
        self.db.add(SessionMedia(
            org_id=m.org_id, meeting_id=meeting.id, kind=_media_kind(content_type),
            object_key=body.key, content_type=content_type, size_bytes=size,
            caption=body.caption, student_id=body.student_id,
            uploaded_by_member_id=m.membership.id))
        self.db.flush()
        return self._meeting_out(m, s, meeting)

    def upload_media(self, m: CurrentMember, meeting_id: uuid.UUID, data: bytes,
                     content_type: str, filename: str, caption: str | None = None,
                     student_id: uuid.UUID | None = None) -> MeetingOut:
        """Pass-through upload for photos/small clips (and the dev fallback when
        R2 isn't configured). Big videos take the presign path."""
        meeting, s = self._meeting(m, meeting_id)
        self._check_media_student(m, s, student_id)
        kind = _media_kind(content_type)
        if len(data) > _MAX_DIRECT_BYTES:
            raise ValidationError("File is too large for direct upload — use the "
                                  "presigned upload.", code="media_too_large")
        key = storage.make_key(org_id=m.org_id, instance_id=meeting.id, filename=filename)
        storage.save_bytes(key, storage.maybe_downscale(data, content_type), content_type)
        self.db.add(SessionMedia(
            org_id=m.org_id, meeting_id=meeting.id, kind=kind, object_key=key,
            content_type=content_type, size_bytes=len(data), caption=caption,
            student_id=student_id, uploaded_by_member_id=m.membership.id))
        self.db.flush()
        return self._meeting_out(m, s, meeting)

    def delete_media(self, m: CurrentMember, media_id: uuid.UUID) -> None:
        md = self.db.scalar(select(SessionMedia).where(
            SessionMedia.id == media_id, SessionMedia.org_id == m.org_id))
        if md is None:
            raise NotFoundError("Media")
        meeting = self.db.scalar(select(SessionMeeting).where(
            SessionMeeting.id == md.meeting_id, SessionMeeting.org_id == m.org_id))
        if meeting is not None:
            s = self._session(m.org_id, meeting.session_id)
            self._own(m, s)
        key = md.object_key
        self.db.delete(md)
        self.db.flush()
        storage.delete_object(key)

    def set_evidence(self, m: CurrentMember, meeting_id: uuid.UUID, data: bytes,
                     content_type: str, filename: str) -> MeetingOut:
        """Legacy single batch photo (pre-HS-1); new uploads land in session_media."""
        meeting, s = self._meeting(m, meeting_id)
        key = storage.make_key(org_id=m.org_id, instance_id=meeting.id, filename=filename)
        meeting.evidence_url = storage.save_bytes(key, storage.maybe_downscale(data, content_type),
                                                  content_type)
        self.db.flush()
        return self._meeting_out(m, s, meeting)

    # ── records feed (dashboard precursor) ───────────────────────────────────
    def records(self, m: CurrentMember, on_date: date | None = None) -> list[SessionRecord]:
        d = on_date or self._today(m)
        q = (
            select(SessionMeeting, SessionModel.name, SessionModel.kind)
            .join(SessionModel, SessionModel.id == SessionMeeting.session_id)
            .where(SessionMeeting.org_id == m.org_id, SessionMeeting.date == d)
            .order_by(SessionModel.name)
        )
        if not m.is_coordinator_up:
            q = q.where(SessionModel.owner_member_id == m.membership.id)
        rows = self.db.execute(q).all()
        meeting_ids = [meeting.id for meeting, _n, _k in rows]
        media_counts: dict[uuid.UUID, int] = {}
        if meeting_ids:
            media_counts = dict(self.db.execute(
                select(SessionMedia.meeting_id, func.count(SessionMedia.id))
                .where(SessionMedia.meeting_id.in_(meeting_ids))
                .group_by(SessionMedia.meeting_id)).all())
        out: list[SessionRecord] = []
        for meeting, name, kind in rows:
            att = list(self.db.scalars(
                select(SessionAttendance).where(SessionAttendance.meeting_id == meeting.id)))
            out.append(SessionRecord(
                session_id=meeting.session_id, meeting_id=meeting.id, session_name=name,
                date=meeting.date, kind=kind,
                present=sum(1 for a in att if a.status == "present"),
                late=sum(1 for a in att if a.status == "late"),
                absent=sum(1 for a in att if a.status == "absent"),
                homework_done=sum(1 for a in att if a.homework_done),
                total=len(att), evidence_url=meeting.evidence_url,
                media_count=media_counts.get(meeting.id, 0)))
        return out
