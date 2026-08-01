"""One weight for a partly-done thing (V1-0d — Q-40, S-88, ux §9).

Before this existed, the same word meant two different amounts in one product:
the syllabus board counted a partially covered topic as **0.5** while the
homework roll-up counted "partly done" as **zero** — so a child who did most of
the work scored identically to one who did nothing, and the two boards could
never be reconciled. Every coverage or completion figure now imports THIS
constant; a second weight anywhere is the defect coming back.
"""

PARTIAL_WEIGHT = 0.5


def taught_weight(coverage: str) -> float:
    """How much a lesson-log coverage state is worth: full=1 · partial=0.5 · else 0."""
    if coverage == "full":
        return 1.0
    if coverage == "partial":
        return PARTIAL_WEIGHT
    return 0.0


def completion_pct(done: int, partial: int, denominator: int) -> float | None:
    """THE homework-completion arithmetic: done counts 1, partly counts
    PARTIAL_WEIGHT. `not_checked` never enters the denominator — the caller
    passes only graded items, because a teacher who checks nothing must never
    read as a class with perfect completion (HW-1's load-bearing rule)."""
    if not denominator:
        return None
    return round((done + PARTIAL_WEIGHT * partial) / denominator, 3)
