"""M4 — homework: is it being done, and is anyone checking (DASH3 §4.4).

`HomeworkService` (HW-1) already answers most of this: completion by class and
subject, the red list of repeat non-doers with the responsible teacher, teacher
checking discipline, perfect-week and most-improved. This module adds the one
thing a board needs that a roll-up cannot give — **the shape over time** — and
otherwise deliberately delegates rather than writing a second set of numbers that
could disagree with the homework screen.

The `not_checked` distinction rides all the way through (HW-1): a missing
`homework_checks` row means the teacher never went through it, which is never
"everyone did it" and is never rendered as a student's miss. On the daily series
it is why `expected` (student-assignments under *checked* homework) is the
completion denominator, and `assigned` is not.
"""

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.schemas.insights import HomeworkBoard, HomeworkDay
from app.services.homework import HomeworkService
from app.services.school_clock import today_in

WINDOW_DAYS = 14


def _plural(n: int, word: str) -> str:
    return word if n == 1 else word + "s"


def _headline(ov) -> str:
    """§7 rule 3 — the sentence the tab opens with.

    Composed only from figures `overview` already computed, so the tab, the
    overview block and Lucy cannot describe the same week differently.

    The care here is HW-1's rule, restated: **`not_checked` is the teacher's gap
    and never a child's miss**, so unchecked sets are named separately and are
    never inside the completion figure. A percentage with nothing checked behind
    it is not a low score, it is no score — and saying "0% done" there would
    blame children for a teacher who has not opened the notebooks.
    """
    if not ov.assigned:
        return f"No homework has been set in the last {ov.window_days} days."
    unchecked = max(0, ov.assigned - ov.checked)
    if ov.overall_completion is None:
        return (f"{ov.assigned} {_plural(ov.assigned, 'set')} of homework set, "
                "none checked yet — completion cannot be read until somebody checks.")

    pct = round(ov.overall_completion * 100)
    parts = [f"{pct}% done across the {ov.checked} of {ov.assigned} "
             f"{_plural(ov.assigned, 'set')} that were checked."]
    # `S-99`: late is done, and reported beside completion rather than inside it.
    if ov.late:
        parts.append(f"{ov.late} done late.")
    if unchecked:
        parts.append(f"{unchecked} still unchecked.")
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
        window = max(1, min(window_days, 60))
        service = HomeworkService(self.db)
        overview = service.overview(m, window)
        until = today_in(m.org.timezone)
        since = until - timedelta(days=window - 1)

        # One more pass over the same loaded window — five queries, shared with
        # the overview's own load, and no per-day query.
        assignments, checks, results, roster, _teachers = service._load(m, since, until)
        per_day: dict[date, list[int]] = defaultdict(lambda: [0, 0, 0, 0])
        for a in assignments:
            hw = a["hw"]
            checked = hw.id in checks
            targets = service._targets(a, roster)
            acc = per_day[hw.date]
            acc[0] += 1
            if not checked:
                continue
            acc[1] += 1
            acc[2] += len(targets)
            acc[3] += sum(
                1 for sid, _n, _r in targets
                if service._status(a, sid, checks, results) == "done")

        daily = [
            HomeworkDay(
                date=d, assigned=v[0], checked=v[1], expected=v[2], done=v[3],
                completion=round(v[3] / v[2], 3) if v[2] else None)
            for d, v in sorted(per_day.items())
        ]
        return HomeworkBoard(headline=_headline(overview), overview=overview, daily=daily)

    def student(self, m: CurrentMember, student_id: uuid.UUID,
                window_days: int = WINDOW_DAYS):
        return HomeworkService(self.db).student_history(m, student_id, window_days)
