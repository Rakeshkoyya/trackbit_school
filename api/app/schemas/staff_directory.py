"""The staff directory (founder, 2026-08-05) — every member of staff as a row.

The school already had a Members screen (Setup → Members), but it is an *account*
screen: who can log in, what their invite state is, reset a password. It cannot
answer the questions an admin actually asks about staff — who teaches 6-A, who is
its class teacher, who is carrying nine class-subjects and who is carrying two —
because none of that lives on `memberships`; it lives on `school_classes` and
`class_subjects`, and nothing had ever joined the three.

**The class teacher is DERIVED, never a third role.** `org_role` stays
`admin | teacher` (SPRD2 §2, the CHECK constraint every guard is built on) and
`school_classes.class_teacher_member_id` remains the one place the fact is
stored. `role_key` is the rendering of the pair — a screen shows *"Class teacher ·
6-A"*, and writing that back is an assignment on the class, not a role change. A
second store for the same fact is the `S-51` defect this codebase keeps closing.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.core.roles import ROLE_PATTERN


class ClassRef(BaseModel):
    class_id: uuid.UUID
    class_label: str


class SubjectRef(BaseModel):
    class_subject_id: uuid.UUID
    class_id: uuid.UUID
    class_label: str
    subject_id: uuid.UUID
    subject_name: str
    periods_per_week: int = 0


class StaffRow(BaseModel):
    """One person in the directory.

    `role_key` is what the Role column renders and what its dropdown writes back:
    `admin` · `class_teacher` · `teacher`. It is COMPUTED from the org role plus
    the class assignment — there is no `class_teacher` value in the database, and
    a reader who treats this as the stored role will be wrong the moment a class
    is reassigned.
    """

    member_id: uuid.UUID
    user_id: uuid.UUID
    name: str
    email: str | None = None
    username: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None

    org_role: str                       # admin | teacher — what is stored
    role_key: str                       # admin | class_teacher | teacher — what is shown
    role_label: str                     # "Class teacher · 6-A"
    status: str = "active"
    pending: bool = False               # invited, never signed in
    last_active_at: datetime | None = None

    # The assignments the org role cannot express.
    class_teacher_of: list[ClassRef] = []
    classes: list[ClassRef] = []        # every class they take a subject in
    subjects: list[SubjectRef] = []
    # Load, stated in the units the school allocates in. Never a score.
    subject_count: int = 0
    periods_per_week: int = 0


class StaffDirectoryOut(BaseModel):
    rows: list[StaffRow] = []
    # Every class in the active year — the group-by and the class filter are
    # built from THIS, not from the classes that happen to appear on a row, so a
    # class with nobody assigned is still selectable and still visibly empty.
    classes: list[ClassRef] = []
    total: int = 0
    admins: int = 0
    teachers: int = 0
    class_teachers: int = 0
    # Classes in the year with no class teacher — the gap the screen exists to
    # close, counted here so the header can say it without re-deriving.
    classes_without_teacher: list[ClassRef] = []


class StaffUpdateIn(BaseModel):
    """Everything the detail page can change. Every field is optional: absent
    means *leave it alone*, which is what lets one form save one edit."""

    name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = None
    username: str | None = None
    phone: str | None = None
    date_of_birth: date | None = None
    # Clearing a contact field needs a value that is not "absent". Absent means
    # untouched; these say "make it null".
    clear_email: bool = False
    clear_phone: bool = False
    clear_date_of_birth: bool = False

    org_role: str | None = Field(default=None, pattern=ROLE_PATTERN)
    # FULL REPLACE of the classes this person is class teacher of — the same
    # shape as marking attendance or saving an observation section. `None` means
    # untouched; `[]` means "they are class teacher of nothing".
    class_teacher_of: list[uuid.UUID] | None = None


class StaffDetailOut(BaseModel):
    """The detail page's own payload: the row, plus what a picker needs.

    The person's *time* (their day, their month, their attendance and leave) is
    NOT here — `GET /insights/staff/{id}/record` has served that since V1-16 and
    duplicating it would give the same screen two versions of one month.
    """

    row: StaffRow
    classes: list[ClassRef] = []
    can_edit: bool = False
    # Why a role dropdown may refuse: the last admin cannot be demoted, and the
    # screen should say so before the tap rather than after it.
    is_last_admin: bool = False
