"""What a teacher does with a period they are not teaching (SF-1).

The timesheet's picker. Deliberately short — a long list makes a teacher think,
and a teacher who has to think about a dropdown stops filling it in (P1v2). Eight
buckets cover the work a school actually tracks; anything else is `other` with a
note the teacher types in their own words.

`WORK_TYPES` is the canonical set, but the column is plain Text with **no CHECK
constraint**: a school that renames its work must never lose rows to a database
error. `label_for` folds an unrecognised value into its own titled label rather
than dropping it, so old data keeps reading correctly after this list changes.
"""

WORK_TYPES: dict[str, str] = {
    "notebook_checking": "Notebook checking",
    "exam_work": "Exam work",
    "event_work": "Event work",
    "student_support": "Student support",
    "prep": "Lesson preparation",
    "meeting": "Meeting",
    "admin_work": "Administrative",
    "other": "Other",
}

DEFAULT_WORK_TYPE = "other"


def label_for(work_type: str) -> str:
    """Human label. An unknown value titles itself instead of vanishing."""
    return WORK_TYPES.get(work_type) or work_type.replace("_", " ").strip().capitalize()


def normalize(raw: str | None) -> str:
    """Accept a key, a label, or free text; return a storable key.

    The importer and the API both go through here so `Notebook Checking`,
    `notebook_checking` and `notebook checking` land in the same bucket.
    """
    if not raw or not raw.strip():
        return DEFAULT_WORK_TYPE
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if key in WORK_TYPES:
        return key
    for k, label in WORK_TYPES.items():
        if label.lower() == raw.strip().lower():
            return k
    return key  # keep the school's own word rather than flattening to "other"
