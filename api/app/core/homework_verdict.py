"""What a homework verdict means, and what it is worth (V1-5, `D-85`/`D-34`).

One vocabulary, one arithmetic, imported by every surface that reports homework:
the check sheet, the admin board, the student report card, the daily report, the
parent portal and Lucy. A second opinion about what "partly" or "carried" is
worth is the defect V1-0 existed to remove — it had already happened once, with
`partial` counting 0.5 in the syllabus board and 0 here.

    status        row?   worth      in the denominator?
    ─────────────────────────────────────────────────────
    done          no     1.0        yes
    late          yes    1.0        yes     — did it, after the deadline
    partial       yes    0.5        yes
    not_done      yes    0.0        yes
    carried       yes    —          NO      — was absent when it was set
    waived        yes    —          NO      — teacher decided it isn't required
    not_checked   n/a    —          NO      — nobody has gone through it yet

**Done on time is still the absence of a row.** That is the property the whole
module rests on (P1v2): the teacher taps "everyone did it" and flags the few who
didn't, and every student's status stays derivable.

Three rules the table encodes, each of which was a decision:

  * **`late` counts as done** (`S-99`/`Q-43`) and is reported *separately*.
    Folding it into `done` hides a class where everything arrives four days
    late; counting it as a miss punishes a child who did the work. `D-85` makes
    it a status the teacher sets at any time, with no threshold and no expiry —
    her judgement, her word.
  * **`carried` is not a miss** (`D-34`). A child who was absent when the
    homework was set never refused it. It leaves the denominator entirely, is
    skipped by the streak and never reaches the red list that fires guardian
    reminders (`S-102`) — otherwise a child off sick for a week tops the
    "keeps missing it" list and their family gets chased for work they were
    never given.
  * **`waived` exists so the yellow can clear** (`S-98`). "I gave him fresh work
    instead" is a real outcome, and without somewhere to record it the carried
    items — and the parent's pending list — accumulate for every absence in the
    year and never resolve.

And the rule that outranks all of them, inherited from HW-1: **`not_checked` is
the teacher's gap, never the student's.** It is counted separately, excluded
from every completion figure, and never rendered as a child's miss on any
surface, parent-facing ones included. A teacher who checks nothing must never
read as a class with perfect completion.
"""

from app.core.coverage import PARTIAL_WEIGHT, completion_pct

# What a `homework_results` row may say. "done on time" is deliberately absent:
# it is the absence of a row, and adding it here would invite someone to write
# 40 rows for a class where nothing happened.
EXCEPTION_STATUSES = ("not_done", "partial", "late", "carried", "waived")

DONE = "done"
NOT_CHECKED = "not_checked"

# Statuses that enter a completion denominator. Everything else is a state of
# the record, not a judgement about the child.
GRADED: frozenset[str] = frozenset({"done", "late", "partial", "not_done"})

# What counts as the child not having done it — the streak, the red list, and
# every "keeps missing it" surface read exactly this set and no other.
MISSES: frozenset[str] = frozenset({"not_done", "partial"})

# Pending work that is nobody's failure: it is waiting on the teacher, or on a
# child's return, or has been let go.
NEUTRAL: frozenset[str] = frozenset({"carried", "waived", "not_checked"})

_WEIGHT: dict[str, float] = {
    "done": 1.0,
    # S-99: a child who handed it in late DID the work. The lateness is real and
    # is reported beside the figure, never inside it.
    "late": 1.0,
    "partial": PARTIAL_WEIGHT,
    "not_done": 0.0,
}


def is_graded(status: str) -> bool:
    """Does this verdict belong in a completion denominator?"""
    return status in GRADED


def is_miss(status: str) -> bool:
    """Is this the child not having done the work? `carried` never is."""
    return status in MISSES


def verdict_weight(status: str) -> float | None:
    """What one verdict contributes, or None when it leaves the denominator."""
    return _WEIGHT.get(status)


def tally(statuses) -> dict[str, int]:
    """Count an iterable of verdicts into the buckets every surface reports.

    Returned keys are stable so a caller never invents its own bucket name:
    done · late · partial · not_done · carried · waived · not_checked · graded.
    """
    out = {s: 0 for s in ("done", "late", "partial", "not_done",
                          "carried", "waived", "not_checked")}
    for status in statuses:
        if status in out:
            out[status] += 1
    out["graded"] = sum(out[s] for s in GRADED)
    return out


def miss_streak(dated) -> int:
    """Consecutive most-recent homework DAYS that were missed.

    `dated` is an iterable of (date, status). Counted by day, not by assignment:
    three subjects missed on one afternoon is one bad day, not a three-day
    streak.

    Days carrying only a NEUTRAL verdict are **skipped** — neither breaking the
    run nor counting as clean. `not_checked` is the teacher's gap; `carried` and
    `waived` are a child's absence (`S-102`). Counting them clean would hide a
    real pattern; counting them as misses would put a child who was off sick at
    the top of the red list and get their family chased for work they never
    received.

    The admin board, the teacher's check sheet and the report card all call
    this, so the number beside a name is the same number everywhere.
    """
    by_day: dict = {}
    for day, status in dated:
        if status in NEUTRAL:
            continue
        by_day[day] = by_day.get(day, False) or is_miss(status)
    streak = 0
    for day in sorted(by_day, reverse=True):
        if not by_day[day]:
            break
        streak += 1
    return streak


def completion(counts: dict[str, int]) -> float | None:
    """Completion from a `tally()`. None when nothing was graded.

    Delegates to `coverage.completion_pct` rather than re-deriving the sum —
    `late` folds into `done` because it IS done, and `partial` keeps the one
    shared weight. Writing the arithmetic a second time here is precisely how
    "partly" came to be worth 0.5 in one board and 0 in another.

    None is not zero, and no screen may render it as one: it means nobody has
    checked anything, which is a gap in the record rather than a class that
    failed.
    """
    return completion_pct(
        counts.get("done", 0) + counts.get("late", 0),
        counts.get("partial", 0),
        counts.get("graded", 0))
