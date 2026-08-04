"""The support child's written summary and key insights (founder 2026-08-04).

Same contract as `ai/report.py::report_summary` and `ai/staff_record.py`: the
model **voices figures it was handed** and computes nothing. A soft failure — no
key, a timeout, prose instead of JSON — falls through to `deterministic_summary`,
so the owner's page is never blank on a machine with no AI key. That is dev,
tests, and every school we have not switched a key on for.

Two rules in the system prompt that this surface in particular cannot get wrong,
both stated in the NEGATIVE because a model asked to summarise a struggling
child reaches for the forbidden register unprompted:

**It is not a diagnosis.** A band is a teaching group, not a condition (module
§7: no IEP, no clinical framing). "Dyslexic", "slow learner", "weak student" and
"low ability" are the words that turn a support programme into a label a child
carries, which is the whole thing `D-67` and P4 exist to prevent. The model is
told to write about *the work*, never about the child's capacity.

**Absence is not effort.** The week is read from capture five other teachers
filled in, and a child who was away has no record — not a bad one. A model that
reads "3 absences, 2 homework not done" and writes "he is not trying" has
invented a motive out of an attendance figure.

And the standing one: **nothing here ever reaches a parent** (P4). This text is
staff-only, like everything else the module produces.
"""

from app.core.config import settings
from app.services.ai.client import chat_json

BAND_SYSTEM = (
    "You write a short factual summary about one child's support work, for the "
    "teacher who owns helping them. You are given figures and notes that have "
    "already been computed by the school's system. "
    "Write 2-3 short sentences (max 60 words) covering: what the record shows "
    "has been happening, then the single most useful thing to do next. "
    "Then give 2-4 key insights, each one short sentence. "
    "Rules you must not break: use ONLY the facts given — never invent, round or "
    "infer a number, a date or an event. "
    "This is a record of WORK, never a judgement of the child: never diagnose, "
    "never describe ability or intelligence, and never use words like weak, "
    "slow, poor, lazy, unmotivated, low-ability, learning difficulty or "
    "disorder. Describe what happened and what to try. "
    "A band is a teaching group, not a grade and not a condition. "
    "Absence is not effort: if the child was away, say the record is thin, never "
    "that they are not trying. "
    "A week with nothing recorded means nobody wrote anything down — say that, "
    "and never call it no progress. "
    "Refer to the child by name or as \"they\" — never guess a gender from a name. "
    "No greetings, no markdown, no bullets, no headings. "
    'Reply as JSON: {"summary": "<the sentences>", "insights": ["<one>", "..."]}'
)


def _prompt(facts: dict) -> str:
    lines = [
        f"Child: {facts.get('name')}",
        f"Subject: {facts.get('subject')} · currently Band {facts.get('tier')}",
    ]
    if facts.get("descriptor"):
        lines.append(f"What that band means here: {facts['descriptor']}")
    if facts.get("goal"):
        lines.append(f"Goal: {facts['goal']}")
    if facts.get("exit_criterion"):
        lines.append(f"Moves up when: {facts['exit_criterion']}")
    for heading, key in (
        ("This week, as his teachers recorded it", "week"),
        ("The owner's check-ins, newest first", "checkins"),
        ("Tests", "tests"),
        ("Figures", "figures"),
    ):
        rows = facts.get(key) or []
        if rows:
            lines.append(f"{heading}:")
            lines += [f"- {r}" for r in rows]
    return "\n".join(lines)


def band_summary(facts: dict) -> tuple[str, str, list[str]]:
    """(source, summary, insights). `source` is 'ai' only when a model answered."""
    if not settings.ai_configured:
        return "computed", "", []
    data = chat_json(BAND_SYSTEM, _prompt(facts), model=settings.AI_MODEL_DRAFT)
    if not isinstance(data, dict):
        return "computed", "", []
    text = data.get("summary")
    raw = data.get("insights")
    insights = [str(i).strip() for i in raw if str(i).strip()][:4] if isinstance(raw, list) else []
    if isinstance(text, str) and text.strip():
        return "ai", text.strip(), insights
    return "computed", "", []
