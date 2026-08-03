"""M4 — homework: is it being done, and is anyone checking (DASH3 §4.4).

`HomeworkService` (HW-1) answers all of it: the funnel, the shape over time,
completion by class and subject and class×subject, the red list of repeat
non-doers with the responsible teacher, teacher checking discipline,
perfect-week and most-improved. This module adds the **sentence** and nothing
else — it deliberately owns no arithmetic, because a second set of numbers here
is a second set of numbers that can disagree with the homework screen.

That is not hypothetical: this file used to compute the daily series itself, by
re-running `HomeworkService._load` and walking the window a second time with its
own rules. `late` was dropped from the numerator, `carried` and `waived` stayed
in the denominator, and the absent→carried rewrite never ran — so the chart read
lower than the sentence directly above it, and a child off sick pulled the line
down. The series is now accumulated inside `overview()`'s single pass, through
`core/homework_verdict` like every other figure. It also halves the query count:
the old path ran `_load` twice, ten statements to draw one board.

The `not_checked` distinction rides all the way through (HW-1): a missing
`homework_checks` row means the teacher never went through it, which is never
"everyone did it" and is never rendered as a student's miss. It is why the
funnel's first gap is drawn as a texture rather than a colour, and why the
completion figure's denominator is `graded` and not `given`.
"""

import uuid

from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.schemas.insights import HomeworkBoard
from app.services.homework import HomeworkService

WINDOW_DAYS = 14
# A year, so the tab's Year range is a real range rather than a clamp. The load
# is still five queries; only the number of rows joined in memory grows.
MAX_WINDOW_DAYS = 400


def _plural(n: int, word: str) -> str:
    return word if n == 1 else word + "s"


def _headline(ov) -> str:
    """§7 rule 3 — the sentence the tab opens with.

    Composed only from figures `overview` already computed, so the tab, the
    overview block and Lucy cannot describe the same week differently.

    The care here is HW-1's rule, restated: **`not_checked` is the teacher's gap
    and never a child's miss**, so unchecked work is named in its own clause,
    with its own denominator, and is never inside the completion figure. A
    percentage with nothing checked behind it is not a low score, it is no
    score — and saying "0% done" there would blame children for a teacher who
    has not opened the notebooks.
    """
    f = ov.funnel
    if not f.given:
        return f"No homework has been set in the last {ov.window_days} days."

    unchecked = max(0, f.given - f.checked)
    if f.completion is None:
        return (f"{f.given} {_plural(f.given, 'homework')} given out across "
                f"{f.assignments} {_plural(f.assignments, 'set')} — none checked "
                "yet, so completion is unknown rather than zero.")

    parts = [f"{round(f.completion * 100)}% of the {f.graded} "
             f"{_plural(f.graded, 'homework')} that carry a verdict were done"
             + (f", {f.late} of them late." if f.late else ".")]
    if unchecked:
        # Its own clause with its own denominator: this is about the teachers,
        # and folding it into the sentence above would read as a figure about
        # the children.
        parts.append(f"{unchecked} of the {f.given} given are still waiting to "
                     "be checked.")
    else:
        parts.append(f"Everything given has been gone through ({f.given} in all).")
    # A named row beats a count (DASH3) — say who, not how many.
    if ov.delayed_teachers:
        t = ov.delayed_teachers[0]
        more = len(ov.delayed_teachers) - 1
        parts.append(f"{t.teacher_name} has checked nothing"
                     + (f" (+{more} more)." if more else "."))
    return " ".join(parts)


class HomeworkInsights:
    def __init__(self, db: Session):
        self.db = db

    def board(self, m: CurrentMember, window_days: int = WINDOW_DAYS) -> HomeworkBoard:
        window = max(1, min(window_days, MAX_WINDOW_DAYS))
        overview = HomeworkService(self.db).overview(m, window)
        # `daily` is mirrored onto the board because that is where every client
        # already reads it from; it is the same list the overview carries,
        # never a recomputation.
        return HomeworkBoard(headline=_headline(overview), overview=overview,
                             daily=overview.daily)

    def student(self, m: CurrentMember, student_id: uuid.UUID,
                window_days: int = WINDOW_DAYS):
        return HomeworkService(self.db).student_history(m, student_id, window_days)
