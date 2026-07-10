"""Plan-generation validators (V2-M2, SPRD2 §5.2) — deterministic, NOT the LLM.

The proposer (greedy `distribute`, or a model draft) suggests a placement; these
pure functions decide whether it is acceptable. A syllabus that cannot fit is a
human decision ("trim topics or add periods"), reported — never silently squeezed.

  V1 capacity      Σ est_periods ≤ effective periods available
  V2 coverage      every topic placed within the window (none spills past its end)
  V3 ordering      unit/topic order preserved (weeks non-decreasing)
  V4 teacher load  no week where a teacher's planned periods exceed her slots
  V5 exam coverage every topic in an exam's portion is taught before the exam starts
  V6 unsized       no topic left without a period estimate
"""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class Violation:
    code: str  # capacity | coverage | ordering | teacher_load | exam_coverage | unsized
    message: str


def validate_capacity(total_est_periods: int, total_effective_periods: float,
                      window: str = "this year") -> Violation | None:
    if total_est_periods > total_effective_periods:
        return Violation(
            "capacity",
            f"Syllabus needs {total_est_periods} periods but only about "
            f"{int(total_effective_periods)} teaching periods exist {window} — "
            f"trim topics or add periods.")
    return None


def validate_unsized(unsized_titles: list[str]) -> Violation | None:
    """V6. An unsized topic cannot be scheduled, so it is not in the plan at all —
    and a plan that quietly omits a third of the syllabus must not report `fits`.
    This is the validator that stops the forecast going green on an unplanned year."""
    if not unsized_titles:
        return None
    first = unsized_titles[0]
    detail = f'"{first}"' if len(unsized_titles) == 1 else \
        f'{len(unsized_titles)} topics, starting with "{first}",'
    return Violation(
        "unsized",
        f"{detail} have no period estimate yet, so they are not scheduled. "
        f"Set the periods for each chapter to plan them.")


def validate_coverage(placements: list[date], window_end_monday: date) -> Violation | None:
    overflow = [w for w in placements if w > window_end_monday]
    if overflow:
        return Violation(
            "coverage",
            f"{len(overflow)} topic(s) spill past the end of the planning window — "
            f"they won't be covered.")
    return None


def validate_ordering(placements: list[date]) -> Violation | None:
    for a, b in zip(placements, placements[1:], strict=False):
        if b < a:
            return Violation("ordering", "Topic order is not preserved in the schedule.")
    return None


def validate_exam_coverage(
    exam_title: str, exam_start: date, portion: list[tuple[str, date]],
) -> Violation | None:
    """The validator that earns the whole planner its keep.

    `portion` is [(topic_title, planned_week_start)] for every topic the exam
    examines. A topic is safe only if its whole planned WEEK ends before the exam
    starts — a topic scheduled for the week the exam begins in has not been taught
    yet when the paper is written."""
    late = [(title, wk) for title, wk in portion if wk + timedelta(days=6) >= exam_start]
    if not late:
        return None
    first = min(late, key=lambda x: x[1])[0]
    if len(late) == 1:
        detail = f'"{first}" is'
    else:
        detail = f'{len(late)} topics starting with "{first}" are'
    return Violation(
        "exam_coverage",
        f"{exam_title} starts {exam_start}, but {detail} not planned to finish "
        f"before it — trim the portion, add periods, or move the exam.")


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
