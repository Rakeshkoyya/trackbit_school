"""The support assessment's vocabulary (founder 2026-08-05) — import it, never
re-decide it.

**This is not an exam, and the distinction is the whole reason the table
exists.** `assessment_cycles` is the school's record: it carries a scale
(`core/exams.py`'s minor/major, *never* pooled), a total, verify-and-lock, and it
feeds a child's standing, his report card and — through `D-76` — his band. A
support owner checking whether Kabir can read page 24 aloud is doing something
else entirely: a small, frequent, often unmarked check that exists to tell HER
whether last week's work moved him.

Putting that on `assessment_cycles` would mean a 1-to-5 reading rating landing in
the same arithmetic as a term paper, which is exactly the pooling `ScaleTally`
was built to make impossible to write by accident. So it is its own table, and
its figures never leave the programme.

Three metrics, and they are three different kinds of statement:

    marks       out of a total she sets — a number with a denominator
    rating      1..N on her own scale — an ordinal judgement, not a score
    other       a word: "read it", "still guessing" — no number at all

**They never pool.** `Tally` has no method returning a blended figure across
metrics, for the `ScaleTally` reason: a caller who wants one has to write the
addition where a reviewer can see it. An average is offered for `marks` (as a
percentage of its own total) and for `rating` (as a mean of its own scale),
separately, each carrying its denominator.

And the rule this module shares with homework: **not evaluated is a word.** An
assessment nobody has marked yet is `pending`, never "everyone scored zero", and
a child with no row is `not_evaluated`, never a nil result.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── the three metrics (founder 2026-08-05) ───────────────────────────────────
MARKS = "marks"
RATING = "rating"
OTHER = "other"
METRICS = (MARKS, RATING, OTHER)

METRIC_LABEL = {
    MARKS: "Marks",
    RATING: "Rating",
    OTHER: "A word",
}

# The default a rating runs to when she doesn't say. Five, because a support
# check is a judgement and a ten-point judgement is a five-point one with more
# hesitation; and odd, so "no change" has somewhere to sit.
DEFAULT_RATING_MAX = 5
MAX_RATING_MAX = 10

# ── the states an assessment can be in ───────────────────────────────────────
PENDING = "pending"          # nobody has recorded anything
PARTIAL = "partial"          # some of the roster, not all
EVALUATED = "evaluated"      # every child on the roster has a result

STATUS_LABEL = {
    PENDING: "Not evaluated",
    PARTIAL: "Part evaluated",
    EVALUATED: "Evaluated",
}


def normalise_metric(value: str | None) -> str:
    """Unknown text is refused, never coerced. A metric the reader invents is a
    column of numbers nobody can interpret."""
    v = (value or "").strip().lower()
    return v if v in METRICS else MARKS


def status_for(evaluated: int, roster: int) -> str:
    """`pending` is a real state, not an empty `evaluated`.

    A roster of zero is `pending`: an assessment whose children have all left
    the programme has not been completed, it has been overtaken."""
    if roster <= 0 or evaluated <= 0:
        return PENDING
    return EVALUATED if evaluated >= roster else PARTIAL


def result_text(metric: str, *, marks: float | None, rating: int | None,
                verdict: str | None, max_marks: float | None,
                rating_max: int | None) -> str | None:
    """One result, rendered in its own units — **always with its denominator**
    (`S-118`'s rule, a fourth time). "12" is unreadable; "12 of 20" is a fact.

    None means *not evaluated*, and every caller must render that as a word.
    """
    if metric == MARKS:
        if marks is None:
            return None
        return f"{marks:g} of {max_marks:g}" if max_marks else f"{marks:g}"
    if metric == RATING:
        if rating is None:
            return None
        return f"{rating} of {rating_max or DEFAULT_RATING_MAX}"
    return (verdict or "").strip() or None


@dataclass
class Tally:
    """One assessment's results, counted — and **never blended across
    metrics**.

    `average` is `None` unless the metric carries a number, and when it does it
    is that metric's own average on that metric's own scale. There is
    deliberately no property that mixes a rating with a mark.
    """

    metric: str = MARKS
    roster: int = 0
    evaluated: int = 0
    max_marks: float | None = None
    rating_max: int | None = None
    _values: list[float] = field(default_factory=list)

    def add(self, value: float | None) -> None:
        if value is not None:
            self._values.append(float(value))
            self.evaluated += 1

    @property
    def not_evaluated(self) -> int:
        # The gap in the record, as its own number. Never folded into a score.
        return max(0, self.roster - self.evaluated)

    @property
    def status(self) -> str:
        return status_for(self.evaluated, self.roster)

    @property
    def average(self) -> float | None:
        if not self._values:
            return None
        return round(sum(self._values) / len(self._values), 2)

    @property
    def average_pct(self) -> float | None:
        """Only where a percentage means something: marks over their own total.

        A rating has **no percentage** — 3 of 5 is not 60% of anything, and
        printing it as one invites it to be averaged with a mark."""
        avg = self.average
        if self.metric != MARKS or avg is None or not self.max_marks:
            return None
        return round(avg / float(self.max_marks) * 100, 1)

    def caption(self) -> str:
        """The figure with its denominator, in the metric's own words — what a
        screen renders instead of a bare number."""
        if not self.roster:
            return "Nobody is on this assessment yet."
        if not self.evaluated:
            return f"Not evaluated yet — {self.roster} child{'' if self.roster == 1 else 'ren'}."
        seen = f"{self.evaluated} of {self.roster} evaluated"
        avg = self.average
        if self.metric == MARKS and avg is not None:
            pct = self.average_pct
            return (f"Average {avg:g} of {self.max_marks:g} · {seen}"
                    + (f" · {pct:g}%" if pct is not None else ""))
        if self.metric == RATING and avg is not None:
            return f"Average {avg:g} of {self.rating_max or DEFAULT_RATING_MAX} · {seen}"
        return seen
