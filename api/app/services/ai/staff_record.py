"""The staff record's written summary (V1-16, §8).

Same contract as `ai/report.py::report_summary`, and for the same reason: the
model **voices figures it was handed** and computes nothing. A soft failure — no
key, a timeout, prose instead of JSON — falls through to the deterministic
sentence builder, so the record is never blank on a machine with no AI key. That
is dev, tests, and every school we have not switched a key on for.

The system prompt carries the one rule this surface cannot get wrong. A timesheet
is filled in by the person it describes, and `D-25`/`S-67` promised them it can
neither rank them nor reach their pay. A model asked to "summarise a teacher's
month" will reach for appraisal language unprompted — "productive", "needs to
improve", "only 4 periods" — so it is told, explicitly and in the negative, that
it is writing a record of where time went and nothing else. A teacher who reads
one line of appraisal here stops filling the thing in, and then the school has no
data at all.
"""

from app.core.config import settings
from app.services.ai.client import chat_json

RECORD_SYSTEM = (
    "You write a factual record of how one member of school staff spent their "
    "working month, for the school's administrator. You are given figures that "
    "have already been computed. Write 2-3 short sentences (max 55 words): where "
    "the time went, then anything the administrator should look at. "
    "Rules you must not break: use ONLY the numbers given — never invent, round "
    "or infer one. This is a RECORD, not an appraisal: never praise, never "
    "criticise, never rate, never compare this person to a colleague, and never "
    "use words like productive, efficient, underutilised, or needs improvement. "
    "A period with nothing written against it is a free period and is never a "
    "failure to record. A day nobody marked is the office's gap, not this "
    "person's absence. Refer to the person by name or as \"they\" — never guess a "
    "gender from a name. No greetings, no markdown, no bullets, no headings. "
    'Reply as JSON: {"summary": "<the sentences>"}'
)


def _prompt(facts: dict) -> str:
    lines = [f"Person: {facts.get('name')} ({facts.get('role')})",
             f"Month: {facts.get('month')}"]
    for heading, key in (("Where the time went", "where_time_went"),
                         ("Notable", "highlights"),
                         ("Worth a look", "watch")):
        rows = facts.get(key) or []
        if rows:
            lines.append(f"{heading}:")
            lines += [f"- {r}" for r in rows]
    return "\n".join(lines)


def record_summary(facts: dict) -> tuple[str, str]:
    """(source, text). `source` is 'ai' only when a model actually answered."""
    if not settings.ai_configured:
        return "computed", ""
    data = chat_json(RECORD_SYSTEM, _prompt(facts), model=settings.AI_MODEL_DRAFT)
    text = (data or {}).get("summary") if isinstance(data, dict) else None
    if isinstance(text, str) and text.strip():
        return "ai", text.strip()
    return "computed", ""


def deterministic_record_summary(facts: dict) -> str:
    """The offline floor. It must read as a finished paragraph, not a stub —
    most schools will only ever see this one."""
    where = facts.get("where_time_went") or []
    highlights = facts.get("highlights") or []
    watch = facts.get("watch") or []
    name = facts.get("name") or "This member of staff"
    month = facts.get("month") or "the month"

    out: list[str] = []
    if where:
        out.append(f"In {month}, {name}'s recorded time was: "
                   + "; ".join(w.lower() for w in where[:3]) + ".")
    else:
        out.append(f"Nothing has been recorded for {name} in {month} yet.")
    if highlights:
        out.append(highlights[0] + ".")
    if watch:
        out.append(watch[0] + ".")
    return " ".join(out)
