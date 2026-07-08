"""AI services (SPRD2 §8) — a single internal, env-gated client.

Every function returns a deterministic fixture when ANTHROPIC_API_KEY is unset so
all drafting/parsing flows are testable offline, and every AI output lands in a
human-confirm surface before persisting (there is no chat UI). Model ids come from
env (AI_MODEL_DRAFT / AI_MODEL_PARSE).
"""

from app.services.ai.checks import draft_checks
from app.services.ai.timetable import parse_timetable

__all__ = ["draft_checks", "parse_timetable"]
