"""The exam vocabulary and arithmetic — one computation, many renderings (V1-8).

`core/homework_verdict.py` and `core/coverage.py` exist because the same phrase was
being decided in five places. This module exists for the same reason, before it
happens a sixth time: **"how did they do"** is currently computed by pooling every
mark in scope — an April diagnostic, twelve slip tests and one final, summed into
one fraction — on the admin board (`insights/exams.py`), in `class_analysis`, and
on the student's report card (`growth.py`). *"Maths is at 61%"* is then a fact
about nothing.

Three things live here and nowhere else:

**`scale` — `minor` | `major`, and the two are NEVER added** (`S-114`, `Q-50`).
A slip test and a term exam measure different things: frequent low-stakes tests
show *movement*, rare high-stakes ones show *standing*. So **trajectory is drawn
from `minor`, standing is read from `major`**, and no screen may sum across them.
`ScaleTally` makes that structural rather than a rule to remember — there is no
method on it that returns a blended number.

> The obvious alternative is weights ("slip test 10%, term exam 60%") and it is a
> trap: that is the **report-card designer** SPRD2 §11 fences. Every school wants
> different weights, the composite is checkable against nothing, and the argument
> about the weights becomes the product. Two buckets and never-pool gets the same
> honesty with none of the policy.

**Every average carries its denominator** (`S-118`, ux-principles §4).
`insights/exams.py` already refuses a bare average at school level — *"88% from 9
of 42 students is not an 88% class"*. `ScoreFigure` applies the same rule one
level down, so a child who was absent for the hard ones cannot read as strong:
*"61% across 5 of the 9 tests 8-B sat"*.

**The school's word is the exam's name; the system kind is code-only** (`D-55`).
`type` stays the nine-value system kind the code branches on (`diagnostic` routes
to the skill grid, `band_test` is admin-only); `exam_types` carries what the
staffroom actually says — *CET*, *pre-board*, *cycle test*. If an analytic ever
groups by `type`, the two have diverged. `type_label` is the fallback for rows
recorded before a school configured its own words, never the primary rendering.

Pure and stdlib-only, so every rule above is unit-testable without a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MINOR = "minor"
MAJOR = "major"
SCALES = (MINOR, MAJOR)

# The system kinds (`assessment_cycles.type`) → (fallback label, default scale).
# Read by code, never rendered when the school has named its own type (`D-55`).
SYSTEM_TYPES: dict[str, tuple[str, str]] = {
    "diagnostic": ("Diagnostic", MINOR),
    "daily_test": ("Daily test", MINOR),
    "slip_test": ("Slip test", MINOR),
    "class_test": ("Class test", MINOR),
    "chapter_test": ("Chapter test", MINOR),
    "objective": ("Objective test", MINOR),
    "band_test": ("Band test", MINOR),
    "unit_test": ("Unit test", MAJOR),
    "term_exam": ("Term exam", MAJOR),
}

SCALE_LABELS = {MINOR: "Minor tests", MAJOR: "Major exams"}
# What each bucket is FOR — the sentence a screen leads with, so nobody has to
# remember why the two are apart.
SCALE_PURPOSE = {
    MINOR: "frequent tests — these show movement",
    MAJOR: "term and unit exams — these show standing",
}


def type_label(system_type: str | None) -> str:
    """The fallback name for a system kind. Used only where a school has not
    named its own exam type — never in place of one that exists."""
    if not system_type:
        return "Test"
    known = SYSTEM_TYPES.get(system_type)
    return known[0] if known else system_type.replace("_", " ").capitalize()


def default_scale(system_type: str | None) -> str:
    """The scale a type gets when nobody has said otherwise. Unknown kinds are
    `minor`: a school's own word is far more likely to be a weekly test than a
    term exam, and calling a slip test `major` is the error that pollutes the
    standing figure."""
    known = SYSTEM_TYPES.get(system_type or "")
    return known[1] if known else MINOR


def normalise_scale(value: str | None, system_type: str | None = None) -> str:
    """A stored scale, or the type's default. Never raises — an unrecognised
    value falls back rather than losing the row (the `work_types` lesson)."""
    if value in SCALES:
        return str(value)
    return default_scale(system_type)


# ── the figure a screen may render ───────────────────────────────────────────
@dataclass(frozen=True)
class ScoreFigure:
    """A percentage that cannot be rendered without its denominators.

    `tests_taken` / `tests_held` is `S-118`: a child absent for the hard papers
    must not read as a strong child. `sentence()` is the rendering every screen
    should use, so the denominator can't be dropped by a component author."""

    scale: str
    score: float
    max_score: float
    tests_taken: int
    tests_held: int

    @property
    def pct(self) -> float | None:
        if self.max_score <= 0 or self.tests_taken == 0:
            return None
        return round(self.score / self.max_score * 100, 1)

    @property
    def complete(self) -> bool:
        """Did they sit everything that was held? A partial denominator is the
        thing worth saying out loud."""
        return self.tests_held > 0 and self.tests_taken >= self.tests_held

    def sentence(self) -> str:
        if self.pct is None:
            return f"No {SCALE_LABELS[self.scale].lower()} recorded"
        if self.tests_held and not self.complete:
            return (f"{self.pct:g}% across {self.tests_taken} of the "
                    f"{self.tests_held} tests")
        n = self.tests_taken
        return f"{self.pct:g}% across {n} test{'' if n == 1 else 's'}"


