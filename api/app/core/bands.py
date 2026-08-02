"""The support programme's vocabulary and arithmetic (V1-9).

A band is **not a grading scheme**. It is a teaching group inside a programme:
assess against a written standard, group, give every C child an owner, work,
re-assess on evidence, and measure the **movement**. Everything in this module
exists to stop the letter drifting back into being a label.

Four rules live here and nowhere else:

**The band is per subject, and there is no overall letter** (`D-75`). A child who
reads two years below his grade and is fine at arithmetic used to get one letter
describing neither — and the daily-check generator then handed him easier
*maths*. `chip()` renders the consequence: **"C · Hindi"**, the lowest band with
the subject that earned it, never an average and never a bare letter (`S-186`).

**The letter never appears without its descriptor** (`S-166`). `placement_sentence`
is what screens render. A letter alone is precisely the label P4 exists to
prevent, and the descriptor is also the answer to *"what should a B child be able
to do?"*.

**Thresholds are per subject** (`D-74`). Before V1-9 there were two numbers for
the whole school, so English and Maths were assumed to grade alike. C is
deliberately **"below B"** rather than its own cut-off, so two thresholds can
never disagree about the same mark.

**Entry may be judgement; movement is a test** (`S-185`, `D-70`/`D-76`). Both
routes are first-class and every row records which one produced it — but once a
class is filed, a child changes band on a band test or a promoted test, never on
an opinion.

Pure and stdlib-only, so all of it is testable without a database.
"""

from __future__ import annotations

from dataclasses import dataclass

TIERS = ("A", "B", "C")
# Worst-first, because every list in this module is a list of who needs help.
TIER_RANK = {"C": 0, "B": 1, "A": 2}

# The defaults a school starts from — two org-wide numbers were the old
# behaviour and stay the fallback for a subject nobody has configured.
DEFAULT_A_MIN = 75
DEFAULT_B_MIN = 50

SOURCE_TEST = "test"
SOURCE_OBSERVATION = "observation"
SOURCES = (SOURCE_TEST, SOURCE_OBSERVATION)

SOURCE_LABEL = {
    SOURCE_TEST: "from a test",
    SOURCE_OBSERVATION: "teacher's assessment",
}

# `S-175`: ship the nine **pre-written and editable**. 27 empty boxes get filled
# in by nobody. Keyed by a coarse subject family so a school's own subject names
# ("English", "English Literature", "Hindi", "Maths") land on something useful,
# with a generic set behind them — never an empty string, which is what a
# teacher would have to invent a standard against.
_LANGUAGE = {
    "A": "Reads unfamiliar text fluently and writes a short paragraph unaided.",
    "B": "Reads a grade-level passage aloud with ≤3 errors; writes four sentences unaided.",
    "C": "Decodes short words; copies but does not yet compose.",
}
_MATHS = {
    "A": "Solves an unfamiliar multi-step problem and explains the method.",
    "B": "Works grade-level problems accurately with occasional prompting.",
    "C": "Needs the number facts in front of him; cannot yet start a word problem alone.",
}
_SCIENCE = {
    "A": "Explains why, not only what — and applies it to a new example.",
    "B": "Recalls and uses the chapter's ideas with the textbook shut.",
    "C": "Recognises the words; cannot yet say what they mean in his own.",
}
_GENERIC = {
    "A": "Works confidently beyond the class task and needs extension, not support.",
    "B": "Keeps up with the class task with occasional help.",
    "C": "Cannot yet start the class task without help.",
}

_FAMILIES: tuple[tuple[tuple[str, ...], dict[str, str]], ...] = (
    (("english", "hindi", "telugu", "urdu", "sanskrit", "language", "literature",
      "marathi", "tamil", "kannada", "malayalam", "bengali", "gujarati"), _LANGUAGE),
    (("math", "maths", "mathematics", "arithmetic", "algebra"), _MATHS),
    (("science", "physics", "chemistry", "biology", "evs"), _SCIENCE),
)


def starter_descriptors(subject_name: str) -> dict[str, str]:
    """The pre-written standard for a subject, by tier. Never empty — a school
    edits a sentence far more readily than it writes one."""
    key = (subject_name or "").strip().casefold()
    for names, texts in _FAMILIES:
        if any(n in key for n in names):
            return dict(texts)
    return dict(_GENERIC)


def tier_for(pct: float | None, a_min: int = DEFAULT_A_MIN,
             b_min: int = DEFAULT_B_MIN) -> str | None:
    """A percentage → a tier, against **this subject's** thresholds.

    `None` in, `None` out: a child who did not sit the test is **not assessed**,
    which is a word, never a C and never a zero (ux §5)."""
    if pct is None:
        return None
    value = pct * 100 if pct <= 1 else pct
    if value >= a_min:
        return "A"
    if value >= b_min:
        return "B"
    return "C"


@dataclass(frozen=True)
class Placement:
    """One child's band in one subject — with everything needed to render it
    honestly: the subject that earned it, and the sentence behind the letter."""

    subject_id: object
    subject_name: str
    tier: str
    descriptor: str | None = None
    source: str = SOURCE_TEST

    @property
    def rank(self) -> int:
        return TIER_RANK.get(self.tier, 3)

    def sentence(self) -> str:
        """`S-166`: the rendering every staff surface should use."""
        head = f"Band {self.tier} in {self.subject_name}"
        return f"{head} — {self.descriptor}" if self.descriptor else head


def chip(placements: list[Placement]) -> str | None:
    """`S-186`: **"C · Hindi"** — the lowest band a child holds, named with the
    subject that earned it.

    Never an average across subjects (there is no overall letter to average),
    and never a bare letter. Returns None when the child has no band at all,
    because *not assessed* is its own state."""
    if not placements:
        return None
    worst = min(placements, key=lambda p: (p.rank, p.subject_name))
    return f"{worst.tier} · {worst.subject_name}"


def lowest(placements: list[Placement]) -> Placement | None:
    if not placements:
        return None
    return min(placements, key=lambda p: (p.rank, p.subject_name))


def movement(before: str | None, after: str | None) -> str:
    """`up` | `down` | `same` | `new` — the programme's only real measure
    (`D-67`). The admin is shown *how many children moved*, never the
    distribution: a distribution looks identical in a school where nobody has
    moved for a year."""
    if after is None:
        return "same"
    if before is None:
        return "new"
    if before == after:
        return "same"
    return "up" if TIER_RANK[after] > TIER_RANK[before] else "down"


def size_warnings(total_marks: float | None, sat: int, roster: int) -> list[str]:
    """`S-184`: **warn, never block.** A teacher who knows the test was small can
    still be right about the child, and a validator that refuses a legitimate
    case is a rule staff route around by hand (SF-1's leave-policy shape)."""
    out: list[str] = []
    if total_marks is not None and total_marks < 20:
        out.append(f"A {total_marks:g}-mark test is a small basis for moving a child.")
    if roster and sat < roster * 0.6:
        out.append(f"Only {sat} of {roster} children sat it — the rest keep their band.")
    return out
