"""The staff month summary (V1-4, `D-78`).

> *"I agree lets defer payroll but I want proper attendance and leave system
> capturing so I have number of days the teacher worked out of working days."*

That sentence is this module. Per member, for one month: **days worked out of
the month's working days**, leave used, leave balance — and nothing else. There
is **no money on this screen and no path from it to one** (`D-25`); payroll is a
v2 packet, and what v1 owes it is a correct input, not a half-built calculation.

Three rules it exists to hold:

  1. **A day nobody marked is `not marked`, never `absent`** (`S-34`). It has its
     own count, in its own word, and it is excluded from `days_present` *and*
     from anything that could be read as a shortfall. Today this is a display
     rule; the moment the figure informs pay it is the difference between a
     clerical gap and an unpaid day, which is why it is enforced in the service
     rather than left to a screen.
  2. **The denominator is `calendar.org_working_days`** — the one implementation
     (V1-0 §5). A fifth copy of "working days between two dates" here would put
     a different number on this screen than on the leave screen for the same
     month, which is exactly the class of defect V1-4 inherited.
  3. **The month ends at today.** A month in progress is not a month where
     everyone has been absent since the 12th, so the window is clamped and the
     screen says which window it used.

Half-days count 0.5 and lates count a full day, both through
`staff_attendance.present_value` — the same function the daily roster uses, so
a month and a day can never disagree about what one person's Tuesday was worth.
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, ValidationError
from app.core.staff import not_operator
from app.models import (
    LeaveRequest,
    Membership,
    StaffAbsence,
    StaffAttendanceDay,
    User,
)
from app.schemas.staff import StaffMonthOut, StaffMonthRow
from app.services.calendar import org_working_days
from app.services.leave import LeaveService
from app.services.school_clock import month_bounds, today_in
from app.services.staff_attendance import present_value


def parse_month(month: str) -> tuple[date, date]:
    """`school_clock.month_bounds`, with the error the API envelope wants."""
    try:
        return month_bounds(month)
    except (ValueError, AttributeError) as exc:
        raise ValidationError("Month must look like 2026-08") from exc


class StaffMonthService:
    def __init__(self, db: Session):
        self.db = db

    def summary(self, m: CurrentMember, month: str | None = None,
                member_id: uuid.UUID | None = None) -> StaffMonthOut:
        """One month for the whole staff (admin) or for one person.

        Five queries flat: the roster, the marked days, the exception rows, the
        approved leave and — inside `org_working_days` — the year and its
        calendar. Nothing loops per member.
        """
        today = today_in(m.org.timezone)
        month = month or f"{today:%Y-%m}"
        start, end = parse_month(month)
        # The month is not over yet, and a day that has not happened is not a
        # day anybody failed to attend.
        end = min(end, today)

        # A teacher may read her own month and nobody else's; an admin reads all.
        if not m.is_admin:
            if member_id is not None and member_id != m.membership.id:
                raise ForbiddenError("You can only see your own month")
            member_id = m.membership.id

        staff_q = (
            select(Membership.id, User.name, Membership.org_role)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == m.org_id, Membership.status == "active",
                   not_operator())
            .order_by(Membership.org_role, User.name))
        if member_id is not None:
            staff_q = staff_q.where(Membership.id == member_id)
        staff = list(self.db.execute(staff_q).all())

        if end < start:
            # A month entirely in the future — no window, so no figures. Says
            # nothing rather than reporting a school of absentees.
            return StaffMonthOut(month=month, start_date=start, end_date=start,
                                 working_days=0, days_marked=0,
                                 rows=[StaffMonthRow(
                                     member_id=mid, name=name, role=role, working_days=0,
                                     days_marked=0, days_not_marked=0, days_present=0,
                                     days_absent=0, half_days=0, lates=0, leave_days=0,
                                     leave_remaining=0)
                                     for mid, name, role in staff])

        working = org_working_days(self.db, m.org_id, start, end)
        working_set = set(working)

        marked = {
            d: day_id for day_id, d in self.db.execute(
                select(StaffAttendanceDay.id, StaffAttendanceDay.date)
                .where(StaffAttendanceDay.org_id == m.org_id,
                       StaffAttendanceDay.date >= start,
                       StaffAttendanceDay.date <= end)).all()
        }
        # Only marked days that are also working days count as captured — an
        # admin who marked a Sunday has not shortened anybody's month.
        marked_working = sorted(d for d in marked if d in working_set)

        exceptions: dict[uuid.UUID, dict[date, tuple[str, str | None]]] = defaultdict(dict)
        if marked:
            day_dates = {day_id: d for d, day_id in marked.items()}
            for member, day_id, status, portion in self.db.execute(
                select(StaffAbsence.member_id, StaffAbsence.day_id,
                       StaffAbsence.status, StaffAbsence.portion)
                .where(StaffAbsence.org_id == m.org_id,
                       StaffAbsence.day_id.in_(list(day_dates)))).all():
                on = day_dates.get(day_id)
                if on is not None:
                    exceptions[member][on] = (status, portion)

        # Approved leave days that FALL in this window. Counted from the request's
        # own `days` when it sits wholly inside, and clipped to working days when
        # it straddles the edge — the balance and this figure read the same rows.
        leave_days: dict[uuid.UUID, float] = defaultdict(float)
        for member, l_start, l_end, days, is_half in self.db.execute(
            select(LeaveRequest.member_id, LeaveRequest.start_date, LeaveRequest.end_date,
                   LeaveRequest.days, LeaveRequest.is_half_day)
            .where(LeaveRequest.org_id == m.org_id, LeaveRequest.status == "approved",
                   LeaveRequest.start_date <= end, LeaveRequest.end_date >= start)).all():
            if is_half:
                if l_start in working_set:
                    leave_days[member] += 0.5
                continue
            if l_start >= start and l_end <= end:
                leave_days[member] += float(days)
                continue
            leave_days[member] += float(sum(
                1 for d in working if l_start <= d <= l_end))

        balances = LeaveService(self.db)
        balances.prime_balances(m, [mid for mid, _n, _r in staff])
        rows: list[StaffMonthRow] = []
        for mid, name, role in staff:
            mine = exceptions.get(mid, {})
            present = absent = 0.0
            halves = lates = 0
            for d in marked_working:
                status, _portion = mine.get(d, ("present", None))
                value = present_value(status)
                present += value
                absent += 1 - value
                if status == "half_day":
                    halves += 1
                elif status == "late":
                    lates += 1
            rows.append(StaffMonthRow(
                member_id=mid, name=name, role=role,
                working_days=len(working), days_marked=len(marked_working),
                days_not_marked=len(working) - len(marked_working),
                days_present=round(present, 1), days_absent=round(absent, 1),
                half_days=halves, lates=lates,
                leave_days=round(leave_days.get(mid, 0.0), 1),
                leave_remaining=balances.balance(m, mid).remaining))

        return StaffMonthOut(
            month=month, start_date=start, end_date=end,
            working_days=len(working), days_marked=len(marked_working), rows=rows)
