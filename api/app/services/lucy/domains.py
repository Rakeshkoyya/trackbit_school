"""The thirteen toolsets — the scope unit of the agent platform (`D-98`).

A toolset does three jobs at once, which is why it is one concept and not three
(MCP-SERVER-PLAN §3.2):

- it is what a **credential** grants, so a connector can be narrower than the
  human who issued it;
- it is what keeps the list **navigable** — a default connector sees ~60 tools,
  not ~170, and the same choice that shortens the list is the choice that limits
  what the agent can do;
- it is where a **package tier** will gate a feature, at schema time.

Named after the feature-ID prefixes already used in FEATURE-MAP §2-§7, so a
tier, a nav gate, a connector scope and a tool filter all name a feature the
same way.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Domain:
    name: str
    summary: str  # one line, shown by `list_domains` — the model reads this
    always_on: bool = False  # cannot be switched off by a credential
    admin_only: bool = False  # documentation; the real gate is ToolSpec.role
    opt_in: bool = False  # not in the default scope, needs a worded opt-in


# Declaration order is display order — `core` first, then the teacher's day,
# then the admin's surfaces.
DOMAINS: tuple[Domain, ...] = (
    Domain("core", "Orientation: the school's structure, students, settings, "
                   "calendar — and the tools that describe the other toolsets. "
                   "Always available.", always_on=True),
    Domain("students", "The student record: directory, growth, timeline, report "
                       "cards, notes and guardians."),
    Domain("attendance", "The register: per-class-period marking, the day's "
                         "state, absence reasons and notes."),
    Domain("capture", "The teacher's daily loop: my day, the period card, lesson "
                      "logs, homework, checks and observations."),
    Domain("planning", "Syllabus, plans and the forecast, the timetable and the "
                       "exam calendar."),
    Domain("exams", "Tests and scores: cycles, result sheets, trends and "
                    "analysis."),
    Domain("bands", "The A/B/C support programme. Staff-only, always — band "
                    "tiers never reach a parent or guardian (P4).", opt_in=True),
    Domain("staff", "People: the staff directory, leave, timesheets and "
                    "substitutions. A record, not an appraisal (D-25)."),
    Domain("tasks", "The repeating-work engine: boards, tasks and recurring "
                    "templates."),
    Domain("insights", "The admin's boards and the generated daily report.",
           admin_only=True),
    Domain("fees", "Fee collection, structures and ledgers. Admin only, and off "
                   "unless separately opted in — teachers never see fees.",
           admin_only=True, opt_in=True),
    Domain("sessions", "Hostel and activity sessions."),
    Domain("events", "The calendar's occasions: observances and what's on."),
)

DOMAIN_NAMES: frozenset[str] = frozenset(d.name for d in DOMAINS)
BY_NAME: dict[str, Domain] = {d.name: d for d in DOMAINS}

ALWAYS_ON: frozenset[str] = frozenset(d.name for d in DOMAINS if d.always_on)

# What a connector gets unless its issuer says otherwise (MCP-SERVER-PLAN §5.1).
# `fees` and `bands` are deliberately absent — each needs its own worded opt-in.
DEFAULT_SCOPE: frozenset[str] = frozenset(
    {"core", "students", "capture", "planning", "tasks"})


def resolve_scope(
    scope: set[str] | frozenset[str] | None,
) -> frozenset[str] | None:
    """Normalise a requested scope. `None` means unscoped (Lucy today, and any
    caller that has not opted into scoping) — it does not mean "nothing".

    `core` is folded in unconditionally: it carries the discovery tools and the
    id-resolution tools, so a scope without it is a scope the model cannot
    navigate.
    """
    if scope is None:
        return None
    unknown = set(scope) - DOMAIN_NAMES
    if unknown:
        raise ValueError(f"unknown toolset(s): {', '.join(sorted(unknown))}")
    return frozenset(scope) | ALWAYS_ON
