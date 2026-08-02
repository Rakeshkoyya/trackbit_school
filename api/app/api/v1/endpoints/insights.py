"""The admin operating board (DASH3) — thin plumbing, fat services (law 6).

Every route here is `require_admin`. The board reads fees-adjacent figures, names
every teacher's pace and lists students by name; none of that is a teacher's to
see (§2 hard rule), and the existing `/staff`, `/my-day` and `/students` surfaces
already give teachers their own slice with their own scoping.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.schemas.insights import (
    ActionIn,
    ActionOut,
    AttendanceBoard,
    CallBoard,
    ExamsBoard,
    FollowupRow,
    HomeworkBoard,
    OverviewBoard,
    ReachBoard,
    StaffBoard,
    StaffImpact,
    StreakBoard,
    SubstitutionOut,
    SyllabusBoard,
    TaskBoardOut,
)
from app.services.insights.actions import ActionService
from app.services.insights.attendance import STREAK_ALERT_DAYS, AttendanceInsights
from app.services.insights.exams import ExamInsights
from app.services.insights.homework import HomeworkInsights
from app.services.insights.overview import OverviewService
from app.services.insights.reach import ReachInsights
from app.services.insights.syllabus import SyllabusInsights
from app.services.insights.tasks import TaskInsights
from app.services.insights.workload import WorkloadInsights

router = APIRouter()


# ── overview ─────────────────────────────────────────────────────────────────
@router.get("/overview", response_model=OverviewBoard)
def overview_board(year_id: uuid.UUID | None = None,
                   m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    """One block per module plus the rail of what is waiting — the summary the
    six one-number tiles could not give (see `services/insights/overview.py`)."""
    return OverviewService(db).board(m, year_id)


# ── M1 attendance ────────────────────────────────────────────────────────────
@router.get("/attendance", response_model=AttendanceBoard)
def attendance_board(year_id: uuid.UUID | None = None,
                     m: CurrentMember = Depends(require_admin),
                     db: Session = Depends(get_db)):
    return AttendanceInsights(db).board(m, year_id)


@router.get("/attendance/streaks", response_model=StreakBoard)
def attendance_streaks(min_days: int = Query(STREAK_ALERT_DAYS, ge=1, le=30),
                       year_id: uuid.UUID | None = None,
                       m: CurrentMember = Depends(require_admin),
                       db: Session = Depends(get_db)):
    return AttendanceInsights(db).streaks(m, min_days, year_id)


@router.get("/attendance/calls", response_model=CallBoard)
def attendance_calls(year_id: uuid.UUID | None = None,
                     m: CurrentMember = Depends(require_admin),
                     db: Session = Depends(get_db)):
    """V1-3 (S-08): the tab's questions — needs a call (D-86 coloured), the
    drifting band, chronic late, left after lunch."""
    return AttendanceInsights(db).call_board(m, year_id)


@router.get("/attendance/reach", response_model=ReachBoard)
def attendance_reach(on_date: date | None = None,
                     m: CurrentMember = Depends(require_admin),
                     db: Session = Depends(get_db)):
    """V1-11 (`S-62`): which families the school's own alerts did not reach.

    Lives under attendance because the absence alert is the message this
    actually protects — removing WhatsApp did not remove the reach problem, it
    made it visible, and this is where it becomes visible."""
    return ReachInsights(db).board(m, on_date)


# ── M3 staff (presence · leave · live board · load) ──────────────────────────
@router.get("/staff", response_model=StaffBoard)
def staff_board(week_start: date | None = None,
                m: CurrentMember = Depends(require_admin),
                db: Session = Depends(get_db)):
    return WorkloadInsights(db).staff_board(m, week_start)


@router.get("/staff/{member_id}/impact", response_model=StaffImpact)
def staff_impact(member_id: uuid.UUID, on_date: date | None = None,
                 m: CurrentMember = Depends(require_admin),
                 db: Session = Depends(get_db)):
    """What this member being away breaks today: the periods they were due to
    teach with ranked substitutes, and (for an admin) their open work."""
    return AttendanceInsights(db).staff_impact(m, member_id, on_date)


# ── M2 syllabus ──────────────────────────────────────────────────────────────
@router.get("/syllabus", response_model=SyllabusBoard)
def syllabus_board(year_id: uuid.UUID | None = None,
                   scope: str = Query("class", pattern="^(school|class|subject|teacher)$"),
                   checkpoint: str = Query("year", pattern="^(year|term|exam)$"),
                   term_id: uuid.UUID | None = None,
                   m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    return SyllabusInsights(db).board(m, year_id, scope, checkpoint, term_id)


# ── M4 homework ──────────────────────────────────────────────────────────────
@router.get("/homework", response_model=HomeworkBoard)
def homework_board(window_days: int = Query(14, ge=1, le=60),
                   m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    return HomeworkInsights(db).board(m, window_days)


# ── M5 tasks + duties ────────────────────────────────────────────────────────
@router.get("/tasks", response_model=TaskBoardOut)
def tasks_board(window_days: int = Query(14, ge=1, le=60),
                m: CurrentMember = Depends(require_admin),
                db: Session = Depends(get_db)):
    return TaskInsights(db).board(m, window_days)


# ── M6 exams ─────────────────────────────────────────────────────────────────
@router.get("/exams", response_model=ExamsBoard)
def exams_board(year_id: uuid.UUID | None = None, type: str | None = None,
                scale: str | None = None,
                m: CurrentMember = Depends(require_admin),
                db: Session = Depends(get_db)):
    """V1-8: `type` filters on the school's own word for the exam type (`D-55`)
    and `scale` on minor/major. Nothing in the payload is pooled across scales —
    the board names the bucket every figure came from (`S-114`)."""
    return ExamInsights(db).board(m, year_id, type, scale)


# ── the action rail ──────────────────────────────────────────────────────────
@router.post("/actions/{kind}", response_model=ActionOut)
def run_action(kind: str, body: ActionIn, m: CurrentMember = Depends(require_admin),
               db: Session = Depends(get_db)):
    return ActionService(db).run(m, kind, body)


@router.get("/actions/history", response_model=list[FollowupRow])
def action_history(subject_type: str | None = None, subject_id: uuid.UUID | None = None,
                   limit: int = Query(50, ge=1, le=200),
                   m: CurrentMember = Depends(require_admin),
                   db: Session = Depends(get_db)):
    return ActionService(db).history(m, subject_type, subject_id, limit)


@router.post("/substitutions/{substitution_id}/cancel", response_model=SubstitutionOut)
def cancel_substitution(substitution_id: uuid.UUID,
                        m: CurrentMember = Depends(require_admin),
                        db: Session = Depends(get_db)):
    from app.services.substitution import SubstitutionService  # noqa: PLC0415

    return SubstitutionService(db).cancel(m, substitution_id)


@router.get("/substitutions", response_model=list[SubstitutionOut])
def list_substitutions(on_date: date | None = None,
                       m: CurrentMember = Depends(require_admin),
                       db: Session = Depends(get_db)):
    from app.services.school_clock import today_in  # noqa: PLC0415
    from app.services.substitution import SubstitutionService  # noqa: PLC0415

    return SubstitutionService(db).list_for_date(m, on_date or today_in(m.org.timezone))
