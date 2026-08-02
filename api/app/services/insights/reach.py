"""`S-62` — who the school did not reach, and who to phone about it.

`D-08` took WhatsApp out of this version and `D-14` replaced it with in-app
messages plus web push. That is a better channel in almost every way, with one
honest weakness: **push is best-effort and the absence alert is not.** iOS wants
the site installed to the home screen before push works at all, permission can
be denied, and a phone can simply be off. So the message that matters most is
carried by the least reliable mechanism.

The answer is not to pretend otherwise. Every guardian message records whether
it arrived (`guardian_messages.push_sent_at` / `unreachable_reason`), and this
module turns those rows into the short list the office can actually work: *this
family was told nothing today, here is the number, ring them.*

Two rules the module holds:

* **Named rows, never a count.** "7 unreachable" sends someone looking; "Aisha
  Khan's family — no app yet · 98xxxxxx21" does not. Same rule as the rest of
  the board (DASH3).
* **An opted-out family is not a failure.** They are listed separately and
  never mixed into the number the office is asked to clear — chasing someone who
  asked not to be messaged is how a school loses the channel entirely.
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.models import Guardian, GuardianMessage, Student
from app.schemas.insights import ReachBoard, ReachRow
from app.services.school_clock import today_in

# The kinds worth phoning about. A homework note that did not arrive is a small
# loss; an absence alert that did not arrive is the whole point of the module.
_URGENT_KINDS = ("absence", "left_after_lunch")

_REASON_WORDS = {
    "no_login": "hasn't signed in to the app yet",
    "no_device": "signed in, but notifications are off",
    "push_failed": "notification didn't get through",
    "opted_out": "asked not to be messaged",
}

_MAX_ROWS = 40


class ReachInsights:
    def __init__(self, db: Session):
        self.db = db

    def board(self, m: CurrentMember, on_date: date | None = None) -> ReachBoard:
        d = on_date or today_in(m.org.timezone)
        # `created_at` is timestamptz, so the bound is tz-aware too — a naive
        # datetime would be coerced using whatever the session timezone happens
        # to be. Deliberately generous (from midnight UTC the previous day):
        # the office would rather see one stale name than miss a live one.
        start = datetime.combine(d - timedelta(days=1), time.min, tzinfo=UTC)
        rows = self.db.execute(
            select(GuardianMessage, Guardian, Student.full_name)
            .join(Guardian, Guardian.id == GuardianMessage.guardian_id)
            .join(Student, Student.id == GuardianMessage.student_id)
            .where(GuardianMessage.org_id == m.org_id,
                   GuardianMessage.created_at >= start)
            .order_by(GuardianMessage.created_at.desc())
        ).all()

        sent = len(rows)
        delivered = sum(1 for gm, _, _ in rows if gm.push_sent_at is not None)
        out: list[ReachRow] = []
        opted_out = 0
        seen: set[tuple[uuid.UUID, str]] = set()
        for gm, g, student_name in rows:
            if gm.unreachable_reason is None:
                continue
            if gm.unreachable_reason == "opted_out":
                opted_out += 1
                continue
            if gm.kind not in _URGENT_KINDS:
                continue
            # One row per family per message kind: two absence alerts for the
            # same child in one day is one phone call, not two.
            key = (g.id, gm.kind)
            if key in seen:
                continue
            seen.add(key)
            out.append(ReachRow(
                student_id=gm.student_id, student_name=student_name,
                guardian_name=g.name, phone=g.phone, kind=gm.kind,
                title=gm.title,
                reason=_REASON_WORDS.get(gm.unreachable_reason, gm.unreachable_reason),
                reason_code=gm.unreachable_reason,
                created_at=gm.created_at))

        return ReachBoard(
            date=d, messages_sent=sent, delivered=delivered,
            unreachable=len(out), opted_out=opted_out,
            summary=self._summary(sent, delivered, len(out)),
            rows=out[:_MAX_ROWS])

    @staticmethod
    def _summary(sent: int, delivered: int, unreachable: int) -> str:
        """Lead with a sentence, and carry the denominator (ux-principles)."""
        if not sent:
            return "No messages went out to families today."
        if not unreachable:
            return f"All {sent} messages to families reached a phone."
        return (f"{delivered} of {sent} messages reached a phone — "
                f"{unreachable} {'family' if unreachable == 1 else 'families'} "
                "worth a call.")
