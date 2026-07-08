"""`checks_draft` (SPRD2 §8, §5.5) — planned topic → a few concrete daily checks.

Real drafting (when a key is set) hands the topic + band distribution to a
sonnet-class model. Offline / no-key — the case that runs in tests and dev —
returns deterministic template checks so the recommendations flow works with zero
teacher setup. The generator (services/recommendations.py) applies volume caps and
turns these into `daily_checks` rows the teacher confirms on the period card.
"""

from dataclasses import dataclass

from app.core.config import settings


@dataclass
class DraftedCheck:
    description: str
    band_scope: str  # 'all' | 'A' | 'B' | 'C'


def draft_checks(topic_title: str | None, *, c_band_present: bool) -> tuple[str, list[DraftedCheck]]:
    """Return (source, checks). `source` is 'ai' when a key is configured, else
    'fixture'. Class-wide checks come first, then the richer C-band check (only when
    C-band students are in the class). Caps are the caller's job."""
    source = "ai" if settings.ai_configured else "fixture"
    topic = (topic_title or "today's topic").strip()

    checks: list[DraftedCheck] = [
        DraftedCheck(description=f"{topic}: 5 practice items reviewed", band_scope="all"),
        DraftedCheck(description=f"{topic}: two students explain it back in their words",
                     band_scope="all"),
    ]
    if c_band_present:
        # The C-band gets the richer, one-on-one style check (§5.5 done-when).
        checks.append(DraftedCheck(
            description=f"{topic}: one-on-one — reads the worked example aloud, then tries one",
            band_scope="C"))
    return source, checks
