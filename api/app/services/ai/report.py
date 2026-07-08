"""`report_write` (SPRD2 §8, §5.6) — deterministic day aggregation → short narrative.

Real writing (when a key is set) hands the assembled sections + flagged
risks/ambiguities to a sonnet-class model for a warm, concise narrative. Offline /
no-key — the case that runs in tests and dev — composes a deterministic Markdown
report from the same structured input, so the 8 AM report exists whether or not AI
is configured. Either way the numbers come from `DailyReportService`, never the model.
"""

from app.core.config import settings


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
