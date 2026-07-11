"""`scores` (SC-1) — transcribe a photographed marksheet; never decide identity.

One job: a photo of evaluated papers or a teacher's mark register → the rows
printed on it, exactly as printed. The model transcribes `{name, roll, score,
max_score}`; it is never asked which *student* a row belongs to — that mapping is
the deterministic matcher's job (`score_match.py`), so a hallucinated name can
never write a score.

Env-gated like every AI service: with no `OPENROUTER_API_KEY` this returns None
and the capture stays in `uploaded` — photos kept as evidence, grid entry stays
manual. Nothing here persists; the output lands in the review grid the teacher
confirms (§8).
"""

from app.core.config import settings
from app.services.ai.client import chat_json, is_visual

_MARKSHEET_SYSTEM = (
    "You read a photo of evaluated school test papers or a teacher's handwritten mark "
    "register. Transcribe every student row you can read. Reply with ONLY "
    '{"rows": [{"name": "...", "roll": "...", "score": 12, "max_score": 20}]}. '
    "name = the student's name exactly as written; roll = the roll/admission number if "
    "one is visible, else null; score = the marks awarded; max_score = the maximum marks "
    "if printed, else null. Never invent a row, never guess an illegible score — skip "
    "that row instead. Do not translate or reorder."
)


def extract_marksheet(filename: str, data: bytes) -> list[dict] | None:
    """One photographed page → transcribed rows.

    Returns None when AI is off, the file isn't a readable format, or the call
    fails — the caller must say so, not pretend it read a blank page. An empty
    list means the model read the page and found no score rows on it."""
    if not settings.ai_configured or not is_visual(filename):
        return None
    result = chat_json(
        _MARKSHEET_SYSTEM,
        "Transcribe the scores on this page.",
        model=settings.AI_MODEL_PARSE,
        max_tokens=4000,
        attachment=(filename, data),
    )
    if result is None:
        return None
    rows = result.get("rows")
    if not isinstance(rows, list):
        return None

    clean: list[dict] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        name = str(r.get("name") or "").strip()
        try:
            score = float(r.get("score"))
        except (TypeError, ValueError):
            continue
        if not name or score < 0:
            continue
        raw_max = r.get("max_score")
        try:
            max_score = float(raw_max) if raw_max not in (None, "") else None
        except (TypeError, ValueError):
            max_score = None
        if max_score is not None and max_score <= 0:
            max_score = None
        roll = str(r.get("roll") or "").strip() or None
        clean.append({"name_text": name, "roll_text": roll,
                      "score": score, "max_score": max_score})
    return clean
