"""`extract` (SPRD2 §8) — AI assists the importer; it never decides for it.

Three jobs, all optional, all falling back to a deterministic heuristic:

  * `suggest_mapping`   — when the keyword heuristic can't find a required column,
                          ask the model which column holds it. The model sees the
                          headers and a few sample rows, and may only answer with
                          columns that actually exist.
  * `phrase_gap_question` — turn a gap the *validator* found into a sentence an
                          admin wants to read.
  * `split_syllabus_text` — free text → chapters and topics with period estimates.

The division of labour is the whole design. **Deterministic validators decide what
is missing; the model only proposes and phrases.** With no `OPENROUTER_API_KEY`
every function here returns its heuristic answer, so the setup wizard runs, and is
tested, entirely offline. Nothing here persists — the output lands in a review
screen the admin confirms.
"""

import re
from typing import Any

from app.core.config import settings
from app.services.ai.client import chat_json, is_visual

# Deterministic phrasings used when no key is configured.
_TEMPLATES: dict[str, str] = {
    "students": "Which column holds each student's {label}?",
    "staff": "Which column holds each teacher's {label}?",
    "syllabus": "Which column holds the {label}?",
}

_MAPPING_SYSTEM = (
    "You map spreadsheet columns to known fields for an Indian school's records. "
    "Reply with ONLY a JSON object of the form {\"mapping\": {\"field\": \"Column Header\"}}. "
    "Use a column header EXACTLY as given. Omit any field you are not confident about — "
    "a missing field is fine, a wrong one is not. Never invent a column."
)

_QUESTION_SYSTEM = (
    "You write one short question for a school administrator who is importing a "
    "spreadsheet. Reply with ONLY {\"question\": \"...\"}. One sentence, plain English, "
    "no jargon, no preamble. Ask which column holds the named field."
)

_SPLIT_SYSTEM = (
    "You convert a school syllabus into structured chapters and topics. Reply with ONLY "
    "{\"units\": [{\"title\": \"...\", \"topics\": [{\"title\": \"...\", \"est_periods\": 1}]}]}. "
    "Preserve the document's order. est_periods is the number of class periods a topic "
    "needs; use the document's own number when it states one, otherwise 1. Never invent "
    "chapters or topics that are not in the text."
)

_OCR_SYSTEM = (
    "You read a scanned or photographed school syllabus. Transcribe it faithfully as plain "
    "text, preserving the chapter/topic hierarchy and any period or day counts exactly as "
    "printed. Reply with ONLY {\"text\": \"...\"}. Do not summarise, reorder, translate, or "
    "add anything that is not in the document. If a line is illegible, write [illegible]."
)


def suggest_mapping(
    kind: str, fields: list[str], columns: list[str], sample_rows: list[dict[str, Any]],
) -> dict[str, str]:
    """Propose `field -> column` for fields the heuristic could not map.

    Returns {} when AI is off or the call fails. The result is **filtered against
    the real column list** before it is returned, so a hallucinated header can
    never reach the importer — and the admin still confirms it on screen."""
    if not settings.ai_configured or not fields or not columns:
        return {}

    preview = sample_rows[:3]
    user = (
        f"Record type: {kind}\n"
        f"Columns: {columns}\n"
        f"Sample rows: {preview}\n"
        f"Map these fields if you can: {fields}"
    )
    result = chat_json(_MAPPING_SYSTEM, user, model=settings.AI_MODEL_PARSE)
    if not result:
        return {}

    proposed = result.get("mapping")
    if not isinstance(proposed, dict):
        return {}

    allowed = set(columns)
    wanted = set(fields)
    return {
        field: column
        for field, column in proposed.items()
        if field in wanted and isinstance(column, str) and column in allowed
    }


def phrase_gap_question(kind: str, field: str, label: str, unmapped_columns: list[str]) -> dict:
    """One gap → one question the admin can answer in a tap.

    `options` are the columns we could not map to anything, because the answer is
    almost always one of them. "skip" is always allowed: a required field the admin
    declines is handled by the importer's per-row error list, never by a crash."""
    template = _TEMPLATES.get(kind, "Which column holds the {label}?")
    text = template.format(label=label)
    source = "fixture"

    if settings.ai_configured:
        user = (
            f"Record type: {kind}\nField we could not find: {label}\n"
            f"Unused columns in their file: {unmapped_columns}"
        )
        result = chat_json(_QUESTION_SYSTEM, user, model=settings.AI_MODEL_DRAFT, max_tokens=200)
        phrased = (result or {}).get("question")
        if isinstance(phrased, str) and phrased.strip():
            text = phrased.strip()
            source = "ai"

    return {
        "field": field,
        "label": label,
        "question": text,
        "options": list(unmapped_columns),
        "skippable": True,
        "source": source,
    }


