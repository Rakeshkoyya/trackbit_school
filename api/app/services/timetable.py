"""Timetable service (V2-M3, SPRD2 §5.3; typed slots + the bell schedule, TT-2).

Grid = one current slot per (class_id, weekday, period_no). Edits are append-only
and effective-dated (Law 3): the old row is closed, a new one opened, so period-by-
period history stays truthful. Deterministic validators (teacher clash) run over
the current grid; the assisted draft (flag-gated) proposes a fill and reports what
it could not satisfy — it is NOT a guaranteed solver.

A cell holds either a **class-subject** or a **block** — a `Session`, which is what
a homework class, a games period, an extra course or assembly is (`D-112`). The
block's flavour is `sessions.kind`; what each flavour asks the teacher to capture
is `core/day_shape.CAPTURE`, and no service branches on the string itself.

`D-113`: a block on the grid takes its schedule from the grid. The session's own
`weekdays`/`time` are ignored while any live slot points at it, so "when does AI
class happen" has one answer.
"""

import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session as OrmSession
from sqlalchemy.orm import selectinload

from app.core import day_shape
from app.core.config import settings
from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    ClassSubject,
    CombinedPeriod,
    Membership,
    SchoolClass,
    SessionClass,
    SessionStaff,
    Student,
    StudentCategory,
    Subject,
    TimetableSlot,
    User,
)
from app.models import Session as SessionModel
from app.schemas.timetable import (
    BellHistoryOut,
    BellScheduleIn,
    BellScheduleOut,
    BlockIn,
    BlockOut,
    BlockUpdate,
    Clash,
    CombinedClassOut,
    CombinedOut,
    CombineIn,
    DraftOut,
    GridBreak,
    GridOut,
    GridPeriod,
    ImportAnalyzeOut,
    ImportCell,
    ImportCommitIn,
    OrgDraftCell,
    OrgDraftIssue,
    OrgGenerateIn,
    OrgGenerateOut,
    PeriodConfigIn,
    PeriodConfigOut,
    PeriodTime,
    SlotBulkIn,
    SlotBulkOut,
    SlotClearIn,
    SlotIn,
    SlotOut,
    TeacherSlot,
    TeacherWeekOut,
    UncombineIn,
)
from app.services import bell
from app.services.ai import parse_timetable
from app.services.ai.timetable import ParsedSubject
from app.services.period_load import recompute_periods_per_week


def _label(klass: SchoolClass) -> str:
    return klass.name + (f"-{klass.section}" if klass.section else "")


def counts_as_clash(slot: TimetableSlot) -> bool:
    """Is a double-booking involving this cell worth telling anybody about?

    **A block is a POOL, not an assignment** (founder, 2026-08-14): *"each block
    can be edited by any teacher that is assigned, so there is no need to give
    warning if an activity teacher is overlapping — the other teacher will take
    care of it."* Games, assembly and the homework class are staffed by whoever
    is free that evening, and `session_staff` lists the people who MAY take it,
    not the one who must. Warning that one of five possible takers also teaches
    Maths in that period is noise about a situation the block was designed to
    absorb — and noise on this banner is what makes a school stop reading the
    real clashes underneath it.

    A subject is the opposite: exactly one teacher is named on it, and if she is
    somewhere else at that hour the class has nobody. That is the clash worth a
    warning, and it is the only one left.
    """
    return slot.slot_type != "block"


def combined_label(class_labels: list[str]) -> str:
    """How a combined meeting names itself: "5-A + 6-A" (TT-4).

    One function, because this string appears on the grid chip, on My Day, on the
    period card and on the attendance sheet — and a room the teacher recognises
    on one screen has to be the same room on the next.
    """
    return " + ".join(class_labels)


class BlockMeta:
    """Everything the grid needs to render one block, resolved once per request."""

    __slots__ = ("active", "category_id", "category_name", "kind", "name",
                 "owner_member_id", "staff_ids", "staff_names")

    def __init__(self, name: str, kind: str, category_id: uuid.UUID | None,
                 category_name: str | None, active: bool,
                 owner_member_id: uuid.UUID | None,
                 staff_ids: list[uuid.UUID], staff_names: list[str]):
        self.name = name
        self.kind = kind
        self.category_id = category_id
        self.category_name = category_name
        self.active = active
        self.owner_member_id = owner_member_id
        self.staff_ids = staff_ids
        self.staff_names = staff_names


