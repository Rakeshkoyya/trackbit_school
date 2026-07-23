"""OTP delivery: WhatsApp authentication template first, MSG91 SMS fallback.

Env-gated like every integration: with neither channel configured the code is
logged to the console (dev + tests + pilot-start). Real sends use httpx with a
short timeout and fail SOFT — a provider error falls through to the next
channel and finally to the console log, so login is never blocked by delivery.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("otp")


def send_otp(phone: str, code: str) -> str:
    """Deliver `code` to E.164 `phone`. Returns the channel used
    ('whatsapp' | 'sms' | 'stub')."""
    if settings.whatsapp_configured and _send_whatsapp(phone, code):
        return "whatsapp"
    if settings.msg91_configured and _send_msg91(phone, code):
        return "sms"
    logger.info("[OTP stub] would send to %s: code %s", phone, code)
    return "stub"


def _send_whatsapp(phone: str, code: str) -> bool:
    """Meta WhatsApp Cloud API authentication template (no DLT needed).
    WHATSAPP_SENDER is the phone-number id; the template must be a pre-approved
    'authentication' template with a copy-code button."""
    try:
        r = httpx.post(
            f"https://graph.facebook.com/v20.0/{settings.WHATSAPP_SENDER}/messages",
            headers={"Authorization": f"Bearer {settings.WHATSAPP_API_KEY}"},
            json={
                "messaging_product": "whatsapp",
                "to": phone.lstrip("+"),
                "type": "template",
                "template": {
                    "name": settings.WHATSAPP_OTP_TEMPLATE,
                    "language": {"code": "en"},
                    "components": [
                        {"type": "body",
                         "parameters": [{"type": "text", "text": code}]},
                        {"type": "button", "sub_type": "url", "index": "0",
                         "parameters": [{"type": "text", "text": code}]},
                    ],
                },
            },
            timeout=10.0,
        )
        if r.status_code < 300:
            return True
        logger.warning("WhatsApp OTP send failed (%s): %s", r.status_code, r.text[:300])
    except httpx.HTTPError as exc:
        logger.warning("WhatsApp OTP send error: %s", exc)
    return False


def _send_msg91(phone: str, code: str) -> bool:
    """MSG91 OTP API with our own code (DLT-registered template with ##OTP##)."""
    try:
        r = httpx.post(
            "https://control.msg91.com/api/v5/otp",
            params={
                "template_id": settings.MSG91_OTP_TEMPLATE_ID,
                "mobile": phone.lstrip("+"),
                "otp": code,
                "otp_expiry": settings.OTP_EXPIRE_MINUTES,
            },
            headers={"authkey": settings.MSG91_AUTH_KEY},
            timeout=10.0,
        )
        if r.status_code < 300 and '"type":"success"' in r.text.replace(" ", ""):
            return True
        logger.warning("MSG91 OTP send failed (%s): %s", r.status_code, r.text[:300])
    except httpx.HTTPError as exc:
        logger.warning("MSG91 OTP send error: %s", exc)
    return False
