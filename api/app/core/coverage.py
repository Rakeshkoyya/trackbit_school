"""One weight for a partly-done thing, and one definition of syllabus coverage
(V1-0d — Q-40, S-88, ux §9; extended by V1-6 — S-51, S-54, Q-16).

Before this existed, the same word meant two different amounts in one product:
the syllabus board counted a partially covered topic as **0.5** while the
homework roll-up counted "partly done" as **zero** — so a child who did most of
the work scored identically to one who did nothing, and the two boards could
never be reconciled. Every coverage or completion figure now imports THIS
constant; a second weight anywhere is the defect coming back.

V1-6 found the same defect one level up, in the phrase *"syllabus covered"*
itself. It was computed in **four** places, no two alike:

    surface            numerator                    denominator
    ─────────────────────────────────────────────────────────────────────
    admin board        distinct topics, partial=0.5  topics on the PLAN
    growth report      topics with a `full` log      ALL topics (partial=0)
    parent progress    summed in the BROWSER         ALL topics
    plan class page    summed in the BROWSER         ALL topics

So a parent and a principal could read the same subject on the same day and
get different percentages, and neither was wrong on its own terms. `basis` now
makes the choice explicit at every call site, and `CoverageFigure` carries the
denominator with the number so no screen can render a percentage that has
forgotten what it is a percentage *of* (rule 3).

**Which basis goes where is a product decision, not a preference** (`Q-16`):

  * Parents see `SYLLABUS` — the whole portion. It is the only denominator that
    **cannot go down**. Coverage against the plan *falls* when the school sizes
    the next term's chapters: nothing was un-taught, the denominator simply
    grew, but a parent reads it as the school going backwards (`S-54`).
  * The admin sees both, side by side — *"34 of 58 in the syllabus · 34 of 41
    planned so far"* — because the first answers "will we finish?" and the
    second answers "are we on pace?", and those are different questions.
  * `PLANNED_TO_DATE` is the pace basis, and it is the only one that can say a
    subject is **genuinely slower** rather than merely short of the year's
    total. It is what `S-41` needs to tell "behind" apart from "not started".
"""

from dataclasses import dataclass

PARTIAL_WEIGHT = 0.5

# ── the three denominators, named once ───────────────────────────────────────
# A basis is never inferred from context. A caller that wants a percentage says
# which question it is answering, and the answer carries the basis back out.
SYLLABUS = "syllabus"                # every topic in the portion — only grows
PLANNED = "planned"                  # topics on the approved plan
PLANNED_TO_DATE = "planned_to_date"  # planned topics whose week has arrived

BASES = (SYLLABUS, PLANNED, PLANNED_TO_DATE)

# What each basis may be called on a screen. The window matters as much as the
# number (rule 3), and mid-year adoption makes it matter more: a school two
# months in must never read as a school 60% behind (plan §5).
BASIS_LABEL: dict[str, str] = {
    SYLLABUS: "of the whole syllabus",
    PLANNED: "of what is planned",
    PLANNED_TO_DATE: "of what was due by today",
}


# ── the states a class-subject can be in, and which of them are a pace ───────
# green/amber/red are a rating. Everything else is a statement about the
# *record*, and V2-P11 exists because treating a state as green made an
# unplanned year look healthy. `unknown` is V1-6's addition (`S-42`).
RAG: frozenset[str] = frozenset({"green", "amber", "red"})

UNKNOWN = "unknown"


def rated_status(pace_status: str, has_evidence: bool) -> str:
    """The status a *screen* shows, given the pace and whether anyone recorded.

    `S-42`: a subject whose teacher has never written a lesson log is
    **unknown**, not behind. The forecast can still rate it — its arithmetic is
    plan against calendar and is perfectly valid without a single log — but
    presenting that rating to a human as "3 weeks behind" states as fact
    something nobody observed. It is the same distinction attendance draws
    between *nobody was absent* and *nobody marked it*, and the same rule: a
    gap in the record is never a failing grade.

    So this is deliberately a **rendering** decision, not a planning one.
    `PlannerService.forecast` keeps returning green/amber/red — several tests
    and the exam-fit maths depend on that — and every surface a person reads
    runs the pace through here first.
    """
    if pace_status in RAG and not has_evidence:
        return UNKNOWN
    return pace_status


