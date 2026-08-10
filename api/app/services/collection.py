"""The collection board (V1-10) — *"how much of Q2 is in, and who do I chase?"*

This is **read + remind only** (`D-62`). The collection system — structures,
instalments, discounts, the append-only ledger, the counter screen — is built and
correct and is not touched here. What did not exist is the read a principal
needs, and one list that did exist and **nothing ever called**: `overdue_students`
has returned name + class + amount + earliest due date since P0-D, and
`school-api.ts` had no function for it. This module is what finally asks.

**Every fee screen is a rendering of `board()`** (ux §9) — the quarter strip, the
curve, the class table, the named defaulters and the dashboard's small block all
come from one computation, so they cannot disagree.

The rules it is built against, each of which was a defect before it:

* **Quarters are due-date windows** (`core/collection.py`, `Q-67`).
* **`collected` · `pending` · `overdue` stay apart** (`S-163`) — pending is a
  forecast, overdue is a phone call, and `Collection` has no method that adds
  them.
* **Years never pool** (`D-88`). Dues carried from a previous year get their own
  labelled line with a link to that year and never enter this year's totals —
  where `opening_dues` used to be silently absent from every roll-up.
* **A full concession is not a defaulter** (`S-158`). The list is built from what
  is *owed*, never from enrolment or status.
* **Every class row carries both denominators** (`S-159`) — *"8-B: 14 of 38
  families pending, ₹1.4L"*, because ₹1.4L is one big defaulter or fourteen
  small ones and those need opposite actions.
* **A defaulter row names the family** (`S-157`) — the person who owes is the
  person you ring.
* **Batched.** `overdue_students` used to run a class lookup per student; the
  whole board is a handful of grouped reads.

And the fence, which outranks the screen: **no fee status ever reaches an
academic surface** — not the report card, not growth, not the timeline, not the
daily report, not a Lucy tool. The one narrow exception is `D-83`, in
`followup_detail` below, and it is guarded there.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.collection import (
    UNSCHEDULED,
    Collection,
    Quarter,
    collection_sentence,
    current_quarter,
    pace_tone,
    quarter_of,
    quarter_windows,
)
from app.core.context import CurrentMember
from app.core.exceptions import ForbiddenError, NotFoundError, ValidationError
from app.models import (
    AcademicYear,
    FeeNote,
    FollowupAction,
    Guardian,
    Installment,
    Membership,
    SchoolClass,
    Student,
    StudentFee,
    TaskInstance,
    User,
)
from app.schemas.collection import (
    ClassCollectionRow,
    CollectionBoard,
    CollectionPoint,
    DefaulterRow,
    FeeFollowupDetail,
    FeeNoteIn,
    FeeNoteOut,
    QuarterRow,
    RemindOut,
    YearCollection,
)
from app.services.fee_math import live_installments, q
from app.services.notify_guardian import notify_guardians
from app.services.school_clock import today_in

_MAX_DEFAULTERS = 60
# `S-156`: at most one reminder per instalment per week, no matter how many staff
# press the button. A parent reminded three times in a morning about money will
# not read the fourth message about their child's attendance.
_REMINDER_COOLDOWN_DAYS = 7
_QUIET_BEFORE, _QUIET_AFTER = 8, 20   # never before 8am or after 8pm


def _label(name: str, section: str | None) -> str:
    return name + (f"-{section}" if section else "")


class CollectionService:
    def __init__(self, db: Session):
        self.db = db

    # ── the board (D-64) ─────────────────────────────────────────────────────
    def board(self, m: CurrentMember, year_id: uuid.UUID | None = None,
              quarter: str | None = None) -> CollectionBoard:
        year = self._year(m, year_id)
        today = today_in(m.org.timezone)
        out = CollectionBoard(as_of=today,
                              academic_year_id=year.id if year else None,
                              academic_year_label=year.label if year else None)
        if year is None:
            out.headline = "Set up an academic year to track collection."
            return out

        windows = quarter_windows(year.start_date, year.end_date)
        out.quarters = [QuarterRow(label=w.label, start=w.start, end=w.end) for w in windows]
        rows = self._rows(m, year.id)
        if not rows:
            out.headline = "Nobody is enrolled for fees in this year yet."
            return out

        # ── one pass over every instalment in the year ───────────────────────
        by_quarter: dict[str, Collection] = defaultdict(Collection)
        # The WHOLE year, which nothing exposed before: `board`'s top-level
        # figures are the picked quarter's, so "how is the year going" could
        # only be reconstructed by summing quarter rows in a browser — and the
        # dashboard did exactly that, in two units, with pending and overdue
        # added together. It is accumulated here, in the same pass, so the year
        # ring and the quarter rings can never disagree.
        year_due = Collection()
        by_class: dict[uuid.UUID | None, Collection] = defaultdict(Collection)
        families_by_class: dict[uuid.UUID | None, set] = defaultdict(set)
        roster_by_class: dict[uuid.UUID | None, set] = defaultdict(set)

        picked = quarter or (current_quarter(windows, today).label if windows else None)
        out.quarter = picked

        for sf in rows:
            class_id = sf.student.class_id if sf.student else None
            roster_by_class[class_id].add(sf.id)
            for inst in live_installments(sf.installments):
                amount, paid = q(inst.amount), q(inst.paid_amount)
                unpaid = q(amount - paid)
                qlabel = quarter_of(inst.due_date, windows)
                bucket = by_quarter[qlabel]
                bucket.add(collected=float(paid), billed=float(amount))
                # What the school asked for by today, paid or not — the
                # schedule's own position, and the only thing that makes a
                # percentage readable in August rather than in March. One extra
                # accumulator on a loop that already has `inst.due_date` and
                # `today` in hand: no new query, no new column.
                #
                # `<=` not `<`: money due TODAY has been asked for today. The
                # overdue test below stays strict, because a family has until
                # the end of the day to pay before anyone rings them.
                due_now = bool(inst.due_date and inst.due_date <= today)
                if due_now:
                    bucket.add(due_by_today=float(amount))
                    year_due.add(due_by_today=float(amount))
                year_due.add(collected=float(paid), billed=float(amount))
                overdue = bool(inst.due_date and inst.due_date < today and unpaid > 0)
                if unpaid > 0:
                    bucket.add(**{"overdue" if overdue else "pending": float(unpaid)})
                    year_due.add(**{"overdue" if overdue else "pending": float(unpaid)})
                if qlabel == picked:
                    cls = by_class[class_id]
                    cls.add(collected=float(paid), billed=float(amount))
                    if unpaid > 0:
                        cls.add(**{"overdue" if overdue else "pending": float(unpaid)})
                        families_by_class[class_id].add(sf.id)

        for row in out.quarters:
            c = by_quarter.get(row.label, Collection())
            row.collected, row.pending, row.overdue = c.collected, c.pending, c.overdue
            row.billed, row.pct = c.billed, c.pct
            row.due_by_today, row.due_pct = c.due_by_today, c.due_pct
            row.shortfall = c.shortfall
            # Decided here, once. Three surfaces render these rows (the
            # dashboard block, the fees board and Lucy) and a tone each worked
            # out for itself would be three verdicts about one term's money.
            row.tone = pace_tone(c)
            row.state = ("future" if row.start > today
                         else "current" if row.end >= today else "past")

        out.year = YearCollection(
            billed=year_due.billed, collected=year_due.collected,
            pending=year_due.pending, overdue=year_due.overdue,
            due_by_today=year_due.due_by_today, pct=year_due.pct,
            due_pct=year_due.due_pct, shortfall=year_due.shortfall,
            tone=pace_tone(year_due))
        unscheduled = by_quarter.get(UNSCHEDULED)
        if unscheduled and unscheduled.billed:
            # A word, not a bucket — never silently folded into Q1 (ux §10).
            out.unscheduled_billed = unscheduled.billed
            out.unscheduled_note = (
                f"₹{unscheduled.billed:,.0f} of instalments have no due date, so they are "
                "in no quarter. Give them a due date and they join one.")

        labels = self._class_labels(m)
        sizes = self._class_sizes(m)
        out.by_class = sorted(
            [ClassCollectionRow(
                class_id=cid, class_label=labels.get(cid, "Unassigned"),
                families_pending=len(families_by_class.get(cid, ())),
                families_total=sizes.get(cid, len(roster_by_class.get(cid, ()))),
                collected=c.collected, pending=c.pending, overdue=c.overdue,
                billed=c.billed, pct=c.pct)
             for cid, c in by_class.items()],
            key=lambda r: (-r.families_pending, -r.overdue, r.class_label))

        picked_window = next((w for w in windows if w.label == picked), None)
        out.curve = self._curve(m, year, picked_window, windows, rows)
        out.defaulters = self._defaulters(m, rows, today, labels)
        out.carried = self._carried(m, rows, year)

        current = by_quarter.get(picked or "", Collection())
        prev = self._previous_pct(windows, picked, by_quarter)
        out.collected, out.pending, out.overdue = (
            current.collected, current.pending, current.overdue)
        out.billed, out.pct = current.billed, current.pct
        out.headline = collection_sentence(
            picked_window, current, len({d.student_fee_id for d in out.defaulters}), prev)
        return out

    @staticmethod
    def _previous_pct(windows: list[Quarter], picked: str | None,
                      by_quarter: dict[str, Collection]) -> float | None:
        """`S-155`: the quarter before this one, as the reference line. A bare
        rupee total decides nothing; *"6 points behind where Q1 stood"* does."""
        labels = [w.label for w in windows]
        if picked not in labels:
            return None
        i = labels.index(picked)
        if i == 0:
            return None
        return by_quarter.get(labels[i - 1], Collection()).pct

    def _curve(self, m: CurrentMember, year: AcademicYear, window: Quarter | None,
               windows: list[Quarter], rows: list[StudentFee]) -> list[CollectionPoint]:
        """Cumulative collection through the quarter, with the previous quarter
        laid over it by day-of-quarter (`S-155`) — the reference-line device
        `class-analytics` already uses for the first test."""
        if window is None:
            return []
        prev = next((w for i, w in enumerate(windows)
                     if i + 1 < len(windows) and windows[i + 1].label == window.label), None)
        spans = [(window, "this"), *([(prev, "prev")] if prev else [])]
        sums: dict[tuple[str, int], float] = defaultdict(float)
        sf_ids = [sf.id for sf in rows]
        if not sf_ids:
            return []
        paid_rows = self.db.execute(
            select(Installment.paid_date, func.sum(Installment.paid_amount))
            .where(Installment.student_fee_id.in_(sf_ids),
                   Installment.paid_date.is_not(None))
            .group_by(Installment.paid_date)).all()
        for paid_day, amount in paid_rows:
            if paid_day is None:
                continue
            day = paid_day if isinstance(paid_day, date) else date.fromisoformat(str(paid_day))
            for w, key in spans:
                if w.holds(day):
                    sums[(key, (day - w.start).days)] += float(amount or 0)

        out: list[CollectionPoint] = []
        run = {"this": 0.0, "prev": 0.0}
        today = today_in(m.org.timezone)
        for offset in range(window.days):
            day = window.start + timedelta(days=offset)
            run["this"] += sums.get(("this", offset), 0.0)
            run["prev"] += sums.get(("prev", offset), 0.0)
            if day > today:
                break        # never draw the future as a flat line
            out.append(CollectionPoint(day=day, collected=round(run["this"], 2),
                                       previous=round(run["prev"], 2) if prev else None))
        return out

    def _defaulters(self, m: CurrentMember, rows: list[StudentFee], today: date,
                    labels: dict) -> list[DefaulterRow]:
        """The named list — **built from what is owed**, never from enrolment or
        status (`S-158`: a child on a full concession owes ₹0 and must never
        appear here). Names the family, because the person who owes is the
        person you ring (`S-157`)."""
        owing: list[tuple[StudentFee, float, date | None]] = []
        for sf in rows:
            overdue_amt, earliest = 0.0, None
            for inst in live_installments(sf.installments):
                unpaid = float(q(inst.amount) - q(inst.paid_amount))
                if unpaid > 0 and inst.due_date and inst.due_date < today:
                    overdue_amt += unpaid
                    if earliest is None or inst.due_date < earliest:
                        earliest = inst.due_date
            if overdue_amt > 0:
                owing.append((sf, round(overdue_amt, 2), earliest))
        if not owing:
            return []
        owing.sort(key=lambda t: (t[2] or date.max, -t[1]))
        owing = owing[:_MAX_DEFAULTERS]

        student_ids = [sf.student_id for sf, _, _ in owing]
        guardians = self._guardians(student_ids)
        actions = self._recent_actions(m, student_ids)
        notes = self._latest_notes(m, [sf.id for sf, _, _ in owing])

        out: list[DefaulterRow] = []
        for sf, amount, earliest in owing:
            g = guardians.get(sf.student_id)
            act = actions.get(sf.student_id, {})
            note = notes.get(sf.id)
            out.append(DefaulterRow(
                student_fee_id=sf.id, student_id=sf.student_id,
                student_name=sf.student.full_name if sf.student else "",
                class_label=labels.get(sf.student.class_id) if sf.student else None,
                overdue_amount=amount, earliest_due_date=earliest,
                guardian_name=g[0] if g else None,
                guardian_phone=g[1] if g else None,
                other_guardians=g[2] if g else [],
                reminded_on=act.get("guardian_reminded"),
                assigned_on=act.get("followup_assigned"),
                last_said=note[0] if note else None,
                last_said_on=note[1] if note else None))
        return out

    def _carried(self, m: CurrentMember, rows: list[StudentFee],
                 year: AcademicYear) -> dict | None:
        """`D-88`: dues carried from a previous year are **never** folded into
        this year's totals — and never silently omitted either, which is what
        used to happen. Their own labelled line, with the year switcher as the
        route to the year that actually owns them."""
        total = sum(float(q(sf.opening_dues or 0)) for sf in rows)
        families = sum(1 for sf in rows if float(q(sf.opening_dues or 0)) > 0)
        if total <= 0:
            return None
        return {
            "amount": round(total, 2), "families": families,
            "note": (f"₹{total:,.0f} carried from before {year.label}, across {families} "
                     f"famil{'y' if families == 1 else 'ies'} — not counted in the figures "
                     "above. Switch the year to work on it."),
        }

    # ── the two actions (D-65) ───────────────────────────────────────────────
    def remind(self, m: CurrentMember, sf_id: uuid.UUID) -> RemindOut:
        """`S-156`: the reminder remembers it fired, and has money-specific
        manners — one per instalment per week however many staff press it, quiet
        hours, never to an opted-out guardian, and it **stops the moment the
        payment lands**, including a payment taken at the counter five minutes
        ago. Every reminder is a human press: no automatic dunning, because a
        message that fires itself will eventually reach a family in the week of
        a bereavement."""
        sf = self._student_fee(m, sf_id)
        today = today_in(m.org.timezone)
        due = self._next_due(sf, today)
        if due is None:
            # It stops the instant the payment lands.
            return RemindOut(sent=0, skipped="nothing_due",
                             message="Nothing is outstanding for this student.")

        recent = self.db.scalar(
            select(FollowupAction.created_at).where(
                FollowupAction.org_id == m.org_id,
                FollowupAction.kind == "guardian_reminded",
                FollowupAction.subject_type == "student",
                FollowupAction.subject_id == sf.student_id,
                FollowupAction.created_at
                >= datetime.now(UTC) - timedelta(days=_REMINDER_COOLDOWN_DAYS))
            .order_by(FollowupAction.created_at.desc()).limit(1))
        if recent is not None:
            return RemindOut(sent=0, skipped="already_reminded",
                             message=f"Already reminded on {recent.date():%d %b}.")

        hour = _local_hour(m)
        if hour < _QUIET_BEFORE or hour >= _QUIET_AFTER:
            return RemindOut(sent=0, skipped="quiet_hours",
                             message="Outside 8am–8pm — money messages wait until morning.")

        # `Q-70`: the PRIMARY guardian only. Money is the one topic where
        # messaging both parents can land badly inside a family; the admin sees
        # the other numbers on the row and rings them by hand.
        g = self._guardians([sf.student_id]).get(sf.student_id)
        if not g or not g[1]:
            return RemindOut(sent=0, skipped="no_number",
                             message="No guardian phone on record — ring the family instead.")
        amount, due_date = due
        text = (f"{sf.student.full_name if sf.student else 'Your child'}: ₹{amount:,.0f} "
                f"fee due{f' by {due_date:%d %b}' if due_date else ''}. "
                f"Please contact the school office if you need to discuss it.")
        if g[3]:
            return RemindOut(sent=0, skipped="opted_out",
                             message="That guardian has opted out of messages.")
        # V1-11 (`D-08`): the reminder is delivered in-app + web push, to the
        # PRIMARY guardian row only (`Q-70`). The cooldown, quiet hours and
        # stops-on-payment rules above are unchanged — they are this module's,
        # and money keeps stricter manners than any other message we send.
        primary = self.db.scalar(select(Guardian).where(
            Guardian.student_id == sf.student_id)
            .order_by(Guardian.is_primary.desc(), Guardian.created_at).limit(1))
        if primary is None:
            return RemindOut(sent=0, skipped="no_number",
                             message="No guardian on record — ring the family instead.")
        sent = notify_guardians(
            self.db, org_id=m.org_id, student_id=sf.student_id, guardians=[primary],
            kind="fee_reminder", title="Fee reminder", body=text).notified

        self.db.add(FollowupAction(
            org_id=m.org_id, kind="guardian_reminded", subject_type="student",
            subject_id=sf.student_id, actor_member_id=m.membership.id,
            detail={"module": "fees", "amount": amount,
                    "due_date": due_date.isoformat() if due_date else None}))
        self.db.add(FeeNote(
            org_id=m.org_id, student_fee_id=sf.id, kind="reminder",
            said=f"Reminder sent to {g[0]}.", author_member_id=m.membership.id))
        self.db.flush()
        return RemindOut(sent=sent, message=f"Reminded {g[0]}.")

    def assign_followup(self, m: CurrentMember, sf_id: uuid.UUID,
                        member_id: uuid.UUID, board_id: uuid.UUID | None = None,
                        ) -> uuid.UUID:
        """`D-83`: the assigned teacher gets **the full detail** — history, the
        instalment date, the pending amount and the conversation log — because
        the person making the call cannot make it usefully while blind to the
        number.

        The narrowing must be exact, and it is asserted by tests: only this
        student, only inside this task. No fees nav item for a teacher, no class
        list, no other family, and no fee field on any academic surface."""
        from app.schemas.task import TaskCreateRequest  # noqa: PLC0415
        from app.services.task import TaskService  # noqa: PLC0415

        sf = self._student_fee(m, sf_id)
        member = self.db.scalar(select(Membership).where(
            Membership.id == member_id, Membership.org_id == m.org_id))
        if member is None:
            raise NotFoundError("Member")
        today = today_in(m.org.timezone)
        due = self._next_due(sf, today)
        detail = self._detail_text(m, sf, due)

        board = board_id or self._followups_board(m)
        if board is None:
            raise ValidationError("Create a board for follow-ups first.", code="no_board")
        task = TaskService(self.db).create(m, TaskCreateRequest(
            board_id=board,
            title=f"Fee follow-up — {sf.student.full_name if sf.student else 'a student'}"
                  + (f" ({self._class_labels(m).get(sf.student.class_id)})"
                     if sf.student and sf.student.class_id else ""),
            description=detail, category="Fees", assignee_id=member.user_id,
            subject_type="student", subject_id=sf.student_id))
        self.db.add(FollowupAction(
            org_id=m.org_id, kind="followup_assigned", subject_type="student",
            subject_id=sf.student_id, actor_member_id=m.membership.id,
            target_member_id=member.id,
            detail={"module": "fees", "task_id": str(task.id)}))
        self.db.add(FeeNote(
            org_id=m.org_id, student_fee_id=sf.id, kind="assigned",
            said=f"Follow-up assigned to {self._member_name(member)}.",
            author_member_id=m.membership.id))
        self.db.flush()
        return task.id

    def _detail_text(self, m: CurrentMember, sf: StudentFee,
                     due: tuple[float, date | None] | None) -> str:
        """What travels into the task (`D-83`) — including the conversation log,
        so the next caller is not the fourth person this month to ask the family
        the same question (`D-84`)."""
        lines = []
        if due:
            amount, due_date = due
            lines.append(f"Pending: ₹{amount:,.0f}"
                         + (f", due {due_date:%d %b %Y}" if due_date else ""))
        paid = sum(float(q(i.paid_amount)) for i in sf.installments)
        lines.append(f"Paid so far this year: ₹{paid:,.0f} of ₹{float(q(sf.net_fee)):,.0f}")
        g = self._guardians([sf.student_id]).get(sf.student_id)
        if g:
            lines.append(f"Family: {g[0]}"
                         + (f" · {g[1]}" if g[1] else " · no number on record"))
        notes = self.notes(m, sf.id)[:4]
        if notes:
            lines.append("")
            lines.append("What the family has already said:")
            lines += [f"· {n.created_at:%d %b} — {n.said}" for n in notes if n.said]
        lines.append("")
        lines.append("Please speak to the family and record what they say.")
        return "\n".join(lines)

    # ── the conversation history (D-84) ──────────────────────────────────────
    def notes(self, m: CurrentMember, sf_id: uuid.UUID) -> list[FeeNoteOut]:
        rows = self.db.execute(
            select(FeeNote, User.name)
            .outerjoin(Membership, Membership.id == FeeNote.author_member_id)
            .outerjoin(User, User.id == Membership.user_id)
            .where(FeeNote.org_id == m.org_id, FeeNote.student_fee_id == sf_id)
            .order_by(FeeNote.created_at.desc())).all()
        return [FeeNoteOut(id=n.id, kind=n.kind, said=n.said,
                           promised_date=n.promised_date, author_name=name,
                           created_at=n.created_at) for n, name in rows]

    def add_note(self, m: CurrentMember, sf_id: uuid.UUID, body: FeeNoteIn) -> FeeNoteOut:
        """Append-only (law 3) — nothing here is ever edited. `said` is what
        makes the row worth keeping: *"spoke to the mother — paying after the
        15th"*, not *"reminded"*."""
        sf = self._student_fee(m, sf_id)
        note = FeeNote(org_id=m.org_id, student_fee_id=sf.id, kind=body.kind,
                       said=(body.said or "").strip() or None,
                       promised_date=body.promised_date,
                       author_member_id=m.membership.id)
        self.db.add(note)
        self.db.flush()
        return self.notes(m, sf.id)[0]

    # ── D-83: the one place a teacher may see fee detail ─────────────────────
    def followup_detail(self, m: CurrentMember, task_id: uuid.UUID) -> FeeFollowupDetail:
        """The assigned teacher's view of ONE student's fee, **inside the task**.

        The guard is the whole feature: the caller must be an admin, or the
        assignee of an open fee follow-up task naming this student. Anything
        else is a 403 — there is no route from here to a class list, a
        collection figure or another family."""
        task = self.db.scalar(select(TaskInstance).where(
            TaskInstance.id == task_id, TaskInstance.org_id == m.org_id))
        if task is None:
            raise NotFoundError("Task")
        if not m.is_coordinator_up and task.assignee_id != m.user_id:
            raise ForbiddenError("This follow-up is not yours.", code="not_your_task")
        if task.subject_type != "student" or task.subject_id is None:
            raise ValidationError("That task is not about a student.", code="not_a_student_task")

        sf = self.db.scalar(
            select(StudentFee).options(
                selectinload(StudentFee.installments), selectinload(StudentFee.student))
            .where(StudentFee.org_id == m.org_id,
                   StudentFee.student_id == task.subject_id)
            .order_by(StudentFee.created_at.desc()).limit(1))
        if sf is None:
            raise NotFoundError("Fee record")
        today = today_in(m.org.timezone)
        due = self._next_due(sf, today)
        g = self._guardians([sf.student_id]).get(sf.student_id)
        return FeeFollowupDetail(
            task_id=task.id, student_id=sf.student_id,
            student_fee_id=sf.id,
            student_name=sf.student.full_name if sf.student else "",
            class_label=(self._class_labels(m).get(sf.student.class_id)
                         if sf.student else None),
            pending_amount=due[0] if due else 0.0,
            due_date=due[1] if due else None,
            paid_so_far=round(sum(float(q(i.paid_amount)) for i in sf.installments), 2),
            total_fee=float(q(sf.net_fee)),
            guardian_name=g[0] if g else None,
            guardian_phone=g[1] if g else None,
            notes=self.notes(m, sf.id))

    # ── helpers ──────────────────────────────────────────────────────────────
    def _rows(self, m: CurrentMember, year_id: uuid.UUID) -> list[StudentFee]:
        return list(self.db.scalars(
            select(StudentFee)
            .options(selectinload(StudentFee.installments),
                     selectinload(StudentFee.student))
            .where(StudentFee.org_id == m.org_id,
                   StudentFee.academic_year_id == year_id)))

    def _year(self, m: CurrentMember, year_id: uuid.UUID | None) -> AcademicYear | None:
        if year_id:
            return self.db.scalar(select(AcademicYear).where(
                AcademicYear.id == year_id, AcademicYear.org_id == m.org_id))
        return self.db.scalar(select(AcademicYear).where(
            AcademicYear.org_id == m.org_id, AcademicYear.is_active.is_(True)))

    def _class_labels(self, m: CurrentMember) -> dict[uuid.UUID, str]:
        return {cid: _label(name, sec) for cid, name, sec in self.db.execute(
            select(SchoolClass.id, SchoolClass.name, SchoolClass.section)
            .where(SchoolClass.org_id == m.org_id)).all()}

    def _class_sizes(self, m: CurrentMember) -> dict[uuid.UUID, int]:
        return dict(self.db.execute(
            select(Student.class_id, func.count()).where(
                Student.org_id == m.org_id, Student.status == "active")
            .group_by(Student.class_id)).all())

    def _guardians(self, student_ids: list[uuid.UUID],
                   ) -> dict[uuid.UUID, tuple[str, str | None, list[dict], bool]]:
        """student → (primary name, primary phone, the other numbers, opted out).

        `Q-70`: the message goes to the primary only; the others ride along so
        the admin can ring them by hand from the same row."""
        if not student_ids:
            return {}
        rows = list(self.db.scalars(select(Guardian).where(
            Guardian.student_id.in_(student_ids))
            .order_by(Guardian.is_primary.desc(), Guardian.created_at)))
        out: dict[uuid.UUID, tuple] = {}
        others: dict[uuid.UUID, list[dict]] = defaultdict(list)
        for g in rows:
            if g.student_id in out:
                others[g.student_id].append({"name": g.name, "phone": g.phone})
                continue
            out[g.student_id] = (g.name, g.phone, [], bool(g.notify_opt_out))
        return {sid: (v[0], v[1], others.get(sid, []), v[3]) for sid, v in out.items()}

    def _recent_actions(self, m: CurrentMember, student_ids: list[uuid.UUID],
                        ) -> dict[uuid.UUID, dict[str, date]]:
        """`S-156`/ux §7: one query for the whole list, so every row can say
        *"reminded this morning by Priya"* instead of the same family being
        chased three times before lunch."""
        if not student_ids:
            return {}
        rows = self.db.execute(
            select(FollowupAction.subject_id, FollowupAction.kind,
                   func.max(FollowupAction.created_at))
            .where(FollowupAction.org_id == m.org_id,
                   FollowupAction.subject_type == "student",
                   FollowupAction.subject_id.in_(student_ids),
                   FollowupAction.kind.in_(("guardian_reminded", "followup_assigned")))
            .group_by(FollowupAction.subject_id, FollowupAction.kind)).all()
        out: dict[uuid.UUID, dict[str, date]] = defaultdict(dict)
        for sid, kind, when in rows:
            if when is not None:
                out[sid][kind] = when.date()
        return out

    def _latest_notes(self, m: CurrentMember, sf_ids: list[uuid.UUID],
                      ) -> dict[uuid.UUID, tuple[str, date]]:
        """The newest thing the family actually said, per row — so the board
        shows the conversation, not just that a button was pressed (`S-161`)."""
        if not sf_ids:
            return {}
        rows = self.db.execute(
            select(FeeNote.student_fee_id, FeeNote.said, FeeNote.created_at)
            .where(FeeNote.org_id == m.org_id, FeeNote.student_fee_id.in_(sf_ids),
                   FeeNote.said.is_not(None))
            .order_by(FeeNote.created_at.desc())).all()
        out: dict[uuid.UUID, tuple[str, date]] = {}
        for sf_id, said, when in rows:
            out.setdefault(sf_id, (said, when.date()))
        return out

    def _student_fee(self, m: CurrentMember, sf_id: uuid.UUID) -> StudentFee:
        sf = self.db.scalar(
            select(StudentFee).options(
                selectinload(StudentFee.installments), selectinload(StudentFee.student))
            .where(StudentFee.id == sf_id, StudentFee.org_id == m.org_id))
        if sf is None:
            raise NotFoundError("Fee record")
        return sf

    @staticmethod
    def _next_due(sf: StudentFee, today: date) -> tuple[float, date | None] | None:
        """(amount outstanding, the earliest unpaid due date) or None when the
        family owes nothing — which is what makes the reminder stop the moment a
        payment lands."""
        total, earliest = 0.0, None
        for inst in live_installments(sf.installments):
            unpaid = float(q(inst.amount) - q(inst.paid_amount))
            if unpaid <= 0:
                continue
            total += unpaid
            if inst.due_date and (earliest is None or inst.due_date < earliest):
                earliest = inst.due_date
        return (round(total, 2), earliest) if total > 0 else None

    def _followups_board(self, m: CurrentMember) -> uuid.UUID | None:
        from app.models import Board  # noqa: PLC0415

        return self.db.scalar(
            select(Board.id).where(Board.org_id == m.org_id, Board.name == "Follow-ups")
        ) or self.db.scalar(select(Board.id).where(Board.org_id == m.org_id)
                            .order_by(Board.created_at).limit(1))

    def _member_name(self, member: Membership) -> str:
        return self.db.scalar(select(User.name).where(User.id == member.user_id)) or "a teacher"


def _local_hour(m: CurrentMember) -> int:
    """The org's local hour — quiet hours are the school's, not the server's."""
    from zoneinfo import ZoneInfo  # noqa: PLC0415

    try:
        return datetime.now(ZoneInfo(m.org.timezone)).hour
    except Exception:  # noqa: BLE001 — a bad tz must never block a reminder
        return datetime.now(UTC).hour
