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
from app.core.work_types import active_work_types
from app.schemas.staff import (
    LeaveApplyIn,
    LeaveBalance,
    LeaveDecisionIn,
    LeaveListOut,
    LeavePolicy,
    LeaveRequestOut,
    StaffAttendanceIn,
    StaffAttendanceOut,
    StaffMonthOut,
    TimesheetDay,
    TimesheetEntryIn,
    TimesheetMonth,
    TimesheetWeek,
    WorkTypeOut,
)
from app.schemas.staff_directory import StaffDetailOut, StaffDirectoryOut, StaffUpdateIn
from app.services.leave import LeaveService
from app.services.staff_attendance import StaffAttendanceService
from app.services.staff_directory import StaffDirectoryService
from app.services.staff_month import StaffMonthService
from app.services.timesheet import TimesheetService

router = APIRouter()


# ── the directory (founder, 2026-08-05) ──────────────────────────────────────
@router.get("/directory", response_model=StaffDirectoryOut)
def staff_directory(m: CurrentMember = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """Who works here and what they carry — the join across memberships,
    homerooms and class-subjects that no screen had ever made."""
    return StaffDirectoryService(db).list_staff(m)


@router.get("/directory/{member_id}", response_model=StaffDetailOut)
def staff_detail(member_id: uuid.UUID, m: CurrentMember = Depends(require_academic),
                 db: Session = Depends(get_db)):
    """`require_academic`, not `require_admin`: the service lets a teacher read
    their own file and refuses a colleague's — the V1-16 record's rule, for the
    same reason. `can_edit` on the payload is what the page keys the form off."""
    return StaffDirectoryService(db).detail(m, member_id)


@router.patch("/directory/{member_id}", response_model=StaffDetailOut)
def update_staff(member_id: uuid.UUID, body: StaffUpdateIn,
                 m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    """Profile, role and homeroom in one call, because they are one form.

    `class_teacher_of` is a FULL REPLACE and writes `school_classes`, never a
    role column — the class teacher is derived from the assignment and is stored
    in exactly one place.
    """
    return StaffDirectoryService(db).update(m, member_id, body)


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


@router.get("/month", response_model=StaffMonthOut)
def staff_month(month: str | None = None, member_id: uuid.UUID | None = None,
                m: CurrentMember = Depends(require_academic),
                db: Session = Depends(get_db)):
    """Days worked out of the month's working days (D-78).

    `require_academic`, not `require_admin`: the service restricts a teacher to
    her own row. A person whose attendance record is being kept must be able to
    read it — if a figure is ever disputed, the evidence has to be visible to
    the person disputing it.
    """
    return StaffMonthService(db).summary(m, month, member_id)


# ── timesheet ────────────────────────────────────────────────────────────────
@router.get("/work-types", response_model=list[WorkTypeOut])
def work_types(m: CurrentMember = Depends(require_academic)):
    """The picker list — the org's own categories (D-19), active only."""
    return [WorkTypeOut(key=k, label=v) for k, v in active_work_types(m.org).items()]


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


@router.get("/timesheet/month", response_model=TimesheetMonth)
def timesheet_month(member_id: uuid.UUID | None = None, month: str | None = None,
                    m: CurrentMember = Depends(require_academic),
                    db: Session = Depends(get_db)):
    """One cell per day (D-18/S-64) — the month is a navigator, not an editor."""
    return TimesheetService(db).month(m, member_id, month)


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
