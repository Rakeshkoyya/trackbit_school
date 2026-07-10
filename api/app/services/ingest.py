"""Shared document-ingestion envelope (V2-P7, SPRD2 §5.1/§8).

Every importer — roster, staff, syllabus, timetable — follows the same shape:

    analyze(file)  → columns, a proposed mapping, the parsed rows, AND the gaps
    (human confirms / answers the gap questions)
    commit(mapping, rows) → real tables

The division of labour is the point. **Deterministic validators decide what is
missing**; the model only phrases the follow-up question and proposes options. That
keeps the whole setup flow runnable with no API key — the gaps are still found, the
questions still asked, the fixtures still answer — which is what makes it testable.

If the model decides what's missing, you cannot test onboarding offline. So it
doesn't.
"""

from dataclasses import dataclass, field
from typing import Any

from app.services.ai.extract import phrase_gap_question, suggest_mapping


@dataclass
class FieldSpec:
    name: str
    hints: list[str]
    required: bool = False
    # Shown to the admin on the "have this ready" screen and the example template.
    label: str = ""


@dataclass
class Analysis:
    columns: list[str]
    mapping: dict[str, str]
    rows: list[dict[str, Any]]
    row_count: int
    unmapped_columns: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    low_confidence: list[str] = field(default_factory=list)
    questions: list[dict] = field(default_factory=list)
    source: str = "heuristic"

    def as_dict(self) -> dict[str, Any]:
        return {
            "columns": self.columns, "mapping": self.mapping, "rows": self.rows,
            "row_count": self.row_count, "unmapped_columns": self.unmapped_columns,
            "missing_required": self.missing_required, "low_confidence": self.low_confidence,
            "questions": self.questions, "source": self.source,
        }


def heuristic_mapping(columns: list[str], specs: list[FieldSpec]) -> tuple[dict[str, str], list[str]]:
    """Keyword-match source columns to target fields. Returns (mapping, low_confidence)
    where low_confidence names fields matched only by a loose substring hit."""
    lc = {c.lower().strip(): c for c in columns}
    mapping: dict[str, str] = {}
    low: list[str] = []
    for spec in specs:
        for hint in spec.hints:
            exact = next((orig for low_c, orig in lc.items() if low_c == hint), None)
            if exact:
                mapping[spec.name] = exact
                break
            loose = next((orig for low_c, orig in lc.items() if hint in low_c), None)
            if loose:
                mapping[spec.name] = loose
                low.append(spec.name)
                break
    return mapping, low


def build_analysis(
    kind: str, columns: list[str], rows: list[dict[str, Any]], specs: list[FieldSpec],
) -> Analysis:
    mapping, low = heuristic_mapping(columns, specs)
    source = "heuristic"

    # Only ask the model about fields the keyword heuristic could not place. It
    # never overrides an exact header match — a column literally named "Student
    # Name" is not a judgement call, and paying a model to second-guess it would
    # make a deterministic result non-deterministic.
    unresolved = [s.name for s in specs if s.name not in mapping]
    if unresolved:
        proposed = suggest_mapping(kind, unresolved, columns, rows)
        # `suggest_mapping` already filtered to real columns; guard against a
        # model handing the same column to two fields.
        for field, column in proposed.items():
            if column in mapping.values():
                continue
            mapping[field] = column
            low.append(field)  # AI proposals are always worth a human glance
            source = "ai"

    used = set(mapping.values())
    unmapped = [c for c in columns if c not in used]
    missing = [s.name for s in specs if s.required and s.name not in mapping]

    questions: list[dict] = []
    for fname in missing:
        spec = next(s for s in specs if s.name == fname)
        questions.append(phrase_gap_question(kind, spec.name, spec.label or spec.name, unmapped))
    return Analysis(
        columns=columns, mapping=mapping, rows=rows, row_count=len(rows),
        unmapped_columns=unmapped, missing_required=missing, low_confidence=low,
        questions=questions, source=source)
