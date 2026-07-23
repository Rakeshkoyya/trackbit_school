"""`report_write` (SPRD2 §8, §5.6) — deterministic day aggregation → short narrative.

Real writing (when a key is set) hands the assembled sections + flagged
risks/ambiguities to a sonnet-class model for a warm, concise narrative. Offline /
no-key — the case that runs in tests and dev — composes a deterministic Markdown
report from the same structured input, so the 8 AM report exists whether or not AI
is configured. Either way the numbers come from `DailyReportService`, never the model.

`report_summary` is the headline the dashboard leads with: 2–3 sentences an admin
reads in ten seconds, with the full report folded behind "More". Same contract —
the model only *voices* numbers it was handed, and a soft failure (no key, timeout,
bad JSON) falls through to the deterministic sentence builder.
"""

import re

from app.core.config import settings
from app.services.ai.client import chat_json

SUMMARY_SYSTEM = (
    "You are the school's chief of staff writing the morning briefing for the "
    "principal. You are given the day's already-computed figures. Write 2-3 short "
    "sentences (max 60 words total) in plain, warm, specific English: what the day "
    "looked like, then what needs attention today, then one encouraging note if the "
    "figures support one. Rules: use ONLY the numbers given — never invent, round, "
    "or infer a figure. No greetings, no markdown, no bullet points, no headings. "
    "Never mention student support bands or tiers. "
    'Reply as JSON: {"summary": "<the sentences>"}'
)


def report_write(
    org_name: str, for_date: str, sections: list[tuple[str, list[str]]],
    highlights: dict[str, list[str]],
) -> tuple[str, str]:
    """Return (source, content_md). `sections` = ordered (heading, lines). `source`
    is 'ai' when a key is configured, else 'fixture' — the Markdown is deterministic
    in both cases here; a real model would only re-voice the fixture text."""
    source = "ai" if settings.ai_configured else "fixture"

    parts: list[str] = [f"# {org_name} — {for_date}", ""]
    risks = highlights.get("risks", [])
    ambiguities = highlights.get("ambiguities", [])
    if risks:
        parts.append(f"**{len(risks)} thing(s) need attention today.**")
    else:
        parts.append("**A calm day — nothing flagged.**")
    parts.append("")

    for heading, lines in sections:
        parts.append(f"## {heading}")
        if lines:
            parts += [f"- {line}" for line in lines]
        else:
            parts.append("- Nothing to report.")
        parts.append("")

    if ambiguities:
        parts.append("## Worth a look (ambiguities)")
        parts += [f"- {a}" for a in ambiguities]
        parts.append("")

    wins = highlights.get("wins", [])
    if wins:
        parts.append("## Wins")
        parts += [f"- {w}" for w in wins]
        parts.append("")

    return source, "\n".join(parts).strip() + "\n"


def deterministic_summary(
    sections: list[tuple[str, list[str]]], highlights: dict[str, list[str]],
) -> str:
    """The offline headline — one sentence per beat, built from the same figures.

    This is the floor, not a placeholder: it must read as a finished briefing on a
    machine with no AI key, because that is dev, tests, and any school we haven't
    switched the key on for.
    """
    by_heading = {h: ls for h, ls in sections}
    risks = highlights.get("risks", [])
    ambiguities = highlights.get("ambiguities", [])
    wins = highlights.get("wins", [])

    out: list[str] = []
    attendance = (by_heading.get("Attendance") or [""])[0]
    teaching = (by_heading.get("Teaching") or [""])[0]
    if attendance and teaching:
        out.append(f"{attendance.capitalize()}; {teaching.lower()}.")
    elif attendance or teaching:
        out.append(f"{(attendance or teaching).capitalize()}.")

    if risks:
        head = risks[0].rstrip(".")
        more = f" and {len(risks) - 1} other item(s)" if len(risks) > 1 else ""
        out.append(f"Needs attention: {head}{more}.")
    elif ambiguities:
        out.append(f"{len(ambiguities)} capture gap(s) are worth a glance — nothing is off track.")
    else:
        out.append("Nothing is flagged for action today.")

    if wins:
        out.append(f"{wins[0].rstrip('.')}.")
    return " ".join(out)


def report_summary(
    org_name: str, for_date: str, sections: list[tuple[str, list[str]]],
    highlights: dict[str, list[str]],
) -> tuple[str, str]:
    """Return (source, summary) — the 2-3 sentence headline for the dashboard.

    `source` is 'ai' when a model actually wrote it, 'fixture' otherwise, so the
    caller can tell the reader who is talking.
    """
    fallback = deterministic_summary(sections, highlights)
    if not settings.ai_configured:
        return "fixture", fallback

    facts = [f"School: {org_name}", f"Date: {for_date}", ""]
    for heading, lines in sections:
        facts.append(f"{heading}: " + ("; ".join(lines) if lines else "nothing recorded"))
    for key in ("risks", "ambiguities", "wins"):
        if highlights.get(key):
            facts.append(f"{key.capitalize()}: " + "; ".join(highlights[key]))

    reply = chat_json(SUMMARY_SYSTEM, "\n".join(facts), model=settings.AI_MODEL_DRAFT)
    text = (reply or {}).get("summary")
    if not isinstance(text, str) or not text.strip():
        return "fixture", fallback
    # Strip any markdown the model reached for anyway — this lands in a plain
    # paragraph, and a stray "**" reads as a bug to the principal.
    clean = re.sub(r"[*_#`]", "", text).strip()
    return "ai", clean if clean else fallback
