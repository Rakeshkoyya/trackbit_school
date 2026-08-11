"""Exam ↔ syllabus mapping (SY-1) — which chapters each exam actually examines.

V2-P7 gave the planner a portion so it could say the sentence it exists for:
*"chapter 5 lands after the exam that examines it."* It expressed the portion as
a **prefix** — everything up to a cut — and one control on the Year tab, buried
under the calendar, was the only way to set it.

A prefix cannot say what a school in November says: *"Term 1 examines chapters 1,
2, 3 and 5. Chapter 4 goes to Term 2."* Skipping a chapter is not an edge case;
it is the normal consequence of losing a fortnight to exams and festivals, and a
model that cannot express it forces the teacher to either examine a chapter she
never taught or leave the portion blank.

So the portion is a **set of chapters**, and this service is its screen: one exam
at a time, every subject of a class, chapters ticked. The fit verdict beside each
subject is `PlannerService.exam_fit`'s — unchanged, and read rather than
recomputed, so this screen and the Year tab's panel cannot disagree about whether
a portion fits.

Two things the shape refuses to hide:

  * a chapter **already examined by an earlier exam** is marked as such, so
    re-examining it is a deliberate tick rather than something nobody noticed;
  * a portion still held as a prefix reads `legacy_prefix` and is shown as the
    chapters it resolves to, never silently rewritten into a set. Converting it
    would be this service inventing a decision the school never made.
"""

import uuid
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.core.context import CurrentMember
from app.core.coverage import chapter_status, shown_chapter_status
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    ExamPortion,
    ExamPortionUnit,
    SchoolClass,
    Subject,
    SyllabusUnit,
)
from app.schemas.syllabus_board import (
    ExamMapChapter,
    ExamMapExam,
    ExamMapOut,
    ExamMapSubject,
    ExamPortionSetIn,
)
from app.services.coverage import CoverageReader
from app.services.periods import visible_class_ids
from app.services.planner import PlannerService
from app.services.school_clock import today_in


