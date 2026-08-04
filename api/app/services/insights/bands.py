"""The shape of the support programme — distribution and allocation.

Founder call, 2026-08-04: the admin wants to see *where the support load sits*
— which classes are carrying it, which subjects — and to allocate owners from a
table rather than one child at a time off the programme board.

This service **composes**. It does not compute a second version of anybody's
band: every tier here comes from `BandService.placements`, and the movement
headline is `BandService.programme`'s own sentence, so the overview block, the
distribution board and the programme board cannot describe the same term
differently (`S-51`, the law this codebase has closed five times).

Two rules that shape everything below:

**The unit is the placement, not the child** (`D-75`). There is no overall
letter, so a child cannot be counted into one tier at school or class level — a
boy who is A in Maths and C in Hindi belongs in both columns. Only a *subject*
row collapses back to children, because inside one subject a child holds exactly
one band. Every row carries `caption`/`assessed` so no screen can quote a bare
percentage (ux §4).

**Not assessed is its own number** (ux §5). `eligible - assessed` is the gap in
the record and is reported beside the tiers, never folded into C — a class
nobody has banded must not read as a class full of struggling children.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.bands import TIERS
from app.core.context import CurrentMember
from app.models import (
    ClassSubject,
    Intervention,
    Membership,
    SchoolClass,
    Student,
    Subject,
    SupportCheckpoint,
    User,
)
from app.schemas.bands import (
    AllocationBoard,
    AllocationRow,
    BandDistribution,
    BandScopeRow,
    OwnerSuggestion,
)
from app.services.bands import BandService


def _label(k: SchoolClass) -> str:
    return f"{k.name}-{k.section}" if k.section else k.name


def _rate(row: BandScopeRow) -> None:
    """Percentages are taken over what was ACTUALLY assessed, never over the
    roster — dividing by a denominator that includes children nobody looked at
    would make an unbanded class read as though it were mostly A."""
    total = row.a + row.b + row.c
    row.assessed = total
    row.not_assessed = max(0, row.eligible - total)
    if total:
        row.a_pct = round(row.a / total * 100, 1)
        row.b_pct = round(row.b / total * 100, 1)
        row.c_pct = round(row.c / total * 100, 1)


class BandInsights:
    def __init__(self, db: Session):
        self.db = db

    # ── the three charts (founder 2026-08-04) ────────────────────────────────
    def distribution(self, m: CurrentMember,
                     term_id: uuid.UUID | None = None) -> BandDistribution:
        """School · by class · by subject, tallied A/B/C.

        The tiers are **current standing**, not this term's rows: `student_bands`
        is append-only, so the newest row per (child, subject) *is* the child's
        band whatever term wrote it. Scoping the tally to the running term would
        empty the whole board for a school that banded in April and has not
        re-banded since — which is most schools, most of the year. Movement
        stays term-scoped, because movement is a thing that happens *within* a
        term, and the caption says which is which."""
        bands = BandService(self.db)
        board = bands.programme(m, term_id)
        subjects = bands.monitored_subjects(m)
        out = BandDistribution(
            term_id=board.term_id, term_name=board.term_name,
            subjects=[s.name for s in subjects], headline=board.headline,
            moved_up=board.moved_up, slipped=board.slipped,
            school=BandScopeRow(key="school", label="School"))
        if not subjects:
            out.caption = "No subject is being monitored yet."
            return out

        # A teacher's board is her own class-subjects (`my_scope`), an admin's is
        # the school. Same computation, narrower input — so her dashboard and the
        # admin's can never state different figures about the classes they share.
        scope = set(bands.my_scope(m))
        subject_ids = {s.id for s in subjects}
        if not m.is_coordinator_up:
            subject_ids = {s for _, s in scope}
            if not subject_ids:
                out.caption = "You don't teach any of the monitored subjects."
                return out
        names = {s.id: s.name for s in subjects}

        roster = self.db.execute(select(Student.id, Student.class_id).where(
            Student.org_id == m.org_id, Student.status == "active")).all()
        class_of = {sid: cid for sid, cid in roster}
        sids = [sid for sid, _ in roster]
        classes = {k.id: _label(k) for k in self.db.scalars(
            select(SchoolClass).where(SchoolClass.org_id == m.org_id)
            .order_by(SchoolClass.name, SchoolClass.section))}

        # Which monitored subjects each class is actually taught — the only
        # honest denominator. A school monitoring three subjects does not teach
        # all three to every class, and counting them as missing placements
        # would invent a gap.
        taught: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        for class_id, subject_id in self.db.execute(
                select(ClassSubject.class_id, ClassSubject.subject_id)
                .where(ClassSubject.org_id == m.org_id,
                       ClassSubject.subject_id.in_(subject_ids))).all():
            if not m.is_coordinator_up and (class_id, subject_id) not in scope:
                continue
            taught[class_id].add(subject_id)

        sizes: dict[uuid.UUID, int] = defaultdict(int)
        for _, class_id in roster:
            if class_id is not None:
                sizes[class_id] += 1

        by_class = {cid: BandScopeRow(key=str(cid), label=label, students=sizes.get(cid, 0))
                    for cid, label in classes.items()}
        by_subject = {sid_: BandScopeRow(key=str(sid_), label=names[sid_])
                      for sid_ in subject_ids}
        for cid, subs in taught.items():
            n = sizes.get(cid, 0)
            if cid in by_class:
                by_class[cid].eligible += n * len(subs)
            for sub in subs:
                by_subject[sub].eligible += n
                by_subject[sub].students += n
        out.school.eligible = sum(r.eligible for r in by_class.values())
        # The children who COULD be assessed — those in a class actually taught a
        # monitored subject. Denominating over the whole roster would report a
        # school as half-assessed because Nursery does not take Maths.
        assessable = {sid for sid, cid in roster if cid in taught}
        out.school.students = len(assessable)

        places = bands.placements(m, sids)
        banded_students: set[uuid.UUID] = set()
        for student_id, placements in places.items():
            cid = class_of.get(student_id)
            for p in placements:
                if p.subject_id not in subject_ids or p.tier not in TIERS:
                    continue
                # Only placements this member's board is denominated over —
                # otherwise a teacher's own figures would count children she is
                # not responsible for and cannot act on.
                if cid is not None and p.subject_id not in taught.get(cid, ()):
                    continue
                banded_students.add(student_id)
                for row in (out.school, by_class.get(cid), by_subject.get(p.subject_id)):
                    if row is None:
                        continue
                    setattr(row, p.tier.lower(), getattr(row, p.tier.lower()) + 1)

        for row in (out.school, *by_class.values(), *by_subject.values()):
            _rate(row)
        # Worst-first: the list exists to find who needs help (`core/bands`'
        # TIER_RANK rule, applied to the board).
        out.by_class = sorted((r for r in by_class.values() if r.eligible),
                              key=lambda r: (-r.c_pct, r.label))
        out.by_subject = sorted((r for r in by_subject.values() if r.eligible),
                                key=lambda r: (-r.c_pct, r.label))

        n_sub = len(subjects)
        out.caption = (
            f"{out.school.assessed} placements across {n_sub} "
            f"subject{'' if n_sub == 1 else 's'} · "
            f"{len(banded_students)} of {len(assessable)} children assessed")
        return out

    # ── allocation: the C list and who owns it (D-71 / D-77) ─────────────────
    def allocation(self, m: CurrentMember, term_id: uuid.UUID | None = None,
                   class_id: uuid.UUID | None = None,
                   subject_id: uuid.UUID | None = None) -> AllocationBoard:
        """Every Band C placement in the school, with its owner or the absence
        of one — the table the admin allocates from.

        Filtering is done here rather than in the browser so the headline counts
        describe the rows on screen; a screen whose sentence and whose list
        disagree is one nobody trusts twice."""
        bands = BandService(self.db)
        term = bands.current_term(m, term_id)
        subjects = {s.id: s.name for s in bands.monitored_subjects(m)}
        out = AllocationBoard(term_id=term.id if term else None,
                              term_name=term.name if term else None)
        if not subjects:
            out.headline = "Turn on the subjects you want to monitor in Setup → Settings."
            return out

        roster = list(self.db.scalars(select(Student).where(
            Student.org_id == m.org_id, Student.status == "active")
            .order_by(Student.full_name)))
        classes = {k.id: _label(k) for k in self.db.scalars(
            select(SchoolClass).where(SchoolClass.org_id == m.org_id)
            .order_by(SchoolClass.name, SchoolClass.section))}
        out.classes = [{"id": str(k), "label": v} for k, v in classes.items()]
        out.subjects = [{"id": str(k), "label": v} for k, v in
                        sorted(subjects.items(), key=lambda kv: kv[1])]

        owners = bands.owner_map(m)
        checkins = self._checkin_stats(m)
        places = bands.placements(m, [s.id for s in roster])
        by_id = {s.id: s for s in roster}

        for student_id, placements in places.items():
            student = by_id.get(student_id)
            if student is None:
                continue
            if class_id and student.class_id != class_id:
                continue
            for p in placements:
                if p.tier != "C" or p.subject_id not in subjects:
                    continue
                if subject_id and p.subject_id != subject_id:
                    continue
                owner = owners.get((student_id, p.subject_id))
                stats = checkins.get(owner[2]) if owner else None
                out.rows.append(AllocationRow(
                    student_id=student_id, full_name=student.full_name,
                    roll_no=student.roll_no, class_id=student.class_id,
                    class_label=classes.get(student.class_id),
                    subject_id=p.subject_id, subject_name=p.subject_name,
                    owner_member_id=owner[0] if owner else None,
                    owner_name=owner[1] if owner else None,
                    intervention_id=owner[2] if owner else None,
                    checkins=stats[0] if stats else 0,
                    last_checkin=stats[1] if stats else None))

        # Unassigned first — the whole point of the screen is the empty column.
        out.rows.sort(key=lambda r: (r.owner_name is not None,
                                     r.class_label or "", r.subject_name, r.full_name))
        out.assigned = sum(1 for r in out.rows if r.owner_member_id)
        out.unassigned = len(out.rows) - out.assigned
        if not out.rows:
            out.headline = "No child is in Band C here."
        elif not out.unassigned:
            out.headline = (f"All {out.assigned} Band C "
                            f"placement{'' if out.assigned == 1 else 's'} have an owner.")
        else:
            out.headline = (f"{out.unassigned} of {len(out.rows)} Band C "
                            f"placement{'' if len(out.rows) == 1 else 's'} "
                            "have nobody assigned.")
        return out

    def _checkin_stats(self, m: CurrentMember) -> dict[uuid.UUID, tuple[int, object]]:
        return {iv_id: (n, last) for iv_id, n, last in self.db.execute(
            select(SupportCheckpoint.intervention_id, func.count(),
                   func.max(SupportCheckpoint.week_start))
            .where(SupportCheckpoint.org_id == m.org_id)
            .group_by(SupportCheckpoint.intervention_id)).all()}

    # ── who could own this child (S-168, founder 2026-08-04) ─────────────────
    def owner_suggestions(self, m: CurrentMember, student_id: uuid.UUID,
                          subject_id: uuid.UUID) -> list[OwnerSuggestion]:
        """The teachers already in front of this child first — then everyone.

        The founder's rule: *suggested, never restricted*. A school where the
        subject teacher is on maternity leave still has to assign somebody, and
        a picker that refuses is a picker the office routes around with a phone
        call. `load` rides along as **capacity, not performance** (`S-170`) — it
        stops twenty children landing on one willing teacher, which is the way
        this programme actually fails."""
        student = self.db.scalar(select(Student).where(
            Student.id == student_id, Student.org_id == m.org_id))
        subject = self.db.get(Subject, subject_id)

        subject_teacher = class_teacher = None
        if student is not None and student.class_id is not None:
            subject_teacher = self.db.scalar(select(ClassSubject.teacher_member_id).where(
                ClassSubject.org_id == m.org_id,
                ClassSubject.class_id == student.class_id,
                ClassSubject.subject_id == subject_id))
            klass = self.db.get(SchoolClass, student.class_id)
            class_teacher = klass.class_teacher_member_id if klass else None
        current = self.db.scalar(select(Intervention.owner_member_id).where(
            Intervention.org_id == m.org_id, Intervention.student_id == student_id,
            Intervention.subject_id == subject_id, Intervention.status == "active"))

        load: dict[uuid.UUID, int] = dict(self.db.execute(
            select(Intervention.owner_member_id, func.count())
            .where(Intervention.org_id == m.org_id, Intervention.status == "active",
                   Intervention.owner_member_id.is_not(None))
            .group_by(Intervention.owner_member_id)).all())
        # Every monitored subject each member teaches, so a teacher who has this
        # child for a DIFFERENT subject is still a named, explicable option.
        teaches: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        if student is not None and student.class_id is not None:
            for member_id, subj in self.db.execute(
                    select(ClassSubject.teacher_member_id, ClassSubject.subject_id)
                    .where(ClassSubject.org_id == m.org_id,
                           ClassSubject.class_id == student.class_id,
                           ClassSubject.teacher_member_id.is_not(None))).all():
                teaches[member_id].add(subj)

        names = {s.id: s.name for s in self.db.scalars(
            select(Subject).where(Subject.org_id == m.org_id))}
        klass_label = None
        if student is not None and student.class_id is not None:
            k = self.db.get(SchoolClass, student.class_id)
            klass_label = _label(k) if k else None

        out: list[OwnerSuggestion] = []
        for membership_id, name, role in self.db.execute(
                select(Membership.id, User.name, Membership.org_role)
                .join(User, User.id == Membership.user_id)
                .where(Membership.org_id == m.org_id,
                       Membership.status == "active")
                .order_by(User.name)).all():
            reason, suggested = "", False
            if membership_id == subject_teacher:
                reason = (f"teaches {klass_label} {subject.name}" if klass_label and subject
                          else "teaches this subject to the class")
                suggested = True
            elif membership_id == class_teacher:
                reason = f"class teacher of {klass_label}" if klass_label else "class teacher"
                suggested = True
            elif membership_id in teaches:
                others = sorted(names.get(s, "?") for s in teaches[membership_id])
                reason = f"teaches {klass_label} {', '.join(others[:2])}" if klass_label \
                    else f"teaches {', '.join(others[:2])}"
                suggested = True
            elif role == "admin":
                reason = "admin"
            out.append(OwnerSuggestion(
                member_id=membership_id, name=name, suggested=suggested,
                reason=reason, load=load.get(membership_id, 0),
                current=membership_id == current))
        out.sort(key=lambda s: (not s.current, not s.suggested, s.load, s.name))
        return out