@dataclass
class ScaleTally:
    """Marks accumulated per scale. **There is no way to ask this for a blended
    number** — that is the point (`S-114`). A caller who wants one has to write
    the addition themselves, in the open, where a reviewer can see it."""

    marks: dict[str, list[float]] = field(default_factory=lambda: {s: [0.0, 0.0] for s in SCALES})
    cycles: dict[str, set] = field(default_factory=lambda: {s: set() for s in SCALES})

    def add(self, scale: str | None, score: float, max_score: float,
            cycle_id: object = None, system_type: str | None = None) -> None:
        s = normalise_scale(scale, system_type)
        if max_score and max_score > 0:
            self.marks[s][0] += float(score)
            self.marks[s][1] += float(max_score)
        if cycle_id is not None:
            self.cycles[s].add(cycle_id)

    def taken(self, scale: str) -> int:
        return len(self.cycles[normalise_scale(scale)])

    def figure(self, scale: str, tests_held: int | None = None) -> ScoreFigure:
        s = normalise_scale(scale)
        taken = len(self.cycles[s])
        return ScoreFigure(scale=s, score=self.marks[s][0], max_score=self.marks[s][1],
                           tests_taken=taken,
                           tests_held=taken if tests_held is None else tests_held)

    def figures(self, held: dict[str, int] | None = None) -> list[ScoreFigure]:
        """Both buckets, in a fixed order, each carrying its own denominator.
        Empty buckets are returned too — *"no major exams yet"* is information,
        and dropping the row is how a screen ends up implying there were none."""
        held = held or {}
        return [self.figure(s, held.get(s)) for s in SCALES]

    @property
    def empty(self) -> bool:
        return not any(self.cycles[s] for s in SCALES)


# ── per-question marks (read off the marked script) ──────────────────────────
def clean_question_marks(raw: object) -> list[dict] | None:
    """Normalise what the model transcribed from a marked paper into
    `[{q, score, max}]`, or None if there is nothing usable.

    This is a **transcription**, not a judgement (`Q-51`): the marks written
    beside each question by the teacher who marked it. Nothing here decides
    whether an answer was right — the product forms no opinion about a child's
    work (`S-117`), and a paper typed in by hand simply has no question detail,
    which the screens say as a word rather than a zero."""
    if not isinstance(raw, list):
        return None
    out: list[dict] = []
    for i, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            continue
        label = str(item.get("q") or item.get("question") or i).strip()[:12]
        try:
            score = float(item.get("score") if item.get("score") is not None else item.get("mark"))
        except (TypeError, ValueError):
            continue
        if score < 0:
            continue
        raw_max = item.get("max") if item.get("max") is not None else item.get("max_score")
        try:
            mx = float(raw_max) if raw_max not in (None, "") else None
        except (TypeError, ValueError):
            mx = None
        if mx is not None and mx <= 0:
            mx = None
        out.append({"q": label or str(i), "score": score, "max": mx})
    return out or None


def question_total(question_marks: object) -> float | None:
    """The sum of the per-question marks, or None if there are none."""
    qs = question_marks if isinstance(question_marks, list) else None
    if not qs:
        return None
    total = 0.0
    for q in qs:
        if isinstance(q, dict) and isinstance(q.get("score"), (int, float)):
            total += float(q["score"])
    return round(total, 2)


def sum_mismatch(question_marks: object, total: float | None,
                 tolerance: float = 0.01) -> float | None:
    """`S-116`'s surviving half: **the marks don't add up.**

    Pure arithmetic over digits the model was already reading, with a ground
    truth the school can verify in three seconds — the most common real error in
    a marked stack, and the one that reaches a parent. Returns the difference
    (question total − written total), or None when there is nothing to compare.

    It is a **flag on the review grid**, never a claim about the child."""
    if total is None:
        return None
    qt = question_total(question_marks)
    if qt is None:
        return None
    diff = round(qt - float(total), 2)
    return diff if abs(diff) > tolerance else None
