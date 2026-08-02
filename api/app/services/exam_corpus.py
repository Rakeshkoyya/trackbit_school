"""The training pair, written once at lock (V1-8, `D-54`/`S-136`/`S-137`/`S-140`).

**This is the only data in the product whose purpose is not running the school
that entered it.** It is children's handwriting with their names on it, and it
belongs to the school — which does not make it wrong, it makes it a thing to ask
for rather than assume. So: `organizations.training_data_opt_in`, default off
(`S-138`), and **no export path at all in v1** (A-4). Capture now, use later,
because it cannot be recovered retrospectively.

Two of the three halves already survived on their own: the page images
(`score_capture_pages`, R2 keys, kept forever as evidence — P5) and the model's
read (`parsed_rows`, which nothing clears on confirm). **The missing third is the
human's answer**, and it is recoverable only at the moment of lock — before
`D-53` the corrected marks lived in `assessment_scores`, a different table with a
different lifecycle, re-written in full on every edit. The pair existed only by
inference, and the inference decayed.

`S-137`: we store the **diff**, not just both sides. Fifty thousand
correctly-read pages teach very little; the rows where a human changed something
teach a lot. `S-140`: each correction carries a **reason bucket**, derived here
rather than asked of the teacher — a tap she would skip on row thirty-eight is
worse than an inference we can name:

    unmatched      the model read a name we could not attach; the human did
    wrong_student  the match attached A and the human moved the mark to B
    misread_digit  right student, different mark (a 7 read as a 1)
    header_wrong   the paper's header (total marks) came back different

Nothing here is shown to anybody, nothing leaves the database, and none of it
touches a child's record — it is written on the capture row beside the photos it
describes.
"""

from __future__ import annotations

import uuid


def _fnum(value: object) -> float | None:
    try:
        return None if value is None else float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def build_pair(parsed_rows: list | None, parsed_meta: dict | None,
               final_rows: list[dict], total_marks: float | None,
               ) -> tuple[list[dict], list[dict]]:
    """`(locked_rows, corrections)` for one capture at the moment of lock.

    `final_rows`: `[{student_id, full_name, score, max_score}]` — what the human
    confirmed. `parsed_rows`: what the model read, already carrying the
    deterministic matcher's verdict. Both sides are kept because a corpus with
    only the diff cannot be re-derived; the diff is kept because a corpus
    without it is a folder."""
    locked = [{
        "student_id": str(r["student_id"]),
        "full_name": r.get("full_name"),
        "score": _fnum(r.get("score")),
        "max_score": _fnum(r.get("max_score")),
        "question_marks": r.get("question_marks"),
    } for r in final_rows if r.get("student_id")]

    corrections: list[dict] = []
    if not parsed_rows:
        return locked, corrections

    final_by_student = {str(r["student_id"]): r for r in final_rows if r.get("student_id")}
    parsed_claimed: set[str] = set()

    for idx, p in enumerate(parsed_rows):
        if not isinstance(p, dict):
            continue
        read_sid = str(p["student_id"]) if p.get("student_id") else None
        read_score = _fnum(p.get("score"))
        if read_sid:
            parsed_claimed.add(read_sid)
            final = final_by_student.get(read_sid)
            if final is None:
                # The model's student was not in the confirmed set at all — the
                # human moved this mark to somebody else, or dropped it.
                corrections.append(_row(idx, p, None, "wrong_student"))
                continue
            if read_score is not None and _fnum(final.get("score")) != read_score:
                corrections.append(_row(idx, p, final, "misread_digit"))
        else:
            # Unmatched by the matcher. If a human later attached a student to a
            # row with this transcription, that is the correction worth keeping.
            match = _by_text(p, final_rows)
            corrections.append(_row(idx, p, match, "unmatched"))

    # Rows a human added that the model never produced at all — the unreadable
    # page mapped by hand (`D-80` step 5), which is the most valuable pair here.
    for sid, final in final_by_student.items():
        if sid not in parsed_claimed and not _text_claimed(sid, parsed_rows, final_rows):
            corrections.append({
                "reason": "unmatched", "parsed_index": None,
                "read": None,
                "human": {"student_id": sid, "score": _fnum(final.get("score"))},
            })

    if parsed_meta:
        read_total = _fnum(parsed_meta.get("total_marks"))
        if read_total is not None and total_marks is not None and read_total != float(total_marks):
            corrections.append({
                "reason": "header_wrong", "parsed_index": None,
                "read": {"total_marks": read_total},
                "human": {"total_marks": float(total_marks)},
            })
    return locked, corrections


def _row(idx: int, parsed: dict, final: dict | None, reason: str) -> dict:
    return {
        "reason": reason,
        "parsed_index": idx,
        "read": {"name_text": parsed.get("name_text"), "roll_text": parsed.get("roll_text"),
                 "score": _fnum(parsed.get("score")),
                 "student_id": str(parsed["student_id"]) if parsed.get("student_id") else None,
                 "confidence": parsed.get("confidence")},
        "human": None if final is None else {
            "student_id": str(final["student_id"]), "score": _fnum(final.get("score"))},
    }


def _by_text(parsed: dict, final_rows: list[dict]) -> dict | None:
    """The confirmed row a human most likely meant for this transcription —
    matched on the mark, which is the only signal an unmatched row carries."""
    score = _fnum(parsed.get("score"))
    if score is None:
        return None
    hits = [r for r in final_rows if _fnum(r.get("score")) == score]
    return hits[0] if len(hits) == 1 else None


def _text_claimed(student_id: str, parsed_rows: list, final_rows: list[dict]) -> bool:
    """Was this confirmed student already accounted for by an unmatched parsed
    row? Keeps one human action from being filed as two corrections."""
    final = next((r for r in final_rows if str(r.get("student_id")) == student_id), None)
    if final is None:
        return False
    return _by_text({"score": final.get("score")}, [final]) is not None and any(
        isinstance(p, dict) and not p.get("student_id")
        and _fnum(p.get("score")) == _fnum(final.get("score"))
        for p in parsed_rows)


def student_uuid(value: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None
