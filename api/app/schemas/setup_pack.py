"""Setup-pack API shapes (SETUP-REDESIGN-PLAN §5, phase P5).

The operator's screen is one page — download, upload, review, import, hand over —
so these are the four things it reads back.

`PackReviewOut` is deliberately the same shape whether it came from the review
endpoint or from a rejected import: the operator is looking at one report either
way, and two shapes would mean two renderings that drift.
"""

import uuid

from pydantic import BaseModel, Field


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

    user_id: uuid.UUID
    name: str
    username: str
    password: str


# ── editing those logins before handover ─────────────────────────────────────
# The generated username is a slug of the person's name, which is right often
# enough to be worth generating and wrong often enough to be worth correcting:
# a school's own employee IDs, a misspelt name in the pack, two teachers the
# slug collided on. This is the one window where a password can still be CHOSEN
# rather than reset — after handover it is hashed and gone.


class StaffLoginRowOut(BaseModel):
    """One editable row. Carries no password: the generated one is unreadable by
    the time this list is fetched, and a blank field means *leave it alone*."""

    user_id: uuid.UUID
    name: str
    username: str | None
    org_role: str


class StaffLoginIn(BaseModel):
    user_id: uuid.UUID
    # Lowercased and validated in the service, not here — the rules are the
    # importer's (`_slugify_username`) and belong next to it.
    username: str = Field(min_length=3, max_length=40)
    # Omitted or blank = keep the password they already have. A password set
    # here is still a TEMP one: `must_set_password` stays on, so the teacher
    # changes it at first sign-in exactly as with a generated one.
    password: str | None = Field(default=None, max_length=128)


class StaffLoginsIn(BaseModel):
    logins: list[StaffLoginIn] = Field(min_length=1, max_length=500)


class StaffLoginsResult(BaseModel):
    saved: int
    renamed: int
    passwords_set: int
    rows: list[StaffLoginRowOut] = []


class UsernameCheckOut(BaseModel):
    username: str
    available: bool
    # Why not, in words the operator can act on — "already taken", "too short".
    reason: str | None = None


class PackImportOut(BaseModel):
    imported: bool
    review: PackReviewOut
    sheets: list[SheetResultOut] = []
    credentials: list[CredentialOut] = []
