"""Package tiers — what a school's plan includes (`D-106`…`D-111`).

**This module is the only place that knows which tier unlocks which feature.**
A route guard, a Lucy tool filter and a nav lock chip all name the same
`Feature`, so two screens can never disagree about what the school bought. See
`docs/architecture/TIERS-PLAN.md`.

Two rules decide every entry below.

1. **Free buys the act of recording; paid buys the record over time** (`D-107`).
   Marking the register, logging the lesson, logging homework, sizing a chapter
   — every daily capture surface is free, in full. What costs money is the
   boards that turn a term of it into a picture. A school that stops capturing
   has nothing to upgrade *for*, and the upgrade has to land on a year of the
   school's own data rather than an empty board.

2. **Tiers are cumulative and ordered.** `max` includes everything in `pro`,
   which includes everything in `free`. `TIER_ADDS` is what each tier *adds*;
   `features_for()` unions the chain. Declared this way a feature cannot be
   listed twice, and moving one between tiers is a one-line edit.

What this module does **not** own is the *price* — that changes on a completely
different clock (`D-106`: "the plan number and costing might change regularly").
Prices live in `plan_prices`, editable by the operator without a deploy. This
map moves when we build something; the price moves when we feel like it.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from app.core.exceptions import PlanLimitError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from app.models import Organization


class Feature(StrEnum):
    """The stable vocabulary. IDs follow the FEATURE-MAP §2-§7 prefixes, so a
    tier, a connector scope, a nav gate and a tool filter all spell a feature
    the same way."""

    # ── the capture loop — never gated (D-107) ──────────────────────────────
    STUDENTS_DIRECTORY = "students.directory"
    CAPTURE_ATTENDANCE = "capture.attendance"
    CAPTURE_PERIOD = "capture.period"
    CAPTURE_HOMEWORK = "capture.homework"
    CAPTURE_LESSON_LOG = "capture.lesson_log"
    PLAN_SYLLABUS = "plan.syllabus"
    PLAN_TIMETABLE = "plan.timetable"
    EVENTS_CALENDAR = "events.calendar"
    BANDS_PROGRAMME = "bands.programme"
    INSIGHTS_DAILY_REPORT = "insights.daily_report"
    COMMS_ABSENCE_ALERT = "comms.absence_alert"
    ORG_SETUP = "org.setup"

    # ── pro — the record over time ──────────────────────────────────────────
    STUDENTS_ACADEMICS = "students.academics"
    HOMEWORK_DESK = "homework.desk"
    EXAMS_BOARD = "exams.board"
    FEES_COLLECTION = "fees.collection"

    # ── max — running the school ────────────────────────────────────────────
    STAFF_ROSTER = "staff.roster"
    TASKS_BOARDS = "tasks.boards"
    INSIGHTS_ACTIONS = "insights.actions"
    SESSIONS_HOSTEL = "sessions.hostel"
    PARENT_PORTAL = "parent.portal"
    COMMS_GUARDIAN = "comms.guardian"
    AGENT_LUCY = "agent.lucy"
    EXAMS_CAPTURE_ADVANCED = "exams.capture_advanced"

    # ── ultra — connecting the school to other systems ──────────────────────
    AGENT_MCP = "agent.mcp"


#: Ordered, cheapest first. Index position IS the ranking — `tier_at_least`
#: compares on it, so never reorder this without meaning to.
TIERS: tuple[str, ...] = ("free", "pro", "max", "ultra")

DEFAULT_TIER = "free"


#: What each tier ADDS to the one before it. Never list a feature twice.
TIER_ADDS: dict[str, frozenset[Feature]] = {
    "free": frozenset({
        Feature.STUDENTS_DIRECTORY,
        Feature.CAPTURE_ATTENDANCE,
        Feature.CAPTURE_PERIOD,
        Feature.CAPTURE_HOMEWORK,
        Feature.CAPTURE_LESSON_LOG,
        Feature.PLAN_SYLLABUS,
        # The timetable is structural, not analytical: per-period attendance
        # cannot resolve a class without it, so gating it would gate the
        # register itself.
        Feature.PLAN_TIMETABLE,
        Feature.EVENTS_CALENDAR,
        Feature.BANDS_PROGRAMME,
        # P5 — "nobody writes a report" is the product promise, not an upsell.
        Feature.INSIGHTS_DAILY_REPORT,
        # Q7 default: a parent hearing nothing when their child is absent
        # because the school is on free is indefensible. Homework auto-notify
        # rides on this same feature but is volume-capped; everything else
        # guardian-facing is COMMS_GUARDIAN (max).
        Feature.COMMS_ABSENCE_ALERT,
        Feature.ORG_SETUP,
    }),
    "pro": frozenset({
        Feature.STUDENTS_ACADEMICS,
        Feature.HOMEWORK_DESK,
        Feature.EXAMS_BOARD,
        Feature.FEES_COLLECTION,
    }),
    "max": frozenset({
        Feature.STAFF_ROSTER,
        Feature.TASKS_BOARDS,
        # D-111: the dashboard's action rail. Every red row still renders on
        # free — the diagnosis is free, the one-tap dispatch is paid.
        Feature.INSIGHTS_ACTIONS,
        Feature.SESSIONS_HOSTEL,
        Feature.PARENT_PORTAL,
        Feature.COMMS_GUARDIAN,
        Feature.AGENT_LUCY,
        Feature.EXAMS_CAPTURE_ADVANCED,
    }),
    "ultra": frozenset({
        # Composes with `organizations.agent_access`, which stays the per-org
        # kill switch: ultra makes the door exist, agent_access opens it.
        Feature.AGENT_MCP,
    }),
}


def _cumulative() -> dict[str, frozenset[Feature]]:
    out: dict[str, frozenset[Feature]] = {}
    running: frozenset[Feature] = frozenset()
    for tier in TIERS:
        running = running | TIER_ADDS[tier]
        out[tier] = running
    return out


#: tier -> everything it includes, the chain already unioned.
TIER_FEATURES: dict[str, frozenset[Feature]] = _cumulative()

#: feature -> the cheapest tier that unlocks it. Derived, never hand-written.
FEATURE_TIER: dict[Feature, str] = {
    f: tier for tier in TIERS for f in TIER_ADDS[tier]
}

#: What the upgrade wall calls each feature — a fragment that reads naturally
#: after "Pro unlocks …".
FEATURE_LABELS: dict[Feature, str] = {
    Feature.STUDENTS_DIRECTORY: "the student directory",
    Feature.CAPTURE_ATTENDANCE: "attendance",
    Feature.CAPTURE_PERIOD: "the period card",
    Feature.CAPTURE_HOMEWORK: "homework logging",
    Feature.CAPTURE_LESSON_LOG: "classwork logging",
    Feature.PLAN_SYLLABUS: "the syllabus and plan",
    Feature.PLAN_TIMETABLE: "the timetable",
    Feature.EVENTS_CALENDAR: "events and the calendar",
    Feature.BANDS_PROGRAMME: "the ABC support programme",
    Feature.INSIGHTS_DAILY_REPORT: "the daily report",
    Feature.COMMS_ABSENCE_ALERT: "absence alerts to guardians",
    Feature.ORG_SETUP: "school setup",
    Feature.STUDENTS_ACADEMICS: "the academic record — class logs, trends and report cards",
    Feature.HOMEWORK_DESK: "the homework check-sheet and day book",
    Feature.EXAMS_BOARD: "exams — cycles, marks, result sheets and trends",
    Feature.FEES_COLLECTION: "fee collection",
    Feature.STAFF_ROSTER: "staff, leave, timesheets and teacher workload",
    Feature.TASKS_BOARDS: "task management",
    Feature.INSIGHTS_ACTIONS: "one-tap actions on the dashboard",
    Feature.SESSIONS_HOSTEL: "hostel and activity sessions",
    Feature.PARENT_PORTAL: "the parent portal",
    Feature.COMMS_GUARDIAN: "parent communications",
    Feature.AGENT_LUCY: "Lucy, the AI assistant",
    Feature.EXAMS_CAPTURE_ADVANCED: "exam script capture",
    Feature.AGENT_MCP: "agent connections (MCP)",
}

#: What the wall calls each tier.
TIER_LABELS: dict[str, str] = {
    "free": "Free", "pro": "Pro", "max": "Max", "ultra": "Ultra",
}


def normalise_plan(plan: str | None) -> str:
    """An unknown plan reads as Free rather than raising.

    Deliberate: a bad value in the database must lock the school out of paid
    surfaces, never out of the app. The CHECK constraint is what stops one
    being written; this is the read-side floor.
    """
    return plan if plan in TIER_FEATURES else DEFAULT_TIER


def features_for(plan: str | None) -> frozenset[Feature]:
    """Everything this tier includes, the chain already unioned."""
    return TIER_FEATURES[normalise_plan(plan)]


def has_feature(org: Organization, feature: Feature) -> bool:
    return feature in features_for(org.plan)


def tier_for(feature: Feature) -> str:
    """The cheapest tier that unlocks this feature."""
    return FEATURE_TIER[feature]


def tier_at_least(plan: str | None, minimum: str) -> bool:
    return TIERS.index(normalise_plan(plan)) >= TIERS.index(minimum)


def label_for(feature: Feature) -> str:
    return FEATURE_LABELS.get(feature, str(feature))


def require_feature(org: Organization, feature: Feature) -> None:
    """Raise unless the school's plan includes `feature`.

    402 `plan_limit` — the contract the client has always rendered as an
    upgrade prompt, now carrying the tier that would unlock it so the wall can
    name a price instead of saying "upgrade" and leaving them to guess.
    """
    if has_feature(org, feature):
        return
    needed = tier_for(feature)
    raise PlanLimitError(
        str(feature),
        required_tier=needed,
        feature_label=label_for(feature),
        message=f"{TIER_LABELS[needed]} unlocks {label_for(feature)}.",
    )
