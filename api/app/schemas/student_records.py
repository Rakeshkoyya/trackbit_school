"""The Academics roster (founder, 2026-08-05) — one row per child.

Directory answers *who is this child*; this answers *how is this child doing*.
Every figure here carries its denominator, and every "nothing recorded yet" is a
null the screen renders as a word — never a zero, never red. That rule is not
decoration: a roster is read left to right at speed, and a 0% that actually
means "nobody has marked anything" is the fastest possible way to blame a class
for a gap in the record.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class RecordAttendance(BaseModel):
    """Marked periods of this child's class, minus their own exception rows.

    `marked_periods == 0` means the register was never taken, so `pct` is None
    and the screen says so. Present is DERIVED (capture-by-exception, P1v2):
    there is no per-student present row to count.
    """

    marked_periods: int = 0
    present: int = 0
    absent: int = 0
    late: int = 0
    pct: float | None = None


class RecordFigure(BaseModel):
    """One never-pooled exam figure (`S-114`/`S-118`).

    `minor` and `major` ride side by side and are never added: trajectory is read
    from minor, standing from major. A caller wanting one blended number has to
    write that addition somewhere a reviewer can see it.
    """

    scale: str
    pct: float | None = None
    tests_taken: int = 0
    tests_held: int = 0
    sentence: str


class RecordHomework(BaseModel):
    """The last homework this child was given, and how the recent run went.

    `latest_status` may be `not_checked`, which is the TEACHER's gap and is never
    rendered as the child's miss (HW-1's rule, kept on every surface). It is also
    why `completion` can be None while `assigned` is non-zero.
    """

    assigned: int = 0
    completion: float | None = None
    not_done: int = 0
    late: int = 0
    carried: int = 0
    not_checked: int = 0
    streak: int = 0
    latest_status: str | None = None
    latest_date: str | None = None
    latest_subject: str | None = None


class StudentRecordRow(BaseModel):
    student_id: uuid.UUID
    full_name: str
    admission_no: str
    roll_no: str | None = None
    class_id: uuid.UUID | None = None
    class_label: str | None = None
    status: str = "active"
    attendance: RecordAttendance = RecordAttendance()
    # Fixed order, both buckets always present — "no major exams yet" is
    # information, and dropping the row is how a screen implies there were none.
    figures: list[RecordFigure] = []
    homework: RecordHomework = RecordHomework()
    # "C · Hindi" — the lowest band with the subject that earned it (`S-186`).
    # Staff-only, never guardian-facing (P4).
    band_chip: str | None = None


class StudentRecordsOut(BaseModel):
    window_days: int
    rows: list[StudentRecordRow] = []
    # What this member is allowed to see, so the screen can say "your 3 classes"
    # rather than leaving a teacher wondering where the rest of the school went.
    scoped: bool = False
    class_count: int = 0
