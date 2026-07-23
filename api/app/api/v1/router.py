"""API v1 router aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import (
    academics,
    assessments,
    attendance,
    auth,
    billing,
    boards,
    checks,
    classroom,
    daily_report,
    dashboard,
    fees,
    lucy,
    marketing,
    me,
    ops,
    org,
    overview,
    parent,
    periods,
    planner,
    platform,
    push,
    recurring,
    sessions,
    students,
    tasks,
    timetable,
    wizard,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(org.router, prefix="/org", tags=["org"])
api_router.include_router(platform.router, prefix="/platform", tags=["platform"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing"])
api_router.include_router(boards.router, prefix="/boards", tags=["boards"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(recurring.router, prefix="/recurring", tags=["recurring"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(push.router, prefix="/push", tags=["push"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
# TrackBit School — master data (SPRD §4.2 / §5.1)
api_router.include_router(academics.router, prefix="/academics", tags=["academics"])
api_router.include_router(planner.router, prefix="/planner", tags=["planner"])
api_router.include_router(timetable.router, prefix="/timetable", tags=["timetable"])
api_router.include_router(wizard.router, prefix="/wizard", tags=["wizard"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
api_router.include_router(periods.router, prefix="/periods", tags=["periods"])
api_router.include_router(overview.router, prefix="/overview", tags=["overview"])
api_router.include_router(checks.router, prefix="/checks", tags=["checks"])
api_router.include_router(classroom.router, prefix="/classroom", tags=["classroom"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(daily_report.router, prefix="/reports", tags=["reports"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
api_router.include_router(students.router, prefix="/students", tags=["students"])
api_router.include_router(fees.router, prefix="/fees", tags=["fees"])
api_router.include_router(lucy.router, prefix="/lucy", tags=["lucy"])
api_router.include_router(parent.router, prefix="/parent", tags=["parent"])
