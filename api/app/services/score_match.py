"""Deterministic roster matcher (SC-1) — the model transcribes, THIS decides.

Maps transcribed marksheet rows (`{name_text, roll_text, score, max_score}`) onto
the class roster. Pure and stdlib-only (difflib), so identity assignment is
reproducible and unit-testable — an AI hallucination can propose text, but only
an exact/fuzzy match against the real roster can attach a student_id, and
anything ambiguous is left for the human review grid to settle.

Confidence levels the review UI renders:
    roll   — roll/admission number matched exactly (strongest signal)
    exact  — normalised full name equals exactly one roster student
    fuzzy  — clear best fuzzy name match (flagged for a second glance)
    None   — unmatched; `candidates` carries the closest roster students

A roster student is never auto-claimed twice: a second row pointing at the same
student is left unmatched with that student as a candidate — two "Ravi K" rows
are a human's call, not ours.
"""

import re
from difflib import SequenceMatcher

_FUZZY_FLOOR = 0.75   # best ratio below this = no match
_FUZZY_MARGIN = 0.08  # best must beat the runner-up by this much
_CANDIDATE_FLOOR = 0.5


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())).strip()


def match_rows(parsed: list[dict], roster: list[dict]) -> list[dict]:
    """`roster`: [{id, full_name, roll_no, admission_no}] (ids as str or UUID).

    Returns one dict per parsed row: the transcription plus
    {student_id, confidence, candidates: [{student_id, full_name}]}."""
    students = [{
        "id": str(st["id"]),
        "full_name": st.get("full_name") or "",
        "name_norm": _norm(st.get("full_name")),
        "roll_norm": _norm(st.get("roll_no")),
        "adm_norm": _norm(st.get("admission_no")),
    } for st in roster]

    claimed: set[str] = set()
    out: list[dict] = []
    for row in parsed:
        name_norm = _norm(row.get("name_text"))
        roll_norm = _norm(row.get("roll_text"))

        student_id: str | None = None
        confidence: str | None = None
        candidates: list[dict] = []

        # 1. roll / admission number — exact, and unique across the roster.
        if roll_norm:
            hits = [s for s in students
                    if roll_norm in (s["roll_norm"], s["adm_norm"]) and s["roll_norm"] + s["adm_norm"]]
            if len(hits) == 1:
                student_id, confidence = hits[0]["id"], "roll"

        # 2. exact normalised name — unique across the roster.
        if student_id is None and name_norm:
            hits = [s for s in students if s["name_norm"] == name_norm]
            if len(hits) == 1:
                student_id, confidence = hits[0]["id"], "exact"
            elif len(hits) > 1:
                candidates = hits  # duplicate names: always a human's call

        # 3. fuzzy name — clear best only; near-ties become candidates.
        if student_id is None and name_norm and not candidates:
            scored = sorted(
                ((SequenceMatcher(None, name_norm, s["name_norm"]).ratio(), s)
                 for s in students if s["name_norm"]),
                key=lambda t: t[0], reverse=True)
            if scored:
                best_ratio, best = scored[0]
                second = scored[1][0] if len(scored) > 1 else 0.0
                if best_ratio >= _FUZZY_FLOOR and best_ratio - second >= _FUZZY_MARGIN:
                    student_id, confidence = best["id"], "fuzzy"
                else:
                    candidates = [s for r, s in scored[:3] if r >= _CANDIDATE_FLOOR]

        # 4. one student, one row — a second claim goes back to the human.
        if student_id is not None and student_id in claimed:
            candidates = [s for s in students if s["id"] == student_id]
            student_id, confidence = None, None
        if student_id is not None:
            claimed.add(student_id)

        out.append({
            "name_text": row.get("name_text"),
            "roll_text": row.get("roll_text"),
            "score": row.get("score"),
            "max_score": row.get("max_score"),
            "student_id": student_id,
            "confidence": confidence,
            "candidates": [{"student_id": c["id"], "full_name": c["full_name"]}
                           for c in candidates],
        })
    return out
