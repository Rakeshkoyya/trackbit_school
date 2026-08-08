"""Setup-pack API shapes (SETUP-REDESIGN-PLAN §5, phase P5).

The operator's screen is one page — download, upload, review, import, hand over —
so these are the four things it reads back.

`PackReviewOut` is deliberately the same shape whether it came from the review
endpoint or from a rejected import: the operator is looking at one report either
way, and two shapes would mean two renderings that drift.
"""

from pydantic import BaseModel


class FindingOut(BaseModel):
    """One line of the report. `severity` is blocker | warning | note; only a
    blocker stops the import."""

    sheet: str
    severity: str
    message: str
    fix: str = ""
    row: int | None = None
    rule: str = ""


class SheetSummaryOut(BaseModel):
    key: str
    title: str
    present: bool
    rows: int = 0
    blocked_rows: int = 0


class PackReviewOut(BaseModel):
    ready: bool
    findings: list[FindingOut] = []
    summaries: list[SheetSummaryOut] = []
    blockers: int = 0
    warnings: int = 0
    notes: int = 0
    total_rows: int = 0
    missing_sheets: list[str] = []
    extra_sheets: list[str] = []


class SheetResultOut(BaseModel):
    key: str
    title: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    notes: list[str] = []


class CredentialOut(BaseModel):
    """A staff login, generated at import. Shown to the operator ONCE — the
    password is hashed on the way in and cannot be read back afterwards, so a
    lost one is reset, never recovered."""

    name: str
    username: str
    password: str


class PackImportOut(BaseModel):
    imported: bool
    review: PackReviewOut
    sheets: list[SheetResultOut] = []
    credentials: list[CredentialOut] = []
