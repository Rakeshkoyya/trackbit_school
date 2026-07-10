"""AI services (SPRD2 §8) — a single internal, env-gated client via OpenRouter.

Every function falls back to a deterministic heuristic when OPENROUTER_API_KEY is
unset, so all drafting/parsing flows are testable offline, and every AI output
lands in a human-confirm surface before persisting (there is no chat UI). Model ids
come from env (AI_MODEL_DRAFT / AI_MODEL_PARSE) as OpenRouter slugs.

`chat_json` is the only thing that touches the network, and it fails soft: on a
timeout, rate limit, or malformed reply it returns None and the caller's heuristic
runs. AI can improve on the deterministic result; it can never break it.
"""

from app.services.ai.checks import draft_checks
from app.services.ai.client import chat_json, is_visual
from app.services.ai.extract import (
    ocr_document,
    phrase_gap_question,
    split_syllabus_text,
    suggest_mapping,
)
from app.services.ai.report import report_write
from app.services.ai.timetable import parse_timetable

__all__ = [
    "chat_json",
    "draft_checks",
    "is_visual",
    "ocr_document",
    "parse_timetable",
    "phrase_gap_question",
    "report_write",
    "split_syllabus_text",
    "suggest_mapping",
]
