"""Setup wizard (V2-M1, SPRD2 §5.1) — a resumable orchestrator, not a store.

The wizard's 9 steps write through to the real tables via the existing module
endpoints (year, terms, timings, classes/subjects, syllabus, teachers, students,
timetable, plan). This service only tracks *where the admin is* (`current_step`,
resumable across logout) and derives *what's done* by counting the real data — so
it never drifts from the truth. `payload` keeps small per-step answers/ids that make
resuming the forms convenient.
"""


from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.models import (
    AcademicYear,
    CalendarEvent,
    ClassSubject,
    ExamPortion,
    Membership,
    OnboardingState,
    Plan,
    SchoolClass,
    Student,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    Term,
    TimetableSlot,
)
from app.schemas.wizard import (
    STEPS,
    WizardAdvanceIn,
    WizardProgress,
    WizardStateOut,
    WizardStepOut,
)


class WizardService:
    def __init__(self, db: Session):
        self.db = db

    def _state(self, m: CurrentMember) -> OnboardingState:
        st = self.db.scalar(
            select(OnboardingState).where(OnboardingState.org_id == m.org_id))
        if st is None:
            st = OnboardingState(org_id=m.org_id, current_step=1, payload={}, status="in_progress")
            self.db.add(st)
            self.db.flush()
        return st

    def _count(self, model, *where) -> int:
        return self.db.scalar(
            select(func.count()).select_from(model).where(*where)) or 0

    def _progress(self, m: CurrentMember) -> WizardProgress:
        org = m.org_id
        years = list(self.db.scalars(select(AcademicYear).where(AcademicYear.org_id == org)))
        has_timings = any((y.period_times or []) for y in years)
        cs_ids = [c for c in self.db.scalars(
            select(ClassSubject.id).where(ClassSubject.org_id == org))]
        syllabus_topics = self.db.scalar(
            select(func.count(SyllabusTopic.id)).where(SyllabusTopic.org_id == org)) or 0
        plans_total = len(cs_ids)
        plans_approved = self.db.scalar(select(func.count(Plan.id)).where(
            Plan.org_id == org, Plan.status == "approved")) or 0
        exams = self._count(
            CalendarEvent, CalendarEvent.org_id == org, CalendarEvent.type == "exam_block")
        timetable_slots = self._count(
            TimetableSlot, TimetableSlot.org_id == org, TimetableSlot.effective_to.is_(None))
        return WizardProgress(
            calendar_events=self._count(CalendarEvent, CalendarEvent.org_id == org),
            exams=exams,
            exam_portions=self._count(ExamPortion, ExamPortion.org_id == org),
            has_year=bool(years),
            terms=self._count(Term, Term.org_id == org),
            has_timings=has_timings,
            classes=self._count(SchoolClass, SchoolClass.org_id == org),
            subjects=self._count(Subject, Subject.org_id == org),
            class_subjects=len(cs_ids),
            syllabus_topics=syllabus_topics,
            teachers=self._count(
                Membership, Membership.org_id == org, Membership.org_role == "teacher"),
            students=self._count(Student, Student.org_id == org),
            timetable_slots=timetable_slots,
            plans_total=plans_total,
            plans_approved=plans_approved,
            gaps=self._gaps(org, cs_ids, timetable_slots))

    def _gaps(self, org, cs_ids: list, timetable_slots: int) -> list[str]:
        """Capture gaps that make a generated plan wrong (V2-P12). Informational —
        the wizard shows them on the generate step; it does not hard-block, because
        a term-wise school legitimately finishes with later terms unsized."""
        if not cs_ids:
            return []
        gaps: list[str] = []

        rows = self.db.execute(
            select(ClassSubject.id, SchoolClass.name, SchoolClass.section, Subject.name,
                   ClassSubject.periods_per_week)
            .join(SchoolClass, SchoolClass.id == ClassSubject.class_id)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == org)
        ).all()
        with_topics = set(self.db.scalars(
            select(SyllabusUnit.class_subject_id)
            .join(SyllabusTopic, SyllabusTopic.unit_id == SyllabusUnit.id)
            .where(SyllabusUnit.org_id == org).distinct()))

        def label(cname, section):
            return cname + (f"-{section}" if section else "")

        no_syllabus = sorted({label(c, s) for cs_id, c, s, _subj, _ppw in rows
                              if cs_id not in with_topics})
        # Only flag a class when NONE of the wizard's syllabus landed on it — the
        # 6-B case, where an import quietly skipped a whole class.
        fully_missing = [
            lbl for lbl in no_syllabus
            if all(cs_id not in with_topics
                   for cs_id, c, s, _subj, _ppw in rows if label(c, s) == lbl)
        ]
        for lbl in fully_missing[:5]:
            gaps.append(f"Class {lbl} has no syllabus at all — its plan cannot be generated.")

        zero_ppw = [(label(c, s), subj) for _id, c, s, subj, ppw in rows if not ppw]
        if zero_ppw:
            sample = ", ".join(f"{lbl} {subj}" for lbl, subj in zero_ppw[:3])
            more = f" (+{len(zero_ppw) - 3} more)" if len(zero_ppw) > 3 else ""
            gaps.append(
                f"{len(zero_ppw)} subject(s) have 0 periods/week — {sample}{more}. "
                f"Set the class allocation or the plan has no pace.")

        if timetable_slots == 0:
            gaps.append("The timetable is empty — teachers will see no periods on My Day.")
        return gaps

    def _complete(self, key: str, p: WizardProgress) -> bool:
        """Whether a step's real data exists. Derived, never stored — an admin who
        deletes every class must see the Classes step go incomplete again."""
        return {
            "year": p.has_year,
            "timings": p.has_timings,
            "classes": p.classes > 0,
            "subjects": p.subjects > 0,
            # The step covers teachers AND what each one teaches, so both must land.
            "staff": p.teachers > 0 and p.class_subjects > 0,
            "syllabus": p.syllabus_topics > 0,
            # Exams are optional for a school that doesn't run them; any calendar
            # entry counts as having visited the step.
            "calendar": p.calendar_events > 0,
            "students": p.students > 0,
            "timetable": p.timetable_slots > 0,
            "generate": p.plans_total > 0 and p.plans_approved == p.plans_total,
        }.get(key, False)

    def _out(self, st: OnboardingState, m: CurrentMember) -> WizardStateOut:
        progress = self._progress(m)
        return WizardStateOut(
            current_step=st.current_step, status=st.status, payload=st.payload or {},
            progress=progress,
            steps=[
                WizardStepOut(key=key, title=title, index=i + 1,
                              complete=self._complete(key, progress))
                for i, (key, title) in enumerate(STEPS)
            ])

    def state(self, m: CurrentMember) -> WizardStateOut:
        return self._out(self._state(m), m)

    def advance(self, m: CurrentMember, body: WizardAdvanceIn) -> WizardStateOut:
        st = self._state(m)
        st.current_step = body.to_step
        if body.payload:
            st.payload = {**(st.payload or {}), **body.payload}
        if st.status == "done":  # re-entering a finished wizard reopens it
            st.status = "in_progress"
        self.db.flush()
        return self._out(st, m)

    def complete(self, m: CurrentMember) -> WizardStateOut:
        st = self._state(m)
        st.status = "done"
        self.db.flush()
        return self._out(st, m)

    def reset(self, m: CurrentMember) -> WizardStateOut:
        st = self._state(m)
        st.current_step = 1
        st.status = "in_progress"
        self.db.flush()
        return self._out(st, m)