# ── S-41: the four reasons a subject is behind ───────────────────────────────
# They need four different responses, and only the last is about teaching:
#
#   not_logged     nobody recorded anything      talk about recording
#   periods_lost   periods were called off       nobody's fault; add periods
#   never_sized    chapters were never sized     a setup gap
#   slower         held, logged, still behind    the real conversation
#
# "6-B Maths is 3 weeks behind" is where a screen stops and an admin's work
# starts. "6-B Maths lost 8 periods to exam week and two holidays" is a
# different conversation, and often one in which nobody is at fault.
CAUSE_NOT_LOGGED = "not_logged"
CAUSE_PERIODS_LOST = "periods_lost"
CAUSE_NEVER_SIZED = "never_sized"
CAUSE_SLOWER = "slower"

# How many periods must have been called off before "we lost periods" is the
# honest reading rather than an excuse. Below this, a slip is about teaching.
LOST_PERIODS_FLOOR = 2


def _plural(n: float, word: str) -> str:
    return word if n == 1 else word + "s"


def attribute_cause(*, status: str, behind_topics: float = 0, weeks_behind: int = 0,
                    unestimated_topics: int = 0, planned_topics: int = 0,
                    periods_not_held: int = 0) -> tuple[str | None, str | None]:
    """Why is this class-subject behind? Returns (cause, the sentence).

    Pure, so the admin board and the class teacher's block give the same teacher
    the same reason on the same day. Returns `(None, None)` for a row that is
    not behind — a green row needs no excuse, and inventing one for it would
    make the cause column noise rather than a finding.

    The order of the tests is a product decision. "Nothing was logged" comes
    first because it invalidates every other reading; "periods were lost" comes
    before "genuinely slower" because one is nobody's fault and the other is a
    conversation about a person, and getting that order wrong turns a scheduling
    accident into an accusation.
    """
    if status == UNKNOWN:
        return CAUSE_NOT_LOGGED, (
            "Nothing has been logged, so there is no way to tell. "
            "Worth asking about recording, not about teaching.")
    if status not in ("amber", "red") and behind_topics <= 0:
        return None, None

    gap = (f"{behind_topics:g} {_plural(behind_topics, 'topic')} due by today "
           f"{'is' if behind_topics == 1 else 'are'} still untaught") \
        if behind_topics > 0 else \
        f"{weeks_behind} {_plural(weeks_behind, 'week')} behind the baseline"

    if periods_not_held >= LOST_PERIODS_FLOOR:
        return CAUSE_PERIODS_LOST, (
            f"{periods_not_held} periods were called off — {gap}. "
            "Nobody's fault; consider extra periods.")
    if unestimated_topics and not planned_topics:
        return CAUSE_NEVER_SIZED, (
            f"{unestimated_topics} {_plural(unestimated_topics, 'chapter')} have never "
            "been sized, so nothing could be scheduled. A setup gap, not a teaching one.")
    if unestimated_topics:
        return CAUSE_NEVER_SIZED, (
            f"{gap}, and {unestimated_topics} "
            f"{_plural(unestimated_topics, 'chapter')} are still unsized.")
    return CAUSE_SLOWER, (
        f"Periods were held and lessons were logged — {gap}. "
        "This is the teaching conversation.")


@dataclass(frozen=True)
class CoverageFigure:
    """A coverage number that cannot be rendered without its denominator.

    `taught` is weighted (a partly-covered topic is `PARTIAL_WEIGHT`), so it is
    a float while `total` is a whole count of topics. `pct` is None — never
    zero — when there is nothing to measure against: an unsized or unplanned
    subject has no coverage, which is a state, not a failure (rule 2).
    """

    taught: float
    total: int
    basis: str

    @property
    def pct(self) -> float | None:
        return coverage_pct(self.taught, self.total)

    @property
    def label(self) -> str:
        """The denominator in words, for the sentence beside the figure."""
        return BASIS_LABEL.get(self.basis, "")

    def sentence(self) -> str:
        """*"34 of 58 of the whole syllabus"* — the renderable form."""
        taught = f"{self.taught:g}"
        return f"{taught} of {self.total} {self.label}".strip()


def taught_weight(coverage: str) -> float:
    """How much a lesson-log coverage state is worth: full=1 · partial=0.5 · else 0."""
    if coverage == "full":
        return 1.0
    if coverage == "partial":
        return PARTIAL_WEIGHT
    return 0.0


