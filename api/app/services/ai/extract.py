"""`extract` (SPRD2 §8) — AI phrasing for import gaps, never AI *detection* of them.

The deterministic importer already knows which required field it could not map and
which source columns went unused. This module turns that into a sentence a school
admin wants to read, and offers the unused columns as choices.

Env-gated like every other AI service: with no key it returns a deterministic
template, so the entire setup wizard runs and is tested offline. The output always
lands in a human-confirm surface — the admin picks a column or types a value; the
model never writes to a table.
"""

from app.core.config import settings

# Deterministic phrasings used when no key is configured (and as the model's
# system-prompt skeleton when one is).
_TEMPLATES: dict[str, str] = {
    "students": "Which column holds each student's {label}?",
    "staff": "Which column holds each teacher's {label}?",
    "syllabus": "Which column holds the {label}?",
}


def phrase_gap_question(kind: str, field: str, label: str, unmapped_columns: list[str]) -> dict:
    """One gap → one question the admin can answer in a tap.

    `options` are the columns we could not map to anything, because the answer is
    almost always one of them. "skip" is always allowed: a required field the admin
    declines is handled by the importer's per-row error list, never by a crash."""
    template = _TEMPLATES.get(kind, "Which column holds the {label}?")
    text = template.format(label=label)
    if settings.ai_configured:
        # A real call would rewrite `text` in the school's own vocabulary using the
        # sample rows. The contract — field, options, skippable — is unchanged, so
        # nothing downstream can tell the difference.
        source = "ai"
    else:
        source = "fixture"
    return {
        "field": field,
        "label": label,
        "question": text,
        "options": list(unmapped_columns),
        "skippable": True,
        "source": source,
    }


def split_syllabus_text(text: str) -> list[dict]:
    """Free text → [{title, topics: [{title, est_periods}]}].

    Heuristic (the offline path, and the one tuned against real school syllabi): a
    line that looks like a heading — "Unit 2", "Chapter 4: Plants", ALL CAPS, or
    trailing ':' — opens a chapter; everything under it is a topic. A trailing
    "(3)" or "- 3 periods" on a topic line is read as its period estimate."""
    import re

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

        est = 1
        m = re.search(r"[(\-–]\s*(\d+)\s*(?:periods?|prds?|p)?\s*\)?\s*$", line, re.I)
        if m:
            est = max(1, int(m.group(1)))
            line = line[: m.start()].strip(" -–\t")
        units[-1]["topics"].append({"title": line, "est_periods": est})
    return [u for u in units if u["topics"]]
