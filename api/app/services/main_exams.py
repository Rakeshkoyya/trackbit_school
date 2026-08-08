"""The main exams (founder, 2026-08-05) — the school's exam calendar, in use.

**This service COMPOSES. It writes no marks and computes no average of its own.**

    the exam itself      `calendar_events` where `type='exam_block'` — the same
                         rows the planner paces against and `ExamPortion` maps
                         chapters onto. Not a new table (see `schemas/main_exams`).
    a paper's marks      `ExamService.save` / `ExamService.detail`, unchanged,
                         with `exam_event_id` set. One write path for every mark
                         in the product.
    a report card        `ReportCardService`, unchanged.
    the portion          `ExamPortion`, read only.

So the Plan → Exams screen is a **third rendering** of facts two other screens
already draw, and by construction it cannot disagree with either.

Two rules the shape enforces rather than trusts the UI for:

  * **A teacher may record only her own subject.** `ExamService.save` has
    always asked `assert_can_take_class`, which answers *may she stand in front
    of this class* — true for every subject of a class she teaches one subject
    of. That is the right rule for attendance and the wrong one for marks: it
    let the Hindi teacher overwrite the Maths paper. `assert_can_record_subject`
    is the narrower question, and it is asked in the service, not the screen.
  * **Reading a report card is deliberately wider than writing a mark.** She
    must see the whole card to talk to a family about a child; she must not be
    able to alter a colleague's column on it.
"""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    AssessmentCycle,
    AssessmentScore,
    CalendarEvent,
    ClassSubject,
    ExamPortion,
    ExamPortionUnit,
    Membership,
    SchoolClass,
    Student,
    Subject,
    User,
)
from app.schemas.main_exams import (
    MainExamBoard,
    MainExamClassGroup,
    MainExamDetail,
    MainExamIn,
    MainExamRow,
    MainExamSubjectRow,
)
from app.services.periods import visible_class_ids
from app.services.school_clock import today_in
from app.services.term_sync import sync_terms_from_exams

EXAM_BLOCK = "exam_block"


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


def _plural(n: int, one: str, many: str | None = None) -> str:
    return one if n == 1 else (many or one + "s")


def _state(ev: CalendarEvent, today: date) -> str:
    if ev.end_date < today:
        return "past"
    if ev.start_date <= today:
        return "running"
    return "upcoming"


