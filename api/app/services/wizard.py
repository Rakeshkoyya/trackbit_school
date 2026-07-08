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
    ClassSubject,
    Membership,
    OnboardingState,
    Plan,
    SchoolClass,
    Student,
    Subject,
    SyllabusTopic,
    Term,
    TimetableSlot,
)
from app.schemas.wizard import WizardAdvanceIn, WizardProgress, WizardStateOut


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
        return WizardProgress(
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
            timetable_slots=self._count(
                TimetableSlot, TimetableSlot.org_id == org, TimetableSlot.effective_to.is_(None)),
            plans_total=plans_total,
            plans_approved=plans_approved)

    def _out(self, st: OnboardingState, m: CurrentMember) -> WizardStateOut:
        return WizardStateOut(
            current_step=st.current_step, status=st.status, payload=st.payload or {},
            progress=self._progress(m))

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
