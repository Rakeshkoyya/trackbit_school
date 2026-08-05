"""Assessments & bands (M3, SPRD §4.5).

TrackBit records and tracks; it never authors or conducts tests (§8 fence). Bands
are private intervention tiers (P4) — staff-only, append-only history. Activating
an intervention spins its checklist into tasks for the class teacher (M5).
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import CreatedAtMixin, UUIDPKMixin

_SCORE = Numeric(6, 2)


def _org_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )


def _actor_fk() -> Mapped[uuid.UUID | None]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class SkillArea(Base, UUIDPKMixin, CreatedAtMixin):
    """Configurable diagnostic skill area (seed: Reading/Writing/Speaking/Math)."""

    __tablename__ = "skill_areas"

    org_id: Mapped[uuid.UUID] = _org_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (UniqueConstraint("org_id", "name", name="uq_skill_areas_org_id"),)


CYCLE_TYPES = ("diagnostic", "unit_test", "term_exam", "daily_test",
               "chapter_test", "class_test", "slip_test", "objective", "band_test")


class ExamType(Base, UUIDPKMixin, CreatedAtMixin):
    """The school's own word for a kind of exam (V1-8, `D-55`/`S-135`).

    A school that runs *CET* could not record one: `assessment_cycles.type` is a
    CHECK over nine fixed values, so CET was either unsaveable or filed as
    `class_test` — and once filed, no analytic could ever separate it again.

    Why a table and not free text (which is what `core/work_types.py` chose for
    the timesheet): **the exam type is the grouping key for a year of trend
    lines.** *"CET"*, *"C.E.T"* and *"Cet"* typed on three different evenings
    become three series on the admin's chart. A timesheet bucket is never a
    chart's x-axis; this is. The table also carries `scale` (`S-114`), so the
    school configures *"CET = minor"* once and the teacher picks **one** thing
    per exam instead of two.

    `system_type` stays the code's kind — `type` on the cycle is what branches
    (`diagnostic` → skill grid, `band_test` → admin-only). The rule that keeps
    this from becoming two sources of truth: **the school's word is what every
    screen displays and groups by; the system kind is read only by code.**

    Retired, never deleted (the `work_types` rule): `active=False` keeps the
    historical exams it names rendering under their own word."""

    __tablename__ = "exam_types"

    org_id: Mapped[uuid.UUID] = _org_fk()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    system_type: Mapped[str] = mapped_column(Text, nullable=False)  # one of CYCLE_TYPES
    scale: Mapped[str] = mapped_column(Text, nullable=False, server_default="minor")
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_exam_types_org_name"),
        CheckConstraint("scale IN ('minor', 'major')", name="exam_type_scale_valid"),
    )


class AssessmentCycle(Base, UUIDPKMixin, CreatedAtMixin):
    __tablename__ = "assessment_cycles"

    org_id: Mapped[uuid.UUID] = _org_fk()
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)  # one of CYCLE_TYPES
    name: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    # SC-1: a daily test is class × subject × date; NULL on both = org-wide cycle
    # (diagnostics, term exams) exactly as before.
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    # SC-5: the paper's own metadata — what was tested and out of how much.
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_marks: Mapped[float | None] = mapped_column(_SCORE, nullable=True)
    # A few-students test: only these students sat it. NULL = the whole class.
    student_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)

    # ── V1-8 ─────────────────────────────────────────────────────────────────
    # `D-55`: the school's own word for this exam. NULL = never configured, and
    # the screens fall back to `core.exams.type_label(type)` — a fallback, never
    # the primary rendering.
    exam_type_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("exam_types.id", ondelete="SET NULL"), nullable=True)
    # `S-114`: minor | major, and never pooled. Denormalised from the exam type
    # (or defaulted from `type`) at write time so every read can split without a
    # join. `core.exams` owns what the two words mean.
    scale: Mapped[str] = mapped_column(Text, nullable=False, server_default="minor")
    # `S-115`: the planned exam block this recorded exam belongs to. Nullable,
    # because a Tuesday slip test has no calendar block and never will. It is
    # the join `exam_portions` was built for: "we covered 70% of the portion —
    # what did that cost?"
    exam_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("calendar_events.id", ondelete="SET NULL"), nullable=True)
    # `D-53`: the derived cache of the newest `exam_lock_events` row. The events
    # are the record (law 3); these two columns exist so a feed of thirty exams
    # doesn't need thirty subqueries.
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[uuid.UUID | None] = _actor_fk()
    # V1-9 (`D-76`/`S-182`): *"use this as the band test"* — a **flag, never a
    # type change**. Re-typing a slip test to `band_test` would remove it from
    # every exam roll-up that counts slip tests, so the school would lose the
    # test to gain the band.
    band_promoted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    band_promoted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "type IN ({})".format(", ".join(f"'{t}'" for t in CYCLE_TYPES)),
            name="type_valid"),
        CheckConstraint("scale IN ('minor', 'major')", name="scale_valid"),
    )


class ExamLockEvent(Base, UUIDPKMixin, CreatedAtMixin):
    """Append-only lock history for an exam (`D-53`, `Q-62`, law 3).

    `ExamService.save` full-deletes and re-inserts a cycle's scores on every
    edit, so a mark corrected in November silently replaced the mark confirmed in
    July with no record that they ever differed. The lock is what freezes it:
    after it, a save is refused until an **admin unlocks with a reason** — and
    the unlock is an appended row, never a mutation, exactly like
    `plan_approvals` / `leave_request_events` / `demo_request_notes`.

    `assessment_cycles.locked_at/locked_by` are the derived cache of the newest
    row here; this table is the truth."""

    __tablename__ = "exam_lock_events"

    org_id: Mapped[uuid.UUID] = _org_fk()
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_cycles.id", ondelete="CASCADE"),
        nullable=False, index=True)
    action: Mapped[str] = mapped_column(Text, nullable=False)  # lock | unlock
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint("action IN ('lock', 'unlock')", name="lock_action_valid"),
    )


class AssessmentScore(Base, UUIDPKMixin, CreatedAtMixin):
    """A student's score in one cycle, against EITHER a subject (tests) or a skill
    area (diagnostic) — exactly one. Verified by a coordinator before it's trusted."""

    __tablename__ = "assessment_scores"

    org_id: Mapped[uuid.UUID] = _org_fk()
    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_cycles.id", ondelete="CASCADE"),
        nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    skill_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skill_areas.id", ondelete="CASCADE"), nullable=True)
    score: Mapped[float] = mapped_column(_SCORE, nullable=False)
    max_score: Mapped[float] = mapped_column(_SCORE, nullable=False, server_default="100")
    entered_by: Mapped[uuid.UUID | None] = _actor_fk()
    # `D-53` finally gives this a meaning: set for every score in the cycle when
    # the teacher verifies and locks. Before V1-8 the exam flow never wrote it,
    # so the feed's "· verified" badge could not light up for any SC-5 exam.
    verified_by: Mapped[uuid.UUID | None] = _actor_fk()
    # V1-8 (§4's reconciliation): the per-question marks the model transcribed
    # from the marked script — `[{q, score, max}]`. Not a new capture surface
    # and nothing extra asked of the teacher: it is read off a paper that
    # already has the marks written beside each question. NULL for an exam typed
    # in by hand, and the screens say so as a WORD ("question-level analysis
    # needs a photo of the marked paper"), never as a zero.
    question_marks: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # The teacher's optional word about this paper (founder 2026-08-05). Written
    # at the moment she is holding it, which is the only moment she knows why the
    # mark is what it is. Never required: a mandatory remark is forty sentences
    # typed to record one, which P1v2 does not permit.
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("num_nonnulls(subject_id, skill_area_id) = 1", name="one_target"),
    )


