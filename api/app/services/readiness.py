"""The readiness report (V1-2, plan §6 ⑤) — the page the operator reads before
handing a school its password.

Eleven checks, each a rendering of data the modules already own. Two rules:

  * every warning names its CONSEQUENCE ("45 parents cannot log in"), never the
    missing field ("45 nulls"), and links to the screen that clears it;
  * a school handing over with only one term planned is READY — per-term
    partial plans count, `unplanned` future terms are a state, not a warning
    (the mid-year guarantee, plan §5).

Runs under require_super_admin (RLS lifted — cross-org reads are the job here);
every query still filters org_id explicitly (law 1 discipline).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import (
    AcademicYear,
    ClassSubject,
    FeeStructure,
    Membership,
    Organization,
    Plan,
    SchoolClass,
    Student,
    StudentFee,
    Subject,
    SyllabusTopic,
    SyllabusUnit,
    Term,
    TimetableSlot,
)
from app.schemas.platform import ReadinessCheck, ReadinessOut


class ReadinessService:
    def __init__(self, db: Session):
        self.db = db

    def _org(self, org_id: uuid.UUID) -> Organization:
        org = self.db.get(Organization, org_id)
        if org is None:
            raise NotFoundError("Organization")
        return org

    def _count(self, model, *where) -> int:
        return int(self.db.scalar(
            select(func.count()).select_from(model).where(*where)) or 0)

    def report(self, org_id: uuid.UUID) -> ReadinessOut:
        org = self._org(org_id)
        checks = [
            self._year(org_id), self._classes(org_id), self._teachers(org_id),
            self._timetable(org_id), self._students(org_id), self._dob(org_id),
            self._syllabus(org_id), self._plans(org_id),
            self._class_teachers(org_id), self._fees(org_id),
            self._portal(org),
        ]
        return ReadinessOut(
            org_id=org.id, org_name=org.name, school_code=org.school_code,
            ready_count=sum(1 for c in checks if c.status == "ok"),
            total=len(checks), handed_over_at=org.handed_over_at, checks=checks)

    def mark_handed_over(self, org_id: uuid.UUID) -> ReadinessOut:
        org = self._org(org_id)
        if org.handed_over_at is None:
            org.handed_over_at = datetime.now(UTC)
            self.db.flush()
        return self.report(org_id)

    # ── the eleven lines ─────────────────────────────────────────────────────
    def _year(self, org_id) -> ReadinessCheck:
        year = self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True)))
        if year is None:
            return ReadinessCheck(
                key="year", title="Academic year and terms", status="warn",
                summary="No active academic year — nothing else can be set up.",
                link="/setup")
        terms = self._count(Term, Term.org_id == org_id,
                            Term.academic_year_id == year.id)
        bits = [year.label, f"{terms} term{'s' if terms != 1 else ''}"]
        if year.tracking_start_date:
            bits.append(f"tracking from {year.tracking_start_date:%d %b}")
        timings = bool(year.period_times)
        return ReadinessCheck(
            key="year", title="Academic year and terms",
            status="ok" if timings else "warn",
            summary=" · ".join(bits) + ("" if timings
                                        else " — school timings not set"),
            link="/setup")

    def _classes(self, org_id) -> ReadinessCheck:
        classes = self._count(SchoolClass, SchoolClass.org_id == org_id)
        subjects = self._count(Subject, Subject.org_id == org_id)
        cs_total = self._count(ClassSubject, ClassSubject.org_id == org_id)
        # TT-3: this check used to warn until every allocation had a
        # periods/week, which is no longer something a human fills in — it is
        # counted off the timetable. Warning about it here would nag a school
        # about a number it cannot enter and we have not derived yet; the
        # timetable check is the one that says "no grid".
        ok = classes > 0 and cs_total > 0
        summary = (f"{classes} classes · {subjects} subjects · "
                   f"{cs_total} teaching allocation{'' if cs_total == 1 else 's'}")
        if classes == 0:
            summary = "No classes created."
        elif cs_total == 0:
            summary = f"{classes} classes · nobody is assigned to teach anything yet."
        return ReadinessCheck(
            key="classes", title="Classes and subjects",
            status="ok" if ok else "warn", summary=summary,
            count=cs_total, total=cs_total, link="/setup")

    def _teachers(self, org_id) -> ReadinessCheck:
        staff = self._count(Membership, Membership.org_id == org_id,
                            Membership.status == "active")
        cs_total = self._count(ClassSubject, ClassSubject.org_id == org_id)
        assigned = self._count(ClassSubject, ClassSubject.org_id == org_id,
                               ClassSubject.teacher_member_id.is_not(None))
        missing = cs_total - assigned
        return ReadinessCheck(
            key="teachers", title="Teachers assigned",
            status="ok" if cs_total > 0 and missing == 0 else "warn",
            summary=(f"{staff} staff · every class-subject has a teacher"
                     if cs_total > 0 and missing == 0 else
                     f"{staff} staff · {missing} class-subject"
                     f"{'s' if missing != 1 else ''} have nobody to teach them"),
            count=assigned, total=cs_total, link="/setup")

    def _timetable(self, org_id) -> ReadinessCheck:
        slots = self._count(TimetableSlot, TimetableSlot.org_id == org_id,
                            TimetableSlot.effective_to.is_(None))
        classes_with = {
            cid for (cid,) in self.db.execute(
                select(TimetableSlot.class_id).where(
                    TimetableSlot.org_id == org_id,
                    TimetableSlot.effective_to.is_(None)).distinct())
        }
        all_classes = {
            cid for (cid,) in self.db.execute(
                select(SchoolClass.id).where(SchoolClass.org_id == org_id))
        }
        bare = len(all_classes - classes_with)
        ok = slots > 0 and bare == 0
        return ReadinessCheck(
            key="timetable", title="Timetable",
            status="ok" if ok else "warn",
            summary=(f"{slots} slots" if ok else
                     "No timetable — teachers will see no periods on My Day."
                     if slots == 0 else
                     f"{slots} slots · {bare} class{'es' if bare != 1 else ''} "
                     "have no periods at all"),
            link="/plan/timetable")

    def _students(self, org_id) -> ReadinessCheck:
        n = self._count(Student, Student.org_id == org_id,
                        Student.status == "active")
        unplaced = self._count(Student, Student.org_id == org_id,
                               Student.status == "active",
                               Student.class_id.is_(None))
        ok = n > 0 and unplaced == 0
        return ReadinessCheck(
            key="students", title="Students",
            status="ok" if ok else "warn",
            summary=(f"{n} imported" if ok else "No students imported."
                     if n == 0 else
                     f"{n} imported · {unplaced} in no class — they appear on "
                     "no register"),
            count=n - unplaced, total=n, link="/students")

    def _dob(self, org_id) -> ReadinessCheck:
        total = self._count(Student, Student.org_id == org_id,
                            Student.status == "active")
        with_dob = self._count(Student, Student.org_id == org_id,
                               Student.status == "active",
                               Student.date_of_birth.is_not(None))
        missing = total - with_dob
        names = [n for (n,) in self.db.execute(
            select(Student.full_name).where(
                Student.org_id == org_id, Student.status == "active",
                Student.date_of_birth.is_(None))
            .order_by(Student.full_name).limit(30))] if missing else []
        return ReadinessCheck(
            key="dob", title="Dates of birth",
            status="ok" if total > 0 and missing == 0 else "warn",
            summary=(f"{with_dob} of {total}" if total and missing == 0 else
                     f"{with_dob} of {total} — {missing} parent"
                     f"{'s' if missing != 1 else ''} cannot log in"),
            count=with_dob, total=total, link="/students", items=names)

    def _syllabus(self, org_id) -> ReadinessCheck:
        cs_total = self._count(ClassSubject, ClassSubject.org_id == org_id)
        with_sized = {
            csid for (csid,) in self.db.execute(
                select(SyllabusUnit.class_subject_id)
                .join(SyllabusTopic, SyllabusTopic.unit_id == SyllabusUnit.id)
                .where(SyllabusUnit.org_id == org_id,
                       SyllabusTopic.est_periods.is_not(None)).distinct())
        }
        n = len(with_sized)
        return ReadinessCheck(
            key="syllabus", title="Syllabus",
            status="ok" if cs_total > 0 and n == cs_total else "warn",
            summary=(f"sized for {n} of {cs_total} class-subjects" if cs_total else
                     "No class-subjects yet."),
            count=n, total=cs_total, link="/plan/syllabus")

    def _plans(self, org_id) -> ReadinessCheck:
        cs_total = self._count(ClassSubject, ClassSubject.org_id == org_id)
        # Partial counts (V3-P0): a school locking only Term 2 is READY — the
        # mid-year case, not a gap.
        locked = self._count(Plan, Plan.org_id == org_id,
                             Plan.status.in_(("approved", "partial")))
        return ReadinessCheck(
            key="plans", title="Plans approved",
            status="ok" if cs_total > 0 and locked == cs_total else "warn",
            summary=(f"{locked} of {cs_total} locked (term-wise counts)"
                     if cs_total else "No class-subjects yet."),
            count=locked, total=cs_total, link="/plan")

    def _class_teachers(self, org_id) -> ReadinessCheck:
        total = self._count(SchoolClass, SchoolClass.org_id == org_id)
        assigned = self._count(SchoolClass, SchoolClass.org_id == org_id,
                               SchoolClass.class_teacher_member_id.is_not(None))
        missing = total - assigned
        return ReadinessCheck(
            key="class_teachers", title="Class teachers",
            status="ok" if total > 0 and missing == 0 else "warn",
            summary=(f"{assigned} of {total} assigned" if missing == 0 and total else
                     f"{assigned} of {total} assigned — absence follow-ups have "
                     f"no owner in {missing} class{'es' if missing != 1 else ''}"),
            count=assigned, total=total, link="/setup")

    def _fees(self, org_id) -> ReadinessCheck:
        structures = self._count(FeeStructure, FeeStructure.org_id == org_id)
        enrolled = self._count(StudentFee, StudentFee.org_id == org_id)
        ok = structures > 0 and enrolled > 0
        return ReadinessCheck(
            key="fees", title="Fee structures",
            status="ok" if ok else "warn",
            summary=(f"{structures} structures · {enrolled} enrolled" if ok else
                     "No fee structures — the fees module will be empty."
                     if structures == 0 else
                     f"{structures} structures · nobody enrolled yet"),
            link="/fees/structures")

    def _portal(self, org: Organization) -> ReadinessCheck:
        ok = bool(org.parent_portal_enabled and org.school_code)
        return ReadinessCheck(
            key="portal", title="Parent portal",
            status="ok" if ok else "warn",
            summary=(f"enabled · school code {org.school_code}" if ok else
                     "Portal disabled — parents cannot log in."
                     if not org.parent_portal_enabled else
                     "No school code — parents cannot find the school."),
            link="/setup/settings")
