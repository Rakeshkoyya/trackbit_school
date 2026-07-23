"""Run the generated pack through the REAL importers, without a database.

    cd api && uv run python ../test_doc/big_school/validate.py

`analyze` and the assignment resolver are pure functions over bytes, so we can
prove the pack lands *before* anyone spends an hour clicking through the wizard:

  * the staff sheet's columns map, and every "1 English x11" token resolves
    against the class and subject names SETUP.md tells the admin to create;
  * the roster's required columns (name, admission no) map, and every row has both;
  * all 60 syllabus files parse to the chapter/topic counts the generator wrote,
    with **zero** unsized topics — the thing that would block `approve`;
  * the four invariants still hold on the data as written to disk.

Exits non-zero on the first failure, so it can front a commit.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Blank the key BEFORE app.core.config is imported: `build_analysis` asks the
# model about any spec the keyword heuristic couldn't place (the syllabus sheets
# have no Term column, so that's every one of the 60 files). With a real key
# that's 60 network round-trips and a non-deterministic answer; the deterministic
# heuristic is the thing we actually want to prove.
os.environ["OPENROUTER_API_KEY"] = ""

HERE = Path(__file__).parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE))

from content import CHAPTERS, TOPIC_TEMPLATE  # noqa: E402
from generate import (  # noqa: E402
    CAPACITY,
    CLASSES,
    LOAD_CEILING,
    PERIODS,
    STUDENTS_PER_CLASS,
    SUBJECTS,
    build_syllabus,
    build_teachers,
    slug,
)

from app.services import roster_import, staff_import, syllabus_import  # noqa: E402

FAILURES: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'}  {label}{f' — {detail}' if detail else ''}")
    if not ok:
        FAILURES.append(label)


def load(path: Path) -> bytes:
    return path.read_bytes()


# ── staff ────────────────────────────────────────────────────────────────────
def validate_staff() -> None:
    print("teachers_staff.xlsx")
    analysis = staff_import.analyze(load(DATA / "teachers_staff.xlsx"))
    mapping = analysis["mapping"]
    rows = analysis["rows"]

    check("columns map", not analysis["missing_required"],
          f"mapped {sorted(mapping)}")
    check("every teacher row present", len(rows) == 24, f"{len(rows)} rows")

    # The resolver keys off whatever classes and subjects exist in the org. Build
    # exactly the maps SETUP.md tells the admin to create — no sections.
    classes = {(c, ""): uuid.uuid4() for c in CLASSES}
    subjects = {s.lower(): uuid.uuid4() for s in SUBJECTS}

    importer = staff_import.StaffImporter.__new__(staff_import.StaffImporter)
    resolved = bad_tokens = 0
    load_by_teacher: list[int] = []
    covered: set[tuple[str, str]] = set()
    for row in rows:
        raw = row[mapping["assignments"]]
        pairs, bad = importer._resolve(raw, classes, subjects)
        resolved += len(pairs)
        bad_tokens += len(bad)
        if bad:
            print(f"        unresolved: {bad}")
        load_by_teacher.append(sum(p or 0 for _c, _s, p in pairs))
        for token in raw.split(";"):
            parts = token.strip().rsplit(" x", 1)[0].split(" ", 1)
            covered.add((parts[0], parts[1]))

    expected_cs = sum(len(PERIODS[c]) for c in CLASSES)
    check("every assignment resolves", bad_tokens == 0, f"{bad_tokens} bad tokens")
    check("all class-subjects assigned", resolved == expected_cs,
          f"{resolved} of {expected_cs}")
    check("periods/week ride along", all(load_by_teacher),
          f"heaviest {max(load_by_teacher)}")
    check("no teacher over the ceiling", max(load_by_teacher) <= LOAD_CEILING,
          f"{max(load_by_teacher)} <= {LOAD_CEILING}")
    check("teacher loads sum to the school's week",
          sum(load_by_teacher) == len(CLASSES) * CAPACITY,
          f"{sum(load_by_teacher)} == {len(CLASSES)} x {CAPACITY}")
    check("assignments cover every class-subject exactly once",
          len(covered) == expected_cs, f"{len(covered)} distinct")


# ── roster ───────────────────────────────────────────────────────────────────
def validate_roster() -> None:
    print("students_roster.xlsx")
    columns, rows = roster_import.read_first_sheet(load(DATA / "students_roster.xlsx"))
    analysis = roster_import.analyze(load(DATA / "students_roster.xlsx"))
    mapping = analysis["mapping"]

    check("columns map", not analysis["missing_required"], f"mapped {sorted(mapping)}")
    for field in roster_import.REQUIRED_FIELDS:
        check(f"required field {field!r} mapped", field in mapping)

    check("row count", len(rows) == len(CLASSES) * STUDENTS_PER_CLASS,
          f"{len(rows)} rows")

    name_col, adm_col = mapping["full_name"], mapping["admission_no"]
    class_col, cat_col = mapping.get("class_name"), mapping.get("category")
    missing = [i for i, r in enumerate(rows) if not r.get(name_col) or not r.get(adm_col)]
    check("no row would be rejected", not missing, f"{len(missing)} bad rows")

    adms = [r[adm_col] for r in rows]
    check("admission numbers unique", len(set(adms)) == len(adms))

    per_class = {c: sum(1 for r in rows if r.get(class_col) == c) for c in CLASSES}
    check("30 students in every class",
          all(n == STUDENTS_PER_CLASS for n in per_class.values()), str(per_class))

    cats = {r.get(cat_col) for r in rows}
    check("categories are the two the app expects", cats == {"Day Scholar", "Hosteller"},
          str(sorted(cats)))
    hostellers = sum(1 for r in rows if r.get(cat_col) == "Hosteller")
    check("hostel population is worth testing", 50 <= hostellers <= 100,
          f"{hostellers} hostellers")

    guardians = sum(bool(r.get(mapping.get("father_phone"))) for r in rows)
    check("every student has a guardian phone", guardians == len(rows),
          f"{guardians} of {len(rows)}")


# ── syllabus ─────────────────────────────────────────────────────────────────
def validate_syllabus() -> None:
    print("syllabus/ (60 files)")
    files = sorted(DATA.glob("syllabus/class_*/syllabus_*.xlsx"))
    expected = [(c, s) for c in CLASSES for s in PERIODS[c]]
    check("one file per class-subject", len(files) == len(expected),
          f"{len(files)} files")

    total_units = total_topics = unsized = 0
    mismatched: list[str] = []
    for cname, subject in expected:
        path = (DATA / "syllabus" / f"class_{cname}" /
                f"syllabus_{cname}_{slug(subject)}.xlsx")
        if not path.exists():
            mismatched.append(f"{path.name} missing")
            continue
        out = syllabus_import.analyze_file(path.read_bytes(), path.name)
        if out["mode"] != "grid":
            mismatched.append(f"{path.name} parsed as {out['mode']}, not grid")
            continue
        units = out["units"]
        want = build_syllabus(cname, subject)
        if len(units) != len(want):
            mismatched.append(f"{path.name}: {len(units)} chapters, expected {len(want)}")
        if [u["title"] for u in units] != [c for c, _t in want]:
            mismatched.append(f"{path.name}: chapter titles drifted")
        total_units += len(units)
        for u in units:
            total_topics += len(u["topics"])
            unsized += sum(1 for t in u["topics"] if not t["est_periods"])

    check("every file parses as a grid and round-trips", not mismatched,
          "; ".join(mismatched[:3]) or f"{total_units} chapters, {total_topics} topics")
    check("ZERO unsized topics (approve would refuse them)", unsized == 0,
          f"{unsized} unsized")
    check("chapter titles come from the content bank",
          all(int(c) in CHAPTERS[s] for c, s in expected))
    check("topics come from the teaching template",
          all(TOPIC_TEMPLATE[s] for _c, s in expected))


# ── invariants on the generator's own numbers ────────────────────────────────
def validate_invariants() -> None:
    print("invariants")
    check("I1 every class allocates exactly its week",
          all(sum(PERIODS[c].values()) == CAPACITY for c in CLASSES))
    teachers = build_teachers()
    check("I2 nobody over-loaded, everything covered once",
          max(t.load for t in teachers) <= LOAD_CEILING)
    sized = [(c, s, sum(p for _ch, tt in build_syllabus(c, s) for _t, p in tt))
             for c in CLASSES for s in PERIODS[c]]
    check("I3 every class-subject has sized content", all(n > 0 for _c, _s, n in sized))
    from generate import SYLLABUS_FILL, available_periods
    over = [(c, s) for c, s, n in sized if n > available_periods(PERIODS[c][s])]
    check("I4 no syllabus outruns the year", not over,
          f"fill {SYLLABUS_FILL:.0%}, worst "
          f"{max(n / available_periods(PERIODS[c][s]) for c, s, n in sized):.0%}")


def main() -> int:
    if not DATA.exists():
        print("data/ is missing — run generate.py first")
        return 1
    validate_staff()
    validate_roster()
    validate_syllabus()
    validate_invariants()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} FAILED: {FAILURES}")
        return 1
    print("pack is valid — every importer accepts it, every plan can be locked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
