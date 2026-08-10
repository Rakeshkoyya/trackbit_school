"""API v1 router aggregation — and where package tiers are enforced (`D-106`).

A module whose whole surface is one feature is gated here, once, at
`include_router`. That keeps the tier map out of thirty-six endpoint files and
puts it somewhere a person can read top to bottom and ask "what does Free
actually get?".

`feature_gate` composes with each route's own role guard — it never replaces
one. The tier says what the school bought; the role says who inside it may look.

**Ungated on purpose (`D-107`): the capture loop.** `attendance`, `classroom`
(the lesson and homework log), `planner`, `timetable`, `academics`, `periods`,
`checks`, `events`, `bands` and `daily_report` are free, in full. Free buys the
act of recording; paid buys the record over time. Do not add a gate to any of
them without reopening `D-107`.

Modules still ungated because they are **mixed** and need per-route decisions
(tracked as P4b in `docs/architecture/TIERS-PLAN.md`): `insights`, `dashboard`,
`students`, `my_class`, and the two routers that do not authenticate as a
member (`parent`, `agent.agent_router`).
"""

from fastapi import APIRouter, Depends

from app.api.v1.endpoints import (
    academics,
    agent,
    assessments,
    attendance,
    auth,
    bands,
    billing,
    blocks,
    boards,
    checks,
    classroom,
    daily_report,
    dashboard,
    events,
    fees,
    homework,
    insights,
    lucy,
    main_exams,
    marketing,
    me,
    my_class,
    oauth,
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
    staff,
    students,
    tasks,
    timetable,
)
from app.core.dependencies import feature_gate
from app.core.features import Feature


def _gate(feature: Feature) -> list:
    return [Depends(feature_gate(feature))]


api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(org.router, prefix="/org", tags=["org"])
# Agent connectors: the human half issues credentials from Setup → Connections,
# the agent half authenticates with the credential itself (D-97).
api_router.include_router(agent.router, prefix="/org", tags=["agent"])
api_router.include_router(agent.agent_router, prefix="/agent", tags=["agent"])
# OAuth connector management — the Connections screen drives these with a
# normal staff JWT. The OAuth protocol endpoints themselves live at the app
# root (see main.py), because the advertised issuer is the bare origin.
api_router.include_router(oauth.router, prefix="/org", tags=["agent"],
                          dependencies=_gate(Feature.AGENT_MCP))
api_router.include_router(platform.router, prefix="/platform", tags=["platform"])
api_router.include_router(billing.router, prefix="/billing", tags=["billing"])
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing"])
# The Tasks module, whole and unmetered (`D-109`): take max and every part of
# it is yours — boards, tasks, recurring templates, attachments, critical.
api_router.include_router(boards.router, prefix="/boards", tags=["boards"],
                          dependencies=_gate(Feature.TASKS_BOARDS))
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"],
                          dependencies=_gate(Feature.TASKS_BOARDS))
api_router.include_router(recurring.router, prefix="/recurring", tags=["recurring"],
                          dependencies=_gate(Feature.TASKS_BOARDS))
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(push.router, prefix="/push", tags=["push"])
api_router.include_router(ops.router, prefix="/ops", tags=["ops"])
# TrackBit School — master data (SPRD §4.2 / §5.1)
api_router.include_router(academics.router, prefix="/academics", tags=["academics"])
api_router.include_router(planner.router, prefix="/planner", tags=["planner"])
api_router.include_router(timetable.router, prefix="/timetable", tags=["timetable"])
# TT-2 `D-114`: capturing a non-subject period is free, for the same reason the
# timetable is. The hostel week planner and the records board stay on /sessions
# behind SESSIONS_HOSTEL (max) — free buys the act of recording (`D-107`).
api_router.include_router(blocks.router, prefix="/blocks", tags=["blocks"])
api_router.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
# V1-3 — the class teacher's area (D-03)
api_router.include_router(my_class.router, prefix="/my-class", tags=["my-class"])
api_router.include_router(periods.router, prefix="/periods", tags=["periods"])
api_router.include_router(overview.router, prefix="/overview", tags=["overview"])
api_router.include_router(checks.router, prefix="/checks", tags=["checks"])
# V1-7 — the read side of the school calendar, and the approval sheet
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(classroom.router, prefix="/classroom", tags=["classroom"])
# HW-1 homework ANALYTICS — the check-sheet desk and the day book. Gated at pro.
# Homework *capture* is on /classroom and stays free (`D-107`); this is the
# board built on top of it, which is the thing that is worth paying for.
api_router.include_router(homework.router, prefix="/homework", tags=["homework"],
                          dependencies=_gate(Feature.HOMEWORK_DESK))
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"],
                          dependencies=_gate(Feature.SESSIONS_HOSTEL))
# SF-1 staff presence, timesheet and leave
api_router.include_router(staff.router, prefix="/staff", tags=["staff"],
                          dependencies=_gate(Feature.STAFF_ROSTER))
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
# DASH3 admin operating board — the six modules + the action rail
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
api_router.include_router(daily_report.router, prefix="/reports", tags=["reports"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["assessments"],
                          dependencies=_gate(Feature.EXAMS_BOARD))
# The school's own exam calendar (founder 2026-08-05) — the `exam_block`
# calendar rows as a screen. Marks still go through /assessments/exams.
api_router.include_router(main_exams.router, prefix="/main-exams", tags=["main-exams"],
                          dependencies=_gate(Feature.EXAMS_BOARD))
# V1-9 the support programme — bands, promotion, ownership and the weekly
# check-in. Its own prefix because it is a programme, not an assessment surface.
api_router.include_router(bands.router, prefix="/bands", tags=["bands"])
api_router.include_router(students.router, prefix="/students", tags=["students"])
# The fee fence (rule 1) is unchanged and still lives on the routes themselves:
# 19 of these 20 are admin-only whatever the school's plan is. This adds the
# second question — did the school buy fees at all.
api_router.include_router(fees.router, prefix="/fees", tags=["fees"],
                          dependencies=_gate(Feature.FEES_COLLECTION))
api_router.include_router(lucy.router, prefix="/lucy", tags=["lucy"],
                          dependencies=_gate(Feature.AGENT_LUCY))
api_router.include_router(parent.router, prefix="/parent", tags=["parent"])
