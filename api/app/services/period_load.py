"""`periods_per_week` — derived from the timetable, never typed (founder, TT-3).

The founder's words: *"there is no way we get this from the school admin, they
don't have this data before, we must calculate it."*

He is right, and the old shape proved it. `class_subjects.periods_per_week` was
an *entered* number — a column on the setup pack's Teaching Assignments sheet —
and it is the divisor the whole planner runs on: `PlannerService.distribute`
refuses to place a chapter without it, `exam_fit` cannot say whether a portion
lands before the exam, and `reschedule` rejects a date range outright. A school
filling in a spreadsheet in April does not know that Class 5 English will get 13
periods; it finds out when the timetable is drawn in June. So the column was
blank or wrong for most schools, and every date the app could have computed was
silently unavailable.

The timetable already holds the answer exactly, as a fact the school states by
drawing its grid. This module is the one place that reads it across.

**One writer.** `class_subjects.periods_per_week` is now a DERIVED CACHE, like
`Plan.status` (of `plan_approvals`) and `year.period_times` (of
`bell_schedules`). Nothing else may assign it. It is a cache rather than a live
count because it is read on nearly every planner path, often for forty
class-subjects at once, and a `COUNT(*)` per read would put a join on the
critical path of every plan, forecast and exam-fit call.

**When a class has no timetable at all, the stored value stands.**
Deliberately, and it is the one judgement in here. Zeroing it would take the
only weekly figure a half-set-up school has and replace it with a number that
stops the planner dead — punishing the school for the very gap this change
exists to fix. As soon as the class has ONE timetable row the grid wins for
every subject in it, including the ones it does not mention, which then
correctly read 0: an untimetabled subject genuinely gets no periods.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ClassSubject, TimetableSlot


def _current_counts(db: Session, org_id: uuid.UUID,
                    class_ids: list[uuid.UUID] | None,
                    ) -> tuple[dict[uuid.UUID, int], set[uuid.UUID]]:
    """(class_subject_id → periods, classes that have any grid at all).

    "Current" is `effective_to IS NULL` — the live grid. Slots closed by a bell
    change or an earlier revision are history and must not count, or a school
    that halved its Tuesday would keep the old number for ever.
    """
    q = (select(TimetableSlot.class_subject_id, TimetableSlot.class_id,
                func.count(TimetableSlot.id))
         .where(TimetableSlot.org_id == org_id,
                TimetableSlot.slot_type == "subject",
                TimetableSlot.effective_to.is_(None),
                TimetableSlot.class_subject_id.is_not(None))
         .group_by(TimetableSlot.class_subject_id, TimetableSlot.class_id))
    if class_ids is not None:
        if not class_ids:
            return {}, set()
        q = q.where(TimetableSlot.class_id.in_(class_ids))
    counts: dict[uuid.UUID, int] = {}
    timetabled: set[uuid.UUID] = set()
    for cs_id, class_id, n in db.execute(q).all():
        counts[cs_id] = int(n)
        timetabled.add(class_id)
    return counts, timetabled


def recompute_periods_per_week(db: Session, org_id: uuid.UUID,
                               class_ids: Iterable[uuid.UUID] | None = None,
                               ) -> int:
    """Re-derive the weekly load for these classes. Returns rows changed.

    Call it after ANY write that can change the live grid — a single cell, a
    bulk paste, a cleared slot, an imported timetable, or a bell change that
    closes the periods off the end of the day. Cheap: two queries whatever the
    number of classes, and it writes only the rows whose number actually moved,
    so a no-op edit produces no UPDATE and no version churn.

    `class_ids=None` means the whole org — used by the setup import and the
    backfill, never on a hot path.
    """
    ids = None if class_ids is None else list(dict.fromkeys(class_ids))
    counts, timetabled = _current_counts(db, org_id, ids)
    if not timetabled:
        # No grid anywhere in scope — nothing to derive from. Leave the stored
        # numbers alone rather than zeroing a school that has not drawn its
        # timetable yet (see the module docstring).
        return 0

    q = select(ClassSubject).where(
        ClassSubject.org_id == org_id,
        ClassSubject.class_id.in_(timetabled))
    if ids is not None:
        q = q.where(ClassSubject.class_id.in_(ids))

    changed = 0
    for cs in db.scalars(q):
        want = counts.get(cs.id, 0)
        if cs.periods_per_week != want:
            cs.periods_per_week = want
            changed += 1
    if changed:
        db.flush()
    return changed