def ocr_document(filename: str, data: bytes) -> str | None:
    """Scanned syllabus / photo of a printed one → plain text.

    Uses AI_MODEL_PARSE, which must be multimodal (gemini-2.5-flash-lite accepts
    image and PDF; deepseek does not). Returns None when AI is off, the format
    isn't one a model can read, or the call fails — the caller then has nothing to
    parse, and must say so rather than pretend it read an empty document."""
    if not settings.ai_configured or not is_visual(filename):
        return None
    result = chat_json(
        _OCR_SYSTEM,
        "Transcribe this syllabus document.",
        model=settings.AI_MODEL_PARSE,
        max_tokens=8000,
        attachment=(filename, data),
    )
    text = (result or {}).get("text")
    return text.strip() if isinstance(text, str) and text.strip() else None


def _split_syllabus_heuristic(text: str) -> list[dict]:
    """A line that looks like a heading — "Unit 2", "Chapter 4: Plants", ALL CAPS, or
    trailing ':' — opens a chapter; everything under it is a topic. A trailing "(3)"
    or "- 3 periods" on a topic line is read as its period estimate.

    A topic line with no number is left UNSIZED (`est_periods=None`), not 1: the
    document did not say, and guessing 1 is what made an unplanned year look green."""
    units: list[dict] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        is_heading = (
            line.endswith(":")
            or (line.isupper() and len(line) > 2)
            or bool(re.match(r"^(unit|chapter)\b", line, re.I))
        )
        if is_heading:
            title = line.split(":", 1)[1].strip() if ":" in line else line.rstrip(":").strip()
            units.append({"title": title or line.rstrip(":").strip(), "topics": []})
            continue
        if not units:
            units.append({"title": "Chapter 1", "topics": []})

        est = None
        m = re.search(r"[(\-–]\s*(\d+)\s*(?:periods?|prds?|p)?\s*\)?\s*$", line, re.I)
        if m:
            est = max(1, int(m.group(1)))
            line = line[: m.start()].strip(" -–\t")
        units[-1]["topics"].append({"title": line, "est_periods": est})
    return [u for u in units if u["topics"]]


def _clean_units(raw: Any) -> list[dict]:
    """Coerce a model reply into the draft shape, dropping anything malformed."""
    if not isinstance(raw, list):
        return []
    units: list[dict] = []
    for u in raw:
        if not isinstance(u, dict):
            continue
        title = str(u.get("title") or "").strip()
        topics_in = u.get("topics")
        if not title or not isinstance(topics_in, list):
            continue
        topics: list[dict] = []
        for t in topics_in:
            if not isinstance(t, dict):
                continue
            t_title = str(t.get("title") or "").strip()
            if not t_title:
                continue
            # No estimate stays None ("not sized yet"). Coercing it to 1 would let an
            # unplanned chapter masquerade as a one-period chapter in the forecast.
            raw_est = t.get("est_periods")
            if raw_est is None or raw_est == "":
                est = None
            else:
                try:
                    est = max(1, int(raw_est))
                except (TypeError, ValueError):
                    est = None
            topics.append({"title": t_title, "est_periods": est})
        if topics:
            units.append({"title": title, "topics": topics})
    return units


def split_syllabus_text(text: str) -> list[dict]:
    """Free text → [{title, topics: [{title, est_periods}]}].

    The model handles the messy real-world cases the heuristic can't — chapters
    numbered in Roman numerals, topics on the same line, no punctuation. It is only
    trusted when it returns something well-formed; otherwise the heuristic wins."""
    if settings.ai_configured and text.strip():
        # Reasoning job -> DRAFT. Structure, not transcription.
        result = chat_json(_SPLIT_SYSTEM, text[:20000], model=settings.AI_MODEL_DRAFT,
                           max_tokens=4000)
        units = _clean_units((result or {}).get("units"))
        if units:
            return units
    return _split_syllabus_heuristic(text)