class TimetableService:
    def __init__(self, db: OrmSession):
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

    def _member_names(self, org_id: uuid.UUID,
                      member_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
        if not member_ids:
            return {}
        rows = self.db.execute(
            select(Membership.id, User.name)
            .join(User, User.id == Membership.user_id)
            .where(Membership.org_id == org_id, Membership.id.in_(member_ids))
        ).all()
        return dict(rows)

    def _block_meta(self, org_id: uuid.UUID) -> dict[uuid.UUID, BlockMeta]:
        """session_id → BlockMeta, staff included. Two queries, never per-slot."""
        sessions = list(self.db.scalars(
            select(SessionModel).where(SessionModel.org_id == org_id)))
        if not sessions:
            return {}
        staff_rows = self.db.execute(
            select(SessionStaff.session_id, SessionStaff.member_id, User.name)
            .join(Membership, Membership.id == SessionStaff.member_id)
            .join(User, User.id == Membership.user_id)
            .where(SessionStaff.org_id == org_id)
            .order_by(User.name)
        ).all()
        by_session: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = {}
        for sid, mid, name in staff_rows:
            by_session.setdefault(sid, []).append((mid, name))
        # The owner counts as staff whether or not a session_staff row exists —
        # otherwise assigning a second teacher would silently drop the first.
        owner_names = self._member_names(
            org_id, {s.owner_member_id for s in sessions if s.owner_member_id})
        # `D-129`: the block names the category it serves, so every screen can
        # say "Hostellers" (or "Transport") rather than a bare checked box.
        cat_ids = {s.category_id for s in sessions if s.category_id}
        cat_names = {c.id: c.name for c in self.db.scalars(
            select(StudentCategory).where(StudentCategory.id.in_(cat_ids)))} if cat_ids else {}
        out: dict[uuid.UUID, BlockMeta] = {}
        for s in sessions:
            pairs = list(by_session.get(s.id, []))
            if s.owner_member_id and s.owner_member_id not in {p[0] for p in pairs}:
                pairs.insert(0, (s.owner_member_id,
                                 owner_names.get(s.owner_member_id, "—")))
            out[s.id] = BlockMeta(
                name=s.name, kind=s.kind, category_id=s.category_id,
                category_name=cat_names.get(s.category_id),
                active=s.active, owner_member_id=s.owner_member_id,
                staff_ids=[p[0] for p in pairs], staff_names=[p[1] for p in pairs])
        return out

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

    def _shape(self, year: AcademicYear | None, on_date: date) -> bell.DayShape:
        return bell.resolve(self.db, year, on_date)

    # ── who is committed where (subjects and blocks alike) ───────────────────
    def _commitments(
        self, slot: TimetableSlot, cs_meta: dict, block_meta: dict[uuid.UUID, BlockMeta],
    ) -> list[tuple[uuid.UUID, tuple]]:
        """(teacher_member_id, engagement) pairs this slot creates.

        The *engagement* is what the teacher is committed to, not which cell said
        so. One assembly block placed on twenty classes is a single engagement —
        the teacher stands in one hall — so it must not read as nineteen clashes.
        Two different class-subjects at one time are two engagements and do.

        TT-4 adds the third case and it is the same idea: classes taught together
        are **one** engagement, keyed on the combination rather than on the
        class. That is the whole mechanism by which combining a period silences
        its clash — no rule anywhere else changes, and a genuine third booking
        elsewhere in the school still reports, because it is still a second
        engagement.
        """
        if slot.slot_type == "block":
            meta = block_meta.get(slot.session_id) if slot.session_id else None
            if meta is None or not meta.active:
                return []
            return [(mid, ("block", slot.session_id)) for mid in meta.staff_ids]
        _sname, tmid, _tname = cs_meta.get(slot.class_subject_id, (None, None, None))
        if tmid is None:
            return []
        if slot.combined_id is not None:
            return [(tmid, ("combined", slot.combined_id))]
        return [(tmid, ("subject", slot.class_id))]

    # ── clash validator (deterministic — §5.2 pipeline V-checks) ─────────────
    def _clashes(
        self, slots: list[TimetableSlot], cs_meta: dict, class_labels: dict,
        block_meta: dict[uuid.UUID, BlockMeta] | None = None,
        only_class: uuid.UUID | None = None,
    ) -> list[Clash]:
        """A teacher committed to two different things at one weekday+period."""
        block_meta = block_meta or {}
        # (weekday, period_no, teacher) → {engagement: {class_id: label}}
        buckets: dict[tuple[int, int, uuid.UUID], dict[tuple, dict[uuid.UUID, str]]] = {}
        for s in slots:
            if not counts_as_clash(s):
                continue
            for tmid, engagement in self._commitments(s, cs_meta, block_meta):
                key = (s.weekday, s.period_no, tmid)
                buckets.setdefault(key, {}).setdefault(engagement, {})[s.class_id] = \
                    class_labels.get(s.class_id, "?")

        teacher_names: dict[uuid.UUID, str | None] = {}
        for _sn, tmid, tname in cs_meta.values():
            if tmid is not None:
                teacher_names.setdefault(tmid, tname)
        for meta in block_meta.values():
            for mid, name in zip(meta.staff_ids, meta.staff_names, strict=False):
                teacher_names.setdefault(mid, name)

        clashes: list[Clash] = []
        for (weekday, period_no, tmid), engagements in buckets.items():
            if len(engagements) < 2:
                continue
            classes: dict[uuid.UUID, str] = {}
            for by_class in engagements.values():
                classes.update(by_class)
            if only_class is not None and only_class not in classes:
                continue
            # TT-4: is this a mistake, or an arrangement the grid cannot say yet?
            # Every engagement being a subject (or an existing combination this
            # would grow) means "these classes could simply sit together", which
            # is usually the true fix and is one tap from the banner. A block in
            # the bucket is neither: a block already spans classes on its own.
            combinable = all(e[0] in ("subject", "combined") for e in engagements)
            ordered = sorted(classes.items(), key=lambda kv: kv[1])
            clashes.append(Clash(
                weekday=weekday, period_no=period_no, teacher_member_id=tmid,
                teacher_name=teacher_names.get(tmid),
                class_labels=[label for _cid, label in ordered],
                class_ids=[cid for cid, _label in ordered],
                combinable=combinable))
        return clashes

    # ── combined periods (TT-4) ──────────────────────────────────────────────
    def _combined_members(
        self, slots: list[TimetableSlot], class_labels: dict[uuid.UUID, str],
    ) -> dict[uuid.UUID, list[tuple[uuid.UUID, str]]]:
        """combined_id → its live member classes, ordered by label.

        Derived from the slots on every read rather than stored: the membership
        IS the set of live cells, so there is nothing to keep in step.
        """
        out: dict[uuid.UUID, dict[uuid.UUID, str]] = {}
        for s in slots:
            if s.combined_id is None:
                continue
            out.setdefault(s.combined_id, {})[s.class_id] = class_labels.get(s.class_id, "?")
        return {cid: sorted(members.items(), key=lambda kv: kv[1])
                for cid, members in out.items()}

    def _slot_out(self, s: TimetableSlot, cs_meta: dict,
                  block_meta: dict[uuid.UUID, BlockMeta],
                  combined: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] | None = None,
                  ) -> SlotOut:
        combined_with = [
            label for cid, label in (combined or {}).get(s.combined_id, [])
            if cid != s.class_id
        ] if s.combined_id else []
        if s.slot_type == "block":
            meta = block_meta.get(s.session_id) if s.session_id else None
            return SlotOut(
                id=s.id, class_id=s.class_id, weekday=s.weekday, period_no=s.period_no,
                slot_type="block", session_id=s.session_id,
                block_name=meta.name if meta else "(removed block)",
                block_kind=meta.kind if meta else None,
                block_kind_label=day_shape.label_for(meta.kind) if meta else None,
                category_id=meta.category_id if meta else None,
                category_name=meta.category_name if meta else None,
                staff_member_ids=list(meta.staff_ids) if meta else [],
                staff_names=list(meta.staff_names) if meta else [],
                effective_from=s.effective_from, effective_to=s.effective_to)
        sname, tmid, tname = cs_meta.get(s.class_subject_id, (None, None, None))
        return SlotOut(
            id=s.id, class_id=s.class_id, weekday=s.weekday, period_no=s.period_no,
            slot_type="subject", class_subject_id=s.class_subject_id, subject_name=sname,
            teacher_member_id=tmid, teacher_name=tname,
            combined_id=s.combined_id, combined_with=combined_with,
            effective_from=s.effective_from, effective_to=s.effective_to)

    def _grid(self, m: CurrentMember, klass: SchoolClass, on_date: date) -> GridOut:
        year = self._year(klass)
        shape = self._shape(year, on_date)
        cs_meta = self._cs_meta(m.org_id)
        block_meta = self._block_meta(m.org_id)
        class_labels = self._class_labels(m.org_id)
        class_slots = self._class_slots(m.org_id, klass.id, on_date)
        org_slots = self._org_slots(m.org_id, on_date)
        combined = self._combined_members(org_slots, class_labels)
        clashes = self._clashes(
            org_slots, cs_meta, class_labels, block_meta, only_class=klass.id)
        return GridOut(
            class_id=klass.id, class_label=_label(klass),
            weekdays=list(year.working_weekdays), periods_per_day=shape.periods_per_day,
            slots=[self._slot_out(s, cs_meta, block_meta, combined) for s in class_slots],
            clashes=clashes,
            periods=[GridPeriod(period_no=p.period_no, start=p.start, end=p.end)
                     for p in shape.periods],
            breaks=[GridBreak(after_period_no=b.after_period_no, label=b.label,
                              start=b.start, end=b.end) for b in shape.breaks],
            has_timings=shape.has_timings)

    # ── grid read/write ──────────────────────────────────────────────────────
    def get_grid(self, m: CurrentMember, class_id: uuid.UUID, on_date: date | None = None) -> GridOut:
        klass = self._class(m.org_id, class_id)
        return self._grid(m, klass, on_date or self._today(m))

    def _current_slot(self, org_id: uuid.UUID, class_id: uuid.UUID,
                      weekday: int, period_no: int) -> TimetableSlot | None:
        return self.db.scalar(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id, TimetableSlot.class_id == class_id,
                TimetableSlot.weekday == weekday, TimetableSlot.period_no == period_no,
                TimetableSlot.effective_to.is_(None))
        )

    def _resolve_payload(self, m: CurrentMember, class_id: uuid.UUID,
                         slot_type: str, class_subject_id: uuid.UUID | None,
                         session_id: uuid.UUID | None) -> tuple[uuid.UUID | None, uuid.UUID | None]:
        """Validate the cell's payload before the DB CHECK has to."""
        if slot_type == "block":
            if session_id is None:
                raise ValidationError("Pick which block runs in this period.")
            s = self.db.scalar(select(SessionModel).where(
                SessionModel.id == session_id, SessionModel.org_id == m.org_id))
            if s is None:
                raise NotFoundError("Block")
            if not s.active:
                raise ValidationError(f"“{s.name}” is archived — reactivate it first.")
            return None, session_id
        if class_subject_id is None:
            raise ValidationError("Pick which subject runs in this period.")
        cs = self.db.scalar(
            select(ClassSubject).where(
                ClassSubject.id == class_subject_id, ClassSubject.org_id == m.org_id))
        if cs is None:
            raise NotFoundError("Class-subject")
        if cs.class_id != class_id:
            raise ValidationError("That subject is not taught in this class.")
        return class_subject_id, None

    def _link_block_class(self, org_id: uuid.UUID, session_id: uuid.UUID,
                          class_id: uuid.UUID) -> None:
        """A class that has the block on its timetable is in the block's roster.

        Without this the admin would have to say "7A does homework class" twice —
        once on the grid and once in the block's own class list — and the two
        would drift on the first change.
        """
        exists = self.db.scalar(select(SessionClass.id).where(
            SessionClass.session_id == session_id, SessionClass.class_id == class_id))
        if exists is None:
            self.db.add(SessionClass(org_id=org_id, session_id=session_id,
                                     class_id=class_id))

    def _unlink_block_class_if_unused(self, org_id: uuid.UUID, session_id: uuid.UUID,
                                      class_id: uuid.UUID) -> None:
        """Drop the roster link once no live cell puts this class in the block."""
        still_used = self.db.scalar(
            select(func.count(TimetableSlot.id)).where(
                TimetableSlot.org_id == org_id, TimetableSlot.class_id == class_id,
                TimetableSlot.session_id == session_id,
                TimetableSlot.effective_to.is_(None)))
        if still_used:
            return
        link = self.db.scalar(select(SessionClass).where(
            SessionClass.session_id == session_id, SessionClass.class_id == class_id))
        if link is not None:
            self.db.delete(link)

    def set_slot(self, m: CurrentMember, body: SlotIn) -> GridOut:
        klass = self._class(m.org_id, body.class_id)
        year = self._year(klass)
        eff = body.effective_from or self._today(m)
        shape = self._shape(year, eff)
        if body.period_no > shape.periods_per_day:
            raise ValidationError(
                f"Period {body.period_no} is beyond the {shape.periods_per_day} "
                f"periods/day set for this year. Add it in the school timings first.")
        cs_id, session_id = self._resolve_payload(
            m, body.class_id, body.slot_type, body.class_subject_id, body.session_id)

        current = self._current_slot(m.org_id, body.class_id, body.weekday, body.period_no)
        old_combined: uuid.UUID | None = None
        if current is not None:
            if (current.slot_type == body.slot_type
                    and current.class_subject_id == cs_id
                    and current.session_id == session_id):
                return self._grid(m, klass, eff)  # no-op
            old_session = current.session_id
            old_combined = current.combined_id
            # Close the old assignment as of the edit date (append-only history).
            if current.effective_from >= eff:
                self.db.delete(current)
            else:
                current.effective_to = eff
            self.db.flush()
            if old_session:
                self._unlink_block_class_if_unused(m.org_id, old_session, body.class_id)
        # TT-4: the new cell is NOT combined. Changing what a class studies in a
        # period is precisely the act that takes it out of a shared lesson, and
        # carrying the combination across would leave 6-A silently attending a
        # Maths meeting it now has Hindi in.
        self.db.add(TimetableSlot(
            org_id=m.org_id, class_id=body.class_id, weekday=body.weekday,
            period_no=body.period_no, slot_type=body.slot_type,
            class_subject_id=cs_id, session_id=session_id,
            effective_from=eff, effective_to=None))
        self.db.flush()
        if old_combined is not None:
            self._settle_combination(m.org_id, old_combined, eff)
        if session_id:
            self._link_block_class(m.org_id, session_id, body.class_id)
            self.db.flush()
        # TT-3: the grid IS the weekly load. Recomputed here rather than left to
        # a nightly job, so the planner can use the new number on the very next
        # request — a teacher who fills her Tuesday expects her plan to move.
        # `set_slots_bulk` routes through this method, so it is covered too.
        recompute_periods_per_week(self.db, m.org_id, [body.class_id])
        return self._grid(m, klass, eff)

    def set_slots_bulk(self, m: CurrentMember, body: SlotBulkIn) -> SlotBulkOut:
        """One block (or subject) across many classes and days in a single call."""
        eff = body.effective_from or self._today(m)
        written = 0
        skipped: list[str] = []
        labels = self._class_labels(m.org_id)
        for class_id in dict.fromkeys(body.class_ids):
            for weekday in dict.fromkeys(body.weekdays):
                try:
                    self.set_slot(m, SlotIn(
                        class_id=class_id, weekday=weekday, period_no=body.period_no,
                        slot_type=body.slot_type, class_subject_id=body.class_subject_id,
                        session_id=body.session_id, effective_from=eff))
                    written += 1
                except (ValidationError, NotFoundError) as exc:
                    skipped.append(f"{labels.get(class_id, '?')} · day {weekday}: {exc.message}")
        return SlotBulkOut(written=written, skipped=skipped)

    def clear_slot(self, m: CurrentMember, body: SlotClearIn) -> GridOut:
        klass = self._class(m.org_id, body.class_id)
        eff = body.effective_from or self._today(m)
        current = self._current_slot(m.org_id, body.class_id, body.weekday, body.period_no)
        if current is None:
            raise NotFoundError("Slot")
        session_id = current.session_id
        combined_id = current.combined_id
        # Closing on its own start date means it never applied — delete it; else close.
        if current.effective_from >= eff:
            self.db.delete(current)
        else:
            current.effective_to = eff
        self.db.flush()
        if session_id:
            self._unlink_block_class_if_unused(m.org_id, session_id, body.class_id)
            self.db.flush()
        if combined_id is not None:
            self._settle_combination(m.org_id, combined_id, eff)
        # Emptying a cell lowers that subject's weekly load by one (TT-3).
        recompute_periods_per_week(self.db, m.org_id, [body.class_id])
        return self._grid(m, klass, eff)

    # ── combining classes into one meeting (TT-4) ────────────────────────────
    def _live_slots_at(self, org_id: uuid.UUID, weekday: int, period_no: int,
                       on_date: date) -> list[TimetableSlot]:
        return list(self.db.scalars(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id, TimetableSlot.weekday == weekday,
                TimetableSlot.period_no == period_no, self._current_at(on_date))))

    def _members_of(self, org_id: uuid.UUID, combined_id: uuid.UUID,
                    on_date: date) -> list[TimetableSlot]:
        return list(self.db.scalars(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id,
                TimetableSlot.combined_id == combined_id,
                self._current_at(on_date))))

    def _restamp(self, slot: TimetableSlot, eff: date,
                 combined_id: uuid.UUID | None) -> None:
        """Move one cell into or out of a combination, append-only.

        A row that has already been live for a while is CLOSED and replaced, so
        the register and the day-book can still answer "was 6-A sitting with 5-A
        in August". A row that has not started applying yet is simply amended —
        there is no history to protect, and closing it at its own start date
        would leave a zero-length row in the grid.
        """
        if slot.combined_id == combined_id:
            return
        if slot.effective_from >= eff:
            slot.combined_id = combined_id
            self.db.flush()
            return
        slot.effective_to = eff
        self.db.add(TimetableSlot(
            org_id=slot.org_id, class_id=slot.class_id, weekday=slot.weekday,
            period_no=slot.period_no, slot_type=slot.slot_type,
            class_subject_id=slot.class_subject_id, session_id=slot.session_id,
            combined_id=combined_id, effective_from=eff, effective_to=None))
        self.db.flush()

    def _settle_combination(self, org_id: uuid.UUID, combined_id: uuid.UUID,
                            eff: date) -> None:
        """A combination of one is not a combination — split the survivor out.

        Called whenever a member cell is cleared or given something else to do.
        Without it, the last class left behind would keep a `combined_id` and go
        on rendering "taught with —", and its clash would stay silenced against
        a partner that no longer exists.

        The `combined_periods` row itself is never deleted: closed slots still
        point at it, and the FK is SET NULL, so deleting it would quietly erase
        the fact from history.
        """
        survivors = self._members_of(org_id, combined_id, eff)
        if len(survivors) >= 2:
            return
        for s in survivors:
            self._restamp(s, eff, None)

    def combine(self, m: CurrentMember, body: CombineIn) -> CombinedOut:
        """"These classes sit together in this period."

        Validated hard, because a combination that is not really one meeting is
        worse than the clash it replaces: it would hide a genuine double-booking
        AND write one teacher's capture into two classes' records.

        Three rules, each with a sentence the admin can act on:
        every named class must actually have this cell filled; every one of them
        must be running a SUBJECT (a block already spans classes on its own — put
        the block on both grids instead); and they must share ONE teacher,
        because "one meeting" means one person standing in one room.
        """
        eff = body.effective_from or self._today(m)
        class_ids = list(dict.fromkeys(body.class_ids))
        if len(class_ids) < 2:
            raise ValidationError("Pick at least two classes to combine.")
        labels = self._class_labels(m.org_id)
        for cid in class_ids:
            if cid not in labels:
                raise NotFoundError("Class")

        live = {s.class_id: s for s in self._live_slots_at(
            m.org_id, body.weekday, body.period_no, eff) if s.class_id in class_ids}
        missing = [labels[c] for c in class_ids if c not in live]
        if missing:
            raise ValidationError(
                f"{', '.join(missing)} has nothing in this period yet — put the "
                f"subject in the cell first, then combine.")

        blocks = [labels[c] for c, s in live.items() if s.slot_type != "subject"]
        if blocks:
            raise ValidationError(
                f"{', '.join(sorted(blocks))} runs a block in this period. A block "
                f"already runs across classes — put the same block on each grid "
                f"instead of combining.")

        cs_meta = self._cs_meta(m.org_id)
        teachers: dict[uuid.UUID | None, list[str]] = {}
        for cid, s in live.items():
            _sname, tmid, _tname = cs_meta.get(s.class_subject_id, (None, None, None))
            teachers.setdefault(tmid, []).append(labels[cid])
        if None in teachers:
            raise ValidationError(
                f"{', '.join(sorted(teachers[None]))} has no teacher on this "
                f"subject. Assign one, then combine.")
        if len(teachers) > 1:
            names = self._member_names(m.org_id, set(teachers))
            named = "; ".join(
                f"{', '.join(sorted(v))} → {names.get(t) or 'another teacher'}"
                for t, v in teachers.items())
            raise ValidationError(
                f"A combined period is one teacher in one room, and these are "
                f"taught by different people ({named}). Give them the same "
                f"teacher first.")

        # Growing an existing combination rather than starting a second one:
        # otherwise adding a third class would leave two combinations at one
        # cell, each silencing half of the clash.
        existing = {s.combined_id for s in live.values() if s.combined_id}
        if len(existing) > 1:
            raise ValidationError(
                "These classes are already in two different combined periods. "
                "Split them first, then combine.")
        if existing:
            combo = self.db.get(CombinedPeriod, next(iter(existing)))
        else:
            combo = CombinedPeriod(org_id=m.org_id, note=body.note)
            self.db.add(combo)
            self.db.flush()
        if body.note is not None:
            combo.note = body.note

        for s in live.values():
            self._restamp(s, eff, combo.id)
        self.db.flush()
        return self._combined_out(m, combo, eff)

    def uncombine(self, m: CurrentMember, body: UncombineIn) -> list[CombinedOut]:
        """Split a combined meeting — one class out of it, or the whole thing."""
        eff = body.effective_from or self._today(m)
        combo = self.db.scalar(select(CombinedPeriod).where(
            CombinedPeriod.id == body.combined_id, CombinedPeriod.org_id == m.org_id))
        if combo is None:
            raise NotFoundError("Combined period")
        members = self._members_of(m.org_id, combo.id, eff)
        if not members:
            return self.list_combinations(m, eff)
        targets = ([s for s in members if s.class_id in set(body.class_ids)]
                   if body.class_ids else members)
        for s in targets:
            self._restamp(s, eff, None)
        self._settle_combination(m.org_id, combo.id, eff)
        return self.list_combinations(m, eff)

    def _combined_out(self, m: CurrentMember, combo: CombinedPeriod,
                      on_date: date, members: list[TimetableSlot] | None = None,
                      cs_meta: dict | None = None,
                      labels: dict[uuid.UUID, str] | None = None) -> CombinedOut:
        members = members if members is not None else self._members_of(
            m.org_id, combo.id, on_date)
        cs_meta = cs_meta if cs_meta is not None else self._cs_meta(m.org_id)
        labels = labels if labels is not None else self._class_labels(m.org_id)
        rows = sorted(members, key=lambda s: labels.get(s.class_id, "?"))
        teacher_id = teacher_name = None
        classes: list[CombinedClassOut] = []
        for s in rows:
            sname, tmid, tname = cs_meta.get(s.class_subject_id, (None, None, None))
            if teacher_id is None:
                teacher_id, teacher_name = tmid, tname
            classes.append(CombinedClassOut(
                class_id=s.class_id, class_label=labels.get(s.class_id, "?"),
                class_subject_id=s.class_subject_id, subject_name=sname))
        return CombinedOut(
            id=combo.id,
            weekday=rows[0].weekday if rows else 0,
            period_no=rows[0].period_no if rows else 0,
            note=combo.note, teacher_member_id=teacher_id, teacher_name=teacher_name,
            classes=classes, label=combined_label([c.class_label for c in classes]))

    def combined_meeting(self, m: CurrentMember, class_id: uuid.UUID, period_no: int,
                         on_date: date) -> CombinedOut | None:
        """The combined meeting this class's period belongs to, if any (TT-4).

        The one lookup every capture surface uses — My Day, the period card, the
        attendance sheet — so "who is in this room" has a single answer.
        """
        slot = self.db.scalar(select(TimetableSlot).where(
            TimetableSlot.org_id == m.org_id, TimetableSlot.class_id == class_id,
            TimetableSlot.weekday == on_date.weekday(),
            TimetableSlot.period_no == period_no,
            TimetableSlot.combined_id.is_not(None),
            self._current_at(on_date)))
        if slot is None:
            return None
        combo = self.db.get(CombinedPeriod, slot.combined_id)
        if combo is None or combo.org_id != m.org_id:
            return None
        members = self._members_of(m.org_id, combo.id, on_date)
        if len(members) < 2:
            return None
        return self._combined_out(m, combo, on_date, members)

    def list_combinations(self, m: CurrentMember,
                          on_date: date | None = None) -> list[CombinedOut]:
        d = on_date or self._today(m)
        slots = [s for s in self._org_slots(m.org_id, d) if s.combined_id]
        if not slots:
            return []
        by_combo: dict[uuid.UUID, list[TimetableSlot]] = {}
        for s in slots:
            by_combo.setdefault(s.combined_id, []).append(s)
        combos = {c.id: c for c in self.db.scalars(
            select(CombinedPeriod).where(CombinedPeriod.id.in_(by_combo)))}
        cs_meta = self._cs_meta(m.org_id)
        labels = self._class_labels(m.org_id)
        out = [self._combined_out(m, combos[cid], d, members, cs_meta, labels)
               for cid, members in by_combo.items() if cid in combos]
        return sorted(out, key=lambda c: (c.weekday, c.period_no, c.label))

    def validate_grid(self, m: CurrentMember, on_date: date | None = None) -> list[Clash]:
        d = on_date or self._today(m)
        return self._clashes(
            self._org_slots(m.org_id, d), self._cs_meta(m.org_id),
            self._class_labels(m.org_id), self._block_meta(m.org_id))

    # ── teacher view (her own week) ──────────────────────────────────────────
    def teacher_week(
        self, m: CurrentMember, member_id: uuid.UUID | None = None, on_date: date | None = None,
    ) -> TeacherWeekOut:
        d = on_date or self._today(m)
        target = member_id or m.membership.id
        year = self._active_year(m.org_id)
        shape = self._shape(year, d)
        weekdays = list(year.working_weekdays) if year else [0, 1, 2, 3, 4, 5]
        cs_meta = self._cs_meta(m.org_id)
        block_meta = self._block_meta(m.org_id)
        class_labels = self._class_labels(m.org_id)
        clock = {p.period_no: (p.start, p.end) for p in shape.periods}

        mine = [
            s for s in self._org_slots(m.org_id, d)
            if any(tmid == target for tmid, _e in self._commitments(s, cs_meta, block_meta))
        ]

        # One row per MEETING (TT-4). A block on twenty classes and a combined
        # lesson on two are each one place this teacher stands, and the whole
        # point of `_commitments` saying so for the clash validator is lost if
        # her own week then draws them twenty and two times. A plain period keys
        # on its own slot id, so it can never merge with anything.
        groups: dict[tuple, list[TimetableSlot]] = {}
        for s in mine:
            if s.slot_type == "block":
                key = (s.weekday, s.period_no, "block", s.session_id)
            elif s.combined_id is not None:
                key = (s.weekday, s.period_no, "combined", s.combined_id)
            else:
                key = (s.weekday, s.period_no, "slot", s.id)
            groups.setdefault(key, []).append(s)

        slots: list[TeacherSlot] = []
        for (weekday, period_no, kind, _key), members in groups.items():
            members = sorted(members, key=lambda s: class_labels.get(s.class_id, "?"))
            first = members[0]
            ids = [s.class_id for s in members]
            names = [class_labels.get(s.class_id, "?") for s in members]
            start, end = clock.get(period_no, ("", ""))
            if kind == "block":
                meta = block_meta.get(first.session_id) if first.session_id else None
                slots.append(TeacherSlot(
                    weekday=weekday, period_no=period_no, class_id=first.class_id,
                    class_label=names[0], slot_type="block",
                    session_id=first.session_id, block_name=meta.name if meta else None,
                    block_kind=meta.kind if meta else None, start=start, end=end,
                    class_ids=ids, class_labels=names))
            else:
                slots.append(TeacherSlot(
                    weekday=weekday, period_no=period_no, class_id=first.class_id,
                    class_label=names[0], slot_type="subject",
                    subject_name=cs_meta.get(first.class_subject_id, (None, None, None))[0],
                    class_subject_id=first.class_subject_id, start=start, end=end,
                    class_ids=ids, class_labels=names,
                    combined_id=first.combined_id))
        slots.sort(key=lambda s: (s.weekday, s.period_no, s.class_label))
        return TeacherWeekOut(
            member_id=target, weekdays=weekdays, periods_per_day=shape.periods_per_day,
            slots=slots,
            periods=[GridPeriod(period_no=p.period_no, start=p.start, end=p.end)
                     for p in shape.periods])

    def _active_year(self, org_id: uuid.UUID) -> AcademicYear | None:
        return self.db.scalar(
            select(AcademicYear).where(
                AcademicYear.org_id == org_id, AcademicYear.is_active.is_(True))
        )

    # ── My Day integration (§5.4 — teacher's periods today) ──────────────────
    def teacher_day(self, m: CurrentMember, on_date: date) -> list[TeacherSlot]:
        week = self.teacher_week(m, on_date=on_date)
        return [s for s in week.slots if s.weekday == on_date.weekday()]

    # ── the bell schedule (TT-2) ─────────────────────────────────────────────
    def _year_by_id(self, org_id: uuid.UUID, year_id: uuid.UUID) -> AcademicYear:
        year = self.db.scalar(
            select(AcademicYear).where(AcademicYear.id == year_id,
                                       AcademicYear.org_id == org_id))
        if year is None:
            raise NotFoundError("Academic year")
        return year

    @staticmethod
    def _bell_out(year_id: uuid.UUID, shape: bell.DayShape) -> BellScheduleOut:
        return BellScheduleOut(
            academic_year_id=year_id, id=shape.schedule_id,
            periods_per_day=shape.periods_per_day,
            entries=[PeriodTime(**e) for e in shape.entries],
            note=shape.note, effective_from=shape.effective_from,
            effective_to=shape.effective_to, has_timings=shape.has_timings)

    def get_bell(self, m: CurrentMember, year_id: uuid.UUID,
                 on_date: date | None = None) -> BellScheduleOut:
        year = self._year_by_id(m.org_id, year_id)
        return self._bell_out(year.id, self._shape(year, on_date or self._today(m)))

    def set_bell(self, m: CurrentMember, body: BellScheduleIn) -> BellScheduleOut:
        year = self._year_by_id(m.org_id, body.academic_year_id)
        eff = body.effective_from or self._today(m)
        entries = [e.model_dump() for e in body.entries]
        row = bell.set_schedule(self.db, m.org_id, year, entries, eff, body.note,
                                today=self._today(m))
        self._close_orphaned_slots(m.org_id, year, row.periods_per_day, eff)
        return self._bell_out(year.id, self._shape(year, eff))

    def _close_orphaned_slots(self, org_id: uuid.UUID, year: AcademicYear,
                              periods_per_day: int, eff: date) -> None:
        """Shortening the day closes the cells that no longer have a period.

        Silently leaving them would be worse: they would stay in the database,
        stay out of every grid (which only draws 1..periods_per_day), and come
        back the day somebody lengthened the day again.
        """
        class_ids = [c.id for c in self.db.scalars(
            select(SchoolClass).where(SchoolClass.org_id == org_id,
                                      SchoolClass.academic_year_id == year.id))]
        if not class_ids:
            return
        orphans = list(self.db.scalars(
            select(TimetableSlot).where(
                TimetableSlot.org_id == org_id,
                TimetableSlot.class_id.in_(class_ids),
                TimetableSlot.period_no > periods_per_day,
                TimetableSlot.effective_to.is_(None))))
        dissolved = {s.combined_id for s in orphans if s.combined_id}
        for s in orphans:
            if s.effective_from >= eff:
                self.db.delete(s)
            else:
                s.effective_to = eff
        if orphans:
            self.db.flush()
            # A shortened day takes whole cells away, so a combination can lose
            # a member here just as surely as through the cell editor (TT-4).
            for combined_id in dissolved:
                self._settle_combination(org_id, combined_id, eff)
            # Shortening the day genuinely removes periods from the week, so
            # the weekly load has to follow it down (TT-3). Missing this would
            # leave the planner pacing against periods the school no longer has.
            recompute_periods_per_week(self.db, org_id, class_ids)

    def bell_history(self, m: CurrentMember, year_id: uuid.UUID) -> BellHistoryOut:
        year = self._year_by_id(m.org_id, year_id)
        rows = bell.history(self.db, year.id)
        return BellHistoryOut(
            academic_year_id=year.id,
            schedules=[
                BellScheduleOut(
                    academic_year_id=year.id, id=r.id, periods_per_day=r.periods_per_day,
                    entries=[PeriodTime(**e) for e in (r.entries or [])], note=r.note,
                    effective_from=r.effective_from, effective_to=r.effective_to,
                    has_timings=any(e.get("start") for e in (r.entries or [])))
                for r in rows
            ])

    # ── legacy period config (kept for the plan page and nine test fixtures) ─
    def get_period_config(self, m: CurrentMember, year_id: uuid.UUID) -> PeriodConfigOut:
        year = self._year_by_id(m.org_id, year_id)
        shape = self._shape(year, self._today(m))
        return PeriodConfigOut(
            academic_year_id=year.id, periods_per_day=shape.periods_per_day,
            period_times=[PeriodTime(**e) for e in shape.entries])

    def set_period_config(self, m: CurrentMember, body: PeriodConfigIn) -> PeriodConfigOut:
        """The pre-TT-2 contract: an explicit period count beside the times.

        Kept because it is how nine test fixtures and the plan page set a school
        up. It writes the same `bell_schedules` row the editor does — one write
        path — but honours the caller's `periods_per_day` even when it disagrees
        with the entries, which the editor never does.
        """
        year = self._year_by_id(m.org_id, body.academic_year_id)
        eff = year.tracking_start_date or year.start_date or self._today(m)
        entries = [pt.model_dump() for pt in body.period_times]
        bell.set_schedule(self.db, m.org_id, year, entries, eff,
                          note=None, periods_per_day=body.periods_per_day,
                          today=self._today(m))
        return self.get_period_config(m, year.id)

    # ── blocks (the non-subject period, TT-2) ────────────────────────────────
    def _block_out(self, s: SessionModel, meta: BlockMeta,
                   roster_counts: dict[uuid.UUID, int],
                   slot_counts: dict[uuid.UUID, int]) -> BlockOut:
        return BlockOut(
            id=s.id, name=s.name, kind=s.kind, kind_label=day_shape.label_for(s.kind),
            category_id=s.category_id, category_name=meta.category_name,
            active=s.active,
            owner_member_id=s.owner_member_id,
            staff_member_ids=list(meta.staff_ids), staff_names=list(meta.staff_names),
            class_ids=[sc.class_id for sc in s.classes],
            roster_count=roster_counts.get(s.id, 0),
            slot_count=slot_counts.get(s.id, 0))

    def _roster_counts(self, org_id: uuid.UUID,
                       sessions: list[SessionModel]) -> dict[uuid.UUID, int]:
        """Roster size per block, batched — the roster is computed, never stored."""
        class_ids = {sc.class_id for s in sessions for sc in s.classes}
        if not class_ids:
            return {s.id: len(s.students) for s in sessions}
        per_class: dict[uuid.UUID, set[uuid.UUID]] = {}
        per_class_cat: dict[tuple[uuid.UUID, uuid.UUID], set[uuid.UUID]] = {}
        for class_id, student_id, cat_id in self.db.execute(
                select(Student.class_id, Student.id, Student.category_id)
                .where(Student.org_id == org_id, Student.class_id.in_(class_ids),
                       Student.status == "active")):
            per_class.setdefault(class_id, set()).add(student_id)
            if cat_id:
                per_class_cat.setdefault((cat_id, class_id), set()).add(student_id)
        out: dict[uuid.UUID, int] = {}
        for s in sessions:
            ids = {ss.student_id for ss in s.students}
            for sc in s.classes:
                ids |= (per_class_cat.get((s.category_id, sc.class_id), set())
                        if s.category_id else per_class.get(sc.class_id, set()))
            out[s.id] = len(ids)
        return out

    def _slot_counts(self, org_id: uuid.UUID) -> dict[uuid.UUID, int]:
        rows = self.db.execute(
            select(TimetableSlot.session_id, func.count(TimetableSlot.id))
            .where(TimetableSlot.org_id == org_id,
                   TimetableSlot.session_id.is_not(None),
                   TimetableSlot.effective_to.is_(None))
            .group_by(TimetableSlot.session_id)).all()
        return dict(rows)

    def list_blocks(self, m: CurrentMember) -> list[BlockOut]:
        sessions = list(self.db.scalars(
            select(SessionModel).where(SessionModel.org_id == m.org_id)
            .options(selectinload(SessionModel.students),
                     selectinload(SessionModel.classes))
            .order_by(SessionModel.name)))
        meta = self._block_meta(m.org_id)
        rosters = self._roster_counts(m.org_id, sessions)
        slots = self._slot_counts(m.org_id)
        return [self._block_out(s, meta[s.id], rosters, slots) for s in sessions]

    def _resolve_owner(self, m: CurrentMember, owner_member_id: uuid.UUID | None) -> uuid.UUID:
        if owner_member_id is None:
            return m.membership.id
        owner = self.db.scalar(select(Membership).where(
            Membership.id == owner_member_id, Membership.org_id == m.org_id,
            Membership.status == "active"))
        if owner is None:
            raise NotFoundError("Member")
        return owner.id

    def _set_block_staff(self, m: CurrentMember, s: SessionModel,
                         member_ids: list[uuid.UUID]) -> None:
        s.staff.clear()
        self.db.flush()
        for mid in dict.fromkeys(member_ids):
            ok = self.db.scalar(select(Membership.id).where(
                Membership.id == mid, Membership.org_id == m.org_id,
                Membership.status == "active"))
            if ok:
                self.db.add(SessionStaff(org_id=m.org_id, session_id=s.id, member_id=mid))

    def _set_block_classes(self, m: CurrentMember, s: SessionModel,
                           class_ids: list[uuid.UUID]) -> None:
        s.classes.clear()
        self.db.flush()
        for cid in dict.fromkeys(class_ids):
            ok = self.db.scalar(select(SchoolClass.id).where(
                SchoolClass.id == cid, SchoolClass.org_id == m.org_id))
            if ok:
                self.db.add(SessionClass(org_id=m.org_id, session_id=s.id, class_id=cid))

    def create_block(self, m: CurrentMember, body: BlockIn) -> BlockOut:
        s = SessionModel(
            org_id=m.org_id, name=body.name, kind=body.kind,
            owner_member_id=self._resolve_owner(m, body.owner_member_id),
            category_id=body.category_id,
            # `D-113` — a block placed on the grid takes its schedule from the
            # grid. It gets no weekdays or clock of its own.
            weekdays=[], time=None, end_time=None)
        self.db.add(s)
        self.db.flush()
        self._set_block_staff(m, s, body.staff_member_ids)
        self._set_block_classes(m, s, body.class_ids)
        self.db.flush()
        self.db.refresh(s)
        return self.get_block(m, s.id)

    def _block(self, org_id: uuid.UUID, block_id: uuid.UUID) -> SessionModel:
        s = self.db.scalar(
            select(SessionModel).where(SessionModel.id == block_id,
                                       SessionModel.org_id == org_id)
            .options(selectinload(SessionModel.students),
                     selectinload(SessionModel.classes),
                     selectinload(SessionModel.staff)))
        if s is None:
            raise NotFoundError("Block")
        return s

    def get_block(self, m: CurrentMember, block_id: uuid.UUID) -> BlockOut:
        s = self._block(m.org_id, block_id)
        meta = self._block_meta(m.org_id)
        return self._block_out(s, meta[s.id],
                               self._roster_counts(m.org_id, [s]),
                               self._slot_counts(m.org_id))

    def update_block(self, m: CurrentMember, block_id: uuid.UUID,
                     body: BlockUpdate) -> BlockOut:
        s = self._block(m.org_id, block_id)
        if body.owner_member_id is not None:
            s.owner_member_id = self._resolve_owner(m, body.owner_member_id)
        for field in ("name", "kind", "active"):
            v = getattr(body, field)
            if v is not None:
                setattr(s, field, v)
        # NULL is meaningful here — it reopens the block to the whole class.
        if "category_id" in body.model_fields_set:
            s.category_id = body.category_id
        if body.staff_member_ids is not None:
            self._set_block_staff(m, s, body.staff_member_ids)
        if body.class_ids is not None:
            self._set_block_classes(m, s, body.class_ids)
        self.db.flush()
        return self.get_block(m, block_id)

    def delete_block(self, m: CurrentMember, block_id: uuid.UUID) -> None:
        """Archive rather than delete once it has been on a timetable.

        `timetable_slots.session_id` is SET NULL on delete, so a hard delete would
        leave historical block cells pointing at nothing and rendering as
        "(removed block)" forever. A block that never made it onto the grid has
        no history to protect and is genuinely deleted.
        """
        s = self._block(m.org_id, block_id)
        used = self.db.scalar(select(func.count(TimetableSlot.id)).where(
            TimetableSlot.org_id == m.org_id, TimetableSlot.session_id == block_id))
        if used:
            s.active = False
            live = list(self.db.scalars(select(TimetableSlot).where(
                TimetableSlot.org_id == m.org_id, TimetableSlot.session_id == block_id,
                TimetableSlot.effective_to.is_(None))))
            today = self._today(m)
            for slot in live:
                if slot.effective_from >= today:
                    self.db.delete(slot)
                else:
                    slot.effective_to = today
            self.db.flush()
            return
        self.db.delete(s)
        self.db.flush()

    def may_take_block(self, m: CurrentMember, session_id: uuid.UUID) -> bool:
        """Is this member on the block's staff (or its owner, or an admin)?"""
        if m.is_coordinator_up:
            return True
        s = self.db.scalar(select(SessionModel).where(
            SessionModel.id == session_id, SessionModel.org_id == m.org_id))
        if s is None:
            return False
        if s.owner_member_id == m.membership.id:
            return True
        return bool(self.db.scalar(select(SessionStaff.id).where(
            SessionStaff.session_id == session_id,
            SessionStaff.member_id == m.membership.id)))

    def assert_may_take_block(self, m: CurrentMember, session_id: uuid.UUID) -> None:
        if not self.may_take_block(m, session_id):
            raise ForbiddenError("You are not on this block's staff.",
                                 code="not_your_block")

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
        shape = self._shape(year, self._today(m))
        subjects = self._parsed_subjects(m.org_id, class_id)
        if not subjects:
            raise ValidationError("Add subjects to this class before importing a timetable.")
        source, cells = parse_timetable(
            subjects, periods_per_day=shape.periods_per_day,
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
                slot_type="subject", class_subject_id=cell.class_subject_id,
                effective_from=eff))
        return self._grid(m, klass, eff)

    # ── whole-school generation (deterministic — the wizard's heavy lifting) ──
    def generate_year_grid(self, m: CurrentMember, body: OrgGenerateIn) -> OrgGenerateOut:
        """Fill EVERY class of the year in one pass, honouring each subject's
        periods_per_week and never double-booking a teacher. Greedy, deterministic
        (same inputs → same grid), and honest: demand it cannot place is reported
        in `unplaced`, never squeezed in as a clash.

        Preview by default; `apply=True` replaces the year's live *subject* grid
        append-only. Blocks are left exactly alone — the generator knows nothing
        about the homework class, and wiping the admin's 15:30 block because they
        regenerated the morning would be the worst kind of surprise."""
        year = self.db.scalar(select(AcademicYear).where(
            AcademicYear.id == body.academic_year_id, AcademicYear.org_id == m.org_id))
        if year is None:
            raise NotFoundError("Academic year")
        eff = body.effective_from or self._today(m)
        shape = self._shape(year, eff)
        classes = list(self.db.scalars(
            select(SchoolClass).where(
                SchoolClass.org_id == m.org_id,
                SchoolClass.academic_year_id == year.id)
            .order_by(SchoolClass.name, SchoolClass.section)))
        if not classes:
            raise ValidationError("This year has no classes yet.")
        weekdays = list(year.working_weekdays or [])
        ppd = shape.periods_per_day
        if not weekdays or not ppd:
            raise ValidationError("Set working weekdays and periods/day first.")

        cs_meta = self._cs_meta(m.org_id)
        block_meta = self._block_meta(m.org_id)
        class_ids = {k.id for k in classes}
        live = self._org_slots(m.org_id, eff)
        # Teachers stay honest across years: live slots of classes we are NOT
        # regenerating still occupy their teachers — and so do blocks, whichever
        # class they sit on.
        busy: set[tuple[int, int, uuid.UUID]] = set()
        for s in live:
            if s.slot_type == "subject" and s.class_id in class_ids:
                continue  # this is what we are replacing
            # Same rule as the clash banner: a block is a pool, so being on its
            # staff does not make this teacher unavailable. Treating it as busy
            # here would refuse to place real subject demand around a games
            # period four other people could take.
            if not counts_as_clash(s):
                continue
            for tmid, _e in self._commitments(s, cs_meta, block_meta):
                busy.add((s.weekday, s.period_no, tmid))
        # Cells already held by a block are not the generator's to fill.
        taken: set[tuple[uuid.UUID, int, int]] = {
            (s.class_id, s.weekday, s.period_no) for s in live if s.slot_type == "block"}

        cells: list[OrgDraftCell] = []
        unplaced: list[OrgDraftIssue] = []
        skipped: list[OrgDraftIssue] = []
        for klass in classes:
            label = _label(klass)
            subs = self._parsed_subjects(m.org_id, klass.id)
            demand: dict[uuid.UUID, int] = {}
            names: dict[uuid.UUID, str] = {}
            for s in subs:
                names[s.class_subject_id] = s.subject_name
                if s.periods_per_week > 0:
                    demand[s.class_subject_id] = s.periods_per_week
                else:
                    skipped.append(OrgDraftIssue(
                        class_label=label, subject_name=s.subject_name,
                        detail="0 periods/week — set the class allocation first"))
            teacher_of = {cs: cs_meta.get(cs, (None, None, None))[1] for cs in demand}
            # Spread cap: a 6-period subject on a 6-day week lands once a day.
            cap_per_day = {cs: max(1, -(-ppw // len(weekdays))) for cs, ppw in demand.items()}
            day_count: dict[tuple[int, uuid.UUID], int] = {}

            for wd in weekdays:
                for p in range(1, ppd + 1):
                    if (klass.id, wd, p) in taken:
                        continue
                    ranked = sorted(
                        (
                            # Prefer subjects still under their daily cap, then the
                            # most-starved; name breaks ties deterministically.
                            (0 if day_count.get((wd, cs), 0) < cap_per_day[cs] else 1,
                             -rem, names[cs], cs)
                            for cs, rem in demand.items()
                            if rem > 0 and (
                                teacher_of[cs] is None
                                or (wd, p, teacher_of[cs]) not in busy)
                        )
                    )
                    if not ranked:
                        continue
                    cs = ranked[0][3]
                    demand[cs] -= 1
                    day_count[wd, cs] = day_count.get((wd, cs), 0) + 1
                    if teacher_of[cs] is not None:
                        busy.add((wd, p, teacher_of[cs]))
                    cells.append(OrgDraftCell(
                        class_id=klass.id, class_label=label, weekday=wd, period_no=p,
                        class_subject_id=cs, subject_name=names[cs]))

            for cs, rem in demand.items():
                if rem > 0:
                    unplaced.append(OrgDraftIssue(
                        class_label=label, subject_name=names[cs],
                        detail=f"{rem} period(s) not placed — the teacher is busy "
                               f"elsewhere or the week is full"))

        if body.apply:
            dissolved: set[uuid.UUID] = set()
            for s in live:
                if s.class_id not in class_ids or s.slot_type == "block":
                    continue
                if s.combined_id:
                    dissolved.add(s.combined_id)
                if s.effective_from >= eff:
                    self.db.delete(s)
                else:
                    s.effective_to = eff
            self.db.flush()
            # Regenerating the year rebuilds every subject cell from scratch, so
            # any combination those cells were in is gone with them (TT-4). The
            # generator knows nothing about shared lessons; leaving the ids on
            # would have the new grid claim arrangements nobody asked for.
            for combined_id in dissolved:
                self._settle_combination(m.org_id, combined_id, eff)
            for c in cells:
                self.db.add(TimetableSlot(
                    org_id=m.org_id, class_id=c.class_id, weekday=c.weekday,
                    period_no=c.period_no, slot_type="subject",
                    class_subject_id=c.class_subject_id,
                    effective_from=eff, effective_to=None))
            self.db.flush()
            # A whole-school grid replaces every class's week at once (TT-3).
            recompute_periods_per_week(self.db, m.org_id, class_ids)

        return OrgGenerateOut(
            academic_year_id=year.id, classes=len(classes), cells=cells,
            unplaced=unplaced, skipped=skipped, applied=body.apply)

    # ── assisted draft (flag-gated, NOT a guaranteed solver) ─────────────────
    def assisted_draft(self, m: CurrentMember, class_id: uuid.UUID) -> DraftOut:
        klass = self._class(m.org_id, class_id)
        if not settings.TIMETABLE_ASSISTED_DRAFT:
            return DraftOut(
                class_id=class_id, enabled=False,
                message="Assisted timetable draft is disabled. Enable TIMETABLE_ASSISTED_DRAFT to pilot it.")
        year = self._year(klass)
        shape = self._shape(year, self._today(m))
        subjects = self._parsed_subjects(m.org_id, class_id)
        # Proposer: round-robin fill, then validator over the whole org grid to flag
        # teacher clashes with other classes. Repair is left to the admin (drag).
        source, cells = parse_timetable(
            subjects, periods_per_day=shape.periods_per_day,
            weekdays=list(year.working_weekdays))
        # Validate the proposed cells against existing OTHER-class current slots.
        cs_meta = self._cs_meta(m.org_id)
        block_meta = self._block_meta(m.org_id)
        class_labels = self._class_labels(m.org_id)
        other = [s for s in self._org_slots(m.org_id, self._today(m)) if s.class_id != class_id]
        proposed = [
            TimetableSlot(
                org_id=m.org_id, class_id=class_id, weekday=c["weekday"],
                period_no=c["period_no"], slot_type="subject",
                class_subject_id=c["class_subject_id"],
                effective_from=self._today(m))
            for c in cells
        ]
        clashes = self._clashes(other + proposed, cs_meta, class_labels, block_meta,
                                only_class=class_id)
        unresolved = [
            f"{cl.class_labels} share a teacher on weekday {cl.weekday} period {cl.period_no}"
            for cl in clashes
        ]
        return DraftOut(
            class_id=class_id, enabled=True, cells=[ImportCell(**c) for c in cells],
            clashes=clashes, unresolved=unresolved,
            message="Draft ready — review and adjust, then confirm to apply.")