class StudentBand(Base, UUIDPKMixin, CreatedAtMixin):
    """A/B/C tier for a student **in one subject**, in a term. Append-only: a new
    row per change keeps the movement history (never update tier in place).

    V1-9 (`D-75`): the band is **per subject and there is no overall letter.**
    Before this, `categorize_from_cycle` summed every score in a cycle into one
    percentage and wrote one tier — so a child who reads two years below his
    grade and is fine at arithmetic got a letter describing neither, and the
    daily check generator then handed him easier *maths* while his English went
    untouched.

    Rows with `subject_id IS NULL` are the **retired overall letter**: kept as
    history, rendered in the band history, and read by no current computation.
    Two definitions of "Kabir's band" is the defect this packet removes."""

    __tablename__ = "student_bands"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False)  # A|B|C
    # V1-9 (`D-75`): the subject this band is for. NULL = a legacy overall row.
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    # `D-70`: both routes are first-class, and a row records which produced it —
    # `test` (marks) or `observation` (the teacher against the descriptors).
    # `S-185`: entry may be judgement; **movement is always a test.**
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default="test")
    # The deciding exam, where there was one — so the row explains itself.
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_cycles.id", ondelete="SET NULL"), nullable=True)
    # Kept where it is and no longer pretending to be a band scope (`Q-77`): it
    # belongs to the diagnostic skill radar, not to the programme.
    scope_skill_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skill_areas.id", ondelete="CASCADE"), nullable=True)
    set_by: Mapped[uuid.UUID | None] = _actor_fk()
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("tier IN ('A', 'B', 'C')", name="tier_valid"),
        CheckConstraint("source IN ('test', 'observation')", name="source_valid"),
    )


