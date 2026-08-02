"""`scores` (SC-1/SC-5/V1-8) — transcribe a photographed paper; never decide identity.

One job: a photo of evaluated papers or a teacher's mark register → what is
printed on it, exactly as printed. The model transcribes the exam header (title,
subject, total marks, topic, date) and the student rows `{name, roll, score,
max_score}`; it is never asked which *student* a row belongs to — that mapping is
the deterministic matcher's job (`score_match.py`), so a hallucinated name can
never write a score. Likewise the header only *prefills* the exam form the human
reviews; the deterministic subject match happens in `score_capture.py`.

**V1-8 (`D-80`) adds `extract_script`: one photo of ONE student's marked answer
script**, which is now the primary flow — a photo per paper, added across a
sitting. It reads the same identity and total, plus **the per-question marks the
teacher has already written beside each question**. That last part is a
transcription of digits on a page the model is already looking at (§4's
reconciliation: no new table, no new capture surface, nothing extra asked of the
teacher) — it is emphatically **not** a judgement about whether the answer was
right (`Q-51`/`S-117`). The product forms no opinion about a child's work.

Env-gated like every AI service: with no `OPENROUTER_API_KEY` this returns None
and the capture stays in `uploaded` — photos kept as evidence, form entry stays
manual. Nothing here persists; the output lands in the review surface the
teacher confirms (§8).
"""

from app.core.config import settings
from app.core.exams import clean_question_marks
from app.services.ai.client import chat_json, is_visual

_MARKSHEET_SYSTEM = (
    "You read a photo of evaluated school test papers or a teacher's handwritten mark "
    "register. Transcribe what is printed — never invent. Reply with ONLY "
    '{"meta": {"title": "...", "subject": "...", "total_marks": 20, "topic": "...", '
    '"date": "YYYY-MM-DD"}, '
    '"rows": [{"name": "...", "roll": "...", "score": 12, "max_score": 20}]}. '
    "meta = the exam header if one is visible (test name/title, subject, maximum marks, "
    "chapter/topic tested, date); use null for anything not printed. "
    "rows = every student row you can read: name = the student's name exactly as "
    "written; roll = the roll/admission number if visible, else null; score = the marks "
    "awarded; max_score = the maximum marks if printed, else null. Never invent a row, "
    "never guess an illegible score — skip that row instead. Do not translate or reorder."
)


def _clean_meta(raw: object) -> dict | None:
    """The header block, kept only where the model actually read something."""
    if not isinstance(raw, dict):
        return None
    meta: dict = {}
    for key in ("title", "subject", "topic", "date"):
        val = str(raw.get(key) or "").strip()
        if val and val.lower() not in ("null", "none", "n/a"):
            meta[key] = val
    try:
        total = float(raw.get("total_marks"))
        if total > 0:
            meta["total_marks"] = total
    except (TypeError, ValueError):
        pass
    return meta or None


def extract_marksheet(filename: str, data: bytes) -> dict | None:
    """One photographed page → {"meta": {...}|None, "rows": [...]}.

    Returns None when AI is off, the file isn't a readable format, or the call
    fails — the caller must say so, not pretend it read a blank page. An empty
    rows list means the model read the page and found no score rows on it."""
    if not settings.ai_configured or not is_visual(filename):
        return None
    result = chat_json(
        _MARKSHEET_SYSTEM,
        "Transcribe the exam header and the scores on this page.",
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
    return {"meta": _clean_meta(result.get("meta")), "rows": clean}


_SCRIPT_SYSTEM = (
    "You read a photo of ONE student's marked answer script from a school test. "
    "Transcribe what is written on it — never invent, never mark the paper yourself. "
    "Reply with ONLY "
    '{"meta": {"title": "...", "subject": "...", "total_marks": 25, "topic": "...", '
    '"date": "YYYY-MM-DD"}, '
    '"student": {"name": "...", "roll": "..."}, '
    '"score": 18, "max_score": 25, '
    '"questions": [{"q": "1", "score": 4, "max": 5}]}. '
    "meta = the printed exam header if visible; use null for anything not printed. "
    "student = the name and roll/admission number written on the paper, exactly as "
    "written; null if not visible. score = the TOTAL marks the teacher awarded (the "
    "figure written at the top or the sum at the end); max_score = the maximum marks "
    "if printed, else null. questions = the mark the teacher wrote beside each "
    "question, in order — q is the question number as printed, score is the mark "
    "awarded, max is the question's maximum if printed. "
    "Omit any question you cannot read a mark for; never guess an illegible mark, and "
    "never judge whether an answer is correct — you are reading the teacher's marks, "
    "not marking the paper. Return an empty questions list if no per-question marks "
    "are visible."
)


def extract_script(filename: str, data: bytes) -> dict | None:
    """One photographed marked script → identity, total and per-question marks.

    Returns None when AI is off or the read fails — and the caller must **keep
    the page and say so**, never pretend it read a blank paper (`D-80` step 5:
    a page we cannot read must never become a page we discard).
    """
    if not settings.ai_configured or not is_visual(filename):
        return None
    result = chat_json(
        _SCRIPT_SYSTEM,
        "Transcribe this student's marked script: who it belongs to, the total "
        "awarded, and the marks written beside each question.",
        model=settings.AI_MODEL_PARSE,
        max_tokens=2000,
        attachment=(filename, data),
    )
    if result is None:
        return None

    student = result.get("student") if isinstance(result.get("student"), dict) else {}
    name = str((student or {}).get("name") or "").strip()
    roll = str((student or {}).get("roll") or "").strip() or None
    try:
        score = float(result.get("score"))
    except (TypeError, ValueError):
        score = None
    if score is not None and score < 0:
        score = None
    try:
        raw_max = result.get("max_score")
        max_score = float(raw_max) if raw_max not in (None, "") else None
    except (TypeError, ValueError):
        max_score = None
    if max_score is not None and max_score <= 0:
        max_score = None

    # No identity AND no total = nothing usable was read. Say so, so the page
    # goes to the teacher for hand-mapping instead of quietly vanishing.
    if not name and not roll and score is None:
        return None
    return {
        "meta": _clean_meta(result.get("meta")),
        "row": {"name_text": name, "roll_text": roll, "score": score,
                "max_score": max_score,
                "question_marks": clean_question_marks(result.get("questions"))},
    }