class MainExamService:
    def __init__(self, db: Session):
        self.db = db

    # ── scope ────────────────────────────────────────────────────────────────
    def _year(self, m: CurrentMember, year_id: uuid.UUID | None) -> AcademicYear | None:
        q = select(AcademicYear).where(AcademicYear.org_id == m.org_id)
        if year_id:
            return self.db.scalar(q.where(AcademicYear.id == year_id))
        # The first request a real screen makes carries no year — the year
        # context resolves a moment later — so this is the common path.
        return self.db.scalar(q.where(AcademicYear.is_active.is_(True))) or self.db.scalar(
            q.order_by(AcademicYear.start_date.desc()))

    def _classes(self, m: CurrentMember, year: AcademicYear,
                 ) -> tuple[list[SchoolClass], bool]:
        """The classes in view, and whether that is the whole school.

        A teacher's set is `visible_class_ids` — the subjects she teaches ∪ the
        homeroom she owns (AT-1). It is a **block**: a class she has nothing to
        do with is never loaded, so there is no filtered-to-empty screen to
        misread as "no exams here".
        """
        allowed = visible_class_ids(self.db, m)
        q = select(SchoolClass).where(
            SchoolClass.org_id == m.org_id,
            SchoolClass.academic_year_id == year.id)
        if allowed is not None:
            if not allowed:
                return [], False
            q = q.where(SchoolClass.id.in_(allowed))
        return (list(self.db.scalars(q.order_by(SchoolClass.name, SchoolClass.section))),
                allowed is None)

    def _events(self, m: CurrentMember, year: AcademicYear) -> list[CalendarEvent]:
        return list(self.db.scalars(
            select(CalendarEvent).where(
                CalendarEvent.org_id == m.org_id,
                CalendarEvent.academic_year_id == year.id,
                CalendarEvent.type == EXAM_BLOCK)
            .order_by(CalendarEvent.start_date)))

    # ── the board ────────────────────────────────────────────────────────────
    def board(self, m: CurrentMember, year_id: uuid.UUID | None = None) -> MainExamBoard:
        """Every exam the school has declared this year, with its progress.

        Five queries whatever the number of exams: the events, the classes in
        scope, their class-subjects, the cycles filed under any of those events,
        and one aggregate pass over those cycles' scores.
        """
        today = today_in(m.org.timezone)
        year = self._year(m, year_id)
        if year is None:
            return MainExamBoard(as_of=today, can_edit=m.is_admin,
                                 headline="No academic year is set up yet.")
        classes, is_school = self._classes(m, year)
        out = MainExamBoard(academic_year_id=year.id, as_of=today,
                            scope="school" if is_school else "mine",
                            can_edit=m.is_admin)

        events = self._events(m, year)
        if not events:
            out.headline = (
                "No exams on the calendar yet — add the year's exams here and "
                "every class's papers hang off them."
                if m.is_admin else
                "No exams have been put on the calendar yet. Your admin adds them.")
            return out

        class_ids = [k.id for k in classes]
        cs_rows = self.db.execute(
            select(ClassSubject.id, ClassSubject.class_id)
            .where(ClassSubject.org_id == m.org_id,
                   ClassSubject.class_id.in_(class_ids))).all() if class_ids else []
        subjects_total = len(cs_rows)

        cycles = self._cycles(m, [e.id for e in events], class_ids)
        agg = self._score_agg([c.id for rows in cycles.values() for c in rows])

        for ev in events:
            rows = cycles.get(ev.id, [])
            row = MainExamRow(
                exam_event_id=ev.id, title=ev.title, start_date=ev.start_date,
                end_date=ev.end_date, notes=ev.notes,
                affects_teaching=ev.affects_teaching,
                blocks_periods=ev.blocks_periods,
                state=_state(ev, today),
                days_away=(ev.start_date - today).days,
                classes_total=len(classes), subjects_total=subjects_total,
                recorded_subjects=len(rows),
                locked_subjects=sum(1 for c in rows if c.locked_at is not None))
            tot_s = tot_x = 0.0
            for c in rows:
                n, s, x = agg.get(c.id, (0, 0.0, 0.0))
                row.scored_students += n
                tot_s += s
                tot_x += x
            row.avg_pct = round(tot_s / tot_x * 100, 1) if tot_x else None
            row.caption = self._caption(row)
            out.rows.append(row)

        out.headline = self._headline(out.rows, today)
        return out

    def _cycles(self, m: CurrentMember, event_ids: list[uuid.UUID],
                class_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[AssessmentCycle]]:
        if not event_ids or not class_ids:
            return {}
        out: dict[uuid.UUID, list[AssessmentCycle]] = defaultdict(list)
        for c in self.db.scalars(
            select(AssessmentCycle).where(
                AssessmentCycle.org_id == m.org_id,
                AssessmentCycle.exam_event_id.in_(event_ids),
                AssessmentCycle.class_id.in_(class_ids))
        ):
            out[c.exam_event_id].append(c)
        return out

    def _score_agg(self, cycle_ids: list[uuid.UUID],
                   ) -> dict[uuid.UUID, tuple[int, float, float]]:
        if not cycle_ids:
            return {}
        return {cid: (int(n), float(s or 0), float(x or 0))
                for cid, n, s, x in self.db.execute(
                    select(AssessmentScore.cycle_id,
                           func.count(func.distinct(AssessmentScore.student_id)),
                           func.sum(AssessmentScore.score),
                           func.sum(AssessmentScore.max_score))
                    .where(AssessmentScore.cycle_id.in_(cycle_ids))
                    .group_by(AssessmentScore.cycle_id)).all()}

    @staticmethod
    def _caption(row: MainExamRow) -> str:
        """A sentence per row, and it never says 0%.

        Nothing recorded is a state of the record, not a result — the same rule
        the register, the homework funnel and the syllabus board all keep.
        """
        if not row.subjects_total:
            return "No subjects set up to examine yet."
        if not row.recorded_subjects:
            return ("Nothing recorded yet — "
                    f"{row.subjects_total} {_plural(row.subjects_total, 'paper')} "
                    "to enter.")
        tail = (f" · average {row.avg_pct}%" if row.avg_pct is not None else "")
        locked = (f" · {row.locked_subjects} locked" if row.locked_subjects else "")
        return (f"{row.recorded_subjects} of {row.subjects_total} papers recorded"
                + tail + locked + ".")

    @staticmethod
    def _headline(rows: list[MainExamRow], today: date) -> str:
        """Lead with a sentence, and lead with the thing waiting (ux §3)."""
        if not rows:
            return "No exams on the calendar yet."
        running = [r for r in rows if r.state == "running"]
        if running:
            r = running[0]
            return (f"{r.title} is on now — {r.recorded_subjects} of "
                    f"{r.subjects_total} papers recorded.")
        upcoming = [r for r in rows if r.state == "upcoming"]
        if upcoming:
            r = upcoming[0]
            when = ("tomorrow" if r.days_away == 1
                    else f"in {r.days_away} {_plural(r.days_away, 'day')}")
            return f"{len(rows)} exams this year · {r.title} is next, {when}."
        behind = [r for r in rows if r.recorded_subjects < r.subjects_total]
        if behind:
            n = len(behind)
            return (f"Every exam is behind us, and {n} still "
                    f"{'has' if n == 1 else 'have'} papers with no marks entered.")
        return f"All {len(rows)} exams are recorded."

    # ── one exam ─────────────────────────────────────────────────────────────
    def detail(self, m: CurrentMember, event_id: uuid.UUID) -> MainExamDetail:
        """Class × subject, each row either a recorded paper or an empty slot.

        The rows a teacher may EDIT are her own subjects; the rows she may SEE
        are every subject of every class she is assigned to. Both are decided
        here, and `can_edit` rides on the row so no client re-derives it.
        """
        today = today_in(m.org.timezone)
        ev = self._event(m, event_id)
        year = self.db.get(AcademicYear, ev.academic_year_id)
        classes, _is_school = (self._classes(m, year) if year else ([], False))
        out = MainExamDetail(
            exam_event_id=ev.id, title=ev.title, start_date=ev.start_date,
            end_date=ev.end_date, notes=ev.notes, state=_state(ev, today),
            can_edit_exam=m.is_admin)
        if not classes:
            out.headline = "You are not assigned to any class in this year."
            return out

        class_ids = [k.id for k in classes]
        cs_rows = self.db.execute(
            select(ClassSubject, Subject.name, User.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .outerjoin(Membership, Membership.id == ClassSubject.teacher_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .where(ClassSubject.org_id == m.org_id,
                   ClassSubject.class_id.in_(class_ids))
            .order_by(Subject.name)).all()

        cycles = {(c.class_id, c.subject_id): c for c in self.db.scalars(
            select(AssessmentCycle).where(
                AssessmentCycle.org_id == m.org_id,
                AssessmentCycle.exam_event_id == ev.id,
                AssessmentCycle.class_id.in_(class_ids)))}
        agg = self._score_agg([c.id for c in cycles.values()])
        rosters = dict(self.db.execute(
            select(Student.class_id, func.count(Student.id))
            .where(Student.org_id == m.org_id, Student.status == "active",
                   Student.class_id.in_(class_ids))
            .group_by(Student.class_id)).all())
        # The homerooms she owns, so `can_edit` on a row says exactly what
        # `assert_can_record_subject` will accept. A grid that greys out a cell
        # the server would have taken is a screen lying about permission — and
        # the class teacher is precisely the person who enters a paper for a
        # colleague who has left.
        homerooms = set() if m.is_admin else set(self.db.scalars(
            select(SchoolClass.id).where(
                SchoolClass.org_id == m.org_id,
                SchoolClass.class_teacher_member_id == m.membership.id)))
        portions = dict(self.db.execute(
            select(ExamPortion.class_subject_id, func.count(ExamPortionUnit.id))
            .outerjoin(ExamPortionUnit, ExamPortionUnit.portion_id == ExamPortion.id)
            .where(ExamPortion.org_id == m.org_id,
                   ExamPortion.exam_event_id == ev.id)
            .group_by(ExamPortion.class_subject_id)).all())

        groups: dict[uuid.UUID, MainExamClassGroup] = {
            k.id: MainExamClassGroup(class_id=k.id,
                                     class_label=_label(k.name, k.section))
            for k in classes}

        for cs, subject_name, teacher_name in cs_rows:
            group = groups[cs.class_id]
            cycle = cycles.get((cs.class_id, cs.subject_id))
            row = MainExamSubjectRow(
                class_subject_id=cs.id, subject_id=cs.subject_id,
                subject_name=subject_name, teacher_name=teacher_name,
                roster=int(rosters.get(cs.class_id, 0)),
                can_edit=(m.is_admin
                          or cs.teacher_member_id == m.membership.id
                          or cs.class_id in homerooms),
                portion_chapters=int(portions.get(cs.id, 0)))
            if cycle is not None:
                n, s, x = agg.get(cycle.id, (0, 0.0, 0.0))
                row.cycle_id = cycle.id
                row.cycle_name = cycle.name
                row.total_marks = (float(cycle.total_marks)
                                   if cycle.total_marks is not None else None)
                row.scored = n
                row.avg_pct = round(s / x * 100, 1) if x else None
                row.locked = cycle.locked_at is not None
                group.recorded += 1
            group.total += 1
            group.subjects.append(row)

        out.classes = [g for g in groups.values() if g.total]
        recorded = sum(g.recorded for g in out.classes)
        total = sum(g.total for g in out.classes)
        mine = sum(1 for g in out.classes for r in g.subjects if r.can_edit)
        todo = sum(1 for g in out.classes for r in g.subjects
                   if r.can_edit and r.cycle_id is None)
        if m.is_admin:
            out.headline = (f"{recorded} of {total} papers recorded across "
                            f"{len(out.classes)} {_plural(len(out.classes), 'class', 'classes')}."
                            if total else "No subjects set up to examine yet.")
        elif todo:
            out.headline = (f"{todo} of your {mine} {_plural(mine, 'paper')} still "
                            "need marks. You can read every subject's card here; "
                            "only your own are yours to enter.")
        else:
            out.headline = (f"All {mine} of your {_plural(mine, 'paper')} are "
                            "recorded. Every other subject is read-only."
                            if mine else
                            "You have no papers to enter for this exam.")
        return out

    # ── the exam list is the admin's (write side) ────────────────────────────
    def _event(self, m: CurrentMember, event_id: uuid.UUID) -> CalendarEvent:
        ev = self.db.scalar(select(CalendarEvent).where(
            CalendarEvent.id == event_id, CalendarEvent.org_id == m.org_id))
        if ev is None:
            raise NotFoundError("Exam")
        if ev.type != EXAM_BLOCK:
            raise ValidationError("That calendar entry is not an exam.",
                                  code="not_an_exam")
        return ev

    def create(self, m: CurrentMember, body: MainExamIn) -> MainExamRow:
        if body.academic_year_id is None:
            raise ValidationError("Say which academic year this exam belongs to.")
        year = self.db.scalar(select(AcademicYear).where(
            AcademicYear.id == body.academic_year_id, AcademicYear.org_id == m.org_id))
        if year is None:
            raise NotFoundError("Academic year")
        self._assert_dates(body, year)
        ev = CalendarEvent(
            org_id=m.org_id, academic_year_id=year.id, type=EXAM_BLOCK,
            title=body.title.strip(), start_date=body.start_date,
            end_date=body.end_date, affects_teaching=body.affects_teaching,
            blocks_periods=body.blocks_periods, notes=body.notes)
        self.db.add(ev)
        self.db.flush()
        # Terms follow the exam calendar (founder, 2026-08-08): a term ends on
        # its exam's last day. Same transaction, so the exam and its term move
        # together or not at all.
        sync_terms_from_exams(self.db, m.org_id, year.id)
        return self._row(m, ev)

    def update(self, m: CurrentMember, event_id: uuid.UUID,
               body: MainExamIn) -> MainExamRow:
        """Title, dates and how much teaching it eats.

        The year is deliberately NOT movable: an exam block is what the planner
        paces against, and moving one between years would silently re-pace two
        calendars at once.
        """
        ev = self._event(m, event_id)
        year = self.db.get(AcademicYear, ev.academic_year_id)
        self._assert_dates(body, year)
        ev.title = body.title.strip()
        ev.start_date = body.start_date
        ev.end_date = body.end_date
        ev.affects_teaching = body.affects_teaching
        ev.blocks_periods = body.blocks_periods
        ev.notes = body.notes
        self.db.flush()
        # Moving an exam moves its term with it — that is the whole point of
        # them being one thing (founder, 2026-08-08).
        sync_terms_from_exams(self.db, m.org_id, ev.academic_year_id)
        return self._row(m, ev)

    def delete(self, m: CurrentMember, event_id: uuid.UUID) -> None:
        """Refused once any paper has been recorded under it.

        Marks are the record (`D-53`), and deleting the block that owns them
        would orphan a term's papers with nothing on screen to say it happened.
        Removing an exam that has been sat is a real request; it is just not a
        one-tap one, and it starts with unlocking and clearing the papers.
        """
        ev = self._event(m, event_id)
        n = int(self.db.scalar(
            select(func.count(AssessmentCycle.id)).where(
                AssessmentCycle.org_id == m.org_id,
                AssessmentCycle.exam_event_id == ev.id)) or 0)
        if n:
            raise ValidationError(
                f"{n} {_plural(n, 'paper has', 'papers have')} already been "
                "recorded under this exam. Remove those first.",
                code="exam_has_marks")
        year_id = ev.academic_year_id
        self.db.delete(ev)
        self.db.flush()
        sync_terms_from_exams(self.db, m.org_id, year_id)

    @staticmethod
    def _assert_dates(body: MainExamIn, year: AcademicYear | None) -> None:
        if body.end_date < body.start_date:
            raise ValidationError("The exam cannot end before it starts.")
        if year is not None and not (
                year.start_date <= body.start_date <= year.end_date
                and year.start_date <= body.end_date <= year.end_date):
            raise ValidationError(
                "Those dates fall outside the academic year.", code="outside_year")

    def _row(self, m: CurrentMember, ev: CalendarEvent) -> MainExamRow:
        """The created/edited row, alone — the screen re-reads the board for the
        rest, so nothing here re-implements the progress arithmetic."""
        today = today_in(m.org.timezone)
        return MainExamRow(
            exam_event_id=ev.id, title=ev.title, start_date=ev.start_date,
            end_date=ev.end_date, notes=ev.notes,
            affects_teaching=ev.affects_teaching, blocks_periods=ev.blocks_periods,
            state=_state(ev, today), days_away=(ev.start_date - today).days,
            caption="Nothing recorded yet.")

    # ── the narrower write rule (founder, 2026-08-05) ────────────────────────
    def assert_can_record_subject(self, m: CurrentMember, class_id: uuid.UUID,
                                  subject_id: uuid.UUID) -> None:
        """May this member enter marks for THIS subject of THIS class?

        `assert_can_take_class` answers *may she stand in front of this class*,
        which is the right question for attendance and the wrong one for a mark:
        it is true for every subject of a class she teaches one subject of, so
        the Hindi teacher could overwrite the Maths paper.

        Admin anywhere. Otherwise the subject's own teacher, or the class
        teacher of the homeroom — she is answerable for the class's record and
        is the person who enters a paper for a colleague who has left.
        """
        if m.is_admin:
            return
        cs = self.db.scalar(select(ClassSubject).where(
            ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id,
            ClassSubject.subject_id == subject_id))
        if cs is not None and cs.teacher_member_id == m.membership.id:
            return
        if self.db.scalar(select(SchoolClass.id).where(
                SchoolClass.id == class_id, SchoolClass.org_id == m.org_id,
                SchoolClass.class_teacher_member_id == m.membership.id)) is not None:
            return
        raise ForbiddenError(
            "That subject is not yours to enter marks for. You can read it here.",
            code="not_your_subject")
