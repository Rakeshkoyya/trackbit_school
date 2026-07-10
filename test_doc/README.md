# test_doc — import fixtures

Dummy files for exercising the three document importers end-to-end against the demo org.
Regenerate with `cd api && uv run python ../test_doc/generate_fixtures.py`.

Every header was picked to hit a real hint in the importers' `FieldSpec`s, and each file
also contains **rows that are meant to fail**, so the error surfaces get exercised and not
just the happy path.

These assume the demo seed (`uv run python -m scripts.seed`): classes **6-A, 6-B, 7-A**,
subjects **English, Mathematics, Science, Social Studies, Hindi**, year **2026-27**.

| File | Import via | What it tests |
|---|---|---|
| `students_roster.xlsx` | Students → Import | 42 rows; class/section resolution, guardians, categories |
| `teachers_staff.xlsx` | Setup → Members → Import | 10 rows; account creation + class-subject assignment |
| `syllabus_6A_science.xlsx` | Plan → Syllabus → Import | grid path, merged-cell chapters, period estimates |
| `syllabus_6A_maths_termwise.xlsx` | Plan → Syllabus → Import | a `Term` column the importer **drops** (see below) |
| `syllabus_7A_maths.txt` | Plan → Syllabus → paste text | free-text path, `(3)` → est_periods |
| `syllabus_messy_freetext.xlsx` | Plan → Syllabus → Import | no Topic column → text fallback |

## What each file should produce

**`students_roster.xlsx`** — 42 rows. All 10 fields map cleanly.
- 36 students across 6-A / 6-B / 7-A land assigned.
- `TB1037` names class 8-A, which the demo org does not have → imports **unassigned**.
- `TB1038` has only a mother → a single guardian row.
- 2 rows land in `errors` (one missing name, one missing admission no.).
- `A601` / `A602` collide with seeded admission numbers → counted in `skipped`.

Expected: `created: 37, skipped: 2, errors: 2`.

**`teachers_staff.xlsx`** — 10 rows. Assignment strings resolve against existing classes
and subjects.
- 8 teachers created, each with a generated password (`must_set_password = True`).
- `Neha Bhatnagar` is created, but her `9-C Astronomy` token comes back in `unresolved` —
  the org has neither that class nor that subject. `7-A Hindi` still resolves. The importer
  deliberately half-fails loudly rather than half-assigning silently.
- `Ramesh` matches a seeded member by name → counted in `skipped`, no second account.
- The nameless row lands in `errors`.

> Note: committing this **reassigns** `class_subjects.teacher_member_id` for every resolved
> pair, overwriting the seeded teachers. That is the importer working as designed — just be
> aware it mutates the demo org's existing assignments.

**`syllabus_6A_science.xlsx`** — 11 chapters, 32 topics, 79 estimated periods. The `Chapter`
column is blank on continuation rows (how a merged-cell sheet exports); `rows_to_units`
carries the previous chapter forward.

**`syllabus_7A_maths.txt`** — 6 chapters, 21 topics. `Chapter 1: Integers` → chapter titled
`Integers`; a trailing `(3)` becomes `est_periods = 3` and is stripped from the topic title.

**`syllabus_messy_freetext.xlsx`** — one column, no recognisable `Topic` header, so
`analyze_file` falls back to reading column 1 as free text (`source: heuristic-text-fallback`).
3 units, 9 topics.

## `syllabus_6A_maths_termwise.xlsx` — the one that shows a gap

This is the sheet a real teacher would hand you: the whole year's chapters are known, split
into Term 1 and Term 2, but **only Term 1 has period estimates** because they size chapters
when the term starts.

Importing it today does two lossy things:

1. The `Term` column comes back in `unmapped_columns` and is **dropped on commit** — there is
   no `term` field on `syllabus_units`, so the term boundary is not stored.
2. The 12 Term-2 topics have a blank `Periods` cell. `rows_to_units` defaults them to
   `est_periods = 1`. There is no "not yet estimated" state, so the planner treats 12 unsized
   chapters as 12 one-period chapters — and `forecast()` reports **green** on a year that has
   not actually been planned.

Use this file to reproduce that before/after if term-wise planning gets built.

## Known quirk (not caused by these files)

`roster_import.heuristic_mapping` maps the generic `phone` field to `Father's Mobile`, because
the hint `"mobile"` substring-matches that header. It is harmless: the lone-guardian branch in
`RosterImporter.commit` only fires when `father_phone` and `mother_phone` are both empty, and
`phone` points at the same column as `father_phone`. Worth knowing if you add a sheet where the
father column is absent but some other `*Mobile` column exists.
