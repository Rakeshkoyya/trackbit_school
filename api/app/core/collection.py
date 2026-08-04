"""Fee collection — the vocabulary and the arithmetic (V1-10).

The fee *system* is built and correct: structures, instalments, discounts, an
append-only ledger, and a counter screen. What did not exist is the **read a
principal needs**: how much of this quarter is in, which class to push, which
family to ring. This module owns the two rules that read depends on.

**A quarter is a due-date window** (`Q-67`, `S-153`). Two obvious grouping keys
break, and it is worth writing down why:

    installment_number   juniors pay in 2 instalments and seniors in 4, so
                         "instalment 1" is a different quarter per class and the
                         school-wide figure is nonsense
    label                free text — "Q1", "Quarter 1", "1st term", "April";
                         one school produces all four and the grouping fragments
    due_date in a window ✅ works across differing structures, aligns every class
                         to one calendar, needs no new column, and matches what
                         the admin means: "money due Jul–Sep"

An instalment with **no due date** is `unscheduled` — a word, never silently
bucketed into Q1 (ux §10).

**`collected` · `pending` · `overdue` are three states and are never added**
(`S-163`). Pending is a forecast; overdue is a phone call. `Collection` therefore
has no `outstanding` property: a caller who wants one has to write the addition
where a reviewer can see it — the same device `ScaleTally` uses for exam scales.

**Years never pool** (`D-88`). Every figure is computed inside one academic year;
dues carried from a previous year are reported as their own labelled line with a
link to that year, and never enter this year's totals. What is not acceptable is
the old behaviour, where `opening_dues` was silently missing from every roll-up
and nothing on screen admitted it.

Pure and stdlib-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

UNSCHEDULED = "unscheduled"


@dataclass(frozen=True)
class Quarter:
    """One due-date window over the academic year."""

    label: str
    start: date
    end: date

    def holds(self, due: date | None) -> bool:
        return due is not None and self.start <= due <= self.end

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


def quarter_windows(year_start: date, year_end: date, count: int = 4) -> list[Quarter]:
    """The academic year cut into `count` equal windows, labelled Q1…Qn.

    Equal windows rather than calendar quarters, because an Indian academic year
    starts in April or June and a school that says "Q1" means *the first quarter
    of our year*, not January–March. `Q-67`(d) — a school declaring its own
    quarters — is a later refinement; nothing here blocks it, because every
    consumer takes the window list rather than computing one."""
    if year_end < year_start or count < 1:
        return []
    total = (year_end - year_start).days + 1
    size = total // count
    out: list[Quarter] = []
    cursor = year_start
    for i in range(count):
        last = i == count - 1
        end = year_end if last else cursor + timedelta(days=size - 1)
        out.append(Quarter(label=f"Q{i + 1}", start=cursor, end=end))
        cursor = end + timedelta(days=1)
    return out


def quarter_of(due: date | None, windows: list[Quarter]) -> str:
    """Which quarter an instalment belongs to, or `unscheduled`."""
    if due is None:
        return UNSCHEDULED
    for w in windows:
        if w.holds(due):
            return w.label
    return UNSCHEDULED


def current_quarter(windows: list[Quarter], today: date) -> Quarter | None:
    """The window today falls in, else the last one that has started, else the
    first. A board opened in the summer holidays still has something to show."""
    for w in windows:
        if w.holds(today):
            return w
    started = [w for w in windows if w.start <= today]
    return started[-1] if started else (windows[0] if windows else None)


@dataclass
class Collection:
    """Money in one scope, with the three states kept apart.

    **There is deliberately no `outstanding` property.** Pending (due later) and
    overdue (due, not paid) are different facts with different actions, and the
    single blended figure is what made the old four-tile screen unreadable."""

    collected: float = 0.0
    pending: float = 0.0        # unpaid, due date still ahead (or unscheduled)
    overdue: float = 0.0        # unpaid, due date passed
    billed: float = 0.0         # what was asked for in this scope
    # What the school ASKED for by today: every instalment whose due date has
    # arrived, paid or not. This is the denominator "are we on schedule?" needs,
    # and it is not `overdue` — overdue is only the *unpaid* part of it, so a
    # school that collected every rupee on time has overdue 0 and due_by_today
    # equal to the whole first half of the year.
    #
    # An unscheduled instalment (no due date) is never in here: the school has
    # not said when it wants that money, so it cannot be late.
    due_by_today: float = 0.0

    def add(self, *, collected: float = 0.0, pending: float = 0.0,
            overdue: float = 0.0, billed: float = 0.0,
            due_by_today: float = 0.0) -> None:
        self.collected += collected
        self.pending += pending
        self.overdue += overdue
        self.billed += billed
        self.due_by_today += due_by_today

    @property
    def pct(self) -> float | None:
        """How much of what was asked for is in. None when nothing was asked —
        a school with no instalments in a window is **not** 0% collected."""
        if self.billed <= 0:
            return None
        return round(self.collected / self.billed * 100, 1)

    @property
    def due_pct(self) -> float | None:
        """Where the schedule says we should be, on the same track as `pct`.

        Drawn as a marker beside the collected arc, never as a second arc: the
        two share a denominator, and the distance between them IS the finding.
        """
        if self.billed <= 0:
            return None
        return round(self.due_by_today / self.billed * 100, 1)

    @property
    def shortfall(self) -> float:
        """How far behind the schedule we are, in money. Zero when level or
        ahead — a school that collected early is not "minus ₹40,000 behind".

        This is the one addition `Collection` DOES make, because unlike
        pending+overdue it names a single fact: money the school asked for by
        today and does not have. It is `overdue` restated on the year's track,
        and the two agree by construction.
        """
        return max(0.0, self.due_by_today - self.collected)


def pace_tone(c: Collection) -> str:
    """Rendered status for a collection scope, decided ONCE, server-side.

    The rule that matters is the first one: a scope with nothing due yet is
    **neutral and a word**, never 0% and never red. A quarter that has not
    started has not been missed, and painting next January red every August is
    how a board stops being read (ux §5, §10).
    """
    if c.billed <= 0:
        return "neutral"          # nothing was asked for here at all
    if c.due_by_today <= 0:
        return "neutral"          # asked for, but not yet — not a score
    ratio = c.collected / c.due_by_today
    if ratio >= 0.995:            # level or ahead; the 0.5% absorbs rounding
        return "green"
    if ratio >= 0.9:
        return "amber"
    return "red"


def collection_sentence(q: Quarter | None, c: Collection, families_overdue: int,
                        prev_pct: float | None = None) -> str:
    """The line the board leads with. *"₹42L of ₹68L collected"* is a fact
    nobody can act on; this names the quarter, the share, and who to ring.

    **A quarter whose money is not due yet is not 0% collected** — it is a
    quarter that has not started. Reading "0%, 20 points behind" off instalments
    dated three months out is invented failure, the same rule that keeps an
    unmarked register out of the red (ux §5)."""
    if q is None or c.billed <= 0:
        return "Nothing is due yet in this year."
    if c.collected <= 0 and c.overdue <= 0:
        out = (f"{q.label}: ₹{c.billed:,.0f} falls due through {q.end:%d %b} — "
               "none of it is overdue yet.")
        if families_overdue:
            out += (f" {families_overdue} famil{'y is' if families_overdue == 1 else 'ies are'} "
                    "behind on an earlier quarter.")
        return out
    parts = [f"{q.label} is {c.pct:g}% collected"]
    if prev_pct is not None:
        gap = round((c.pct or 0) - prev_pct, 1)
        if abs(gap) >= 1:
            parts[0] += (f" — {abs(gap):g} points "
                         f"{'ahead of' if gap > 0 else 'behind'} the previous quarter")
    out = ", ".join(parts) + "."
    if families_overdue:
        out += (f" {families_overdue} famil{'y' if families_overdue == 1 else 'ies'} "
                "past a due date.")
    return out


def reminder_line(amount: float, due: date | None, paid_so_far: float) -> str:
    """The parent's one line (`Q-69`, `S-160`) — *how much, and by when*.

    Neutral and never dunning: it is read by a family that may be having a hard
    year, and it is a reminder, not a demand. Never the word *defaulter*, never
    red, and it does not render at all when nothing is due."""
    when = f" by {due:%d %b}" if due else ""
    paid = f" ₹{paid_so_far:,.0f} paid so far this year." if paid_so_far > 0 else ""
    return f"₹{amount:,.0f} due{when}.{paid}"