class BandDescriptor(Base, UUIDPKMixin, CreatedAtMixin):
    """What a child in this band, in this subject, **can do** (V1-9, `D-69`).

    The founder's *"help doc of characteristics for each band"*. Without it a
    tier means only *"scored below 50% on whatever the last test was"*, which is
    why two teachers in the same school band the same child differently and
    neither is wrong.

    `S-166` is the rule that makes it load-bearing rather than documentation:
    **the letter never renders without its sentence.** A letter alone is exactly
    the label P4 exists to prevent.

    It also carries the subject's **own threshold** (`D-74`). Before V1-9 there
    were two numbers for the whole school, so English and Maths were assumed to
    be measured on the same scale. C carries no `min_pct` — C is *below B*,
    never its own cut-off, or two thresholds could disagree."""

    __tablename__ = "band_descriptors"

    org_id: Mapped[uuid.UUID] = _org_fk()
    subject_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False)   # A|B|C
    text: Mapped[str] = mapped_column(Text, nullable=False)
    min_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # `Q-76`: reserved, unused. 9 texts get written, 72 do not.
    grade_group: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("org_id", "subject_id", "tier", "grade_group",
                         name="uq_band_descriptors_subject_tier"),
        CheckConstraint("tier IN ('A', 'B', 'C')", name="tier_valid"),
        CheckConstraint("min_pct IS NULL OR (min_pct >= 0 AND min_pct <= 100)",
                        name="min_pct_valid"),
    )


class ScoreCapture(Base, UUIDPKMixin, CreatedAtMixin):
    """A batch of photos of evaluated papers for one (cycle × class × subject-or-skill).

    A draft container: the AI transcription + deterministic roster match live in
    `parsed_rows`; `assessment_scores` are written ONLY when a human confirms the
    review grid (§8 — every AI output lands in a human-confirm surface). The photo
    pages are kept forever as evidence (P5)."""

    __tablename__ = "score_captures"

    org_id: Mapped[uuid.UUID] = _org_fk()
    # NULL = a draft exam capture: papers dropped first, the cycle is created
    # when the human saves the reviewed exam (SC-5).
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assessment_cycles.id", ondelete="CASCADE"),
        nullable=True, index=True)
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    skill_area_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skill_areas.id", ondelete="CASCADE"), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="uploaded")
    # [{name_text, roll_text, score, max_score, student_id, confidence, candidates}]
    parsed_rows: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # AI-read exam header {title, subject_text, subject_id, total_marks, topic, date}
    # — proposals only, the human-confirm form is what persists (§8).
    parsed_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Few-students capture: the picked subset. NULL = the whole class roster.
    student_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)  # ai_off|unreadable_page
    # V1-8 (`D-80`): `register` = one page listing many students (the SC-1 mark
    # register). `scripts` = **one page per student's marked script**, which is
    # now the primary flow — `D-82` makes per-student exam photos an explicit
    # exception to P5, because here the photo IS the capture mechanism.
    mode: Mapped[str] = mapped_column(Text, nullable=False, server_default="register")
    # V1-8 (`D-54`/`S-136`/`S-137`): the training pair, written ONCE at lock and
    # never after. `parsed_rows` is what the model read; `locked_rows` is what
    # the human confirmed; `corrections` is the explicit diff — which is where
    # the entire value is, because fifty thousand correctly-read pages teach very
    # little and the rows a human changed teach a lot. Each correction carries a
    # reason bucket (`S-140`). Written only when the org has opted in (`S-138`);
    # there is **no export path in v1** (A-4) — capture now, use later, because
    # this cannot be recovered retrospectively.
    locked_rows: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    corrections: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    created_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)
    confirmed_by_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    pages: Mapped[list["ScoreCapturePage"]] = relationship(
        back_populates="capture", cascade="all, delete-orphan",
        order_by="ScoreCapturePage.page_no")

    __table_args__ = (
        # At most one — a draft capture's subject is unknown until the parse.
        CheckConstraint("num_nonnulls(subject_id, skill_area_id) <= 1", name="capture_one_target"),
        CheckConstraint("status IN ('uploaded', 'parsed', 'confirmed', 'discarded')",
                        name="status_valid"),
        CheckConstraint("mode IN ('register', 'scripts')", name="capture_mode_valid"),
    )


