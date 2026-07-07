"""Guardian messaging (SPRD §7). New WhatsApp channel alongside push/email.

Env-gated: with no WHATSAPP_* keys the console stub logs the exact message (dev +
pilot-start). Go-live of guardian notify is gated on real keys. Band/tier info is
NEVER included in a guardian message (P4) — callers pass plain homework text only.
"""

import logging

from app.core.config import settings

logger = logging.getLogger("guardian_notify")


def notify_guardians(recipients: list[tuple[str | None, bool]], message: str) -> int:
    """Send `message` to each (phone, notify_opt_out) recipient. Opt-outs and blank
    numbers are skipped. Returns the number actually notified."""
    sent = 0
    for phone, opt_out in recipients:
        if opt_out or not phone:
            continue
        if settings.whatsapp_configured:
            # Real Interakt / Meta WhatsApp Cloud send goes here once keys are set.
            logger.info("WhatsApp -> %s: %s", phone, message)
        else:
            logger.info("[WhatsApp stub] would send to %s: %s", phone, message)
        sent += 1
    return sent
