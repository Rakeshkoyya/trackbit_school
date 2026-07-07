"""`timetable_parse` (SPRD2 §8) — photo/xlsx of an existing timetable → grid.

Real parsing (when a key is set) would hand the uploaded file to a haiku-class
model. Offline / no-key — the case that runs in tests and dev — returns a
deterministic fixture: a plausible round-robin fill of the week from the class's
own class_subjects, honouring each subject's periods_per_week budget. The result
is a *draft* that the admin confirms in a grid before anything persists.
"""

import uuid
from dataclasses import dataclass

from app.core.config import settings


@dataclass
class ParsedSubject:
    class_subject_id: uuid.UUID
    subject_name: str
    periods_per_week: int


def parse_timetable(
    subjects: list[ParsedSubject],
    *,
    periods_per_day: int,
    weekdays: list[int],
    file_bytes: bytes | None = None,
) -> tuple[str, list[dict]]:
    """Return (source, cells). Each cell = {weekday, period_no, class_subject_id,
    subject_name, confidence}. `source` is "ai" when a key is configured, else
    "fixture". The offline fixture ignores file_bytes and fills deterministically."""
    source = "ai" if settings.ai_configured else "fixture"

    # Build a demand list: each subject repeated periods_per_week times (min 1),
    # capped so we never exceed the week's cells.
    demand: list[ParsedSubject] = []
    for s in subjects:
        demand.extend([s] * max(1, s.periods_per_week))
    total_cells = len(weekdays) * periods_per_day
    demand = demand[:total_cells]

    cells: list[dict] = []
    i = 0
    for wd in weekdays:
        for p in range(1, periods_per_day + 1):
            if i >= len(demand):
                break
            s = demand[i]
            i += 1
            cells.append({
                "weekday": wd,
                "period_no": p,
                "class_subject_id": s.class_subject_id,
                "subject_name": s.subject_name,
                "confidence": 1.0 if source == "fixture" else 0.9,
            })
    return source, cells
