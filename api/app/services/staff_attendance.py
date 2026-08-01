"""Staff attendance — admin-marked, capture-by-exception (SF-1).

The admin opens the day, sees every staff member already ticked present, unticks
whoever is away, and saves. That is the whole interaction, and it is the same
shape the classroom uses for students (P1v2): the roster is the norm, and only
deviations are written.

Two rules make it safe to reopen a day:

  * `mark` is a **full replace** of the absence set for that date, so saving
    twice cannot double-count and correcting a mistake needs no undo path.
  * The day row (`StaffAttendanceDay`) records that attendance was taken at all.
    Without it an unmarked morning would read as a full house — the same
    distinction `class_periods.attendance_marked_at` draws for students.

Approved leave pre-unticks the person and says so. The admin still saves the
day, so the record is always something a human confirmed, but they never have to
retype a decision they already made on the leave screen.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.models import (
    LeaveRequest,
    Membership,
    StaffAbsence,
    StaffAttendanceDay,
    User,
)
from app.schemas.staff import StaffAttendanceIn, StaffAttendanceOut, StaffRosterRow
from app.services.school_clock import today_in


class StaffAttendanceService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_in(m.org.timezone)

    def _staff(self, org_id: uuid.UUID) -> list[tuple[Membership, User]]:
        """Every active member — teachers and admin staff alike. Both are 'staff'
        for attendance; the role rides along so the UI can group them."""
        return list(self.db.execute(
            select(Membership, User)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org_id, Membership.status == "active")
            .order_by(Membership.org_role, User.name)
        ).all())

    def _day(self, org_id: uuid.UUID, on: date) -> StaffAttendanceDay | None:
        return self.db.scalar(
            select(StaffAttendanceDay)
            .options(selectinload(StaffAttendanceDay.absences))
            .where(StaffAttendanceDay.org_id == org_id, StaffAttendanceDay.date == on))

    def _approved_leave(self, org_id: uuid.UUID, on: date) -> dict[uuid.UUID, str]:
        """member_id → reason, for approved leave covering this date."""
        rows = self.db.execute(
            select(LeaveRequest.member_id, LeaveRequest.reason)
            .where(LeaveRequest.org_id == org_id, LeaveRequest.status == "approved",
                   LeaveRequest.start_date <= on, LeaveRequest.end_date >= on)
        ).all()
        return {mid: reason for mid, reason in rows}

    def roster(self, m: CurrentMember, on: date | None = None) -> StaffAttendanceOut:
        on = on or self._today(m)
        staff = self._staff(m.org_id)
        day = self._day(m.org_id, on)
        on_leave = self._approved_leave(m.org_id, on)

        absent: dict[uuid.UUID, StaffAbsence] = (
            {a.member_id: a for a in day.absences} if day else {}
        )
        marked_by = None
        if day and day.marked_by_member_id:
            marked_by = self.db.scalar(
                select(User.name).join(Membership, Membership.user_id == User.id)
                .where(Membership.id == day.marked_by_member_id))

        rows: list[StaffRosterRow] = []
        for membership, user in staff:
            leave_reason = on_leave.get(membership.id)
            existing = absent.get(membership.id)
            # Before the day is marked, approved leave is the only thing that
            # can untick someone — everyone else opens as present.
            present = not existing if day else leave_reason is None
            rows.append(StaffRosterRow(
                member_id=membership.id, name=user.name, role=membership.org_role,
                present=present, on_leave=leave_reason is not None,
                leave_reason=leave_reason,
                note=existing.note if existing else None,
            ))

        present_count = sum(1 for r in rows if r.present)
        return StaffAttendanceOut(
            date=on, marked=day is not None,
            marked_at=day.marked_at if day else None, marked_by=marked_by,
            roster=rows, total=len(rows),
            present_count=present_count, absent_count=len(rows) - present_count)

    def mark(self, m: CurrentMember, body: StaffAttendanceIn) -> StaffAttendanceOut:
        on = body.date or self._today(m)
        day = self._day(m.org_id, on)
        if day is None:
            day = StaffAttendanceDay(
                org_id=m.org_id, date=on, marked_by_member_id=m.membership.id)
            self.db.add(day)
            self.db.flush()
        else:
            day.marked_by_member_id = m.membership.id

        # Only members of THIS org can be marked — the ids arrive from a client,
        # and org_id comes from the token (law 1), so the intersection is the guard.
        valid = {ms.id for ms, _ in self._staff(m.org_id)}
        wanted = {mid for mid in body.absent_member_ids if mid in valid}
        on_leave = self._approved_leave(m.org_id, on)

        # Full replace: drop the rows that are no longer absent, add the new ones,
        # leave the untouched ones alone so their created_at stays honest.
        existing = {a.member_id: a for a in (day.absences or [])}
        for member_id, row in existing.items():
            if member_id not in wanted:
                self.db.delete(row)
        for member_id in wanted:
            if member_id in existing:
                existing[member_id].note = body.notes.get(member_id)
                existing[member_id].source = "leave" if member_id in on_leave else "manual"
                continue
            self.db.add(StaffAbsence(
                org_id=m.org_id, day_id=day.id, member_id=member_id,
                source="leave" if member_id in on_leave else "manual",
                note=body.notes.get(member_id)))
        self.db.flush()
        self.db.expire(day, ["absences"])
        return self.roster(m, on)

    # ── read model for the dashboard ─────────────────────────────────────────
    def summary(self, m: CurrentMember, on: date | None = None) -> dict:
        """Counts only — cheap enough for the dashboard to call every load."""
        out = self.roster(m, on)
        return {
            "date": out.date, "marked": out.marked, "total": out.total,
            "present": out.present_count, "absent": out.absent_count,
            "absentees": [r.name for r in out.roster if not r.present],
        }