def better_coverage(current: str | None, incoming: str) -> str:
    """The winning coverage state when one topic has several lesson logs.

    A topic taught across two periods — partially, then finished — is **taught
    once**, at its best state. Without this the same topic counted 1.5, and the
    admin board and the growth report disagreed about which log won because
    each walked the rows in its own order.
    """
    if current == "full":
        return current
    if incoming == "full":
        return incoming
    return current or incoming


def coverage_pct(taught: float, total: int) -> float | None:
    """THE syllabus-coverage arithmetic. None when there is nothing to divide by.

    None is not zero and no screen may render it as one — a subject with no
    plan and no portion has *unknown* coverage, which is a gap in the record
    (rule 2). Rounded to one decimal because a topic can be worth a half.
    """
    if not total:
        return None
    return round(taught / total * 100, 1)


def completion_pct(done: int, partial: int, denominator: int) -> float | None:
    """THE homework-completion arithmetic: done counts 1, partly counts
    PARTIAL_WEIGHT. `not_checked` never enters the denominator — the caller
    passes only graded items, because a teacher who checks nothing must never
    read as a class with perfect completion (HW-1's load-bearing rule)."""
    if not denominator:
        return None
    return round((done + PARTIAL_WEIGHT * partial) / denominator, 3)


# ── SY-1: the four states a CHAPTER can be in, on the board ──────────────────
# The syllabus table's "teaching status" column. Deliberately four words and no
# colour rule of its own — a chapter is late or not by comparison with its
# planned dates, which is `rated_status`' job on the class-subject above it.
#
#   not_started   nothing logged against any of its topics
#   in_progress   some taught, or one taught partially
#   completed     every topic taught in full
#   not_scheduled the chapter is not on the plan at all — a state, not a zero
#
# `not_scheduled` outranks the rest because it answers a different question: an
# unplanned chapter has not been missed, it has not been promised. Rendering it
# as "not started" would put a school that plans term by term permanently in
# the red every April (V2-P11's whole reason for existing).
CHAPTER_NOT_SCHEDULED = "not_scheduled"
CHAPTER_NOT_STARTED = "not_started"
CHAPTER_IN_PROGRESS = "in_progress"
CHAPTER_COMPLETED = "completed"

CHAPTER_STATUS_LABEL: dict[str, str] = {
    CHAPTER_NOT_SCHEDULED: "not scheduled",
    CHAPTER_NOT_STARTED: "not started",
    CHAPTER_IN_PROGRESS: "in progress",
    CHAPTER_COMPLETED: "completed",
}


def chapter_status(*, topics: int, taught_full: int, taught_partial: int,
                   planned: int, excluded: bool = False) -> str:
    """THE chapter-level teaching status. Import it; do not re-decide it.

    `taught_full`/`taught_partial` are counts of topics at their BEST logged
    state (`better_coverage` has already run), so a topic taught twice is
    counted once here.

    A chapter with no topics at all is `not_scheduled`: there is nothing to
    teach and nothing to have finished, and calling it completed would let an
    empty chapter carry a school's coverage figure upward.

    `excluded` is `syllabus_units.not_planned` — the school having *decided*
    this chapter is out of scope this year. It wins over every derived reading,
    including a chapter somebody once logged against: the decision is the more
    recent statement, the flag is trivially reversible, and a stale green would
    quietly inflate the school's coverage. It returns the SAME word as "nobody
    planned this", deliberately — to every reader both mean *there is nothing
    here to be behind on*, and a fifth word would have to be taught to three
    TypeScript unions and the parent report to draw a distinction only the
    person who set the flag can act on.
    """
    if excluded or not topics:
        return CHAPTER_NOT_SCHEDULED
    if taught_full >= topics:
        return CHAPTER_COMPLETED
    if taught_full or taught_partial:
        return CHAPTER_IN_PROGRESS
    # Nothing taught. Only now does it matter whether anybody ever promised to.
    return CHAPTER_NOT_STARTED if planned else CHAPTER_NOT_SCHEDULED


# The school's own reading of how hard a chapter is (SY-1). A vocabulary rather
# than free text because it is a filter and a sort key on the board; NULL —
# nobody has judged it — is a fourth state and never renders as 'moderate'.
DIFFICULTY_LEVELS = ("easy", "moderate", "hard")
