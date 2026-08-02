"""Guardian messaging — V1-11 (`D-08`, `D-14`, `S-62`).

**What changed.** Until now this module was a WhatsApp stub: every guardian
message — the absence alert, homework set, the Saturday note — ended its life
as a line in a log file, whatever keys were configured. `D-08` takes WhatsApp
out of this version entirely, so the message needs a real destination, and
`D-14` names it: a row the parent reads in the portal, woken up by web push.

**The three rules this module exists to hold.**

1. **Every message is recorded, delivered or not.** A `guardian_messages` row
   is written even when we know push will not arrive. That is deliberate: the
   parent still sees it next time they open the portal, and the office still
   gets to see that nobody was reached.

2. **`S-62` — reach is recorded honestly.** Push is best-effort (iOS wants the
   site installed to the home screen, permission can be denied, phones are
   off); the absence alert is not best-effort. So `unreachable_reason` names
   why a message did not arrive and the admin's board lists those families for
   the office to phone. *Removing WhatsApp does not remove the reach problem —
   it makes it visible.*

3. **Never a band, a tier, a skill or an observation** (P4). Callers pass plain
   sentences; nothing in here composes text from staff-only data.

Delivery never breaks the work that triggered it. A teacher marking attendance
is not made to wait on a push endpoint, and a failure there must never roll back
her capture — every send is wrapped, and a failure becomes an unreachable row.
"""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Guardian, GuardianMessage

logger = logging.getLogger("guardian_notify")


class GuardianDelivery(NamedTuple):
    """What actually happened, in the four numbers a caller may need.

    `notified` deliberately EXCLUDES opted-out guardians: a family that asked
    not to be messaged was not messaged, and a caller reporting "2 guardians
    notified" when one of them opted out would be lying to the teacher. They
    are counted separately, and never mixed into a failure figure either —
    opting out is a choice, not a delivery problem to be chased.
    """

    notified: int      # guardians we actually messaged
    pushed: int        # ...of those, how many woke a device (D-14)
    unreachable: int   # ...of those, how many got nothing — the office's list (S-62)
    opted_out: int     # asked not to be messaged; not notified, not a failure


def notify_guardians(
    db: Session,
    *,
    org_id: uuid.UUID,
    student_id: uuid.UUID,
    guardians: Sequence[Guardian],
    kind: str,
    title: str,
    body: str,
    url: str | None = None,
    dedupe_key: str | None = None,
) -> GuardianDelivery:
    """Deliver `body` to each guardian: an inbox row + a best-effort push.

    `dedupe_key`, if given, is a per-message key; the guardian's id is appended
    so one alert reaches both parents exactly once each. A repeat call with the
    same key is a no-op — a family chased twice for one absence stops reading
    the channel, which is the channel the school needs next week.
    """
    from app.services.dispatcher import push_to_user  # noqa: PLC0415 — no import cycle

    notified = pushed = unreachable = opted_out = 0
    for g in guardians:
        key = f"{dedupe_key}:{g.id}" if dedupe_key else None
        if key is not None and db.scalar(
                select(GuardianMessage.id).where(GuardianMessage.dedupe_key == key)):
            continue

        # `notify_opt_out` is a choice about being *messaged*, not about the
        # portal. The row is still written so the archive is complete if they
        # ever open it, and the reason is named so the office can see that this
        # family will not be reached by push — and decide, rather than discover.
        reason: str | None = None
        sent_at: datetime | None = None
        if g.notify_opt_out:
            reason = "opted_out"
        elif g.user_id is None:
            reason = "no_login"
        else:
            try:
                ok, had_devices = push_to_user(
                    db, g.user_id, title=title, body=body,
                    url=f"{settings.FRONTEND_BASE_URL}{url or '/parent'}")
            except Exception:  # noqa: BLE001 — delivery never breaks capture
                logger.exception("guardian push failed for %s", g.id)
                ok, had_devices = False, True
            if ok:
                sent_at = datetime.now(UTC)
            else:
                reason = "push_failed" if had_devices else "no_device"

        db.add(GuardianMessage(
            org_id=org_id, guardian_id=g.id, student_id=student_id, kind=kind,
            title=title, body=body, url=url, push_sent_at=sent_at,
            unreachable_reason=reason, dedupe_key=key))
        if reason == "opted_out":
            opted_out += 1
        elif sent_at is not None:
            notified += 1
            pushed += 1
        else:
            notified += 1
            unreachable += 1

    db.flush()
    if unreachable:
        logger.info("guardian message '%s' for student %s: %d pushed, %d unreachable",
                    kind, student_id, pushed, unreachable)
    return GuardianDelivery(notified=notified, pushed=pushed,
                            unreachable=unreachable, opted_out=opted_out)
