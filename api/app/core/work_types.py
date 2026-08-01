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


def label_for(work_type: str, org=None) -> str:
    """Human label. An unknown value titles itself instead of vanishing.

    Pass the org to render with ITS label (D-19 rule 1): a school that renamed
    "Event work" to "Programmes" reads historical rows under the new name —
    same key, new word."""
    if org is not None:
        for c in org.work_categories or []:
            if c.get("key") == work_type and (c.get("label") or "").strip():
                return c["label"].strip()
    return WORK_TYPES.get(work_type) or work_type.replace("_", " ").strip().capitalize()


# ── org-configurable categories (V1-2, D-19/S-69) ────────────────────────────
# `organizations.work_categories` = [{key, label, active}] or NULL (= defaults).
# Four rules, enforced here and in OrgService.update:
#   1. Stable key, mutable label — a rename must not orphan last term's rows.
#   2. Retire, never delete — a disabled category keeps rendering on old rows.
#   3. Keep the list short (~10 visible).
#   4. "Other + type it" is always present and always active.

def org_categories(org) -> list[dict]:
    """The resolved category list for an org: defaults overlaid with its config,
    org-added keys appended, `other` forced present-and-active, config order
    honoured."""
    config = {c["key"]: c for c in (org.work_categories or []) if c.get("key")}
    ordered_keys = [c["key"] for c in (org.work_categories or []) if c.get("key")]
    out: list[dict] = []
    seen: set[str] = set()
    keys = ordered_keys if ordered_keys else list(WORK_TYPES)
    for key in keys + [k for k in WORK_TYPES if k not in keys]:
        if key in seen:
            continue
        seen.add(key)
        entry = config.get(key, {})
        out.append({
            "key": key,
            "label": (entry.get("label") or "").strip() or label_for(key),
            "active": bool(entry.get("active", True)),
        })
    for row in out:  # rule 4 — "other" can be relabelled, never retired
        if row["key"] == DEFAULT_WORK_TYPE:
            row["active"] = True
    if not any(r["key"] == DEFAULT_WORK_TYPE for r in out):
        out.append({"key": DEFAULT_WORK_TYPE, "label": WORK_TYPES[DEFAULT_WORK_TYPE],
                    "active": True})
    return out


def active_work_types(org) -> dict[str, str]:
    """key → label for pickers: only active categories, in the org's order."""
    return {c["key"]: c["label"] for c in org_categories(org) if c["active"]}


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
