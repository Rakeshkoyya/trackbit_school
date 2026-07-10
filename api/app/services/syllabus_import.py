"""Syllabus / lesson-plan document importer (V2-P7, SPRD2 §5.1).

Two shapes reach us, so we handle both and normalise to one:

  * a **grid** (xlsx/csv) with chapter / topic / periods columns → column mapping;
  * **free text** (paste, .txt, a PDF's extracted text) → heuristic split.

Both produce the same `units: [{title, topics: [{title, est_periods}]}]` draft,
which the admin edits before commit. Nothing persists until they confirm — the AI
never writes to `syllabus_units` (SPRD2 §8).

`est_periods` is the number the whole plan hangs off, so when a document doesn't
state it we leave it **NULL** — "not sized yet" — rather than inventing a
plausible-looking estimate the admin won't think to check. A school that hands us
the year's chapters but only sizes Term 1 is the normal case, not an error.

A `Term` column, when present, files each chapter under a term so the term can be
planned and locked on its own (V2-P11).
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import CurrentMember
from app.core.exceptions import NotFoundError, ValidationError
from app.models import ClassSubject, SchoolClass, SyllabusTopic, SyllabusUnit, Term
from app.services.ai.client import is_visual
from app.services.ai.extract import ocr_document, split_syllabus_text
from app.services.ingest import FieldSpec, build_analysis
from app.services.roster_import import read_first_sheet

SPECS = [
    FieldSpec("unit_title", ["chapter", "unit", "chapter name", "unit name", "lesson"],
              required=True, label="chapter / unit name"),
    FieldSpec("topic_title", ["topic", "sub topic", "subtopic", "sub-topic", "concept",
                              "topic name"],
              required=True, label="topic name"),
    FieldSpec("est_periods", ["periods", "no of periods", "period", "days", "no of days",
                              "duration"],
              label="estimated periods"),
    FieldSpec("term", ["term", "semester", "part"], label="term this chapter belongs to"),
]


def analyze_text(text: str) -> dict[str, Any]:
    """Free-text path: no columns to map, so the draft IS the answer."""
    units = split_syllabus_text(text)
    return {
        "mode": "text", "units": units,
        "unit_count": len(units),
        "topic_count": sum(len(u["topics"]) for u in units),
        "columns": [], "mapping": {}, "rows": [], "row_count": 0,
        "unmapped_columns": [], "missing_required": [], "low_confidence": [],
        "questions": [], "source": "heuristic",
    }


def analyze_file(data: bytes, filename: str = "syllabus.xlsx") -> dict[str, Any]:
    """Three shapes, one draft.

    A PDF or a photo goes to the multimodal model for transcription, then down the
    text path. A spreadsheet is parsed locally. If the sheet has no recognisable
    topic column, fall back to reading the first column as free text — a lot of
    "syllabus.xlsx" files are really just a typed-out list."""
    if is_visual(filename):
        text = ocr_document(filename, data)
        if not text:
            # Be honest: we could not read it. Returning an empty draft would look
            # like "your syllabus has no chapters", which is a different problem.
            raise ValidationError(
                "Couldn't read that file. Scans and photos need the AI key configured — "
                "otherwise export it as .xlsx, or paste the chapter list as text.")
        out = analyze_text(text)
        out["mode"] = "text"
        out["source"] = "ai-ocr"
        return out

    columns, rows = read_first_sheet(data)
    analysis = build_analysis("syllabus", columns, rows, SPECS)
    if "topic_title" not in analysis.mapping and columns:
        text = "\n".join(
            str(r.get(columns[0]) or "").strip() for r in rows if r.get(columns[0]))
        out = analyze_text(text)
        out["source"] = "heuristic-text-fallback"
        return out
    out = analysis.as_dict()
    out["mode"] = "grid"
    out["units"] = rows_to_units(analysis.mapping, rows)
    out["unit_count"] = len(out["units"])
    out["topic_count"] = sum(len(u["topics"]) for u in out["units"])
    return out


def rows_to_units(mapping: dict[str, str], rows: list[dict]) -> list[dict]:
    """Flat (term, chapter, topic, periods) rows → nested units, preserving sheet order.
    A blank chapter cell continues the previous chapter, which is how humans write
    these sheets (merged cells export as blanks); a blank term does the same.

    A blank period cell means **not sized yet** (`est_periods: None`), which is the
    honest reading of a Term-2 chapter in April. It is not 1."""
    units: list[dict] = []
    current: tuple[str | None, str] | None = None  # (term, chapter)
    current_term: str | None = None

    def cell(row: dict, field: str) -> str | None:
        col = mapping.get(field)
        v = row.get(col) if col else None
        return v.strip() if isinstance(v, str) and v.strip() else None

    for row in rows:
        term = cell(row, "term") or current_term
        unit_title = cell(row, "unit_title") or (current[1] if current else None)
        topic_title = cell(row, "topic_title")
        if not unit_title or not topic_title:
            continue
        current_term = term
        # Key on (term, chapter): the same chapter name may legitimately appear in
        # two terms, and merging them would fuse two planning windows into one.
        key = (term, unit_title)
        if key != current:
            units.append({"title": unit_title, "term": term, "topics": []})
            current = key
        est_raw = cell(row, "est_periods")
        est: int | None
        try:
            est = max(1, int(float(est_raw))) if est_raw else None
        except ValueError:
            est = None
        units[-1]["topics"].append({"title": topic_title, "est_periods": est})
    return [u for u in units if u["topics"]]


class SyllabusImporter:
    def __init__(self, db: Session):
        self.db = db

    def _term_map(self, org_id: uuid.UUID, cs: ClassSubject) -> dict[str, uuid.UUID]:
        """Terms of the class's academic year, keyed by lowercased name. A sheet that
        says "Term 1" only matches a term the school actually created."""
        klass = self.db.get(SchoolClass, cs.class_id)
        if klass is None:
            return {}
        return {t.name.strip().lower(): t.id for t in self.db.scalars(
            select(Term).where(Term.org_id == org_id,
                               Term.academic_year_id == klass.academic_year_id))}

    def commit(self, m: CurrentMember, *, class_subject_id: uuid.UUID, units: list[dict],
               replace: bool = False) -> dict[str, Any]:
        cs = self.db.scalar(select(ClassSubject).where(
            ClassSubject.id == class_subject_id, ClassSubject.org_id == m.org_id))
        if cs is None:
            raise NotFoundError("Class-subject")
        if not units:
            raise ValidationError("Nothing to import — no chapters were found.")

        existing = list(self.db.scalars(select(SyllabusUnit).where(
            SyllabusUnit.org_id == m.org_id,
            SyllabusUnit.class_subject_id == class_subject_id)))
        if replace:
            for u in existing:
                self.db.delete(u)
            self.db.flush()
            position = 0
        else:
            position = len(existing)

        terms = self._term_map(m.org_id, cs)
        units_created = topics_created = unsized = 0
        # A term name we don't recognise leaves the chapter untermed rather than
        # inventing a term — the admin sees which names failed and fixes them.
        unresolved_terms: list[str] = []
        for u in units:
            title = (u.get("title") or "").strip()
            topics = u.get("topics") or []
            if not title or not topics:
                continue
            raw_term = (u.get("term") or "").strip()
            term_id = terms.get(raw_term.lower()) if raw_term else None
            if raw_term and term_id is None and raw_term not in unresolved_terms:
                unresolved_terms.append(raw_term)

            unit = SyllabusUnit(org_id=m.org_id, class_subject_id=class_subject_id,
                                title=title, term_id=term_id, position=position)
            self.db.add(unit)
            self.db.flush()
            position += 1
            units_created += 1
            for i, t in enumerate(topics):
                t_title = (t.get("title") or "").strip()
                if not t_title:
                    continue
                raw_est = t.get("est_periods")
                est = max(1, int(raw_est)) if raw_est else None
                if est is None:
                    unsized += 1
                self.db.add(SyllabusTopic(
                    org_id=m.org_id, unit_id=unit.id, title=t_title,
                    est_periods=est, position=i))
                topics_created += 1
        self.db.flush()
        return {"units_created": units_created, "topics_created": topics_created,
                "replaced": replace, "unsized_topics": unsized,
                "unresolved_terms": unresolved_terms}
