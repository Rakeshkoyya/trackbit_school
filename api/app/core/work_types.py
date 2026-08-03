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


# ── the colour vocabulary (V1-16) ────────────────────────────────────────────
# The day-book paints one cell per person per period, so a category finally needs
# a COLOUR as well as a word. Two rules, and they are both load-bearing:
#
#   1. **The school picks from a list, never types a hex.** A colour a human
#      typed is a colour nobody validated: the five below were run through the
#      dataviz six-checks against BOTH surfaces, in this order, together with the
#      teaching green they sit beside — lightness band, chroma floor, adjacent
#      CVD separation, the normal-vision floor and contrast. An admin with a
#      colour wheel produces a board that two of every hundred readers cannot
#      read, and no test can catch it.
#   2. **There are FIVE, and that is the point.** A sixth hue cannot be told
#      apart from the five without failing a check, so categories past the fifth
#      render in a plain slate and are read by their label. The colour budget is
#      the short-picker rule (see this module's docstring) with teeth: a school
#      that wants every category coloured has to retire the ones it never uses.
#
# `other` is pinned to the gold slot rather than taking its turn: it is the one
# category every school has, so it must mean the same colour in every school.
CATEGORY_COLORS: list[str] = [
    "#3f6fd8",  # blue
    "#a94f8f",  # orchid
    "#7b5ea8",  # violet
    "#d1603a",  # brick
    "#c99a1e",  # gold — pinned to `other`
]
OTHER_COLOR = "#c99a1e"
#: Categories past the fifth. Not a colour — the absence of one, read by label.
SLATE = "slate"
ALLOWED_COLORS = {*CATEGORY_COLORS, SLATE}


def _assign_colors(rows: list[dict]) -> None:
    """Fill in each row's `color`, in place, honouring what the org chose.

    Position among the ACTIVE categories decides the default, so the same school
    reads the same colours from one term to the next; a retired category keeps
    whatever it was given so last month's grid still renders in the colours the
    admin remembers.
    """
    free = [c for c in CATEGORY_COLORS if c != OTHER_COLOR]
    taken = {r["color"] for r in rows if r.get("color") in CATEGORY_COLORS}
    queue = [c for c in free if c not in taken]
    for row in rows:
        if row.get("color") in ALLOWED_COLORS:
            continue
        if row["key"] == DEFAULT_WORK_TYPE:
            row["color"] = OTHER_COLOR
        elif row["active"] and queue:
            row["color"] = queue.pop(0)
        else:
            row["color"] = SLATE


# ── org-configurable categories (V1-2, D-19/S-69) ────────────────────────────
# `organizations.work_categories` = [{key, label, active, color}] or NULL
# (= defaults). Four rules, enforced here and in OrgService.update:
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
        color = entry.get("color")
        out.append({
            "key": key,
            "label": (entry.get("label") or "").strip() or label_for(key),
            "active": bool(entry.get("active", True)),
            "color": color if color in ALLOWED_COLORS else None,
        })
    for row in out:  # rule 4 — "other" can be relabelled, never retired
        if row["key"] == DEFAULT_WORK_TYPE:
            row["active"] = True
    if not any(r["key"] == DEFAULT_WORK_TYPE for r in out):
        out.append({"key": DEFAULT_WORK_TYPE, "label": WORK_TYPES[DEFAULT_WORK_TYPE],
                    "active": True, "color": OTHER_COLOR})
    _assign_colors(out)
    return out


def color_for(work_type: str, org=None) -> str:
    """The colour a category is painted in. Always resolves — a work type the
    picker has never heard of (an import, a renamed key) reads as slate, which
    is a legible state, not a missing one."""
    if org is not None:
        for c in org_categories(org):
            if c["key"] == work_type:
                return c["color"]
    return OTHER_COLOR if work_type == DEFAULT_WORK_TYPE else SLATE


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
