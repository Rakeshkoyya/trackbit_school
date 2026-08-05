"""The support owner's two screens, rebuilt (founder 2026-08-05).

The ABC bands area gave her a list of children and a weekly check-in. What it
could not do was record **the check itself** — she gave work, she wrote a note
about the week, and whether any of it moved him was answered from memory. This
service is the missing half:

    my_students     her assigned children, per class, as a table — and a
                    sentence when she has none, rather than an empty screen
    assessments     every check she has set, newest first, PAGINATED, because a
                    year of small weekly checks is hundreds of rows
    sheet / record  the roster with one input each, in the metric she chose

**Assigned only, and blocked rather than filtered.** Ownership is per subject
(`D-77`), so the unit here is the intervention and not the child: a boy who is C
in Hindi and C in Maths is two rows on two teachers' lists, and collapsing him
to one would quietly reinstate the overall letter `D-75` retired.

**Not `assessment_cycles`, and the separation is load-bearing** — see
`core/band_assessment.py`. Nothing this service writes reaches a child's
standing, his report card, or his band.

Two rules carried in from the modules this borrows its shape from:

* **Not evaluated is a word.** An assessment nobody has marked is `pending`, a
  child with no row is not a zero, and no average is ever taken over a roster
  rather than over the children actually evaluated (HW-1's rule, which is the
  same rule).
* **No score for the teacher** (`S-170`). There is no completion percentage for
  her checks, no comparison against other owners, and no streak. A support log
  that can cost her an appraisal is a support log that flatters her, and the
  children handed to the best teacher are by construction the hardest ones.
"""

from __future__ import annotations

import math
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.band_assessment import (
    DEFAULT_RATING_MAX,
    MARKS,
    OTHER,
    RATING,
    Tally,
    result_text,
    status_for,
)
from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    BandAssessment,
    BandAssessmentResult,
    BandAssessmentStudent,
    HomeworkAssignment,
    HomeworkCheck,
    Intervention,
    Membership,
    SchoolClass,
    Student,
    StudentNote,
    Subject,
    SupportCheckpoint,
    User,
)
from app.schemas.bands import (
    AssessmentRecordIn,
    AssessmentResultRow,
    BandAssessmentCreate,
    BandAssessmentList,
    BandAssessmentRow,
    BandAssessmentSheet,
    MyStudentRow,
    MyStudentsBoard,
)
from app.services.bands import BandService
from app.services.school_clock import today_in

MAX_PER_PAGE = 100


def _label(k: SchoolClass | None) -> str | None:
    if k is None:
        return None
    return f"{k.name}-{k.section}" if k.section else k.name


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


