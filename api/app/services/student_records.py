"""The Academics roster — every child, and how each one is doing (founder, 2026-08-05).

The Students area has always held two different kinds of fact about a child and
offered one screen for both. **Directory** is the administration record: the name
the school registered, the parent's number, the date of birth. **Academics** is
the record the school *makes* — the register, the class log, the homework, the
exams. This module is the roster for the second one.

It COMPOSES and computes almost nothing of its own, which is the point:

    attendance   marked `class_periods` minus this child's `attendance_exceptions`
                 — the same derivation `growth.py` makes, capture-by-exception
    exams        `services/exam_marks.load_marks`, the one batched marks reader,
                 through `core/exams.ScaleTally` so minor and major never pool
    homework     `core/homework_verdict`, so `late` is worth what it is worth
                 here and everywhere else
    bands        `BandService.chip_map` (`S-186`)

Nothing new is decided here. If a figure on this table disagrees with the tab it
links to, this file has grown an opinion it should not have.

**Six queries for the whole school**, whatever its size — not per class. The
exam half was the trap: `load_class_marks` is four round-trips and the roster
asks it of every class on one page load, which is 80 for a 20-class school. It
is batched (`load_marks`) for the same reason `forecast_org` was (`PR-6`).
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core import homework_verdict as verdicts
from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError
from app.models import (
    AcademicYear,
    AttendanceException,
    ClassPeriod,
    ClassSubject,
    HomeworkAssignment,
    HomeworkCheck,
    HomeworkResult,
    SchoolClass,
    Student,
    Subject,
)
from app.schemas.student_records import (
    RecordAttendance,
    RecordFigure,
    RecordHomework,
    StudentRecordRow,
    StudentRecordsOut,
)
from app.services.bands import BandService
from app.services.exam_marks import load_marks
from app.services.periods import today_for, visible_class_ids

# How far back the homework run is read. Matches `HomeworkService.WINDOW_DAYS`'
# intent — recent enough to describe how the term is going, long enough that a
# holiday week doesn't empty the column.
WINDOW_DAYS = 30


def _label(name: str, section: str | None) -> str:
    return f"{name}-{section}" if section else name


class StudentRecordsService:
    def __init__(self, db: Session):
        self.db = db

    def _today(self, m: CurrentMember) -> date:
        return today_for(m)

    def _scope(self, m: CurrentMember,
               class_id: uuid.UUID | None) -> tuple[list[uuid.UUID], bool]:
        """The classes this member may read, and whether that is a narrowing.

        A teacher asking for a class she doesn't teach is **refused with a
        sentence, never filtered to an empty table** (`S-46`). An empty table
        reads as "this class has no students", which is a different and much
        more alarming fact than "this isn't yours".
        """
        allowed = visible_class_ids(self.db, m)
        every = list(self.db.scalars(
            select(SchoolClass.id).where(SchoolClass.org_id == m.org_id)))
        if allowed is None:
            ids = [class_id] if class_id else every
            return ids, False
        if class_id is not None:
            if class_id not in allowed:
                raise ForbiddenError(
                    "That class isn't one you teach.", code="not_your_class")
            return [class_id], True
        return [c for c in every if c in allowed], True

    def roster(self, m: CurrentMember, class_id: uuid.UUID | None = None,
               query: str | None = None,
               window_days: int = WINDOW_DAYS) -> StudentRecordsOut:
        class_ids, scoped = self._scope(m, class_id)
        out = StudentRecordsOut(window_days=window_days, scoped=scoped,
                                class_count=len(class_ids))
        if not class_ids:
            return out

        today = self._today(m)
        since = today - timedelta(days=max(1, window_days) - 1)

        # ── 1. the children ──────────────────────────────────────────────────
        q = select(Student, SchoolClass.name, SchoolClass.section).join(
            SchoolClass, SchoolClass.id == Student.class_id).where(
            Student.org_id == m.org_id, Student.class_id.in_(class_ids))
        if query:
            like = f"%{query.strip()}%"
            q = q.where(or_(Student.full_name.ilike(like),
                            Student.admission_no.ilike(like)))
        student_rows = self.db.execute(
            q.order_by(SchoolClass.name, SchoolClass.section, Student.full_name)).all()
        if not student_rows:
            return out
        students = [s for s, _, _ in student_rows]
        sids = [s.id for s in students]
        by_class: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        for s in students:
            by_class[s.class_id].append(s.id)

        # ── 2/3. attendance — marked periods per class, this child's deviations ──
        year = self.db.scalar(
            select(AcademicYear).where(AcademicYear.org_id == m.org_id,
                                       AcademicYear.is_active.is_(True)))
        floor = year.tracking_start_date or year.start_date if year else None
        cond = [ClassPeriod.org_id == m.org_id,
                ClassPeriod.class_id.in_(class_ids),
                ClassPeriod.attendance_marked_at.is_not(None)]
        if floor:
            cond.append(ClassPeriod.date >= floor)
        # Both halves aggregate in POSTGRES. The first cut of this read pulled
        # every marked period id into Python purely to count them, then sent the
        # thousands back in an `IN (...)` for the exceptions — on a real school
        # (240 children, 422 marked periods per class) that was seconds of round
        # trip and a query string measured in kilobytes. The join does the same
        # work in the database, where the ids already are.
        marked_per_class: dict[uuid.UUID, int] = dict(self.db.execute(
            select(ClassPeriod.class_id, func.count())
            .where(*cond).group_by(ClassPeriod.class_id)).all())

        deviations: dict[uuid.UUID, dict[str, int]] = defaultdict(
            lambda: {"absent": 0, "late": 0})
        on_page = set(sids)
        for sid, status, n in self.db.execute(
                select(AttendanceException.student_id, AttendanceException.status,
                       func.count())
                .join(ClassPeriod, ClassPeriod.id == AttendanceException.period_id)
                .where(*cond)
                .group_by(AttendanceException.student_id,
                          AttendanceException.status)).all():
            # The class join already scopes these rows; the page's own narrowing
            # (a search box) is applied here rather than as a second huge IN.
            if sid in on_page and status in deviations[sid]:
                deviations[sid][status] = n

        # ── 4. exams — batched across every class on the page ────────────────
        # Deliberately NOT narrowed by `student_ids`. The cycles already belong
        # to these classes, so their scores already belong to these children —
        # the filter was redundant, and passing 240 ids made an 11.7KB query
        # that cost 2.3s on its own against the remote database. `figures()`
        # keys by student, so a search box narrows the rows without needing the
        # scores query to know about it.
        marks = load_marks(self.db, m.org_id, class_ids)

        # ── 5/6. homework — the recent run, per child ────────────────────────
        homework = self._homework(m, class_ids, sids, by_class, since, today)

        # bands: one query, and the chip is `core/bands.chip` (`S-186`) — the
        # lowest band WITH the subject that earned it, never a bare letter.
        chips = BandService(self.db).chip_map(m)

        for student, cname, section in student_rows:
            att = RecordAttendance(marked_periods=marked_per_class.get(student.class_id, 0))
            dev = deviations.get(student.id, {"absent": 0, "late": 0})
            att.absent, att.late = dev["absent"], dev["late"]
            att.present = max(0, att.marked_periods - att.absent)
            if att.marked_periods:
                att.pct = round(att.present * 100.0 / att.marked_periods, 1)

            cm = marks.get(student.class_id)
            figures = cm.figures(student.id) if cm else []
            out.rows.append(StudentRecordRow(
                student_id=student.id, full_name=student.full_name,
                admission_no=student.admission_no, roll_no=student.roll_no,
                class_id=student.class_id, class_label=_label(cname, section),
                status=student.status, attendance=att,
                figures=[RecordFigure(
                    scale=f.scale, pct=f.pct, tests_taken=f.tests_taken,
                    tests_held=f.tests_held, sentence=f.sentence()) for f in figures],
                homework=homework.get(student.id, RecordHomework()),
                band_chip=chips.get(str(student.id))))
        return out

    def _homework(self, m: CurrentMember, class_ids: list[uuid.UUID],
                  sids: list[uuid.UUID], by_class: dict[uuid.UUID, list[uuid.UUID]],
                  since: date, until: date) -> dict[uuid.UUID, RecordHomework]:
        """Two queries for every child's recent homework run.

        The verdict for one (child, assignment) is derived exactly as
        `HomeworkService.history_for` derives it, through `core/homework_verdict`:
        no check row → `not_checked`; a check with no result row for this child →
        `done`. Writing that rule a second time is how `late` came to be worth
        two different things once already, so nothing here decides it — the
        tally, the completion and the streak are all the shared functions.
        """
        rows = self.db.execute(
            select(HomeworkAssignment.id, HomeworkAssignment.date,
                   HomeworkAssignment.student_id, ClassSubject.class_id, Subject.name)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   ClassSubject.class_id.in_(class_ids),
                   HomeworkAssignment.date >= since,
                   HomeworkAssignment.date <= until)
            .order_by(HomeworkAssignment.date)).all()
        out: dict[uuid.UUID, RecordHomework] = {}
        if not rows:
            return out
        on_page = set(sids)
        # Both of these JOIN back to the assignment rather than listing its ids.
        # Passing them (plus 240 student ids) built 10–16KB query strings for
        # what the same three-table scope expresses in a few hundred bytes, and
        # the database has the ids already.
        scope = (
            HomeworkAssignment.org_id == m.org_id,
            ClassSubject.class_id.in_(class_ids),
            HomeworkAssignment.date >= since,
            HomeworkAssignment.date <= until,
        )
        checked = set(self.db.scalars(
            select(HomeworkCheck.assignment_id)
            .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkCheck.assignment_id)
            .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
            .where(*scope)))
        results = {
            (r.assignment_id, r.student_id): r.status
            for r in self.db.scalars(
                select(HomeworkResult)
                .join(HomeworkAssignment, HomeworkAssignment.id == HomeworkResult.assignment_id)
                .join(ClassSubject, ClassSubject.id == HomeworkAssignment.class_subject_id)
                .where(*scope))
        }

        per_student: dict[uuid.UUID, list[tuple[date, str, str]]] = defaultdict(list)
        for hw_id, on, target, cid, subject in rows:
            # A per-student assignment has a roster of one; a class-wide one
            # reaches everyone in the class who is on this page.
            in_class = by_class.get(cid, [])
            targets = ([target] if target in on_page else []) if target is not None else in_class
            for sid in targets:
                status = ("not_checked" if hw_id not in checked
                          else results.get((hw_id, sid), verdicts.DONE))
                per_student[sid].append((on, status, subject))

        for sid, items in per_student.items():
            items.sort(key=lambda x: x[0])
            counts = verdicts.tally([s for _, s, _ in items])
            last_on, last_status, last_subject = items[-1]
            out[sid] = RecordHomework(
                assigned=len(items),
                completion=verdicts.completion(counts),
                not_done=counts["not_done"], late=counts["late"],
                carried=counts["carried"], not_checked=counts["not_checked"],
                streak=verdicts.miss_streak([(d, s) for d, s, _ in items]),
                latest_status=last_status, latest_date=last_on.isoformat(),
                latest_subject=last_subject)
        return out
