"""Timetable service (V2-M3, SPRD2 §5.3).

Grid = one current slot per (class_id, weekday, period_no). Edits are append-only
and effective-dated (Law 3): the old row is closed, a new one opened, so period-by-
period history stays truthful. Deterministic validators (teacher clash) run over
the current grid; the assisted draft (flag-gated) proposes a fill and reports what
it could not satisfy — it is NOT a guaranteed solver.
"""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    ClassSubject,
    Membership,
    SchoolClass,
    Subject,
    TimetableSlot,
    User,
)
from app.schemas.timetable import (
    Clash,
    DraftOut,
    GridOut,
    ImportAnalyzeOut,
    ImportCell,
    ImportCommitIn,
    PeriodConfigIn,
    PeriodConfigOut,
    SlotClearIn,
    SlotIn,
    SlotOut,
    TeacherSlot,
    TeacherWeekOut,
)
from app.services.ai import parse_timetable
from app.services.ai.timetable import ParsedSubject


def _label(klass: SchoolClass) -> str:
    return klass.name + (f"-{klass.section}" if klass.section else "")


class TimetableService:
    def __init__(self, db: Session):
        self.db = db

    # ── helpers ──────────────────────────────────────────────────────────────
    def _today(self, m: CurrentMember) -> date:
        return datetime.now(ZoneInfo(m.org.timezone)).date()

    def _class(self, org_id: uuid.UUID, class_id: uuid.UUID) -> SchoolClass:
        klass = self.db.scalar(
            select(SchoolClass).where(SchoolClass.id == class_id, SchoolClass.org_id == org_id)
        )
        if klass is None:
            raise NotFoundError("Class")
        return klass

    def _year(self, klass: SchoolClass) -> AcademicYear:
        year = self.db.get(AcademicYear, klass.academic_year_id)
        if year is None:
            raise ValidationError("This class has no academic year.")
        return year

    def _cs_meta(self, org_id: uuid.UUID) -> dict[uuid.UUID, tuple[str | None, uuid.UUID | None, str | None]]:
        """class_subject_id → (subject_name, teacher_member_id, teacher_name)."""
        rows = self.db.execute(
            select(ClassSubject.id, Subject.name, ClassSubject.teacher_member_id, User.name)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .outerjoin(Membership, Membership.id == ClassSubject.teacher_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .where(ClassSubject.org_id == org_id)
        ).all()
        return {cs_id: (sname, tmid, tname) for cs_id, sname, tmid, tname in rows}

    def _class_labels(self, org_id: uuid.UUID) -> dict[uuid.UUID, str]:
        rows = self.db.scalars(select(SchoolClass).where(SchoolClass.org_id == org_id))
        return {k.id: _label(k) for k in rows}

    def _current_at(self, on_date: date):
        return and_(
            TimetableSlot.effective_from <= on_date,
            or_(TimetableSlot.effective_to.is_(None), TimetableSlot.effective_to > on_date),
        )

    def _class_slots(self, org_id: uuid.UUID, class_id: uuid.UUID, on_date: date) -> list[TimetableSlot]:
        return list(self.db.scalars(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id,
                TimetableSlot.class_id == class_id,
                self._current_at(on_date),
            )
        ))

    def _org_slots(self, org_id: uuid.UUID, on_date: date) -> list[TimetableSlot]:
        return list(self.db.scalars(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id, self._current_at(on_date))
        ))

    # ── clash validator (deterministic — §5.2 pipeline V-checks) ─────────────
    def _clashes(
        self, slots: list[TimetableSlot], cs_meta: dict, class_labels: dict,
        only_class: uuid.UUID | None = None,
    ) -> list[Clash]:
        """A teacher assigned to two different classes at one weekday+period."""
        # (weekday, period_no, teacher_member_id) → {class_id: label}
        buckets: dict[tuple[int, int, uuid.UUID], dict[uuid.UUID, str]] = {}
        for s in slots:
            _sname, tmid, _tname = cs_meta.get(s.class_subject_id, (None, None, None))
            if tmid is None:
                continue
            key = (s.weekday, s.period_no, tmid)
            buckets.setdefault(key, {})[s.class_id] = class_labels.get(s.class_id, "?")
        clashes: list[Clash] = []
        for (weekday, period_no, tmid), classes in buckets.items():
            if len(classes) < 2:
                continue
            if only_class is not None and only_class not in classes:
                continue
            _sn, _t, tname = next(
                ((cs_meta[cs][0], cs, cs_meta[cs][2]) for cs in cs_meta
                 if cs_meta[cs][1] == tmid), (None, None, None))
            clashes.append(Clash(
                weekday=weekday, period_no=period_no, teacher_member_id=tmid,
                teacher_name=tname, class_labels=sorted(classes.values())))
        return clashes

    def _slot_out(self, s: TimetableSlot, cs_meta: dict) -> SlotOut:
        sname, tmid, tname = cs_meta.get(s.class_subject_id, (None, None, None))
        return SlotOut(
            id=s.id, class_id=s.class_id, weekday=s.weekday, period_no=s.period_no,
            class_subject_id=s.class_subject_id, subject_name=sname,
            teacher_member_id=tmid, teacher_name=tname,
            effective_from=s.effective_from, effective_to=s.effective_to)

    def _grid(self, m: CurrentMember, klass: SchoolClass, on_date: date) -> GridOut:
        year = self._year(klass)
        cs_meta = self._cs_meta(m.org_id)
        class_labels = self._class_labels(m.org_id)
        class_slots = self._class_slots(m.org_id, klass.id, on_date)
        clashes = self._clashes(
            self._org_slots(m.org_id, on_date), cs_meta, class_labels, only_class=klass.id)
        return GridOut(
            class_id=klass.id, class_label=_label(klass),
            weekdays=list(year.working_weekdays), periods_per_day=year.periods_per_day,
            slots=[self._slot_out(s, cs_meta) for s in class_slots], clashes=clashes)

    # ── grid read/write ──────────────────────────────────────────────────────
    def get_grid(self, m: CurrentMember, class_id: uuid.UUID, on_date: date | None = None) -> GridOut:
        klass = self._class(m.org_id, class_id)
        return self._grid(m, klass, on_date or self._today(m))

    def set_slot(self, m: CurrentMember, body: SlotIn) -> GridOut:
        klass = self._class(m.org_id, body.class_id)
        year = self._year(klass)
        if body.period_no > year.periods_per_day:
            raise ValidationError(
                f"Period {body.period_no} is beyond the {year.periods_per_day} periods/day set for this year.")
        cs = self.db.scalar(
            select(ClassSubject).where(
                ClassSubject.id == body.class_subject_id, ClassSubject.org_id == m.org_id)
        )
        if cs is None:
            raise NotFoundError("Class-subject")
        if cs.class_id != body.class_id:
            raise ValidationError("That subject is not taught in this class.")
        eff = body.effective_from or self._today(m)

        current = self.db.scalar(
            select(TimetableSlot).where(
                TimetableSlot.org_id == m.org_id, TimetableSlot.class_id == body.class_id,
                TimetableSlot.weekday == body.weekday, TimetableSlot.period_no == body.period_no,
                TimetableSlot.effective_to.is_(None))
        )
        if current is not None:
            if current.class_subject_id == body.class_subject_id:
                return self._grid(m, klass, eff)  # no-op
            # Close the old assignment as of the edit date (append-only history).
            current.effective_to = eff
        self.db.add(TimetableSlot(
            org_id=m.org_id, class_id=body.class_id, weekday=body.weekday,
            period_no=body.period_no, class_subject_id=body.class_subject_id,
            effective_from=eff, effective_to=None))
        self.db.flush()
        return self._grid(m, klass, eff)

    def clear_slot(self, m: CurrentMember, body: SlotClearIn) -> GridOut:
        klass = self._class(m.org_id, body.class_id)
        eff = body.effective_from or self._today(m)
        current = self.db.scalar(
            select(TimetableSlot).where(
                TimetableSlot.org_id == m.org_id, TimetableSlot.class_id == body.class_id,
                TimetableSlot.weekday == body.weekday, TimetableSlot.period_no == body.period_no,
                TimetableSlot.effective_to.is_(None))
        )
        if current is None:
            raise NotFoundError("Slot")
        # Closing on its own start date means it never applied — delete it; else close.
        if current.effective_from >= eff:
            self.db.delete(current)
        else:
            current.effective_to = eff
        self.db.flush()
        return self._grid(m, klass, eff)

    def validate_grid(self, m: CurrentMember, on_date: date | None = None) -> list[Clash]:
        d = on_date or self._today(m)
        return self._clashes(
            self._org_slots(m.org_id, d), self._cs_meta(m.org_id), self._class_labels(m.org_id))

    # ── teacher view (her own week) ──────────────────────────────────────────
    def teacher_week(
        self, m: CurrentMember, member_id: uuid.UUID | None = None, on_date: date | None = None,
    ) -> TeacherWeekOut:
        d = on_date or self._today(m)
        target = member_id or m.membership.id
        year = self._active_year(m.org_id)
        weekdays = list(year.working_weekdays) if year else [0, 1, 2, 3, 4, 5]
        ppd = year.periods_per_day if year else 8
        cs_meta = self._cs_meta(m.org_id)
        class_labels = self._class_labels(m.org_id)
        mine = [
            s for s in self._org_slots(m.org_id, d)
            if cs_meta.get(s.class_subject_id, (None, None, None))[1] == target
        ]
        slots = [
            TeacherSlot(
                weekday=s.weekday, period_no=s.period_no, class_id=s.class_id,
                class_label=class_labels.get(s.class_id, "?"),
                subject_name=cs_meta.get(s.class_subject_id, (None, None, None))[0],
                class_subject_id=s.class_subject_id)
            for s in sorted(mine, key=lambda s: (s.weekday, s.period_no))
        ]
        return TeacherWeekOut(member_id=target, weekdays=weekdays, periods_per_day=ppd, slots=slots)

    def _active_year(self, org_id: uuid.UUID) -> AcademicYear | None:
        return self.db.scalar(
            select(AcademicYear).where(
                AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True))
        )

    # ── My Day integration (§5.4 — teacher's periods today) ──────────────────
    def teacher_day(self, m: CurrentMember, on_date: date) -> list[TeacherSlot]:
        week = self.teacher_week(m, on_date=on_date)
        return [s for s in week.slots if s.weekday == on_date.weekday()]

    # ── period timing config ─────────────────────────────────────────────────
    def get_period_config(self, m: CurrentMember, year_id: uuid.UUID) -> PeriodConfigOut:
        year = self.db.scalar(
            select(AcademicYear).where(AcademicYear.id == year_id, AcademicYear.org_id == m.org_id))
        if year is None:
            raise NotFoundError("Academic year")
        return PeriodConfigOut(
            academic_year_id=year.id, periods_per_day=year.periods_per_day,
            period_times=year.period_times)

    def set_period_config(self, m: CurrentMember, body: PeriodConfigIn) -> PeriodConfigOut:
        year = self.db.scalar(
            select(AcademicYear).where(
                AcademicYear.id == body.academic_year_id, AcademicYear.org_id == m.org_id))
        if year is None:
            raise NotFoundError("Academic year")
        year.periods_per_day = body.periods_per_day
        year.period_times = [pt.model_dump() for pt in body.period_times]
        self.db.flush()
        return PeriodConfigOut(
            academic_year_id=year.id, periods_per_day=year.periods_per_day,
            period_times=year.period_times)

    # ── import (photo/xlsx → parse → confirm) ────────────────────────────────
    def _parsed_subjects(self, org_id: uuid.UUID, class_id: uuid.UUID) -> list[ParsedSubject]:
        rows = self.db.execute(
            select(ClassSubject.id, Subject.name, ClassSubject.periods_per_week)
            .join(Subject, Subject.id == ClassSubject.subject_id)
            .where(ClassSubject.org_id == org_id, ClassSubject.class_id == class_id)
        ).all()
        return [ParsedSubject(cs_id, sname, ppw) for cs_id, sname, ppw in rows]

    def import_analyze(
        self, m: CurrentMember, class_id: uuid.UUID, file_bytes: bytes | None = None,
    ) -> ImportAnalyzeOut:
        klass = self._class(m.org_id, class_id)
        year = self._year(klass)
        subjects = self._parsed_subjects(m.org_id, class_id)
        if not subjects:
            raise ValidationError("Add subjects to this class before importing a timetable.")
        source, cells = parse_timetable(
            subjects, periods_per_day=year.periods_per_day,
            weekdays=list(year.working_weekdays), file_bytes=file_bytes)
        return ImportAnalyzeOut(
            class_id=class_id, source=source,
            cells=[ImportCell(**c) for c in cells], unmatched=[])

    def import_commit(self, m: CurrentMember, body: ImportCommitIn) -> GridOut:
        klass = self._class(m.org_id, body.class_id)
        eff = body.effective_from or self._today(m)
        for cell in body.cells:
            self.set_slot(m, SlotIn(
                class_id=body.class_id, weekday=cell.weekday, period_no=cell.period_no,
                class_subject_id=cell.class_subject_id, effective_from=eff))
        return self._grid(m, klass, eff)

    # ── assisted draft (flag-gated, NOT a guaranteed solver) ─────────────────
    def assisted_draft(self, m: CurrentMember, class_id: uuid.UUID) -> DraftOut:
        klass = self._class(m.org_id, class_id)
        if not settings.TIMETABLE_ASSISTED_DRAFT:
            return DraftOut(
                class_id=class_id, enabled=False,
                message="Assisted timetable draft is disabled. Enable TIMETABLE_ASSISTED_DRAFT to pilot it.")
        year = self._year(klass)
        subjects = self._parsed_subjects(m.org_id, class_id)
        # Proposer: round-robin fill, then validator over the whole org grid to flag
        # teacher clashes with other classes. Repair is left to the admin (drag).
        source, cells = parse_timetable(
            subjects, periods_per_day=year.periods_per_day, weekdays=list(year.working_weekdays))
        # Validate the proposed cells against existing OTHER-class current slots.
        cs_meta = self._cs_meta(m.org_id)
        class_labels = self._class_labels(m.org_id)
        other = [s for s in self._org_slots(m.org_id, self._today(m)) if s.class_id != class_id]
        proposed = [
            TimetableSlot(
                org_id=m.org_id, class_id=class_id, weekday=c["weekday"],
                period_no=c["period_no"], class_subject_id=c["class_subject_id"],
                effective_from=self._today(m))
            for c in cells
        ]
        clashes = self._clashes(other + proposed, cs_meta, class_labels, only_class=class_id)
        unresolved = [
            f"{cl.class_labels} share a teacher on weekday {cl.weekday} period {cl.period_no}"
            for cl in clashes
        ]
        return DraftOut(
            class_id=class_id, enabled=True, cells=[ImportCell(**c) for c in cells],
            clashes=clashes, unresolved=unresolved,
            message="Draft ready — review and adjust, then confirm to apply.")