class BandAssessmentService:
    def __init__(self, db: Session):
        self.db = db

    # ── who is hers ──────────────────────────────────────────────────────────
    def _interventions(self, m: CurrentMember, class_id: uuid.UUID | None = None,
                       owner_member_id: uuid.UUID | None = None,
                       subject_id: uuid.UUID | None = None,
                       active_only: bool = True) -> list[tuple[Intervention, Student]]:
        """Her support plans, joined to the child.

        An admin runs the programme, so with no owner named they see every
        plan — the same asymmetry `BandService.my_scope` already draws. A
        teacher always sees her own and only her own (`S-170`)."""
        owner = owner_member_id
        if owner is None and not m.is_coordinator_up:
            owner = m.membership.id
        q = (select(Intervention, Student)
             .join(Student, Student.id == Intervention.student_id)
             .where(Intervention.org_id == m.org_id))
        if owner is not None:
            q = q.where(Intervention.owner_member_id == owner)
        if active_only:
            q = q.where(Intervention.status == "active")
        if class_id is not None:
            q = q.where(Student.class_id == class_id)
        if subject_id is not None:
            q = q.where(Intervention.subject_id == subject_id)
        return list(self.db.execute(q.order_by(Student.full_name)).all())

    def _class_labels(self, m: CurrentMember) -> dict[uuid.UUID, str]:
        return {k.id: _label(k) for k in self.db.scalars(select(SchoolClass).where(
            SchoolClass.org_id == m.org_id).order_by(SchoolClass.name, SchoolClass.section))}

    def _subject_names(self, m: CurrentMember) -> dict[uuid.UUID, str]:
        return {s.id: s.name for s in self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id))}

    # ── My students (founder 2026-08-05) ─────────────────────────────────────
    def my_students(self, m: CurrentMember,
                    class_id: uuid.UUID | None = None) -> MyStudentsBoard:
        """The table, and the empty state that matters more than the table.

        A teacher with nobody assigned must be told **that**, not shown a blank
        grid she reads as a broken screen. And the class picker is built from
        the classes she actually has children in — a dropdown of twelve classes
        where eleven are empty is a dropdown nobody uses."""
        today = today_in(m.org.timezone)
        week = _monday(today)
        labels = self._class_labels(m)
        subjects = self._subject_names(m)

        every = self._interventions(m, active_only=False)
        active = [(iv, st) for iv, st in every if iv.status == "active"]
        # The picker's vocabulary comes from the UNFILTERED set, so choosing a
        # class can never remove the option that would get you back.
        present: dict[uuid.UUID, int] = defaultdict(int)
        for _, st in active:
            if st.class_id:
                present[st.class_id] += 1
        classes = [{"id": str(cid), "label": labels.get(cid, "?"), "count": n}
                   for cid, n in sorted(present.items(),
                                        key=lambda kv: labels.get(kv[0], ""))]

        rows_src = [(iv, st) for iv, st in active
                    if class_id is None or st.class_id == class_id]
        moved_src = [(iv, st) for iv, st in every if iv.status != "active"
                     and (class_id is None or st.class_id == class_id)]

        out = MyStudentsBoard(as_of=today, week_start=week, class_id=class_id,
                              classes=classes, total=len(active))
        if not every:
            out.headline = ("No students are assigned to you yet. The admin assigns "
                            "them once a class has been banded.")
            return out

        iv_ids = [iv.id for iv, _ in rows_src + moved_src]
        st_ids = [st.id for _, st in rows_src + moved_src]
        checkpoints = self._checkpoint_map(m, iv_ids)
        placements = BandService(self.db).placements(m, st_ids)
        open_hw = self._open_assignments(m, st_ids)
        note_counts = self._note_counts(m, st_ids)

        def build(iv: Intervention, st: Student) -> MyStudentRow:
            cps = checkpoints.get(iv.id, [])
            last = cps[0] if cps else None
            place = next((p for p in placements.get(st.id, [])
                          if p.subject_id == iv.subject_id), None)
            return MyStudentRow(
                intervention_id=iv.id, student_id=st.id, full_name=st.full_name,
                roll_no=st.roll_no, class_id=st.class_id,
                class_label=labels.get(st.class_id) if st.class_id else None,
                subject_id=iv.subject_id,
                subject_name=subjects.get(iv.subject_id) if iv.subject_id else None,
                tier=place.tier if place else None,
                # `S-166`: the letter never renders without its sentence.
                descriptor=place.descriptor if place else None,
                since=iv.created_at.date() if iv.created_at else None,
                checkins=len(cps),
                last_checkin=last.week_start if last else None,
                weeks_since_checkin=((week - last.week_start).days // 7) if last else None,
                checked_in_this_week=bool(last and last.week_start == week),
                ready_to_retest=bool(last and last.ready_to_retest),
                open_assignments=open_hw.get(st.id, 0),
                notes=note_counts.get(st.id, 0),
                status=iv.status)

        out.rows = [build(iv, st) for iv, st in rows_src]
        out.moved_on = [build(iv, st) for iv, st in moved_src]

        if not out.rows and class_id is not None:
            # A filter that empties the table says so — it is not the same
            # sentence as having no children at all.
            out.headline = (f"Nobody assigned to you in {labels.get(class_id, 'that class')}. "
                            f"You have {len(active)} across the school.")
        elif not out.rows:
            out.headline = ("Everyone you were supporting has moved on. "
                            "Nothing open right now.")
        else:
            done = sum(1 for r in out.rows if r.checked_in_this_week)
            n = len(out.rows)
            out.headline = (f"{n} child{'' if n == 1 else 'ren'} assigned to you"
                            + (f" in {labels.get(class_id, '')}" if class_id else "")
                            + f" · {done} checked in this week.")
            overdue = [r for r in out.rows if (r.weeks_since_checkin or 99) >= 3]
            if overdue:
                worst = min(overdue, key=lambda r: r.last_checkin or date.min)
                out.headline += (f" {worst.full_name} hasn't been checked in "
                                 f"{worst.weeks_since_checkin} weeks.")
        return out

    def _checkpoint_map(self, m: CurrentMember, iv_ids: list[uuid.UUID],
                        ) -> dict[uuid.UUID, list[SupportCheckpoint]]:
        if not iv_ids:
            return {}
        out: dict[uuid.UUID, list[SupportCheckpoint]] = defaultdict(list)
        for cp in self.db.scalars(select(SupportCheckpoint).where(
                SupportCheckpoint.org_id == m.org_id,
                SupportCheckpoint.intervention_id.in_(iv_ids))
                .order_by(SupportCheckpoint.week_start.desc())):
            out[cp.intervention_id].append(cp)
        return out

    def _open_assignments(self, m: CurrentMember,
                          student_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Per-student homework nobody has checked yet — **the teacher's gap,
        counted as the teacher's gap** (HW-1's load-bearing rule).

        It is never rendered as the child having failed to do it. One query."""
        if not student_ids:
            return {}
        rows = self.db.execute(
            select(HomeworkAssignment.student_id, func.count())
            .outerjoin(HomeworkCheck, HomeworkCheck.assignment_id == HomeworkAssignment.id)
            .where(HomeworkAssignment.org_id == m.org_id,
                   HomeworkAssignment.student_id.in_(student_ids),
                   HomeworkCheck.id.is_(None))
            .group_by(HomeworkAssignment.student_id)).all()
        return {sid: int(n) for sid, n in rows}

    def _note_counts(self, m: CurrentMember,
                     student_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not student_ids:
            return {}
        return {sid: int(n) for sid, n in self.db.execute(
            select(StudentNote.student_id, func.count())
            .where(StudentNote.org_id == m.org_id,
                   StudentNote.student_id.in_(student_ids))
            .group_by(StudentNote.student_id)).all()}

    # ── the assessments feed (founder 2026-08-05) ────────────────────────────
    def list(self, m: CurrentMember, class_id: uuid.UUID | None = None,
             status: str | None = None, page: int = 1,
             per_page: int = 20) -> BandAssessmentList:
        """Everything she has set, newest first, grouped by class in the
        rendering and **paginated** — a year of weekly checks is hundreds of
        rows and a screen that loads all of them stops being opened.

        A teacher sees her own; an admin sees the school's. Not other owners'
        (`S-170`) — a list of another teacher's checks is a list nobody can act
        on and an invitation to compare."""
        per_page = max(1, min(per_page, MAX_PER_PAGE))
        page = max(1, page)
        labels = self._class_labels(m)
        subjects = self._subject_names(m)

        q = select(BandAssessment).where(BandAssessment.org_id == m.org_id)
        if not m.is_coordinator_up:
            q = q.where(BandAssessment.created_by_member_id == m.membership.id)
        scoped = q
        if class_id is not None:
            q = q.where(BandAssessment.class_id == class_id)

        rows = list(self.db.scalars(q.order_by(
            BandAssessment.class_id, BandAssessment.given_on.desc(),
            BandAssessment.created_at.desc())))

        # The picker is built from the UNFILTERED set, so choosing a class can
        # never hide the option that gets you back.
        all_rows = rows if class_id is None else list(self.db.scalars(scoped))
        present: dict[uuid.UUID, int] = defaultdict(int)
        for a in all_rows:
            present[a.class_id] += 1
        classes = [{"id": str(cid), "label": labels.get(cid, "?"), "count": n}
                   for cid, n in sorted(present.items(),
                                        key=lambda kv: labels.get(kv[0], ""))]

        # Status is derived, not stored — so it can never drift from the rows
        # that decide it. Computed over the whole filtered set BEFORE paging,
        # because a status filter that only looked at page one would lie.
        rosters = self._rosters(m, rows)
        results = self._result_counts(m, [a.id for a in rows])
        authors = self._authors(m, rows)
        built = [self._row(a, labels, subjects, rosters.get(a.id, []),
                           results.get(a.id, []), authors) for a in rows]
        out_open = sum(1 for r in built if r.status != "evaluated")
        if status:
            built = [r for r in built if r.status == status]

        total = len(built)
        pages = max(1, math.ceil(total / per_page))
        page = min(page, pages)
        start = (page - 1) * per_page

        out = BandAssessmentList(
            rows=built[start:start + per_page], page=page, per_page=per_page,
            total=total, pages=pages, classes=classes, open_count=out_open)
        if not all_rows:
            out.headline = ("No assessments yet. Set one to record how your children "
                            "do on the work you give them.")
        elif out_open:
            out.headline = (f"{total} assessment{'' if total == 1 else 's'} · "
                            f"{out_open} still to evaluate.")
        else:
            out.headline = (f"{total} assessment{'' if total == 1 else 's'} · "
                            "all evaluated.")
        return out

    def _authors(self, m: CurrentMember,
                 rows: list[BandAssessment]) -> dict[uuid.UUID, str]:
        ids = {a.created_by_member_id for a in rows if a.created_by_member_id}
        if not ids:
            return {}
        return {mid: name for mid, name in self.db.execute(
            select(Membership.id, User.name)
            .join(User, User.id == Membership.user_id)
            .where(Membership.id.in_(ids))).all()}

    def _rosters(self, m: CurrentMember,
                 rows: list[BandAssessment]) -> dict[uuid.UUID, list[uuid.UUID]]:
        """Every assessment's roster, batched — **computed where `covers_all`**.

        Three queries for any number of assessments. The computed half is HS-1's
        rule: a child assigned to her next week is on this assessment without
        anyone remembering to edit it, and a child who has moved on drops off."""
        if not rows:
            return {}
        out: dict[uuid.UUID, list[uuid.UUID]] = {}

        explicit: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        ids = [a.id for a in rows if not a.covers_all]
        if ids:
            for aid, sid in self.db.execute(
                    select(BandAssessmentStudent.assessment_id,
                           BandAssessmentStudent.student_id)
                    .where(BandAssessmentStudent.org_id == m.org_id,
                           BandAssessmentStudent.assessment_id.in_(ids))).all():
                explicit[aid].append(sid)

        computed = [a for a in rows if a.covers_all]
        pool: dict[tuple[uuid.UUID, uuid.UUID | None, uuid.UUID | None],
                   list[uuid.UUID]] = defaultdict(list)
        if computed:
            # One pass over the org's active plans; each assessment then reads
            # its own (owner, class, subject) slice out of it.
            for iv, st in self.db.execute(
                    select(Intervention, Student)
                    .join(Student, Student.id == Intervention.student_id)
                    .where(Intervention.org_id == m.org_id,
                           Intervention.status == "active")).all():
                if st.class_id is None:
                    continue
                pool[(iv.owner_member_id, st.class_id, iv.subject_id)].append(st.id)

        for a in rows:
            if not a.covers_all:
                out[a.id] = explicit.get(a.id, [])
                continue
            owner = a.created_by_member_id
            found: list[uuid.UUID] = []
            for (own, cls, subj), sids in pool.items():
                if cls != a.class_id:
                    continue
                # An assessment written for one subject goes to the children she
                # owns IN that subject; one that crosses subjects goes to all of
                # them. Where the author's account is gone, the class's whole
                # support group is the honest fallback.
                if owner is not None and own != owner:
                    continue
                if a.subject_id is not None and subj != a.subject_id:
                    continue
                found.extend(sids)
            out[a.id] = sorted(set(found), key=str)
        return out

    def _result_counts(self, m: CurrentMember, ids: list[uuid.UUID],
                       ) -> dict[uuid.UUID, list[BandAssessmentResult]]:
        if not ids:
            return {}
        out: dict[uuid.UUID, list[BandAssessmentResult]] = defaultdict(list)
        for r in self.db.scalars(select(BandAssessmentResult).where(
                BandAssessmentResult.org_id == m.org_id,
                BandAssessmentResult.assessment_id.in_(ids))):
            out[r.assessment_id].append(r)
        return out

    @staticmethod
    def _value(a: BandAssessment, r: BandAssessmentResult) -> float | None:
        """The one number this metric carries, or None for *not evaluated*.

        `other` never yields a number — a word is not a quantity, and the tally
        counts it as evaluated without averaging it."""
        if a.metric == MARKS:
            return float(r.marks) if r.marks is not None else None
        if a.metric == RATING:
            return float(r.rating) if r.rating is not None else None
        return None

    def _row(self, a: BandAssessment, labels: dict, subjects: dict,
             roster: list[uuid.UUID], results: list[BandAssessmentResult],
             authors: dict) -> BandAssessmentRow:
        tally = Tally(metric=a.metric, roster=len(roster),
                      max_marks=float(a.max_marks) if a.max_marks is not None else None,
                      rating_max=a.rating_max)
        on_roster = set(roster)
        # Results for children no longer on a computed roster are kept in the
        # table (the record of a real evaluation) but do not inflate a
        # denominator they are no longer part of.
        evaluated_ids = {r.student_id for r in results
                         if r.student_id in on_roster and self._recorded(a, r)}
        for r in results:
            if r.student_id in on_roster:
                tally.add(self._value(a, r))
        # `add` counts the numbers it averaged; `evaluated` is how many children
        # were judged at all. They differ under `other`, where a word is a
        # verdict and not a quantity — so the count is set from the verdicts.
        tally.evaluated = len(evaluated_ids)

        return BandAssessmentRow(
            id=a.id, name=a.name, class_id=a.class_id,
            class_label=labels.get(a.class_id, "?"), subject_id=a.subject_id,
            subject_name=subjects.get(a.subject_id) if a.subject_id else None,
            instructions=a.instructions, description=a.description,
            metric=a.metric,
            max_marks=float(a.max_marks) if a.max_marks is not None else None,
            rating_max=a.rating_max, covers_all=a.covers_all,
            given_on=a.given_on, due_date=a.due_date,
            author_name=authors.get(a.created_by_member_id),
            status=status_for(len(evaluated_ids), len(roster)),
            roster=len(roster), evaluated=len(evaluated_ids),
            not_evaluated=max(0, len(roster) - len(evaluated_ids)),
            average=tally.average, average_pct=tally.average_pct,
            caption=tally.caption())

    @staticmethod
    def _recorded(a: BandAssessment, r: BandAssessmentResult) -> bool:
        """Whether this row is an evaluation at all. A row carrying only a note
        is a remark, not a verdict — and must not count as one."""
        if a.metric == MARKS:
            return r.marks is not None
        if a.metric == RATING:
            return r.rating is not None
        return bool((r.verdict or "").strip())

    # ── create (founder 2026-08-05) ──────────────────────────────────────────
    def create(self, m: CurrentMember, body: BandAssessmentCreate) -> BandAssessmentRow:
        klass = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == body.class_id, SchoolClass.org_id == m.org_id))
        if klass is None:
            raise NotFoundError("Class")
        if body.subject_id is not None and not self.db.scalar(select(Subject.id).where(
                Subject.id == body.subject_id, Subject.org_id == m.org_id)):
            raise NotFoundError("Subject")

        mine = {st.id for _, st in self._interventions(
            m, class_id=body.class_id, subject_id=body.subject_id)}
        if not m.is_coordinator_up and not mine:
            # Blocked with a sentence, never an empty form she fills in and then
            # cannot save (`S-46`).
            raise ForbiddenError(
                "You have no support students in that class, so there is nobody "
                "to assess.", code="no_students_assigned")

        chosen: list[uuid.UUID] = []
        if not body.covers_all:
            if not body.student_ids:
                raise ValidationError("Pick at least one student, or set it for everyone.",
                                      code="no_students_picked")
            roster = mine if not m.is_coordinator_up else {
                st.id for _, st in self._interventions(m, class_id=body.class_id)}
            for sid in body.student_ids:
                if roster and sid not in roster:
                    raise ValidationError(
                        "One of those students is not assigned to you in this class.",
                        code="not_your_student")
                chosen.append(sid)

        metric = body.metric
        max_marks = body.max_marks if metric == MARKS else None
        if metric == MARKS and max_marks is None:
            raise ValidationError("Marks need a total to be out of.", code="no_total")
        rating_max = (body.rating_max or DEFAULT_RATING_MAX) if metric == RATING else None

        term = BandService(self.db).current_term(m, None)
        a = BandAssessment(
            org_id=m.org_id, class_id=body.class_id, subject_id=body.subject_id,
            term_id=term.id if term else None,
            name=body.name.strip(),
            instructions=(body.instructions or "").strip() or None,
            description=(body.description or "").strip() or None,
            metric=metric, max_marks=max_marks, rating_max=rating_max,
            covers_all=body.covers_all,
            given_on=body.given_on or today_in(m.org.timezone),
            due_date=body.due_date, created_by_member_id=m.membership.id)
        self.db.add(a)
        self.db.flush()
        for sid in dict.fromkeys(chosen):
            self.db.add(BandAssessmentStudent(
                org_id=m.org_id, assessment_id=a.id, student_id=sid))
        self.db.flush()

        labels, subjects = self._class_labels(m), self._subject_names(m)
        roster = self._rosters(m, [a]).get(a.id, [])
        return self._row(a, labels, subjects, roster, [], self._authors(m, [a]))

    # ── the evaluation sheet (founder 2026-08-05) ────────────────────────────
    def _assessment(self, m: CurrentMember, assessment_id: uuid.UUID) -> BandAssessment:
        a = self.db.scalar(select(BandAssessment).where(
            BandAssessment.id == assessment_id, BandAssessment.org_id == m.org_id))
        if a is None:
            raise NotFoundError("Assessment")
        if not m.is_coordinator_up and a.created_by_member_id != m.membership.id:
            raise ForbiddenError("That is another teacher's assessment.",
                                 code="not_your_assessment")
        return a

    def sheet(self, m: CurrentMember, assessment_id: uuid.UUID) -> BandAssessmentSheet:
        """The roster with one input each, in the metric she chose.

        Deliberately not capture-by-exception: P1v2's budget is about *daily*
        capture across a whole class, and this is six children where the number
        for each one is the entire point — the same reasoning that lets
        `file_bands` touch every row of a class."""
        a = self._assessment(m, assessment_id)
        labels, subjects = self._class_labels(m), self._subject_names(m)
        roster = self._rosters(m, [a]).get(a.id, [])
        results = {r.student_id: r for r in self._result_counts(m, [a.id]).get(a.id, [])}
        row = self._row(a, labels, subjects, roster, list(results.values()),
                        self._authors(m, [a]))

        students = {s.id: s for s in self.db.scalars(select(Student).where(
            Student.org_id == m.org_id, Student.id.in_(roster)))} if roster else {}
        placements = BandService(self.db).placements(m, roster)
        notes = self._note_counts(m, roster)

        out = BandAssessmentSheet(assessment=row, can_record=True)
        for sid in roster:
            st = students.get(sid)
            if st is None:
                continue
            r = results.get(sid)
            place = next((p for p in placements.get(sid, [])
                          if a.subject_id is None or p.subject_id == a.subject_id), None)
            out.rows.append(AssessmentResultRow(
                student_id=sid, full_name=st.full_name, roll_no=st.roll_no,
                class_label=labels.get(st.class_id) if st.class_id else None,
                tier=place.tier if place else None,
                marks=float(r.marks) if r and r.marks is not None else None,
                rating=r.rating if r else None,
                verdict=r.verdict if r else None,
                note=r.note if r else None,
                result_text=result_text(
                    a.metric,
                    marks=float(r.marks) if r and r.marks is not None else None,
                    rating=r.rating if r else None,
                    verdict=r.verdict if r else None,
                    max_marks=float(a.max_marks) if a.max_marks is not None else None,
                    rating_max=a.rating_max) if r else None,
                evaluated=bool(r and self._recorded(a, r)),
                notes=notes.get(sid, 0)))
        out.rows.sort(key=lambda r: r.full_name)
        return out

    def record(self, m: CurrentMember, assessment_id: uuid.UUID,
               body: AssessmentRecordIn) -> BandAssessmentSheet:
        """**Full replace**, like `check_homework` and `mark`.

        Results are capture, and law 3's append-only governs *decisions* — a
        band, an approval, a fee conversation. A mistyped 7 for 17 is corrected
        in place, exactly the way a mis-tapped absence is; a row left out of the
        payload is cleared back to *not evaluated*, which is a legitimate answer
        and not a zero."""
        a = self._assessment(m, assessment_id)
        roster = set(self._rosters(m, [a]).get(a.id, []))
        now = datetime.now(UTC)

        existing = {r.student_id: r for r in self.db.scalars(
            select(BandAssessmentResult).where(
                BandAssessmentResult.org_id == m.org_id,
                BandAssessmentResult.assessment_id == a.id))}
        keep: set[uuid.UUID] = set()

        for row in body.results:
            if row.student_id not in roster:
                raise ValidationError("A row points at a student outside this assessment.",
                                      code="not_on_assessment")
            marks = row.marks if a.metric == MARKS else None
            rating = row.rating if a.metric == RATING else None
            verdict = ((row.verdict or "").strip() or None) if a.metric == OTHER else None
            note = (row.note or "").strip() or None
            if marks is None and rating is None and verdict is None and note is None:
                continue      # nothing said about this child — leave him unevaluated
            if marks is not None and a.max_marks is not None and marks > float(a.max_marks):
                raise ValidationError(
                    f"{marks:g} is more than the {float(a.max_marks):g} this is out of.",
                    code="over_total")
            if rating is not None and rating > (a.rating_max or DEFAULT_RATING_MAX):
                raise ValidationError(
                    f"The rating only goes up to {a.rating_max or DEFAULT_RATING_MAX}.",
                    code="over_rating")

            keep.add(row.student_id)
            r = existing.get(row.student_id)
            if r is None:
                r = BandAssessmentResult(
                    org_id=m.org_id, assessment_id=a.id, student_id=row.student_id)
                self.db.add(r)
            r.marks, r.rating, r.verdict, r.note = marks, rating, verdict, note
            r.recorded_by_member_id = m.membership.id
            r.recorded_at = now

        for sid, r in existing.items():
            # Full replace: a child omitted from the payload goes back to not
            # evaluated. Only ever within the roster this save covered, so an
            # admin opening a teacher's sheet cannot silently wipe a child who
            # has since moved off the computed roster.
            if sid not in keep and sid in roster:
                self.db.delete(r)
        self.db.flush()
        return self.sheet(m, a.id)

    def delete(self, m: CurrentMember, assessment_id: uuid.UUID) -> None:
        """Only while nothing has been recorded against it.

        Once a child's result is on it, the assessment is part of his record and
        removing it would take a real evaluation with it — the same reason a
        locked exam cannot be re-typed (`D-53`)."""
        a = self._assessment(m, assessment_id)
        if self.db.scalar(select(func.count()).select_from(BandAssessmentResult).where(
                BandAssessmentResult.org_id == m.org_id,
                BandAssessmentResult.assessment_id == a.id)):
            raise ValidationError(
                "Results have been recorded on this — it is part of those children's "
                "record now.", code="has_results")
        self.db.delete(a)
        self.db.flush()
