"""Plan-generation validators (V2-M2, SPRD2 §5.2) — deterministic, NOT the LLM.

The proposer (greedy `distribute`, or a model draft) suggests a placement; these
pure functions decide whether it is acceptable. A syllabus that cannot fit is a
human decision ("trim topics or add periods"), reported — never silently squeezed.

  V1 capacity     Σ est_periods ≤ effective periods available
  V2 coverage     every topic placed within the year (none spills past year end)
  V3 ordering     unit/topic order preserved (weeks non-decreasing)
  V4 teacher load no week where a teacher's planned periods exceed her slots
"""

from dataclasses import dataclass
from datetime import date


@dataclass
class Violation:
    code: str  # capacity | coverage | ordering | teacher_load
    message: str


def validate_capacity(total_est_periods: int, total_effective_periods: float) -> Violation | None:
    if total_est_periods > total_effective_periods:
        return Violation(
            "capacity",
            f"Syllabus needs {total_est_periods} periods but only about "
            f"{int(total_effective_periods)} teaching periods exist this year — "
            f"trim topics or add periods.")
    return None


def validate_coverage(placements: list[date], year_end_monday: date) -> Violation | None:
    overflow = [w for w in placements if w > year_end_monday]
    if overflow:
        return Violation(
            "coverage",
            f"{len(overflow)} topic(s) spill past the year end — they won't be covered.")
    return None


def validate_ordering(placements: list[date]) -> Violation | None:
    for a, b in zip(placements, placements[1:], strict=False):
        if b < a:
            return Violation("ordering", "Topic order is not preserved in the schedule.")
    return None


def validate_teacher_load(
    weekly_load: dict[date, int], weekly_slots: int, *, teacher: str = "",
) -> list[Violation]:
    """weekly_load = week_start → planned periods for one teacher across her classes."""
    out: list[Violation] = []
    if not weekly_slots:
        return out
    for wk, load in sorted(weekly_load.items()):
        if load > weekly_slots:
            who = f"{teacher} " if teacher else ""
            out.append(Violation(
                "teacher_load",
                f"Week of {wk}: {who}planned {load} periods but has {weekly_slots} slots."))
    return out
