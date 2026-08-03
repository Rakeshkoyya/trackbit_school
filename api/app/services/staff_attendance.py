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

Approved leave pre-unticks the person and says so — a half-day leave pre-fills
as a half-day, not a whole absence. The admin still saves the day, so the record
is always something a human confirmed, but they never have to retype a decision
they already made on the leave screen.

**V1-4 (`D-04`) widened the exception**: a row now says absent · half_day (with
which half) · late, and `present_value` is the one place a marked day becomes a
number of days present. Late is worth a full day — it is a flag to be seen, not
a deduction (`S-19`).
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

# What one day is worth in "days present" (D-04 → D-78). Late is a full day —
# it is a flag to be seen, never a deduction (S-19); a school that wants lates to
# cost something sets a policy ("N lates = half a day") rather than having the
# capture surface quietly decide it.
PRESENT_VALUE: dict[str, float] = {"present": 1.0, "late": 1.0, "half_day": 0.5, "absent": 0.0}


def present_value(status: str) -> float:
    """Days-present value of one marked day. THE one place this is decided."""
    return PRESENT_VALUE.get(status, 0.0)


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

    def _approved_leave(self, org_id: uuid.UUID, on: date
                        ) -> dict[uuid.UUID, tuple[str, bool, str | None, date, date]]:
        """member_id → (reason, is_half_day, portion, start, end) for approved
        leave covering `on`.

        The dates ride along because cover is arranged for the whole absence,
        not for one day of it (V1-14): a teacher away Monday to Wednesday leaves
        three days of periods, and a sheet that only ever knew about today made
        the other two invisible.
        """
        rows = self.db.execute(
            select(LeaveRequest.member_id, LeaveRequest.reason,
                   LeaveRequest.is_half_day, LeaveRequest.portion,
                   LeaveRequest.start_date, LeaveRequest.end_date)
            .where(LeaveRequest.org_id == org_id, LeaveRequest.status == "approved",
                   LeaveRequest.start_date <= on, LeaveRequest.end_date >= on)
        ).all()
        return {mid: (reason, bool(half), portion, start, end)
                for mid, reason, half, portion, start, end in rows}

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
            leave = on_leave.get(membership.id)
            existing = absent.get(membership.id)
            if existing is not None:
                status, portion = existing.status, existing.portion
            elif day is not None:
                status, portion = "present", None
            elif leave is not None:
                # Before the day is marked, approved leave is the only thing that
                # can untick someone — and a half-day leave pre-fills as a
                # half-day, not a whole absence.
                status = "half_day" if leave[1] else "absent"
                portion = leave[2] if leave[1] else None
            else:
                status, portion = "present", None
            rows.append(StaffRosterRow(
                member_id=membership.id, name=user.name, role=membership.org_role,
                # `late` is present — the boolean every existing caller reads
                # must not start calling a punctual-ish teacher absent.
                present=status in ("present", "late"),
                status=status, portion=portion,
                on_leave=leave is not None, leave_reason=leave[0] if leave else None,
                leave_start=leave[3] if leave else None,
                leave_end=leave[4] if leave else None,
                note=existing.note if existing else None,
            ))

        present_count = sum(1 for r in rows if r.present)
        return StaffAttendanceOut(
            date=on, marked=day is not None,
            marked_at=day.marked_at if day else None, marked_by=marked_by,
            roster=rows, total=len(rows),
            present_count=present_count, absent_count=len(rows) - present_count,
            half_day_count=sum(1 for r in rows if r.status == "half_day"),
            late_count=sum(1 for r in rows if r.status == "late"),
            present_days=round(sum(present_value(r.status) for r in rows), 1))

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
        # The two input shapes merge here, `marks` winning: the shorthand says
        # "away", the rich form says how. One resolved set either way.
        wanted: dict[uuid.UUID, tuple[str, str | None, str | None]] = {
            mid: ("absent", None, body.notes.get(mid))
            for mid in body.absent_member_ids if mid in valid
        }
        for mark in body.marks:
            if mark.member_id not in valid:
                continue
            portion = mark.portion if mark.status == "half_day" else None
            wanted[mark.member_id] = (
                mark.status, portion,
                (mark.note or "").strip() or body.notes.get(mark.member_id))
        on_leave = self._approved_leave(m.org_id, on)

        # Full replace: drop the rows that are no longer exceptions, add the new
        # ones, leave the untouched ones alone so their created_at stays honest.
        existing = {a.member_id: a for a in (day.absences or [])}
        for member_id, row in existing.items():
            if member_id not in wanted:
                self.db.delete(row)
        for member_id, (status, portion, note) in wanted.items():
            source = "leave" if member_id in on_leave else "manual"
            if member_id in existing:
                row = existing[member_id]
                row.note, row.source, row.status, row.portion = note, source, status, portion
                continue
            self.db.add(StaffAbsence(
                org_id=m.org_id, day_id=day.id, member_id=member_id,
                source=source, status=status, portion=portion, note=note))
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
            "half_day": out.half_day_count, "late": out.late_count,
            "absentees": [r.name for r in out.roster if not r.present],
        }