class ExamMapService:
    def __init__(self, db: Session):
        self.db = db

    def map(self, m: CurrentMember, class_id: uuid.UUID) -> ExamMapOut:
        klass = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == class_id, SchoolClass.org_id == m.org_id))
        if klass is None:
            raise NotFoundError("Class")
        allowed = visible_class_ids(self.db, m)
        if allowed is not None and class_id not in allowed:
            raise NotFoundError("Class")
        label = klass.name + (f"-{klass.section}" if klass.section else "")
        today = today_in(m.org.timezone)

        css = self.db.execute(
            select(ClassSubject, Subject.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id)
            .order_by(Subject.name)).all()
        cs_ids = [cs.id for cs, _n in css]
        if not cs_ids:
            return ExamMapOut(class_id=class_id, class_label=label,
                              headline="This class has no subjects yet.")

        units_by_cs: dict[uuid.UUID, list[SyllabusUnit]] = {}
        for u in self.db.scalars(
            select(SyllabusUnit)
            .where(SyllabusUnit.org_id == m.org_id,
                   SyllabusUnit.class_subject_id.in_(cs_ids))
            .options(selectinload(SyllabusUnit.topics))
            .order_by(SyllabusUnit.position)
        ):
            units_by_cs.setdefault(u.class_subject_id, []).append(u)

        portions = {(p.exam_event_id, p.class_subject_id): p
                    for p in self.db.scalars(
                        select(ExamPortion)
                        .where(ExamPortion.org_id == m.org_id,
                               ExamPortion.class_subject_id.in_(cs_ids))
                        .options(selectinload(ExamPortion.units)))}

        # The verdict comes from the planner, unchanged (`S-51`).
        fit = PlannerService(self.db).exam_fit(m, class_id)
        fit_by = {(e.exam_event_id, s.class_subject_id): (e, s)
                  for e in fit.exams for s in e.subjects}

        # The chapter's own state, from the one coverage reader.
        year = self.db.get(AcademicYear, klass.academic_year_id)
        snap = CoverageReader(self.db).snapshot(m.org_id, cs_ids, year, today=today)
        state_by_unit: dict[uuid.UUID, tuple[str, date | None]] = {}
        for cs_id, topics in snap.topics.items():  # noqa: B007
            per_unit: dict[uuid.UUID, list] = {}
            for t in topics:
                if t.unit_id:
                    per_unit.setdefault(t.unit_id, []).append(t)
            for unit_id, group in per_unit.items():
                full = sum(1 for t in group if t.best == "full")
                partial = sum(1 for t in group if t.best == "partial")
                weeks = [t.week_start for t in group if t.week_start]
                state_by_unit[unit_id] = (
                    chapter_status(topics=len(group), taught_full=full,
                                   taught_partial=partial, planned=len(weeks)),
                    max(weeks) if weeks else None)

        exams = list(self.db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.org_id == m.org_id,
                CalendarEvent.academic_year_id == klass.academic_year_id,
                CalendarEvent.type == "exam_block")
            .order_by(CalendarEvent.start_date)))

        out: list[ExamMapExam] = []
        for i, ev in enumerate(exams):
            subjects: list[ExamMapSubject] = []
            for cs, sname in css:
                p = portions.get((ev.id, cs.id))
                units = units_by_cs.get(cs.id, [])
                ordered = [t for u in units
                           for t in sorted(u.topics, key=lambda x: x.position)]
                mine = (PlannerService._portion_topic_ids(p, ordered, units)
                        if p is not None else set())
                selected_units = self._selected_units(p, units, mine)
                # What every earlier exam already examined, so a chapter ticked
                # twice is visibly a re-examination.
                earlier_units: set[uuid.UUID] = set()
                for prior in exams[:i]:
                    pp = portions.get((prior.id, cs.id))
                    if pp is None:
                        continue
                    prior_ids = PlannerService._portion_topic_ids(pp, ordered, units)
                    earlier_units |= self._selected_units(pp, units, prior_ids)

                efit = fit_by.get((ev.id, cs.id))
                subjects.append(ExamMapSubject(
                    class_subject_id=cs.id, subject_name=sname,
                    source=("none" if p is None else
                            "chapters" if p.units else "legacy_prefix"),
                    verdict=efit[1].verdict if efit else "no_portion",
                    required_periods=efit[1].required_periods if efit else 0,
                    capacity_periods=efit[1].capacity_periods if efit else 0,
                    unsized_topics=efit[1].unsized_topics if efit else 0,
                    chapters=[
                        ExamMapChapter(
                            unit_id=u.id, title=u.title, position=u.position,
                            est_periods=(sum(t.est_periods for t in u.topics
                                             if t.est_periods is not None) or None),
                            term_id=u.term_id,
                            selected=u.id in selected_units,
                            covered_earlier=u.id in earlier_units,
                            # SY-2: the SHOWN status, by the same rule the
                            # syllabus board uses — a human's typed word wins
                            # over the logs unless the chapter is out of scope.
                            # Re-deriving it here is how the same chapter came
                            # to read "Completed" on one tab and "not started"
                            # on the next.
                            status=shown_chapter_status(
                                u.manual_status, u.not_planned,
                                state_by_unit.get(u.id, ("not_scheduled", None))[0]),
                            planned_end=state_by_unit.get(u.id, ("", None))[1])
                        for u in units]))
            ex_row = next((e for e in fit.exams if e.exam_event_id == ev.id), None)
            out.append(ExamMapExam(
                exam_event_id=ev.id, title=ev.title, start_date=ev.start_date,
                end_date=ev.end_date, days_to_exam=(ev.start_date - today).days,
                teaching_days_in_gap=ex_row.teaching_days_in_gap if ex_row else 0,
                subjects=subjects))

        return ExamMapOut(class_id=class_id, class_label=label,
                          headline=self._headline(out, today), exams=out)

    @staticmethod
    def _selected_units(p: ExamPortion | None, units: list[SyllabusUnit],
                        topic_ids: set[uuid.UUID]) -> set[uuid.UUID]:
        """Which chapters a portion selects.

        An explicit set says so directly. A legacy prefix is resolved back to
        chapters — a chapter counts as in the portion when ANY of its topics is,
        because the prefix could cut a chapter in half and a half-examined
        chapter is still examined."""
        if p is None:
            return set()
        if p.units:
            return {pu.unit_id for pu in p.units}
        return {u.id for u in units if any(t.id in topic_ids for t in u.topics)}

    @staticmethod
    def _headline(exams: list[ExamMapExam], today: date) -> str:
        upcoming = [e for e in exams if e.start_date >= today]
        if not exams:
            return "No exams on the calendar yet — add them on Plan → Year."
        if not upcoming:
            return "Every exam this year is behind us."
        nxt = upcoming[0]
        short = [s for s in nxt.subjects if s.verdict == "short"]
        blank = [s for s in nxt.subjects if s.verdict == "no_portion"]
        days = (nxt.start_date - today).days
        when = "today" if days == 0 else f"in {days} day{'' if days == 1 else 's'}"
        if short:
            names = ", ".join(s.subject_name for s in short[:3])
            return (f"{nxt.title} {when} — {names} "
                    f"{'has' if len(short) == 1 else 'have'} more portion than "
                    f"teaching days left.")
        if blank:
            return (f"{nxt.title} {when} — {len(blank)} subject"
                    f"{'' if len(blank) == 1 else 's'} have no portion mapped, so "
                    f"nothing can warn you about them.")
        return f"{nxt.title} {when} — every subject's portion fits the days before it."

    # ── the write ────────────────────────────────────────────────────────────
    def set_portion(self, m: CurrentMember, body: ExamPortionSetIn) -> ExamMapOut:
        """Full replace of one (exam, class-subject) portion.

        Full replace, not add/remove: the teacher is looking at a list of ticks
        and what she sees when she presses save is the portion. An empty list
        clears it — *"this exam examines nothing of this subject"* is a real
        answer for a languages-only block, and a delete-shaped API cannot say it
        without also deleting the row somebody may be about to re-tick.
        """
        event = self.db.scalar(select(CalendarEvent).where(
            CalendarEvent.id == body.exam_event_id, CalendarEvent.org_id == m.org_id))
        if event is None:
            raise NotFoundError("Exam")
        if event.type != "exam_block":
            raise ValidationError("Only an exam block can have a portion.")
        cs = self.db.scalar(select(ClassSubject).where(
            ClassSubject.id == body.class_subject_id, ClassSubject.org_id == m.org_id))
        if cs is None:
            raise NotFoundError("Class-subject")

        wanted = list(dict.fromkeys(body.unit_ids))
        if wanted:
            valid = set(self.db.scalars(select(SyllabusUnit.id).where(
                SyllabusUnit.org_id == m.org_id,
                SyllabusUnit.class_subject_id == cs.id,
                SyllabusUnit.id.in_(wanted))))
            missing = [u for u in wanted if u not in valid]
            if missing:
                raise ValidationError(
                    "Some of those chapters are not in this subject's syllabus.")

        portion = self.db.scalar(select(ExamPortion).where(
            ExamPortion.org_id == m.org_id,
            ExamPortion.exam_event_id == body.exam_event_id,
            ExamPortion.class_subject_id == cs.id))
        if not wanted:
            if portion is not None:
                self.db.delete(portion)
            self.db.flush()
            return self.map(m, cs.class_id)

        if portion is None:
            portion = ExamPortion(org_id=m.org_id, exam_event_id=body.exam_event_id,
                                  class_subject_id=cs.id, upto_topic_id=None)
            self.db.add(portion)
            self.db.flush()
        else:
            # Stating the chapters retires the prefix: keeping both would leave
            # two answers on one row and `_portion_topic_ids` silently
            # preferring one.
            portion.upto_topic_id = None
            self.db.execute(delete(ExamPortionUnit).where(
                ExamPortionUnit.org_id == m.org_id,
                ExamPortionUnit.portion_id == portion.id))
        for unit_id in wanted:
            self.db.add(ExamPortionUnit(org_id=m.org_id, portion_id=portion.id,
                                        unit_id=unit_id))
        self.db.flush()
        return self.map(m, cs.class_id)
