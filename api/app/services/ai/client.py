"""The single internal AI client (SPRD2 §8) — OpenRouter, OpenAI-compatible.

One endpoint (`POST /chat/completions`), one key, any model. Model ids are env
config (`AI_MODEL_DRAFT` / `AI_MODEL_PARSE`), so upgrading a model is a deploy
variable, not a code change.

Two rules make this safe to put in the setup wizard's critical path:

**It is env-gated.** With no `OPENROUTER_API_KEY`, `chat_json` returns None
immediately without touching the network. Every caller already has a
deterministic heuristic to fall back on, so the entire ingestion flow — gap
detection, column mapping, syllabus splitting — runs and is tested offline.

**It fails soft, never up.** A timeout, a rate limit, a 500, a truncated body,
a model that ignored the JSON instruction: all of it returns None. An admin
importing a staff sheet on a Monday morning must never see a stack trace because
a model was slow. The heuristic result is always the floor, and AI can only
improve on it.

Nothing here writes to a table. The output goes to a human-confirm surface.
"""

import json
import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Guard against a model that ignores the schema and streams prose forever.
MAX_TOKENS = 2000


def _headers() -> dict[str, str]:
    h = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    # Optional attribution headers; OpenRouter ignores them when blank.
    if settings.OPENROUTER_SITE_URL:
        h["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
    if settings.OPENROUTER_APP_NAME:
        h["X-Title"] = settings.OPENROUTER_APP_NAME
    return h


def _extract_json(text: str) -> dict[str, Any] | None:
    """Parse the model's reply as a JSON object.

    `response_format={"type": "json_object"}` makes this reliable on models that
    support it, but not every OpenRouter model honours it — some still wrap the
    object in prose or a ```json fence. Slice to the outermost braces before
    giving up, rather than discarding an otherwise-good answer."""
    text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def chat_json(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = MAX_TOKENS,
) -> dict[str, Any] | None:
    """Ask for a JSON object. Returns None when AI is off or anything goes wrong.

    Callers MUST treat None as "use the heuristic", never as an error."""
    if not settings.ai_configured:
        return None

    payload = {
        "model": model or settings.AI_MODEL_PARSE,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "max_tokens": max_tokens,
    }

    url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions"
    last_error: object = None

    for attempt in range(settings.AI_MAX_RETRIES + 1):
        try:
            response = httpx.post(
                url, headers=_headers(), json=payload, timeout=settings.AI_TIMEOUT_SECONDS)
        except httpx.HTTPError as exc:  # timeout, DNS, connection reset — worth a retry
            last_error = exc
            if attempt >= settings.AI_MAX_RETRIES:
                break
            continue

        status = response.status_code
        # Rate limits and server errors are transient. Everything else in 4xx is
        # our bug — a bad key, a model slug that doesn't exist — and retrying just
        # makes the admin watch the spinner twice as long for the same failure.
        if status == 429 or status >= 500:
            last_error = f"retryable HTTP {status}"
            if attempt >= settings.AI_MAX_RETRIES:
                break
            continue
        if status >= 400:
            last_error = f"HTTP {status}: {response.text[:200]}"
            break

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            last_error = exc
            break
        return _extract_json(content)

    logger.warning("AI call failed, falling back to heuristic: %s", last_error)
    return None
