"""The teacher's side of the syllabus (V1-6 — `S-46`, `D-10`, `D-15`).

Two screens, one visibility rule each, and the rule is the module:

  * **My subjects** (`S-46`) — one row per class-subject *she* teaches, each
    saying where she is and **what to teach next**. `/plan/*` is open to
    teachers but the screens are admin-shaped: pick a year, pick a class, pick a
    subject, look at one plan. A teacher with six class-subjects picked her way
    to each one, every time, and `?mine=true` — which has existed on the classes
    endpoint all along — was used by no plan screen.

  * **My class's syllabus** (`D-15`, `S-28`) — for a **class teacher**: all
    subjects and all teachers' pace, **but only for her own class.** Never
    school-wide.

`D-15` is a block, not a default: *"a subject teacher sees her own subjects
only."* Claude argued the other way — that a coverage figure is not confidential
between colleagues and that hiding it invites the belief it is being used
against them (`S-52`) — and was **overruled**. The argument is recorded in
`modules/syllabus.md` so it is not re-made; the code implements `D-15`.

The numbers come from exactly the same two places the admin board reads —
`PlannerService.forecast_org` for pace and `CoverageReader` for coverage — so a
teacher and her principal can never be looking at different figures for the same
subject, which was the defect (`S-51`) this packet exists to remove. What differs
between the two screens is **which rows you may see**, never how a row is
computed.
"""

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.coverage import (
    PLANNED,
    SYLLABUS,
    UNKNOWN,
    attribute_cause,
    rated_status,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models import (
    AcademicYear,
    ClassSubject,
    Membership,
    SchoolClass,
    Subject,
    User,
)
from app.schemas.my_syllabus import ClassSyllabusOut, MySubjectsOut, SubjectPaceRow
from app.services.coverage import CoverageReader
from app.services.planner import PlannerService
from app.services.school_clock import today_in


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


def _plural(n: float, word: str) -> str:
    return word if n == 1 else word + "s"


class MySyllabusService:
    def __init__(self, db: Session):
        self.db = db

    # ── S-46: her own subjects ───────────────────────────────────────────────
    def my_subjects(self, m: CurrentMember,
                    year_id: uuid.UUID | None = None) -> MySubjectsOut:
        """Every class-subject this member teaches. No other rows exist here.

        Scoped on `teacher_member_id` rather than filtered after the fact, so
        there is no query shape in which another teacher's subject could arrive
        and be dropped by the caller — `D-15` is enforced where the rows are
        chosen (law 1's spirit: the identity comes from the token, and the scope
        rides with it).
        """
        today = today_in(m.org.timezone)
        year = self._year(m, year_id)
        out = MySubjectsOut(academic_year_id=year.id if year else None, as_of=today,
                            headline="No academic year is set up yet.")
        if year is None:
            return out

        rows = self.db.execute(
            select(ClassSubject.id, ClassSubject.class_id, ClassSubject.subject_id,
                   SchoolClass.name, SchoolClass.section, Subject.name)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == m.org_id,
                   SchoolClass.academic_year_id == year.id,
                   ClassSubject.teacher_member_id == m.membership.id)
            .order_by(SchoolClass.name, SchoolClass.section, Subject.name)).all()
        out.rows = self._pace_rows(m, year, rows, today)
        out.headline = self._my_headline(out.rows)
        return out

    # ── D-15: her class, every subject ───────────────────────────────────────
    def class_syllabus(self, m: CurrentMember, class_id: uuid.UUID) -> ClassSyllabusOut:
        """All subjects for one class — the class teacher's block (`S-28`).

        Names the subject teacher beside each row, because she cannot act on it
        otherwise and she is staff (`Q-20` → `D-15`). It carries the same
        honesty guard as the admin board — the numbers beside the name, framed
        as *needs support*, **never a rank** — and no pace figure from here ever
        reaches a parent (`D-11`).
        """
        klass = self.db.scalar(
            select(SchoolClass).where(SchoolClass.id == class_id,
                                      SchoolClass.org_id == m.org_id))
        if klass is None:
            raise NotFoundError("Class")
        if not m.is_admin and klass.class_teacher_member_id != m.membership.id:
            # Same words and same code as MyClassService — a second phrasing of
            # one rule is how a guard drifts into a leak.
            raise ForbiddenError("This is not your class.", code="not_your_class")

        today = today_in(m.org.timezone)
        year = self.db.get(AcademicYear, klass.academic_year_id)
        rows = self.db.execute(
            select(ClassSubject.id, ClassSubject.class_id, ClassSubject.subject_id,
                   SchoolClass.name, SchoolClass.section, Subject.name,
                   ClassSubject.teacher_member_id)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == m.org_id, ClassSubject.class_id == class_id)
            .order_by(Subject.name)).all()

        teacher_ids = {r[6] for r in rows if r[6]}
        teachers = {
            mid: name for mid, name in self.db.execute(
                select(Membership.id, User.name).join(User, User.id == Membership.user_id)
                .where(Membership.id.in_(teacher_ids))).all()
        } if teacher_ids else {}

        pace = self._pace_rows(m, year, [r[:6] for r in rows], today, with_cause=True)
        by_id = {r.class_subject_id: r for r in pace}
        for r in rows:
            row = by_id.get(r[0])
            if row is not None:
                row.teacher_name = teachers.get(r[6])
        return ClassSyllabusOut(
            class_id=class_id, class_label=_label(klass.name, klass.section),
            as_of=today, headline=self._class_headline(pace), rows=pace)

    # ── shared ───────────────────────────────────────────────────────────────
    def _year(self, m: CurrentMember, year_id: uuid.UUID | None) -> AcademicYear | None:
        if year_id is not None:
            return self.db.scalar(select(AcademicYear).where(
                AcademicYear.id == year_id, AcademicYear.org_id == m.org_id))
        return self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))

    def _pace_rows(self, m: CurrentMember, year: AcademicYear | None, meta: list,
                   today: date, *, with_cause: bool = False) -> list[SubjectPaceRow]:
        """Build the rows from the same two reads the admin board uses.

        `forecast_org` covers the whole year and is filtered down here rather
        than re-queried per subject: it is one batched pass either way, and a
        second narrower query would be a second definition of pace waiting to
        drift from the first.
        """
        if not meta or year is None:
            return []
        wanted = {r[0] for r in meta}
        forecasts = {f.class_subject_id: f
                     for f in PlannerService(self.db).forecast_org(m, year.id)
                     if f.class_subject_id in wanted}
        cov = CoverageReader(self.db).rows(m.org_id, list(wanted), year, today=today)

        out: list[SubjectPaceRow] = []
        for cs_id, class_id, subject_id, cname, section, sname in meta:
            f = forecasts.get(cs_id)
            c = cov.get(cs_id)
            status = rated_status(f.status, bool(c and c.has_evidence)) if f else "none"
            row = SubjectPaceRow(
                class_subject_id=cs_id, class_id=class_id, class_label=_label(cname, section),
                subject_id=subject_id, subject_name=sname, status=status,
                taught_topics=c.taught_weighted if c else 0.0,
                planned_topics=c.planned_topics if c else 0,
                total_topics=c.total_topics if c else 0,
                coverage_pct=c.figure(PLANNED).pct if c else None,
                syllabus_pct=c.figure(SYLLABUS).pct if c else None,
                due_topics=c.due_topics if c else 0,
                behind_topics=c.behind_topics if c else 0.0,
                weeks_behind=(f.weeks_behind or 0) if f else 0,
                unestimated_topics=(f.unestimated_topics or 0) if f else 0,
                logged_periods=(f.logged_periods or 0) if f else 0,
                next_topic_title=c.next_topic_title if c else None,
                next_chapter_title=c.next_chapter_title if c else None,
                last_taught_on=c.last_taught_on if c else None)
            if with_cause:
                # The same attribution the admin board runs, so the class
                # teacher and the principal give a teacher the same reason on
                # the same day (`S-41`). `periods_not_held` is deliberately not
                # passed: this view does not read `class_periods`, and claiming
                # "periods were lost" without having counted them would be worse
                # than leaving the cause at "slower".
                row.cause, row.cause_detail = attribute_cause(
                    status=row.status, behind_topics=row.behind_topics,
                    weeks_behind=row.weeks_behind,
                    unestimated_topics=row.unestimated_topics,
                    planned_topics=row.planned_topics)
            out.append(row)
        return out

    def _my_headline(self, rows: list[SubjectPaceRow]) -> str:
        if not rows:
            return "You are not assigned to any class-subject yet."
        behind = [r for r in rows if r.status in ("amber", "red")]
        nxt = next((r for r in rows if r.next_topic_title), None)
        if behind:
            worst = max(behind, key=lambda r: r.weeks_behind)
            return (f"{len(behind)} of your {len(rows)} "
                    f"{_plural(len(rows), 'subject')} need catching up — "
                    f"{worst.class_label} {worst.subject_name} most of all.")
        if nxt is not None:
            return (f"All {len(rows)} of your {_plural(len(rows), 'subject')} are on "
                    f"track. Next up in {nxt.class_label} {nxt.subject_name}: "
                    f"{nxt.next_topic_title}.")
        return f"All {len(rows)} of your {_plural(len(rows), 'subject')} are on track."

    def _class_headline(self, rows: list[SubjectPaceRow]) -> str:
        if not rows:
            return "This class has no subjects set up yet."
        behind = [r for r in rows if r.status in ("amber", "red")]
        unknown = [r for r in rows if r.status == UNKNOWN]
        if behind:
            names = ", ".join(sorted(r.subject_name for r in behind)[:3])
            return (f"{len(behind)} of {len(rows)} subjects "
                    f"{'is' if len(behind) == 1 else 'are'} behind: {names}.")
        if unknown:
            return (f"{len(unknown)} of {len(rows)} subjects "
                    f"{'has' if len(unknown) == 1 else 'have'} nothing logged yet, "
                    "so their pace is unknown.")
        return f"All {len(rows)} subjects are on track."
