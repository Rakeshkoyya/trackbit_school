"""The setup pack — one workbook that carries a whole school.

    build_pack(name)  → the blank .xlsx the school fills in
    parse_pack(bytes) → what it actually sent back, as structure

Meaning (P2) and writing (P3) live elsewhere on purpose: the operator re-uploads
a corrected file as often as they need, and nothing persists until they commit.

Design and decisions: `docs/architecture/SETUP-REDESIGN-PLAN.md`.
"""

from app.services.setup_pack.commit import CommitResult, PackCommitter, SheetResult
from app.services.setup_pack.parse import (
    ParsedPack,
    SheetData,
    cell_text,
    fill_down,
    map_headers,
    normalise,
    parse_pack,
)
from app.services.setup_pack.specs import (
    BY_KEY,
    COMMIT_ORDER,
    SHEETS,
    Column,
    Setting,
    SheetSpec,
    required_sheets,
    sheet,
)
from app.services.setup_pack.validate import (
    BLOCKER,
    NOTE,
    WARNING,
    Finding,
    SheetSummary,
    ValidationReport,
    to_date,
    to_int,
    validate,
)
from app.services.setup_pack.welcome import build_welcome, welcome_filename
from app.services.setup_pack.workbook import build_pack, filename_for

__all__ = [
    "BLOCKER",
    "BY_KEY",
    "COMMIT_ORDER",
    "NOTE",
    "SHEETS",
    "WARNING",
    "Column",
    "CommitResult",
    "Finding",
    "PackCommitter",
    "ParsedPack",
    "Setting",
    "SheetData",
    "SheetResult",
    "SheetSpec",
    "SheetSummary",
    "ValidationReport",
    "build_pack",
    "build_welcome",
    "cell_text",
    "fill_down",
    "filename_for",
    "map_headers",
    "normalise",
    "parse_pack",
    "required_sheets",
    "sheet",
    "to_date",
    "to_int",
    "validate",
    "welcome_filename",
]