class ScoreCapturePage(Base, UUIDPKMixin, CreatedAtMixin):
    """One photographed page of a capture — an R2 object key (URLs minted per read)."""

    __tablename__ = "score_capture_pages"

    org_id: Mapped[uuid.UUID] = _org_fk()
    capture_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("score_captures.id", ondelete="CASCADE"),
        nullable=False, index=True)
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    # V1-8 (`D-80` step 5): in `scripts` mode this page IS one student's paper.
    # Set by the match, or **by the teacher's hand when the page is unreadable** —
    # a page we cannot read must never become a page we discard. It is also what
    # puts the paper one tap from the report card (`S-119`).
    student_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True, index=True)

    capture: Mapped["ScoreCapture"] = relationship(back_populates="pages")

    __table_args__ = (
        UniqueConstraint("capture_id", "page_no", name="uq_score_capture_pages_capture_id"),
    )


class Intervention(Base, UUIDPKMixin, CreatedAtMixin):
    """One child's support plan **in one subject** (V1-9, `D-77`).

    Three things V1-9 gives it, and each closes a live defect:

    * **an owner** (`D-71`/`D-77`) — the founder's *"for every C band child there
      will be a teacher assigned, and it is her responsibility"* was implemented
      as a dead link: the tasks were assigned to
      `school_classes.class_teacher_member_id`, which no screen set until V1-2,
      and one owner for a child is ambiguous the moment he is C in two subjects.
    * **an exit criterion** (`S-167`) written when the child **enters** — a goal
      decided at the end is a judgement, not a target.
    * **a way to close** (`S-180`) — nothing could set `status='achieved'`, and
      `RecommendationsService` filters on `status == 'active'`, so a goal met in
      July kept injecting a targeted daily check into the period card in March.
      The one loop the module exists to close was the one thing the schema
      allowed and the code could not do."""

    __tablename__ = "interventions"

    org_id: Mapped[uuid.UUID] = _org_fk()
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    term_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    # V1-9: one row per (child × subject) — Kabir C in Hindi and Maths has two
    # plans and two owners, and neither can assume the other is on it (`S-188`).
    subject_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True)
    owner_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)
    goal_text: Mapped[str] = mapped_column(Text, nullable=False)
    # `S-167`: "moves to B when he reads 60 wpm with ≤3 errors, twice running."
    exit_criterion: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="B")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    items: Mapped[list["InterventionItem"]] = relationship(
        back_populates="intervention", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('active', 'achieved', 'dropped')", name="status_valid"),
    )


class SupportCheckpoint(Base, UUIDPKMixin, CreatedAtMixin):
    """The weekly check-in (V1-9, `D-87`/`S-165`) — append-only (law 3).

    **The only genuinely new capture in the module**, and it is deliberately the
    *weekly* unit rather than a daily log: a free textarea per child per day is a
    compliance chore that dies by week three. Four fields, once a week, six
    children, under five minutes on a Friday — and it is also the only thing
    that produces the movement evidence the admin's report needs.

    The page it is written on **opens already filled in** (`S-164`) from capture
    other teachers already did, so the owner is never asked to record what the
    product already knows. She is asked for the one thing only she knows: what
    she actually did with him."""

    __tablename__ = "support_checkpoints"

    org_id: Mapped[uuid.UUID] = _org_fk()
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interventions.id", ondelete="CASCADE"),
        nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    worked_on: Mapped[str | None] = mapped_column(Text, nullable=True)
    what_changed: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_step: Mapped[str | None] = mapped_column(Text, nullable=True)
    # She proposes readiness; **a test moves the band** (`D-76`). That split is
    # the honest one: she is the person who knows he is ready, and also the
    # person with an interest in him being ready.
    ready_to_retest: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    author_member_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="SET NULL"), nullable=True)


class InterventionItem(Base, UUIDPKMixin, CreatedAtMixin):
    """A checklist line. Activating the intervention spawns a task for the class
    teacher (M5); we link it so completion shows back in the intervention view."""

    __tablename__ = "intervention_items"

    org_id: Mapped[uuid.UUID] = _org_fk()
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("interventions.id", ondelete="CASCADE"),
        nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    task_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("task_instances.id", ondelete="SET NULL"), nullable=True)

    intervention: Mapped["Intervention"] = relationship(back_populates="items")
