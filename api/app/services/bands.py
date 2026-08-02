"""The support programme (V1-9) — bands, descriptors, promotion and ownership.

Every band read and write lives here. Before V1-9 they were spread through
`AssessmentService` in four methods that each filtered `scope_skill_area_id IS
NULL` — the *overall* row — which is the shape `D-75` retires.

What this service is responsible for, in the order a school meets it:

    descriptors     what a B child in English can do (`D-69`), per subject,
                    shipped pre-written, carrying that subject's threshold
    class_board     assess a class for ONE subject — the test's marks pre-fill
                    every row and the teacher moves only what she disagrees
                    with (`Q-79`); the by-hand route is the school with no test
    file_bands      ENTRY (`S-185`): append rows, each naming its source
    promote         MOVEMENT (`D-76`): a locked test the teacher chooses, with
                    the moves shown for review before they commit (`Q-81`)
    programme       the admin's board — **movement is the headline** (`D-67`),
                    the distribution goes under More (`S-169`)

Two rules that are easy to lose and expensive to lose:

* **Not assessed is a word**, never a C and never a zero. A child absent for the
  band test keeps whatever band he had.
* **`student_bands` is append-only** (law 3) — which is exactly why a re-band
  shows its moves first: a mistake is permanent in a child's history, and the
  only correction is another row saying he moved back.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.bands import (
    DEFAULT_A_MIN,
    DEFAULT_B_MIN,
    SOURCE_OBSERVATION,
    SOURCE_TEST,
    TIERS,
    Placement,
    chip,
    movement,
    size_warnings,
    starter_descriptors,
    tier_for,
)
from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AssessmentCycle,
    AssessmentScore,
    BandDescriptor,
    ClassSubject,
    Intervention,
    Membership,
    Organization,
    SchoolClass,
    Student,
    StudentBand,
    Subject,
    SupportCheckpoint,
    Term,
    User,
)
from app.schemas.bands import (
    AssessRow,
    BandClassBoard,
    BandDescriptorOut,
    BandFileIn,
    BandMoveRow,
    BandPromotePreview,
    BandSubjectSetup,
    ProgrammeBoard,
    ProgrammeGridCell,
    ProgrammeRow,
)


def _label(k: SchoolClass) -> str:
    return f"{k.name}-{k.section}" if k.section else k.name


class BandService:
    def __init__(self, db: Session):
        self.db = db

    # ── setup: monitored subjects + descriptors (D-68 / D-69 / D-74) ─────────
    def setup(self, m: CurrentMember) -> list[BandSubjectSetup]:
        """Every subject, with its monitored flag and its three descriptors.

        Descriptors are seeded **on first read of a monitored subject** — a
        school that turns English on gets three editable sentences, not three
        empty boxes it will never fill (`S-175`)."""
        subjects = list(self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id).order_by(Subject.name)))
        monitored = [s for s in subjects if s.band_monitored]
        if monitored:
            self._ensure_descriptors(m, monitored)
        rows = self._descriptor_rows(m)
        out: list[BandSubjectSetup] = []
        for s in subjects:
            mine = sorted(rows.get(s.id, []), key=lambda d: TIERS.index(d.tier))
            out.append(BandSubjectSetup(
                subject_id=s.id, subject_name=s.name, monitored=s.band_monitored,
                descriptors=[BandDescriptorOut(
                    id=d.id, subject_id=s.id, subject_name=s.name, tier=d.tier,
                    text=d.text, min_pct=d.min_pct) for d in mine]))
        return out

    def _descriptor_rows(self, m: CurrentMember) -> dict[uuid.UUID, list[BandDescriptor]]:
        out: dict[uuid.UUID, list[BandDescriptor]] = defaultdict(list)
        for d in self.db.scalars(select(BandDescriptor).where(
                BandDescriptor.org_id == m.org_id)):
            out[d.subject_id].append(d)
        return out

    def _ensure_descriptors(self, m: CurrentMember, subjects: list[Subject]) -> None:
        have = self._descriptor_rows(m)
        org = self.db.get(Organization, m.org_id)
        for s in subjects:
            existing = {d.tier for d in have.get(s.id, [])}
            if existing >= set(TIERS):
                continue
            texts = starter_descriptors(s.name)
            for tier in TIERS:
                if tier in existing:
                    continue
                self.db.add(BandDescriptor(
                    org_id=m.org_id, subject_id=s.id, tier=tier, text=texts[tier],
                    # The old org-wide pair becomes each subject's starting
                    # point, so nothing a school already configured is lost.
                    min_pct=(org.band_a_min if tier == "A"
                             else org.band_b_min if tier == "B" else None)))
        self.db.flush()

    def set_monitored(self, m: CurrentMember, subject_ids: list[uuid.UUID]) -> list[BandSubjectSetup]:
        wanted = set(subject_ids)
        subjects = list(self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id)))
        for s in subjects:
            s.band_monitored = s.id in wanted
        self.db.flush()
        self._ensure_descriptors(m, [s for s in subjects if s.band_monitored])
        return self.setup(m)

    def update_descriptor(self, m: CurrentMember, descriptor_id: uuid.UUID,
                          text: str | None, min_pct: int | None) -> BandDescriptorOut:
        d = self.db.scalar(select(BandDescriptor).where(
            BandDescriptor.id == descriptor_id, BandDescriptor.org_id == m.org_id))
        if d is None:
            raise NotFoundError("Descriptor")
        if text is not None:
            d.text = text.strip()
        if min_pct is not None:
            if d.tier == "C":
                raise ValidationError(
                    "C is 'below B' — it has no threshold of its own.", code="c_has_no_threshold")
            d.min_pct = min_pct
        self.db.flush()
        subject = self.db.get(Subject, d.subject_id)
        self._assert_thresholds_ordered(m, d.subject_id)
        return BandDescriptorOut(id=d.id, subject_id=d.subject_id, subject_name=subject.name,
                                 tier=d.tier, text=d.text, min_pct=d.min_pct)

    def _assert_thresholds_ordered(self, m: CurrentMember, subject_id: uuid.UUID) -> None:
        a, b = self.thresholds(m).get(subject_id, (DEFAULT_A_MIN, DEFAULT_B_MIN))
        if b >= a:
            raise ValidationError("The B threshold must be below the A threshold.",
                                  code="thresholds_out_of_order")

    def thresholds(self, m: CurrentMember) -> dict[uuid.UUID, tuple[int, int]]:
        """subject → (a_min, b_min) (`D-74`). A subject nobody configured falls
        back to the org pair, so nothing breaks the day a school adds one."""
        org = self.db.get(Organization, m.org_id)
        out: dict[uuid.UUID, list[int]] = {}
        for d in self.db.scalars(select(BandDescriptor).where(
                BandDescriptor.org_id == m.org_id, BandDescriptor.min_pct.is_not(None))):
            pair = out.setdefault(d.subject_id, [org.band_a_min, org.band_b_min])
            if d.tier == "A":
                pair[0] = d.min_pct
            elif d.tier == "B":
                pair[1] = d.min_pct
        return {k: (v[0], v[1]) for k, v in out.items()}

    def descriptor_text(self, m: CurrentMember) -> dict[tuple[uuid.UUID, str], str]:
        return {(d.subject_id, d.tier): d.text for d in self.db.scalars(
            select(BandDescriptor).where(BandDescriptor.org_id == m.org_id))}

    def monitored_subjects(self, m: CurrentMember) -> list[Subject]:
        return list(self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id,
                                  Subject.band_monitored.is_(True))
            .order_by(Subject.name)))

    # ── the per-subject read path (D-75 / S-173) ─────────────────────────────
    def placements(self, m: CurrentMember, student_ids: list[uuid.UUID],
                   term_id: uuid.UUID | None = None,
                   ) -> dict[uuid.UUID, list[Placement]]:
        """student → their current band **in each subject**, batched.

        Newest row per (student, subject) wins. Legacy rows with no subject —
        the retired overall letter — are ignored here and survive only in the
        history, because two definitions of "Kabir's band" is the defect this
        packet removes."""
        if not student_ids:
            return {}
        q = (select(StudentBand).where(
            StudentBand.org_id == m.org_id,
            StudentBand.student_id.in_(student_ids),
            StudentBand.subject_id.is_not(None))
            .order_by(StudentBand.created_at.desc()))
        if term_id:
            q = q.where(StudentBand.term_id == term_id)
        names = {s.id: s.name for s in self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id))}
        texts = self.descriptor_text(m)

        seen: set[tuple[uuid.UUID, uuid.UUID]] = set()
        out: dict[uuid.UUID, list[Placement]] = defaultdict(list)
        for b in self.db.scalars(q):
            key = (b.student_id, b.subject_id)
            if key in seen:
                continue
            seen.add(key)
            out[b.student_id].append(Placement(
                subject_id=b.subject_id, subject_name=names.get(b.subject_id, "?"),
                tier=b.tier, descriptor=texts.get((b.subject_id, b.tier)),
                source=b.source))
        for placements in out.values():
            placements.sort(key=lambda p: p.subject_name)
        return out

    def chip_map(self, m: CurrentMember) -> dict[str, str]:
        """student → **"C · Hindi"** for staff directory chips (`S-186`, P4).

        One query for the org. Never an average, never a bare letter."""
        sids = list(self.db.scalars(select(Student.id).where(Student.org_id == m.org_id)))
        return {str(sid): text for sid, places in self.placements(m, sids).items()
                if (text := chip(places))}

    def tier_map_for_subject(self, org_id: uuid.UUID, student_ids: list[uuid.UUID],
                             subject_id: uuid.UUID) -> dict[uuid.UUID, str]:
        """student → tier **in this subject** — what the daily-check generator
        needs, and the reason `D-75` makes the checks more accurate for free:
        the English period now hands the easier route to the children who cannot
        read, instead of to whoever the blended letter happened to catch."""
        if not student_ids:
            return {}
        out: dict[uuid.UUID, str] = {}
        for b in self.db.scalars(
                select(StudentBand).where(
                    StudentBand.org_id == org_id,
                    StudentBand.student_id.in_(student_ids),
                    StudentBand.subject_id == subject_id)
                .order_by(StudentBand.created_at.desc())):
            out.setdefault(b.student_id, b.tier)
        return out

    # ── assess a class, for one subject (D-70 / Q-79) ────────────────────────
    def class_board(self, m: CurrentMember, class_id: uuid.UUID, subject_id: uuid.UUID,
                    cycle_id: uuid.UUID | None = None,
                    term_id: uuid.UUID | None = None) -> BandClassBoard:
        klass = self.db.scalar(select(SchoolClass).where(
            SchoolClass.id == class_id, SchoolClass.org_id == m.org_id))
        if klass is None:
            raise NotFoundError("Class")
        subject = self.db.scalar(select(Subject).where(
            Subject.id == subject_id, Subject.org_id == m.org_id))
        if subject is None:
            raise NotFoundError("Subject")

        students = list(self.db.scalars(select(Student).where(
            Student.org_id == m.org_id, Student.class_id == class_id,
            Student.status == "active").order_by(Student.full_name)))
        sids = [s.id for s in students]
        current = {sid: next((p for p in places if p.subject_id == subject_id), None)
                   for sid, places in self.placements(m, sids, term_id).items()}

        a_min, b_min = self.thresholds(m).get(subject_id, (DEFAULT_A_MIN, DEFAULT_B_MIN))
        pcts: dict[uuid.UUID, float] = {}
        cycle = None
        if cycle_id:
            cycle = self._cycle(m, cycle_id)
            pcts = self._cycle_pcts(m, cycle, subject_id)

        texts = self.descriptor_text(m)
        rows = [AssessRow(
            student_id=st.id, full_name=st.full_name, roll_no=st.roll_no,
            current_tier=(current.get(st.id).tier if current.get(st.id) else None),
            pct=round(pcts[st.id] * 100, 1) if st.id in pcts else None,
            # Not assessed is a WORD: a child absent for the test gets no
            # suggestion at all rather than a C by default (ux §5).
            suggested_tier=tier_for(pcts.get(st.id), a_min, b_min)) for st in students]

        return BandClassBoard(
            class_id=class_id, class_label=_label(klass), subject_id=subject_id,
            subject_name=subject.name, term_id=term_id,
            a_min=a_min, b_min=b_min,
            cycle_id=cycle.id if cycle else None,
            cycle_name=cycle.name if cycle else None,
            descriptors=[BandDescriptorOut(
                id=None, subject_id=subject_id, subject_name=subject.name, tier=t,
                text=texts.get((subject_id, t), ""), min_pct=None) for t in TIERS],
            rows=rows)

    def _cycle(self, m: CurrentMember, cycle_id: uuid.UUID) -> AssessmentCycle:
        c = self.db.scalar(select(AssessmentCycle).where(
            AssessmentCycle.id == cycle_id, AssessmentCycle.org_id == m.org_id))
        if c is None:
            raise NotFoundError("Exam")
        return c

    def _cycle_pcts(self, m: CurrentMember, cycle: AssessmentCycle,
                    subject_id: uuid.UUID | None) -> dict[uuid.UUID, float]:
        """student → fraction scored in this cycle, for one subject."""
        q = select(AssessmentScore).where(
            AssessmentScore.org_id == m.org_id, AssessmentScore.cycle_id == cycle.id)
        if subject_id is not None:
            q = q.where(AssessmentScore.subject_id == subject_id)
        totals: dict[uuid.UUID, list[float]] = {}
        for sc in self.db.scalars(q):
            pair = totals.setdefault(sc.student_id, [0.0, 0.0])
            pair[0] += float(sc.score)
            pair[1] += float(sc.max_score)
        return {sid: p[0] / p[1] for sid, p in totals.items() if p[1]}

    def file_bands(self, m: CurrentMember, body: BandFileIn) -> int:
        """**Entry** (`S-185`): file a whole class into A/B/C for one subject.

        The one screen in the product that legitimately touches every child in a
        class — and it does not break P1v2, whose budget rule is about *daily*
        capture. Append-only: re-filing appends, it never overwrites, and each
        row carries its source so the history explains itself (`D-70`)."""
        if body.source not in (SOURCE_TEST, SOURCE_OBSERVATION):
            raise ValidationError("Unknown assessment source.")
        if not self.db.scalar(select(Term.id).where(
                Term.id == body.term_id, Term.org_id == m.org_id)):
            raise NotFoundError("Term")
        roster = set(self.db.scalars(select(Student.id).where(
            Student.org_id == m.org_id, Student.class_id == body.class_id)))
        current = self.placements(m, list(roster), body.term_id)
        note = body.note or (
            f"band test: {self._cycle(m, body.cycle_id).name}" if body.cycle_id
            else f"teacher assessment: {m.user.name}" if getattr(m, "user", None)
            else "teacher assessment")

        applied = 0
        for row in body.rows:
            if row.student_id not in roster:
                raise ValidationError("A row points at a student outside this class.",
                                      code="not_in_class")
            if row.tier is None:      # not assessed — never written as a band
                continue
            existing = next((p for p in current.get(row.student_id, [])
                             if p.subject_id == body.subject_id), None)
            if existing and existing.tier == row.tier:
                continue
            self.db.add(StudentBand(
                org_id=m.org_id, student_id=row.student_id, term_id=body.term_id,
                subject_id=body.subject_id, tier=row.tier, source=body.source,
                cycle_id=body.cycle_id, set_by=m.user_id, note=note))
            applied += 1
        self.db.flush()
        return applied

    # ── movement: promote a test (D-76 / S-182 / S-184 / S-187 / Q-81) ───────
    def promote_preview(self, m: CurrentMember, cycle_id: uuid.UUID) -> BandPromotePreview:
        """*"Use this as the band test."* Shows the moves **before** they commit
        (`Q-81`): `student_bands` is append-only, so a mistaken re-band is
        permanent in a child's record, and a child slipping B → C is the most
        consequential thing this module ever does."""
        c = self._cycle(m, cycle_id)
        out = BandPromotePreview(
            cycle_id=c.id, name=c.name, date=c.date,
            total_marks=float(c.total_marks) if c.total_marks is not None else None,
            locked=c.locked_at is not None,
            already_promoted=c.band_promoted_at is not None)
        if c.class_id is None or c.subject_id is None:
            out.blocked = "A band test has to be one class and one subject."
            return out
        subject = self.db.get(Subject, c.subject_id)
        klass = self.db.get(SchoolClass, c.class_id)
        out.subject_id, out.subject_name = c.subject_id, subject.name
        out.class_id, out.class_label = c.class_id, _label(klass)
        if not subject.band_monitored:
            out.blocked = f"{subject.name} is not part of the support programme."
            return out
        # `S-184`/`D-53`: an unverified transcription must not move a child
        # between support tiers.
        if c.locked_at is None:
            out.blocked = "Verify and lock the marks first — an unlocked exam can still change."
            return out

        students = list(self.db.scalars(select(Student).where(
            Student.org_id == m.org_id, Student.class_id == c.class_id,
            Student.status == "active").order_by(Student.full_name)))
        sids = [s.id for s in students]
        pcts = self._cycle_pcts(m, c, c.subject_id)
        a_min, b_min = self.thresholds(m).get(c.subject_id, (DEFAULT_A_MIN, DEFAULT_B_MIN))
        current = self.placements(m, sids, c.term_id)

        out.roster, out.sat = len(students), len(pcts)
        out.warnings = size_warnings(out.total_marks, out.sat, out.roster)
        for st in students:
            if st.id not in pcts:
                out.not_sat += 1     # keeps their band — never re-banded to C
                continue
            before = next((p.tier for p in current.get(st.id, [])
                           if p.subject_id == c.subject_id), None)
            after = tier_for(pcts[st.id], a_min, b_min)
            move = movement(before, after)
            if move == "same":
                out.unchanged += 1
                continue
            out.moves.append(BandMoveRow(
                student_id=st.id, full_name=st.full_name, from_tier=before,
                to_tier=after, pct=round(pcts[st.id] * 100, 1), direction=move))
        out.moves.sort(key=lambda r: (r.direction != "down", r.full_name))
        return out

    def promote(self, m: CurrentMember, cycle_id: uuid.UUID) -> BandPromotePreview:
        """Commit the preview. A **flag, never a type change** (`S-182`): the
        exam stays a slip test in every roll-up that counts slip tests."""
        preview = self.promote_preview(m, cycle_id)
        if preview.blocked:
            raise ValidationError(preview.blocked, code="cannot_promote")
        c = self._cycle(m, cycle_id)
        texts = self.descriptor_text(m)
        for row in preview.moves:
            self.db.add(StudentBand(
                org_id=m.org_id, student_id=row.student_id, term_id=c.term_id,
                subject_id=c.subject_id, tier=row.to_tier, source=SOURCE_TEST,
                cycle_id=c.id, set_by=m.user_id,
                note=f"band test: {c.name} ({row.pct:g}%)"))
        c.band_promoted_at = datetime.now(UTC)
        c.band_promoted_by = m.membership.id
        self.db.flush()
        preview.applied = len(preview.moves)
        preview.already_promoted = True
        # The descriptor rides back so the confirmation can say what the new
        # band MEANS, not just which letter it is (`S-166`).
        preview.descriptor = texts.get((c.subject_id, "C"))
        return preview

    # ── the admin's programme board (D-73 / S-169 / S-188) ───────────────────
    def programme(self, m: CurrentMember, term_id: uuid.UUID | None = None) -> ProgrammeBoard:
        """**Movement is the headline** (`D-67`). A distribution donut is a
        photograph of a decision already made and looks identical in a school
        where nobody has moved for a year — it goes under More."""
        term = self._term(m, term_id)
        subjects = self.monitored_subjects(m)
        out = ProgrammeBoard(term_id=term.id if term else None,
                             term_name=term.name if term else None,
                             subjects=[s.name for s in subjects])
        if term is None or not subjects:
            out.headline = ("Turn on the subjects you want to monitor in Setup → Bands."
                            if not subjects else "No term is running.")
            return out
        subject_ids = [s.id for s in subjects]
        names = {s.id: s.name for s in subjects}

        classes = list(self.db.scalars(select(SchoolClass).where(
            SchoolClass.org_id == m.org_id).order_by(SchoolClass.name, SchoolClass.section)))
        class_of = {}
        for st_id, cls_id in self.db.execute(select(Student.id, Student.class_id).where(
                Student.org_id == m.org_id, Student.status == "active")).all():
            class_of[st_id] = cls_id

        # Every band row this term, newest first — one query for the school.
        rows = list(self.db.scalars(
            select(StudentBand).where(
                StudentBand.org_id == m.org_id, StudentBand.term_id == term.id,
                StudentBand.subject_id.in_(subject_ids))
            .order_by(StudentBand.created_at)))
        # (student, subject) → the sequence of tiers this term.
        seq: dict[tuple[uuid.UUID, uuid.UUID], list[StudentBand]] = defaultdict(list)
        for b in rows:
            seq[(b.student_id, b.subject_id)].append(b)

        grid: dict[tuple[uuid.UUID, uuid.UUID], ProgrammeGridCell] = {}
        moved_up = slipped = 0
        current_c: list[tuple[uuid.UUID, uuid.UUID, StudentBand]] = []
        for (sid, subj_id), band_rows in seq.items():
            cls_id = class_of.get(sid)
            if cls_id is None:
                continue
            cell = grid.setdefault((cls_id, subj_id), ProgrammeGridCell(
                class_id=cls_id, subject_id=subj_id, subject_name=names.get(subj_id, "?")))
            first, last = band_rows[0], band_rows[-1]
            direction = movement(first.tier, last.tier) if len(band_rows) > 1 else "same"
            if direction == "up":
                moved_up += 1
                cell.moved_up += 1
            elif direction == "down":
                slipped += 1
                cell.slipped += 1
            if last.tier == "C":
                cell.c_count += 1
                current_c.append((sid, subj_id, last))

        out.moved_up, out.slipped = moved_up, slipped
        out.stuck = self._stuck(m, current_c, names)
        for klass in classes:
            for subj_id in subject_ids:
                cell = grid.get((klass.id, subj_id))
                if cell is None:
                    continue
                cell.class_label = _label(klass)
                out.grid.append(cell)
        out.not_assessed = self._not_assessed(m, classes, subjects, term)

        stuck_n = len(out.stuck)
        if not rows:
            out.headline = ("Nobody has been banded yet. Start with a band test, or assess a "
                            "class against the descriptors.")
        else:
            parts = [f"{moved_up} child{'' if moved_up == 1 else 'ren'} moved up this term",
                     f"{slipped} slipped"]
            out.headline = ", ".join(parts) + "."
            if stuck_n:
                out.headline += (f" {stuck_n} ha{'s' if stuck_n == 1 else 've'} been Band C all "
                                 "term with no movement.")
            elif current_c and all(r.owner_name for r in out.stuck):
                out.headline += " Every C child has an owner."
        # The week-one state, and the single most useful sentence this screen can
        # say then: bands are set and the programme has not started. It only
        # replaces the movement headline when there is **no movement to report** —
        # once children are moving, that is the news (`D-67`).
        no_owner = sum(1 for r in out.stuck if not r.owner_name)
        if no_owner == len(out.stuck) and no_owner and not moved_up and not slipped:
            out.headline = (f"{len(current_c)} children are in Band C and none has an owner."
                            if no_owner == len(current_c)
                            else f"{no_owner} children in Band C have no owner.")
        return out

    def _stuck(self, m: CurrentMember, current_c: list, names: dict) -> list[ProgrammeRow]:
        """Every child still in C, **named with the subject** (`S-188`) — with
        two owners possible, "Kabir Shah — owner Priya" lets each of them assume
        the other is on it."""
        if not current_c:
            return []
        sids = [sid for sid, _, _ in current_c]
        students = {s.id: s for s in self.db.scalars(
            select(Student).where(Student.id.in_(sids)))}
        classes = {k.id: _label(k) for k in self.db.scalars(select(SchoolClass).where(
            SchoolClass.org_id == m.org_id))}
        owners = self._owner_map(m)
        last_checkin = self._last_checkin_map(m)

        out: list[ProgrammeRow] = []
        for sid, subj_id, band in current_c:
            st = students.get(sid)
            if st is None:
                continue
            owner = owners.get((sid, subj_id))
            out.append(ProgrammeRow(
                student_id=sid, full_name=st.full_name,
                class_label=classes.get(st.class_id),
                subject_id=subj_id, subject_name=names.get(subj_id, "?"),
                since=band.created_at.date() if band.created_at else None,
                owner_member_id=owner[0] if owner else None,
                owner_name=owner[1] if owner else None,
                intervention_id=owner[2] if owner else None,
                last_checkin=last_checkin.get(owner[2]) if owner else None))
        out.sort(key=lambda r: (r.owner_name is not None, r.last_checkin is not None,
                                r.full_name))
        return out

    def _owner_map(self, m: CurrentMember,
                   ) -> dict[tuple[uuid.UUID, uuid.UUID], tuple[uuid.UUID, str, uuid.UUID]]:
        """(student, subject) → (member, name, intervention) for ACTIVE plans."""
        rows = self.db.execute(
            select(Intervention, User.name)
            .outerjoin(Membership, Membership.id == Intervention.owner_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .where(Intervention.org_id == m.org_id,
                   Intervention.status == "active")).all()
        out = {}
        for iv, name in rows:
            if iv.subject_id is None:
                continue
            out[(iv.student_id, iv.subject_id)] = (iv.owner_member_id, name, iv.id)
        return out

    def _last_checkin_map(self, m: CurrentMember) -> dict[uuid.UUID, object]:
        return dict(self.db.execute(
            select(SupportCheckpoint.intervention_id,
                   func.max(SupportCheckpoint.week_start))
            .where(SupportCheckpoint.org_id == m.org_id)
            .group_by(SupportCheckpoint.intervention_id)).all())

    def _not_assessed(self, m: CurrentMember, classes: list[SchoolClass],
                      subjects: list[Subject], term: Term) -> list[str]:
        """Class-subjects with no band row this term — **a word, never a zero and
        never red** (ux §5). A class nobody assessed is a gap in the record."""
        taught = {(cs.class_id, cs.subject_id) for cs in self.db.scalars(
            select(ClassSubject).where(ClassSubject.org_id == m.org_id))}
        banded = {(class_id, subject_id) for class_id, subject_id in self.db.execute(
            select(Student.class_id, StudentBand.subject_id)
            .join(Student, Student.id == StudentBand.student_id)
            .where(StudentBand.org_id == m.org_id,
                   StudentBand.term_id == term.id,
                   StudentBand.subject_id.is_not(None)).distinct()).all()}
        labels = {k.id: _label(k) for k in classes}
        sizes = dict(self.db.execute(
            select(Student.class_id, func.count()).where(
                Student.org_id == m.org_id, Student.status == "active")
            .group_by(Student.class_id)).all())
        out = []
        for s in subjects:
            for k in classes:
                if (k.id, s.id) in taught and (k.id, s.id) not in banded:
                    n = sizes.get(k.id, 0)
                    out.append(f"{labels[k.id]} {s.name} ({n} children) — "
                               "no band recorded this term")
        return out[:12]

    def _term(self, m: CurrentMember, term_id: uuid.UUID | None) -> Term | None:
        if term_id:
            return self.db.scalar(select(Term).where(
                Term.id == term_id, Term.org_id == m.org_id))
        today = datetime.now(UTC).date()
        return self.db.scalar(select(Term).where(
            Term.org_id == m.org_id, Term.start_date <= today, Term.end_date >= today)
            .order_by(Term.start_date.desc()).limit(1)) or self.db.scalar(
            select(Term).where(Term.org_id == m.org_id)
            .order_by(Term.start_date.desc()).limit(1))

    # ── ownership (D-71 / D-77) ──────────────────────────────────────────────
    def assign_owner(self, m: CurrentMember, student_id: uuid.UUID, subject_id: uuid.UUID,
                     member_id: uuid.UUID | None, term_id: uuid.UUID | None = None,
                     goal_text: str | None = None,
                     exit_criterion: str | None = None) -> uuid.UUID:
        """Give a C child a teacher, by name, for one subject.

        Creates the support plan if there isn't one — the moment the C list
        exists is the only moment anyone is thinking about ownership (`D-71`),
        so this is offered right after a class is filed."""
        if not m.is_coordinator_up:
            raise ForbiddenError("Only an admin assigns support owners.", code="admin_only")
        student = self.db.scalar(select(Student).where(
            Student.id == student_id, Student.org_id == m.org_id))
        if student is None:
            raise NotFoundError("Student")
        if member_id is not None and not self.db.scalar(select(Membership.id).where(
                Membership.id == member_id, Membership.org_id == m.org_id)):
            raise NotFoundError("Member")
        term = self._term(m, term_id)
        if term is None:
            raise ValidationError("Set up a term first.", code="no_term")
        iv = self.db.scalar(select(Intervention).where(
            Intervention.org_id == m.org_id, Intervention.student_id == student_id,
            Intervention.subject_id == subject_id, Intervention.status == "active"))
        if iv is None:
            subject = self.db.get(Subject, subject_id)
            iv = Intervention(
                org_id=m.org_id, student_id=student_id, term_id=term.id,
                subject_id=subject_id,
                goal_text=goal_text or f"Move {student.full_name} from C to B in {subject.name}",
                exit_criterion=exit_criterion, target_tier="B")
            self.db.add(iv)
        iv.owner_member_id = member_id or self._default_owner(m, student, subject_id)
        if goal_text:
            iv.goal_text = goal_text
        if exit_criterion is not None:
            iv.exit_criterion = exit_criterion
        self.db.flush()
        return iv.id

    def _default_owner(self, m: CurrentMember, student: Student,
                       subject_id: uuid.UUID) -> uuid.UUID | None:
        """`S-168`: the subject teacher of his class, then the class teacher.
        A default is not an answer — the admin still sees who it landed on."""
        if student.class_id is None:
            return None
        teacher = self.db.scalar(select(ClassSubject.teacher_member_id).where(
            ClassSubject.org_id == m.org_id, ClassSubject.class_id == student.class_id,
            ClassSubject.subject_id == subject_id))
        if teacher:
            return teacher
        klass = self.db.get(SchoolClass, student.class_id)
        return klass.class_teacher_member_id if klass else None
