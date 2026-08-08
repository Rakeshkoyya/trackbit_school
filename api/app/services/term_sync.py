"""Terms are derived from exams — never typed (founder, 2026-08-08).

A term IS its exam. The school states when an exam runs; the term is the stretch
of teaching that leads up to it, so:

    term N  starts  the day after term N-1's exam ended (the first: the year's
                    first day)
    term N  ends    on its own exam's last day

There is deliberately **no terms editor**. Sunrise is what having one costs: two
terms beside five exam blocks, both "correct", and every downstream figure quietly
answering a different question from the one the principal asked. The exam calendar
is the single place a date is typed, and this module makes the terms follow.

**Why derive rather than delete `Term`.** `term_id` is read by thirty-one modules
and is a real foreign key on `syllabus_units`, `assessment_cycles`,
`band_assessments` and `plans`. Deriving keeps every one of them working, unchanged
and correct; removing the table would be a migration that rewrites live rows for no
gain the school can see.

Two rules that keep this safe to call on every exam save:

  * **A term with anything hanging off it is never deleted.** If the school
    removes an exam whose term already carries chapters or marks, that term is
    kept and stretched instead. Silently deleting it would cascade a year's work
    out of existence.
  * **Names follow date order.** Terms are renumbered by position, so a school
    inserting a mid-year exam gets Term 3 becoming Term 4 rather than a second
    row also called Term 3.
"""

import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AcademicYear,
    AssessmentCycle,
    CalendarEvent,
    SyllabusUnit,
    Term,
)

EXAM_BLOCK = "exam_block"


def _in_use(db: Session, org_id: uuid.UUID, term_id: uuid.UUID) -> bool:
    """Does anything hang off this term? A term carrying a year's chapters or a
    term's marks is not ours to delete because somebody retyped an exam date."""
    for model, column in ((SyllabusUnit, SyllabusUnit.term_id),
                          (AssessmentCycle, AssessmentCycle.term_id)):
        found = db.scalar(select(func.count()).select_from(model)
                          .where(model.org_id == org_id, column == term_id))
        if found:
            return True
    return False


def sync_terms_from_exams(db: Session, org_id: uuid.UUID,
                          year_id: uuid.UUID | None = None) -> list[Term]:
    """Rebuild the year's terms from its exam blocks. Idempotent.

    Call it after any write to an `exam_block` — create, edit or delete. Flushes
    but never commits: the caller's request owns the transaction, so an exam save
    and its term move land together or not at all.
    """
    year = db.scalar(
        select(AcademicYear).where(AcademicYear.org_id == org_id,
                                   AcademicYear.id == year_id)
        if year_id else
        select(AcademicYear).where(AcademicYear.org_id == org_id,
                                   AcademicYear.is_active.is_(True)))
    if year is None:
        return []

    exams = list(db.scalars(
        select(CalendarEvent)
        .where(CalendarEvent.org_id == org_id,
               CalendarEvent.academic_year_id == year.id,
               CalendarEvent.type == EXAM_BLOCK)
        .order_by(CalendarEvent.start_date, CalendarEvent.end_date)))
    existing = list(db.scalars(
        select(Term).where(Term.org_id == org_id,
                           Term.academic_year_id == year.id)
        .order_by(Term.start_date)))
    if not exams:
        # No exam calendar yet: leave whatever the school has. A school mid-setup
        # with one hand-made term should not have it deleted from under it.
        return existing

    cursor = year.start_date
    out: list[Term] = []
    for i, exam in enumerate(exams):
        end = max(exam.end_date, cursor)
        term = existing[i] if i < len(existing) else None
        if term is None:
            term = Term(org_id=org_id, academic_year_id=year.id,
                        name=f"Term {i + 1}", start_date=cursor, end_date=end)
            db.add(term)
        else:
            term.name = f"Term {i + 1}"
            term.start_date, term.end_date = cursor, end
        out.append(term)
        cursor = end + timedelta(days=1)

    # Fewer exams than terms: the tail has nothing to end it. Drop the empty ones,
    # keep any that carry work, and stretch the last one to the year's end so no
    # teaching day falls outside every term.
    db.flush()
    for spare in existing[len(exams):]:
        if _in_use(db, org_id, spare.id):
            spare.start_date = cursor
            spare.end_date = max(year.end_date, cursor)
            out.append(spare)
            cursor = spare.end_date + timedelta(days=1)
        else:
            db.delete(spare)
    if out and out[-1].end_date < year.end_date:
        out[-1].end_date = year.end_date
    db.flush()
    return out
