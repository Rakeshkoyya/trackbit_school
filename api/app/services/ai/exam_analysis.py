"""`exam_analysis` (V1-8, `D-80`/`D-81`) — narrative over figures already computed.

Two writers, one contract, and the contract is the whole safety of the feature:
**the model only voices numbers it was handed.** It never sees a paper, never
judges an answer (`Q-51`/`S-117`), never invents a figure, and never mentions a
support band (P4 — the report card is the surface most likely to be printed and
handed to a parent).

Env-gated like every AI service: with no key, or on a timeout, a 429 or
prose-instead-of-JSON, the deterministic sentence builder runs and the screen is
never empty. That is not a degraded path — it is the path the tests run on.
"""

import re

from app.core.config import settings
from app.services.ai.client import chat_json

_EXAM_SYSTEM = (
    "You are a school's academic coordinator writing the short analysis under an "
    "exam's results. You are given already-computed figures for one exam. Write 2-4 "
    "short sentences (max 80 words) in plain, specific English: how the class did, "
    "where the difficulty was, and what a teacher might do next. Rules: use ONLY the "
    "numbers and names given — never invent, round or infer a figure. Never rank "
    "students, never name a child as weak, never mention support bands or tiers. No "
    "markdown, no headings, no bullets. "
    'Reply as JSON: {"summary": "<the sentences>"}'
)

_SUBJECT_SYSTEM = (
    "You are a teacher writing the per-subject paragraph of a student's report. You "
    "are given already-computed figures for one student in one subject. Write 1-3 "
    "short sentences (max 55 words), addressed to the family, in plain, warm, "
    "specific English: how they are doing, and one thing to work on if the figures "
    "support one. Rules: use ONLY the numbers given — never invent a figure, never "
    "compare with other children, never rank, never mention support bands or tiers, "
    "and never describe the child in terms of ability. No markdown. "
    'Reply as JSON: {"summary": "<the sentences>"}'
)


def _voiced(system: str, facts: list[str], fallback: str) -> tuple[str, str]:
    if not settings.ai_configured:
        return "fixture", fallback
    reply = chat_json(system, "\n".join(facts), model=settings.AI_MODEL_DRAFT)
    text = (reply or {}).get("summary")
    if not isinstance(text, str) or not text.strip():
        return "fixture", fallback
    clean = re.sub(r"[*_#`]", "", text).strip()
    return ("ai", clean) if clean else ("fixture", fallback)


def deterministic_exam_summary(facts: dict) -> str:
    """The sentence the screen shows when no model wrote one — assembled from
    the same figures, so it is never emptier than the truth."""
    out: list[str] = []
    name = facts.get("exam") or "This exam"
    avg = facts.get("avg_pct")
    scored, roster = facts.get("scored") or 0, facts.get("roster") or 0
    if avg is not None:
        out.append(f"{name}: average {avg:g}%"
                   + (f" across {scored} of {roster} students." if roster else "."))
    else:
        out.append(f"{name} has no marks recorded yet.")
    if facts.get("not_sat"):
        n = len(facts["not_sat"])
        out.append(f"{n} student{'' if n == 1 else 's'} did not sit it: "
                   + ", ".join(facts["not_sat"][:3])
                   + ("…" if n > 3 else "") + ".")
    if facts.get("struggling"):
        n = len(facts["struggling"])
        out.append(f"{n} scored well below the class: "
                   + ", ".join(facts["struggling"][:3]) + ("…" if n > 3 else "") + ".")
    if facts.get("hardest_question"):
        out.append(f"Question {facts['hardest_question']} was the one most often lost.")
    elif not facts.get("has_questions"):
        out.append("Question-level analysis needs a photo of the marked paper.")
    return " ".join(out)


def exam_summary(facts: dict) -> tuple[str, str]:
    """(source, summary) for an exam's Report tab."""
    fallback = deterministic_exam_summary(facts)
    lines = [f"Exam: {facts.get('exam')}",
             f"Class: {facts.get('class_label')}", f"Subject: {facts.get('subject')}",
             f"Type: {facts.get('type_label')} ({facts.get('scale')})",
             f"Topic examined: {facts.get('topic') or 'not recorded'}",
             f"Average: {facts.get('avg_pct')}% over {facts.get('scored')} of "
             f"{facts.get('roster')} students",
             f"Distribution: {facts.get('distribution')}",
             f"Did not sit: {', '.join(facts.get('not_sat') or []) or 'nobody'}",
             f"Scored well below the class: {', '.join(facts.get('struggling') or []) or 'nobody'}",
             f"Scored well above: {', '.join(facts.get('strong') or []) or 'nobody'}",
             f"Syllabus coverage for this class-subject: {facts.get('coverage') or 'unknown'}"]
    if facts.get("questions"):
        lines.append("Per-question averages: " + facts["questions"])
    else:
        lines.append("Per-question marks: not available (no photo of the marked paper)")
    return _voiced(_EXAM_SYSTEM, lines, fallback)


def deterministic_subject_summary(facts: dict) -> str:
    out: list[str] = []
    subject = facts.get("subject") or "This subject"
    figures = facts.get("figures") or []
    if figures:
        out.append(f"{subject}: " + "; ".join(figures) + ".")
    else:
        out.append(f"No marks are recorded in {subject} yet.")
    if facts.get("coverage"):
        out.append(f"The class has covered {facts['coverage']}.")
    if facts.get("attendance_pct") is not None:
        out.append(f"Attendance in this subject is {facts['attendance_pct']:g}%.")
    if facts.get("missed"):
        out.append(f"{facts['missed']} topic(s) were taught while they were absent.")
    return " ".join(out)


def subject_summary(facts: dict) -> tuple[str, str]:
    """(source, summary) for one subject on a student's analysis."""
    fallback = deterministic_subject_summary(facts)
    lines = [f"Student: {facts.get('student')}", f"Subject: {facts.get('subject')}",
             f"Marks: {'; '.join(facts.get('figures') or []) or 'none recorded'}",
             f"Recent marks: {facts.get('recent') or 'none'}",
             f"Syllabus covered: {facts.get('coverage') or 'unknown'}",
             f"Attendance in this subject: {facts.get('attendance_pct')}%",
             f"Topics taught while absent: {facts.get('missed') or 0}"]
    return _voiced(_SUBJECT_SYSTEM, lines, fallback)
