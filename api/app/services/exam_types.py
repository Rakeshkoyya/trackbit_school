"""The school's own exam vocabulary (V1-8, `D-55`/`S-135`).

A school that runs **CET** could not record one. `assessment_cycles.type` is a
CHECK over nine values, so CET was either unsaveable or filed as `class_test` —
and once filed, no analytic could ever separate it again.

Two rules govern everything here, and they are the whole reason the field is
*beside* `type` rather than replacing it:

1. **The school's word is what every screen displays and groups by.** If an
   analytic ever groups by `system_type`, the two have diverged (ux-principles
   §9).
2. **The system kind is read only by code** — `diagnostic` routes to the skill
   grid, `band_test` is admin-only, `grid_only` in the feed. Those branches must
   keep working when a school renames *Term exam* to *Annual*.

Retire, never delete (the `core/work_types.py` rule): an exam type that named
forty exams last year keeps rendering on them. Deactivating drops it from the
picker and nothing else.

Zero setup: `ensure_defaults` seeds the nine pre-written types the first time a
school reads the list, so a teacher picks **one** thing per exam (the type
carries its `scale`) rather than configuring vocabulary before recording a test.
"""

from __future__ import annotations  # `list` is a method name here — keep annotations lazy

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exams import SYSTEM_TYPES, normalise_scale
from app.core.exceptions import NotFoundError, ValidationError
from app.models import AssessmentCycle, ExamType
from app.schemas.assessments import ExamTypeCreate, ExamTypeOut, ExamTypeUpdate

# The pre-written nine, in the order a school reads them: what they run weekly
# first, what they run twice a year last.
_DEFAULTS: tuple[tuple[str, str, int], ...] = (
    ("slip_test", "Slip test", 10),
    ("class_test", "Class test", 20),
    ("chapter_test", "Chapter test", 30),
    ("daily_test", "Daily test", 40),
    ("objective", "Objective test", 50),
    ("band_test", "Band test", 60),
    ("diagnostic", "Diagnostic", 70),
    ("unit_test", "Unit test", 80),
    ("term_exam", "Term exam", 90),
)


def _out(t: ExamType, in_use: int = 0) -> ExamTypeOut:
    return ExamTypeOut(id=t.id, name=t.name, system_type=t.system_type, scale=t.scale,
                       position=t.position, active=t.active, exams=in_use)


class ExamTypeService:
    def __init__(self, db: Session):
        self.db = db

    # ── read ─────────────────────────────────────────────────────────────────
    def list(self, m: CurrentMember, include_retired: bool = False) -> list[ExamTypeOut]:
        rows = self._rows(m)
        if not rows:
            rows = self.ensure_defaults(m)
        counts = dict(self.db.execute(
            select(AssessmentCycle.exam_type_id, func.count())
            .where(AssessmentCycle.org_id == m.org_id,
                   AssessmentCycle.exam_type_id.is_not(None))
            .group_by(AssessmentCycle.exam_type_id)).all())
        return [_out(t, int(counts.get(t.id, 0))) for t in rows
                if include_retired or t.active]

    def _rows(self, m: CurrentMember) -> list[ExamType]:
        return list(self.db.scalars(
            select(ExamType).where(ExamType.org_id == m.org_id)
            .order_by(ExamType.position, ExamType.name)))

    def ensure_defaults(self, m: CurrentMember) -> list[ExamType]:
        """Seed the nine, once, without disturbing anything a school has already
        named.

        `ON CONFLICT DO NOTHING` rather than a read-then-insert, because this
        runs on a **read**: two people opening the scores screen for the first
        time on a fresh school would otherwise race into the unique index and
        one of them would get a 500 while recording a test. Seeding must never
        be the reason a mark cannot be entered."""
        rows = [{"org_id": m.org_id, "name": name, "system_type": system_type,
                 "scale": SYSTEM_TYPES[system_type][1], "position": position}
                for system_type, name, position in _DEFAULTS]
        self.db.execute(
            pg_insert(ExamType.__table__).values(rows)
            .on_conflict_do_nothing(index_elements=["org_id", "name"]))
        self.db.flush()
        return self._rows(m)

    def get(self, m: CurrentMember, exam_type_id: uuid.UUID) -> ExamType:
        t = self.db.scalar(select(ExamType).where(
            ExamType.id == exam_type_id, ExamType.org_id == m.org_id))
        if t is None:
            raise NotFoundError("Exam type")
        return t

    def resolve(self, m: CurrentMember, exam_type_id: uuid.UUID | None,
                system_type: str) -> tuple[uuid.UUID | None, str]:
        """(exam_type_id, scale) for a save. The picked type owns the scale —
        that is what makes it one choice for the teacher instead of two. An
        exam saved without one keeps working and falls back to the kind's
        default scale, because an old client must never be the reason a mark
        cannot be recorded."""
        if exam_type_id is None:
            return None, normalise_scale(None, system_type)
        t = self.get(m, exam_type_id)
        if t.system_type != system_type:
            raise ValidationError(
                f"“{t.name}” is recorded as a {t.system_type.replace('_', ' ')}.",
                code="type_mismatch")
        return t.id, t.scale

    # ── write (admin) ────────────────────────────────────────────────────────
    def create(self, m: CurrentMember, body: ExamTypeCreate) -> ExamTypeOut:
        name = body.name.strip()
        if self.db.scalar(select(ExamType.id).where(
                ExamType.org_id == m.org_id, func.lower(ExamType.name) == name.casefold())):
            raise ValidationError(f"“{name}” already exists.", code="duplicate_name")
        if body.system_type not in SYSTEM_TYPES:
            raise ValidationError("Unknown exam kind.", code="bad_system_type")
        position = body.position if body.position is not None else (
            (self.db.scalar(select(func.max(ExamType.position)).where(
                ExamType.org_id == m.org_id)) or 0) + 10)
        t = ExamType(org_id=m.org_id, name=name, system_type=body.system_type,
                     scale=normalise_scale(body.scale, body.system_type), position=position)
        self.db.add(t)
        self.db.flush()
        return _out(t)

    def update(self, m: CurrentMember, exam_type_id: uuid.UUID,
               body: ExamTypeUpdate) -> ExamTypeOut:
        t = self.get(m, exam_type_id)
        if body.name is not None:
            name = body.name.strip()
            clash = self.db.scalar(select(ExamType.id).where(
                ExamType.org_id == m.org_id, ExamType.id != t.id,
                func.lower(ExamType.name) == name.casefold()))
            if clash:
                raise ValidationError(f"“{name}” already exists.", code="duplicate_name")
            t.name = name
        if body.scale is not None:
            # Changing a type's scale re-files every exam recorded under it —
            # deliberately, because the alternative is a school stuck with
            # "CET = major" polluting standing on every screen forever.
            t.scale = normalise_scale(body.scale, t.system_type)
            self.db.execute(
                AssessmentCycle.__table__.update()
                .where(AssessmentCycle.org_id == m.org_id,
                       AssessmentCycle.exam_type_id == t.id)
                .values(scale=t.scale))
        if body.position is not None:
            t.position = body.position
        if body.active is not None:
            t.active = body.active
        self.db.flush()
        return _out(t)
