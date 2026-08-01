"""Staff presence, timesheet and leave endpoints (SF-1).

Guard shape:
  * attendance  — `require_admin`. Marking who came in is the admin's job; a
    teacher never marks their colleagues.
  * timesheet   — `require_academic`. A teacher writes their own; the service's
    `_resolve_member` is what lets an admin read someone else's and refuses a
    teacher who asks for one.
  * leave       — `require_academic` to apply/cancel/read-own, `require_admin` to
    decide and to set the policy.

Thin as the law requires (6): every line here is plumbing.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_academic, require_admin
from app.core.work_types import WORK_TYPES
from app.schemas.staff import (
    LeaveApplyIn,
    LeaveBalance,
    LeaveDecisionIn,
    LeaveListOut,
    LeavePolicy,
    LeaveRequestOut,
    StaffAttendanceIn,
    StaffAttendanceOut,
    TimesheetDay,
    TimesheetEntryIn,
    TimesheetWeek,
    WorkTypeOut,
)
from app.services.leave import LeaveService
from app.services.staff_attendance import StaffAttendanceService
from app.services.timesheet import TimesheetService

router = APIRouter()


# ── staff attendance (admin) ─────────────────────────────────────────────────
@router.get("/attendance", response_model=StaffAttendanceOut)
def staff_roster(on_date: date | None = None,
                 m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    return StaffAttendanceService(db).roster(m, on_date)


@router.post("/attendance", response_model=StaffAttendanceOut)
def mark_staff(body: StaffAttendanceIn, m: CurrentMember = Depends(require_admin),
               db: Session = Depends(get_db)):
    return StaffAttendanceService(db).mark(m, body)


# ── timesheet ────────────────────────────────────────────────────────────────
@router.get("/work-types", response_model=list[WorkTypeOut])
def work_types(_: CurrentMember = Depends(require_academic)):
    return [WorkTypeOut(key=k, label=v) for k, v in WORK_TYPES.items()]


@router.get("/timesheet/day", response_model=TimesheetDay)
def timesheet_day(member_id: uuid.UUID | None = None, on_date: date | None = None,
                  m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    return TimesheetService(db).day(m, member_id, on_date)


@router.get("/timesheet/week", response_model=TimesheetWeek)
def timesheet_week(member_id: uuid.UUID | None = None, week_start: date | None = None,
                   m: CurrentMember = Depends(require_academic),
                   db: Session = Depends(get_db)):
    return TimesheetService(db).week(m, member_id, week_start)


@router.put("/timesheet/entry", response_model=TimesheetDay)
def set_timesheet_entry(body: TimesheetEntryIn, m: CurrentMember = Depends(require_academic),
                        db: Session = Depends(get_db)):
    return TimesheetService(db).set_entry(m, body)


@router.delete("/timesheet/entry", response_model=TimesheetDay)
def clear_timesheet_entry(on_date: date, period_no: int, member_id: uuid.UUID | None = None,
                          m: CurrentMember = Depends(require_academic),
                          db: Session = Depends(get_db)):
    return TimesheetService(db).clear_entry(m, on_date, period_no, member_id)


@router.get("/timesheet/today", response_model=list[TimesheetWeek])
def org_timesheet_today(on_date: date | None = None,
                        m: CurrentMember = Depends(require_admin),
                        db: Session = Depends(get_db)):
    """Every teacher's day in one payload — who is teaching, working, free."""
    return TimesheetService(db).org_day(m, on_date)


# ── leave ────────────────────────────────────────────────────────────────────
@router.get("/leave/policy", response_model=LeavePolicy)
def leave_policy(m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return LeaveService(db).policy(m)


@router.put("/leave/policy", response_model=LeavePolicy)
def set_leave_policy(body: LeavePolicy, m: CurrentMember = Depends(require_admin),
                     db: Session = Depends(get_db)):
    return LeaveService(db).set_policy(m, body)


@router.get("/leave/balance", response_model=LeaveBalance)
def leave_balance(member_id: uuid.UUID | None = None,
                  m: CurrentMember = Depends(require_academic),
                  db: Session = Depends(get_db)):
    return LeaveService(db).balance(m, member_id)


@router.get("/leave", response_model=LeaveListOut)
def list_leave(status: str | None = None, mine: bool = False,
               m: CurrentMember = Depends(require_academic), db: Session = Depends(get_db)):
    return LeaveService(db).list_requests(m, status, mine)


@router.post("/leave", response_model=LeaveRequestOut)
def apply_leave(body: LeaveApplyIn, m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    return LeaveService(db).apply(m, body)


@router.post("/leave/{request_id}/decision", response_model=LeaveRequestOut)
def decide_leave(request_id: uuid.UUID, body: LeaveDecisionIn,
                 m: CurrentMember = Depends(require_admin), db: Session = Depends(get_db)):
    return LeaveService(db).decide(m, request_id, body)


@router.post("/leave/{request_id}/cancel", response_model=LeaveRequestOut)
def cancel_leave(request_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    return LeaveService(db).cancel(m, request_id)
