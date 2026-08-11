"""Does the pack make sense? (SETUP-REDESIGN-PLAN §7, phase P2.)

Nothing here writes. The operator uploads, reads this report, sends the sheet back
to the school, and uploads again — as many times as it takes. Only then does P3
commit, in one transaction. That separation is the point: a half-imported school
is far worse than a rejected file.

Three rules the report obeys, taken from `readiness.py` because they were already
right there:

  * **Every finding names its consequence, not its field.** "45 parents cannot log
    in", never "45 nulls". The operator is deciding whether to send this back to a
    principal, and "date_of_birth is null" does not help them make that call.
  * **Not-captured is a word, never a zero and never red.** An unsized chapter, an
    unplanned term and a subject with no teacher are *states*. They are notes. A
    school that has planned half its year is READY (D-4) — the mid-year guarantee
    would be worthless if this file quietly reinstated a full-year requirement.
  * **Only a blocker blocks.** A blocker is something that would import wrong data
    or import nothing: a missing sheet, a missing required column, a row whose
    class does not exist. Everything else informs.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from app.core.dates import read_date
from app.services.setup_pack.parse import ParsedPack, SheetData, fill_down
from app.services.setup_pack.specs import BY_KEY, SHEETS

BLOCKER, WARNING, NOTE = "blocker", "warning", "note"

# One rule that fires on 900 rows produces 900 findings and an unreadable page.
# Report the first few and say how many more there are.
MAX_PER_RULE = 8

DAYS_IN_WEEK = {"mon fri": 5, "mon sat": 6, "mon sun": 7}


@dataclass(frozen=True)
class Finding:
    sheet: str
    severity: str
    message: str
    fix: str = ""
    row: int | None = None
    rule: str = ""


@dataclass
class SheetSummary:
    key: str
    title: str
    present: bool
    rows: int = 0
    blocked_rows: int = 0


@dataclass
class ValidationReport:
    findings: list[Finding] = field(default_factory=list)
    summaries: list[SheetSummary] = field(default_factory=list)

    def of(self, severity: str) -> list[Finding]:
        return [f for f in self.findings if f.severity == severity]

    @property
    def blockers(self) -> list[Finding]:
        return self.of(BLOCKER)

    @property
    def ready(self) -> bool:
        """Ready to import — which is not the same as ready to hand over. The
        readiness report (`services/readiness.py`) answers that, after the data
        is in."""
        return not self.blockers


def to_date(text: str | None) -> date | None:
    """A calendar date, or None if it cannot be read safely.

    Deliberately not `roster_import.parse_dob`: that one enforces a plausible
    *age* because the value it guards becomes a parent's password, and it reads a
    two-digit year as the past. A term end date has no age and runs forward, so it
    takes `core.dates` at its default. Both now share one format vocabulary, which
    is what lets a school write `21-Aug-2026` on any sheet of the pack.
    """
    return read_date(text)


def to_int(text: str | None) -> int | None:
    if not text:
        return None
    try:
        return int(float(str(text).strip()))
    except ValueError:
        return None


def _label(class_name: str | None, section: str | None) -> str:
    return f"{class_name}-{section}" if section else str(class_name or "")


class _Report:
    """Accumulator that keeps the per-rule cap in one place."""

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self._counts: Counter = Counter()

    def add(self, sheet: str, severity: str, message: str, *, fix: str = "",
            row: int | None = None, rule: str = "") -> None:
        key = rule or message
        self._counts[key] += 1
        if self._counts[key] <= MAX_PER_RULE:
            self.findings.append(Finding(sheet, severity, message, fix, row, rule))

    def close(self) -> list[Finding]:
        """Replace the cap with an honest count — a silently truncated list reads
        as 'that was everything'."""
        for key, total in list(self._counts.items()):
            if total <= MAX_PER_RULE:
                continue
            first = next(f for f in self.findings if (f.rule or f.message) == key)
            self.findings.append(Finding(
                first.sheet, first.severity,
                f"…and {total - MAX_PER_RULE} more like this.",
                rule=f"{key}:overflow"))
        return self.findings


# ── structure ────────────────────────────────────────────────────────────────
def _structure(pack: ParsedPack, out: _Report) -> None:
    for spec in SHEETS:
        data = pack.sheets.get(spec.key)
        if data is None or not data.present:
            if spec.required:
                out.add(spec.title, BLOCKER,
                        f"The {spec.title} sheet is missing — nothing from it can "
                        f"be imported.",
                        fix=f"Add a sheet named '{spec.title}' from the blank pack.",
                        rule=f"{spec.key}:missing_sheet")
            continue
        for key in data.missing_columns:
            column = next(c for c in (spec.columns or spec.settings)
                          if c.key == key)
            header = getattr(column, "header", None) or getattr(column, "label", key)
            out.add(spec.title, BLOCKER,
                    f"No '{header}' column — every row on this sheet would be "
                    f"skipped.",
                    fix=f"Add a column headed '{header}'.",
                    rule=f"{spec.key}:missing_column:{key}")
        # A column we could not place is silent data loss: the school typed
        # guardian phone numbers under "Parent Contact", the mapper found no
        # hint for it, and every one of them is dropped with the review still
        # green. Reported as a warning, not a blocker, because the same shape
        # covers a school's own working columns ("S.No", "Remarks") which are
        # genuinely fine to ignore — the operator is the one who can tell which.
        for header in data.unmapped_columns:
            noun = "setting" if spec.is_key_value else "column"
            out.add(spec.title, WARNING,
                    f"'{header}' is not a {noun} we recognise, so nothing in it "
                    f"will be imported.",
                    fix="Rename it to one of the pack's own headers if it holds "
                        "data we should keep — otherwise ignore this.",
                    rule=f"{spec.key}:unmapped_column")
    for title in pack.extra_sheets:
        out.add(title, NOTE,
                f"'{title}' is not part of the pack and will be ignored.",
                rule="extra_sheet")


def _required_cells(data: SheetData, out: _Report) -> set[int]:
    """Rows missing something required. Returns their indices so later rules can
    skip them rather than piling three findings onto one broken row."""
    spec = BY_KEY[data.key]
    broken: set[int] = set()
    for i, row in enumerate(data.rows):
        for key in spec.required_keys:
            if key in data.missing_columns or row.get(key):
                continue
            column = next(c for c in spec.columns if c.key == key)
            out.add(spec.title, BLOCKER,
                    f"No {column.header.lower()} — this row cannot be imported.",
                    fix=f"Fill '{column.header}', or delete the row.",
                    row=data.excel_row(i), rule=f"{data.key}:blank:{key}")
            broken.add(i)
    return broken


# ── the school itself ────────────────────────────────────────────────────────
def _school(pack: ParsedPack, out: _Report) -> None:
    title = BY_KEY["school"].title
    start, end = to_date(pack.setting("year_start")), to_date(pack.setting("year_end"))
    if pack.setting("year_start") and start is None:
        out.add(title, BLOCKER, "The year's start date cannot be read.",
                fix="Write it day-first, like 01/06/2026.", rule="school:year_start")
    if pack.setting("year_end") and end is None:
        out.add(title, BLOCKER, "The year's end date cannot be read.",
                fix="Write it day-first, like 30/04/2027.", rule="school:year_end")
    if start and end and end <= start:
        out.add(title, BLOCKER,
                "The year ends before it starts — no term or plan can be built.",
                fix="Check the two dates.", rule="school:year_order")

    tracking = to_date(pack.setting("tracking_start"))
    if tracking and start and end and not (start <= tracking <= end):
        out.add(title, WARNING,
                "Tracking starts outside the academic year — the school would see "
                "an empty calendar on day one.",
                fix="Set it to the day TrackBit goes live, inside the year.",
                rule="school:tracking_range")

    ppd = to_int(pack.setting("periods_per_day"))
    if pack.setting("periods_per_day") and ppd is None:
        out.add(title, BLOCKER, "Periods per day is not a number.",
                fix="Write a whole number, like 8.", rule="school:ppd")
    elif ppd is not None and not 1 <= ppd <= 16:
        out.add(title, BLOCKER,
                f"{ppd} periods a day is outside what a timetable can hold.",
                fix="Between 1 and 16.", rule="school:ppd_range")


def _week_capacity(pack: ParsedPack) -> int | None:
    """Teaching periods available to one class in a week — the ceiling every
    allocation is measured against (`new_org` invariant 1)."""
    ppd = to_int(pack.setting("periods_per_day"))
    days = DAYS_IN_WEEK.get(
        " ".join((pack.setting("working_days") or "mon sat").lower()
                 .replace("-", " ").split()), 6)
    return ppd * days if ppd else None


# ── terms ────────────────────────────────────────────────────────────────────
def term_windows(pack: ParsedPack) -> list[dict]:
    """The year's terms, each derived from its exam (founder, 2026-08-08).

    A term ENDS on its exam's last day and starts the day after the previous
    term's exam ended; the first starts with the year. So the school states one
    date range per term — when the exam runs — and the teaching window, the exam
    block and the portion all fall out of it. Nothing is entered twice, and a
    term and its exam cannot drift apart, which is exactly what happened while
    they were two sheets linked only by overlapping dates.

    Returned in sheet order with every date resolved, so the validator and the
    committer read one derivation rather than each writing their own.
    """
    out: list[dict] = []
    cursor = to_date(pack.setting("year_start"))
    for i, row in enumerate(pack.rows("terms")):
        name = (row.get("term_name") or "").strip()
        exam_end = to_date(row.get("exam_end"))
        out.append({
            "index": i, "name": name,
            "exam_name": (row.get("exam_name") or "").strip() or name,
            "exam_start": to_date(row.get("exam_start")), "exam_end": exam_end,
            "start": cursor, "end": exam_end,
        })
        if exam_end:
            cursor = exam_end + timedelta(days=1)
    return out


def _terms(pack: ParsedPack, out: _Report,
           ) -> dict[str, tuple[date | None, date | None]]:
    """Returns {term name: (start, end)} for the syllabus to file chapters under."""
    data = pack.sheets["terms"]
    title = data.title
    broken = _required_cells(data, out)
    year_start = to_date(pack.setting("year_start"))
    year_end = to_date(pack.setting("year_end"))
    names: dict[str, tuple[date | None, date | None]] = {}
    previous_end: date | None = None

    for term in term_windows(pack):
        i, name = term["index"], term["name"]
        names[name.lower()] = (term["start"], term["end"])
        if i in broken:
            continue
        exam_start, exam_end = term["exam_start"], term["exam_end"]
        if exam_start is None or exam_end is None:
            out.add(title, BLOCKER,
                    f"{name}: the exam dates cannot be read, so the term has no "
                    f"end and nothing can be planned into it.",
                    fix="Write both day-first, like 22/09/2026.",
                    row=data.excel_row(i), rule="terms:dates")
            continue
        if exam_end < exam_start:
            out.add(title, BLOCKER, f"{name}'s exam ends before it starts.",
                    fix="Check the two dates.", row=data.excel_row(i),
                    rule="terms:order")
            continue
        if previous_end and exam_start <= previous_end:
            out.add(title, BLOCKER,
                    f"{name}'s exam starts {exam_start:%d %b}, on or before the "
                    f"previous term's exam ended ({previous_end:%d %b}) — two "
                    f"terms would claim the same days.",
                    fix="List the terms in order, with exams that do not overlap.",
                    row=data.excel_row(i), rule="terms:overlap")
            continue
        if year_start and year_end and not (
                year_start <= exam_start and exam_end <= year_end):
            out.add(title, WARNING,
                    f"{name}'s exam falls outside the academic year, so its term "
                    f"would run into days the school is not open.",
                    fix="Check it against the year on the School sheet.",
                    row=data.excel_row(i), rule="terms:range")
        if term["start"] and exam_start <= term["start"]:
            out.add(title, WARNING,
                    f"{name} has no teaching days before its exam.",
                    fix="Check the exam dates and the order of the terms.",
                    row=data.excel_row(i), rule="terms:no_teaching")
        previous_end = exam_end
    return names


# ── classes and staff ────────────────────────────────────────────────────────
def _staff(pack: ParsedPack, out: _Report) -> set[str]:
    data = pack.sheets["staff"]
    broken = _required_cells(data, out)
    names: set[str] = set()
    emails: Counter = Counter()

    for i, row in enumerate(data.rows):
        if i in broken:
            continue
        names.add((row.get("full_name") or "").strip().lower())
        email = (row.get("email") or "").strip().lower()
        if email:
            emails[email] += 1
        role = (row.get("role") or "Teacher").strip().lower()
        if role not in {"teacher", "admin"}:
            out.add(data.title, WARNING,
                    f"'{row.get('role')}' is not a role — this person would be "
                    f"created as a teacher.",
                    fix="Write Teacher or Admin. Wardens and coordinators are "
                        "teachers.",
                    row=data.excel_row(i), rule="staff:role")
    for email, count in emails.items():
        if count > 1:
            out.add(data.title, BLOCKER,
                    f"{email} appears {count} times — one person cannot have two "
                    f"logins.",
                    fix="Give each person their own email, or leave it blank.",
                    rule="staff:duplicate_email")
    return names


def _classes(pack: ParsedPack, out: _Report, staff: set[str]) -> set[tuple[str, str]]:
    data = pack.sheets["classes"]
    broken = _required_cells(data, out)
    seen: Counter = Counter()
    known: set[tuple[str, str]] = set()

    for i, row in enumerate(data.rows):
        if i in broken:
            continue
        name = (row.get("class_name") or "").strip()
        section = (row.get("section") or "").strip()
        key = (name.lower(), section.lower())
        seen[key] += 1
        known.add(key)
        teacher = (row.get("class_teacher") or "").strip()
        if teacher and teacher.lower() not in staff:
            out.add(data.title, BLOCKER,
                    f"{_label(name, section)}: '{teacher}' is not on the Staff "
                    f"sheet, so this class would have no class teacher and its "
                    f"absence follow-ups no owner.",
                    fix="Add them to Staff, or correct the spelling to match.",
                    row=data.excel_row(i), rule="classes:unknown_teacher")
    for (name, section), count in seen.items():
        if count > 1:
            out.add(data.title, BLOCKER,
                    f"{_label(name, section)} is listed {count} times.",
                    fix="Keep one row per class and section.",
                    rule="classes:duplicate")
    return known


def _class_exists(known: set[tuple[str, str]], name: str, section: str) -> bool:
    """A blank section means every section of that class, so it matches if the
    class exists at all."""
    if section:
        return (name.lower(), section.lower()) in known
    return any(c == name.lower() for c, _ in known)


def _sections_of(known: set[tuple[str, str]], name: str,
                 section: str) -> list[tuple[str, str]]:
    if section:
        return [(name.lower(), section.lower())]
    return [(c, s) for c, s in known if c == name.lower()]


# ── assignments ──────────────────────────────────────────────────────────────
def _assignments(pack: ParsedPack, out: _Report, known: set[tuple[str, str]],
                 staff: set[str],
                 ) -> tuple[dict[tuple[str, str, str], str],
                            dict[tuple[str, str, str], str]]:
    """`(offered, teachers)`.

    `offered` — the (class, section, subject) triples the syllabus and
    timetable may legitimately refer to, each mapped to how it should be
    *written* back to the operator. Matching is case-folded; a report that says
    "6-a science" when the school wrote "6-A Science" looks like a different
    thing to the person reading it.

    `teachers` — the same triples mapped to the teacher who owns them, so the
    Timetable pass can say *"Anita Desai is on the grid 42 times"* without
    re-reading this sheet.
    """
    data = pack.sheets["assignments"]
    broken = _required_cells(data, out)
    offered: dict[tuple[str, str, str], str] = {}
    teachers: dict[tuple[str, str, str], str] = {}
    seen: Counter = Counter()

    for i, row in enumerate(data.rows):
        if i in broken:
            continue
        name = (row.get("class_name") or "").strip()
        section = (row.get("section") or "").strip()
        subject = (row.get("subject") or "").strip()
        if not _class_exists(known, name, section):
            out.add(data.title, BLOCKER,
                    f"{_label(name, section)} is not on the Classes sheet — "
                    f"{subject} would be taught to a class that does not exist.",
                    fix="Add the class, or correct the spelling.",
                    row=data.excel_row(i), rule="assignments:unknown_class")
            continue

        targets = _sections_of(known, name, section)
        for target in targets:
            triple = (*target, subject.lower())
            seen[triple] += 1
            # Written as the school wrote it, with the real section it fanned to.
            offered[triple] = f"{_label(name, target[1].upper())} {subject}"

        teacher = (row.get("teacher") or "").strip()
        if teacher and teacher.lower() not in staff:
            out.add(data.title, BLOCKER,
                    f"{_label(name, section)} {subject}: '{teacher}' is not on the "
                    f"Staff sheet and cannot be given a login.",
                    fix="Add them to Staff, or correct the spelling.",
                    row=data.excel_row(i), rule="assignments:unknown_teacher")
        elif not teacher:
            out.add(data.title, NOTE,
                    f"{_label(name, section)} {subject} has no teacher yet.",
                    fix="Fill it in when the school decides — this does not stop "
                        "handover.",
                    row=data.excel_row(i), rule="assignments:no_teacher")

        # TT-3: no periods/week on this sheet any more. Who teaches what is
        # recorded here; HOW MUCH is counted off the Timetable sheet, so the
        # capacity invariants moved there with it. All this pass keeps is the
        # mapping the timetable needs to attribute a period to a teacher.
        if teacher:
            for target in targets:
                teachers[(*target, subject.lower())] = teacher.lower()

    for triple, count in seen.items():
        if count > 1:
            out.add(data.title, WARNING,
                    f"{_label(triple[0], triple[1])} {triple[2]} appears {count} "
                    f"times — the last row would win.",
                    fix="Keep one row per class, section and subject.",
                    rule="assignments:duplicate")

    for name, section in sorted(known - {(c, s) for c, s, _subj in offered}):
        out.add(data.title, WARNING,
                f"{_label(name, section)} is not taught any subject — it would be "
                f"an empty class with an empty timetable.",
                fix=f"Add {_label(name, section)}'s subjects, or remove the class.",
                rule="assignments:class_without_subjects")

    return offered, teachers


def _capacity_checks(title: str, out: _Report, per_class: dict, per_teacher: dict,
                     capacity: int | None) -> None:
    """`new_org` invariants 1 and 2 — the two that make an import land cleanly.

    Counted off the TIMETABLE since TT-3, not off a weekly budget somebody
    typed. That is a stronger check than the one it replaces: it tests the grid
    the school will actually run rather than its intention for it, and a
    double-booked teacher is a real timetable that cannot be taught, not an
    arithmetic slip on a spreadsheet.
    """
    if not capacity:
        return
    for (name, section), total in sorted(per_class.items()):
        if total > capacity:
            out.add(title, WARNING,
                    f"{_label(name, section)} has {total} periods on the grid but "
                    f"the week only holds {capacity} — some of them cannot run.",
                    fix="Remove periods, or raise the periods per day.",
                    rule="timetable:class_over_capacity")
    for teacher, total in sorted(per_teacher.items()):
        if total > capacity:
            out.add(title, WARNING,
                    f"{teacher.title()} is on the grid for {total} periods a week "
                    f"— more than the {capacity} periods that exist in a week.",
                    fix="Spread the subjects across more teachers.",
                    rule="timetable:teacher_over_capacity")


# ── syllabus ─────────────────────────────────────────────────────────────────
def _syllabus(pack: ParsedPack, out: _Report,
              offered: dict[tuple[str, str, str], str],
              known: set[tuple[str, str]], terms: set[str]) -> None:
    data = pack.sheets["syllabus"]
    title = data.title
    if not data.present:
        return
    # One sheet now holds every class, so class and subject get the same
    # blank-continues-above treatment chapter always had.
    rows = fill_down(data.rows, ("class_name", "section", "subject", "term",
                                 "chapter"))
    unsized = 0
    planned_terms: set[str] = set()
    seen_subjects: set[tuple[str, str, str]] = set()

    for i, row in enumerate(rows):
        name = (row.get("class_name") or "").strip()
        section = (row.get("section") or "").strip()
        subject = (row.get("subject") or "").strip()
        chapter = (row.get("chapter") or "").strip()
        if not name or not subject or not chapter:
            out.add(title, BLOCKER,
                    "This row has no class, subject or chapter — it cannot be "
                    "filed anywhere.",
                    fix="Fill the three, or delete the row.",
                    row=data.excel_row(i), rule="syllabus:incomplete")
            continue
        if not _class_exists(known, name, section):
            out.add(title, BLOCKER,
                    f"{_label(name, section)} is not on the Classes sheet — these "
                    f"chapters would belong to nobody.",
                    fix="Add the class, or correct the spelling.",
                    row=data.excel_row(i), rule="syllabus:unknown_class")
            continue

        targets = _sections_of(known, name, section)
        if not any((*t, subject.lower()) in offered for t in targets):
            out.add(title, BLOCKER,
                    f"Nobody is assigned to teach {subject} to "
                    f"{_label(name, section)}, so its syllabus has no plan to "
                    f"hang on.",
                    fix=f"Add {_label(name, section)} {subject} to Teaching "
                        f"Assignments.",
                    row=data.excel_row(i), rule="syllabus:not_offered")
            continue
        seen_subjects.update((*t, subject.lower()) for t in targets)

        term = (row.get("term") or "").strip()
        if term:
            planned_terms.add(term.lower())
            if term.lower() not in terms:
                out.add(title, WARNING,
                        f"'{term}' is not on the Terms sheet — these chapters "
                        f"would be filed under no term and could not be locked on "
                        f"their own.",
                        fix="Match the spelling on the Terms sheet.",
                        row=data.excel_row(i), rule="syllabus:unknown_term")
        if to_int(row.get("periods")) is None:
            unsized += 1

    _syllabus_notes(title, out, unsized, len(rows), terms, planned_terms,
                    offered, seen_subjects)


def _syllabus_notes(title: str, out: _Report, unsized: int, total: int,
                    terms: set[str], planned: set[str],
                    offered: dict[tuple[str, str, str], str], seen: set) -> None:
    """The mid-year guarantee, written down (D-3 / D-4). None of this blocks."""
    if unsized:
        out.add(title, NOTE,
                f"{unsized} of {total} chapters have no period estimate yet — they "
                f"are recorded but cannot be paced until they are sized.",
                fix="Add estimates when the school has them. A blank is honest; a "
                    "guess is not.",
                rule="syllabus:unsized")
    for term in sorted(terms - planned):
        out.add(title, NOTE,
                f"{term.title()} has no chapters yet — that term simply is not "
                f"planned, which is normal part-way through a year.",
                fix="Upload the rest whenever the school is ready; it adds to what "
                    "is already here.",
                rule="syllabus:term_unplanned")
    for triple in sorted(set(offered) - seen):
        out.add(title, NOTE,
                f"{offered[triple]} has no syllabus yet.",
                fix="Add its chapters when the school sends them.",
                rule="syllabus:subject_unplanned")


# ── students ─────────────────────────────────────────────────────────────────
def _students(pack: ParsedPack, out: _Report, known: set[tuple[str, str]]) -> None:
    data = pack.sheets["students"]
    broken = _required_cells(data, out)
    admissions: Counter = Counter()
    no_dob = 0

    for i, row in enumerate(data.rows):
        if i in broken:
            continue
        admissions[(row.get("admission_no") or "").strip().lower()] += 1
        name = (row.get("class_name") or "").strip()
        section = (row.get("section") or "").strip()
        if not name:
            out.add(data.title, WARNING,
                    f"{row.get('full_name')} is in no class and would appear on no "
                    f"register.",
                    fix="Fill the class.", row=data.excel_row(i),
                    rule="students:no_class")
        elif not _class_exists(known, name, section):
            out.add(data.title, BLOCKER,
                    f"{row.get('full_name')}: {_label(name, section)} is not on the "
                    f"Classes sheet.",
                    fix="Add the class, or correct the spelling.",
                    row=data.excel_row(i), rule="students:unknown_class")
        if not to_date(row.get("date_of_birth")):
            no_dob += 1

    for admission, count in admissions.items():
        if count > 1:
            out.add(data.title, BLOCKER,
                    f"Admission number {admission} is used by {count} children — a "
                    f"re-upload could not tell them apart.",
                    fix="Give each child a unique admission number.",
                    rule="students:duplicate_admission")
    if no_dob:
        subject = ("1 student has" if no_dob == 1
                   else f"{no_dob} students have")
        out.add(data.title, WARNING,
                f"{subject} no readable date of birth — that many parents cannot "
                f"log in to the portal.",
                fix="Fill it day-first, like 14/06/2014.", rule="students:dob")


# ── timetable, calendar, fees ────────────────────────────────────────────────
def _timetable(pack: ParsedPack, out: _Report, offered: set,
               teachers: dict[tuple[str, str, str], str], known: set,
               periods_per_day: int | None, capacity: int | None) -> None:
    data = pack.sheets["timetable"]
    if not data.present or not data.rows:
        return
    broken = _required_cells(data, out)
    slots: Counter = Counter()
    # TT-3: the grid IS the weekly load, so the capacity invariants are counted
    # here now rather than summed off a column on Teaching Assignments.
    per_class: defaultdict = defaultdict(int)
    per_teacher: defaultdict = defaultdict(int)
    per_class_subject: defaultdict = defaultdict(int)

    for i, row in enumerate(data.rows):
        if i in broken:
            continue
        name = (row.get("class_name") or "").strip()
        section = (row.get("section") or "").strip()
        subject = (row.get("subject") or "").strip()
        period = to_int(row.get("period"))
        if not _class_exists(known, name, section):
            out.add(data.title, BLOCKER,
                    f"{_label(name, section)} is not on the Classes sheet.",
                    fix="Add the class, or correct the spelling.",
                    row=data.excel_row(i), rule="timetable:unknown_class")
            continue
        if not any((*t, subject.lower()) in offered
                   for t in _sections_of(known, name, section)):
            out.add(data.title, BLOCKER,
                    f"{subject} is not taught to {_label(name, section)}, so this "
                    f"period has no teacher.",
                    fix="Add it to Teaching Assignments.",
                    row=data.excel_row(i), rule="timetable:not_offered")
            continue
        if period is None or period < 1 or (
                periods_per_day and period > periods_per_day):
            out.add(data.title, BLOCKER,
                    f"Period '{row.get('period')}' is outside the school's day.",
                    fix=f"Between 1 and {periods_per_day or 'the periods per day'}.",
                    row=data.excel_row(i), rule="timetable:period_range")
            continue
        slots[(name.lower(), section.lower(),
               (row.get("day") or "").strip().lower(), period)] += 1

        # One row is one period. Attribute it to the class, and to whoever the
        # Teaching Assignments sheet says owns that subject on that class.
        for target in _sections_of(known, name, section):
            per_class[target] += 1
            per_class_subject[(*target, subject.lower())] += 1
            owner = teachers.get((*target, subject.lower()))
            if owner:
                per_teacher[owner] += 1

    for (name, section, day, period), count in slots.items():
        if count > 1:
            out.add(data.title, BLOCKER,
                    f"{_label(name, section)} has {count} subjects in period "
                    f"{period} on {day.title()}.",
                    fix="One subject per class, per period, per day.",
                    rule="timetable:double_booked")

    # TT-3: a subject the school teaches but never puts on the grid has no
    # weekly load, so its plan cannot be paced and none of its chapters can be
    # dated. It replaces the old "no periods per week" note, and it is a NOTE
    # for the same reason that one was: a school mid-way through building its
    # timetable must still be handed over (D-3/D-4).
    for triple, written in sorted(offered.items()):
        if not per_class_subject.get(triple):
            out.add(data.title, NOTE,
                    f"{written} is not on the timetable, so it has no weekly "
                    f"period count and its plan cannot be paced yet.",
                    fix="Add its periods to this sheet when the grid is drawn.",
                    rule="timetable:subject_not_scheduled")

    _capacity_checks(data.title, out, per_class, per_teacher, capacity)


def _calendar(pack: ParsedPack, out: _Report) -> None:
    data = pack.sheets["calendar"]
    if not data.present or not data.rows:
        return
    broken = _required_cells(data, out)
    for i, row in enumerate(data.rows):
        if i in broken:
            continue
        start, end = to_date(row.get("start_date")), to_date(row.get("end_date"))
        if start is None:
            out.add(data.title, BLOCKER,
                    f"{row.get('title')}: the date cannot be read.",
                    fix="Write it day-first, like 15/08/2026.",
                    row=data.excel_row(i), rule="calendar:date")
        elif end and end < start:
            out.add(data.title, BLOCKER,
                    f"{row.get('title')} ends before it starts.",
                    fix="Check the two dates.", row=data.excel_row(i),
                    rule="calendar:order")
        kind = (row.get("type") or "").strip().lower()
        if kind == "exam":
            out.add(data.title, WARNING,
                    f"{row.get('title')}: exams belong on the Exams sheet, where "
                    f"they carry a date per subject and a syllabus portion. "
                    f"Here it would be recorded as an ordinary event.",
                    fix="Move it to the Exams sheet.",
                    row=data.excel_row(i), rule="calendar:exam_here")
        elif kind not in {"holiday", "event"}:
            out.add(data.title, WARNING,
                    f"{row.get('title')}: '{row.get('type')}' is not a type, so "
                    f"this would be recorded as an ordinary event.",
                    fix="Write Holiday or Event.",
                    row=data.excel_row(i), rule="calendar:type")


def _fees(pack: ParsedPack, out: _Report, known: set) -> None:
    data = pack.sheets["fees"]
    if not data.present or not data.rows:
        return
    broken = _required_cells(data, out)
    totals: defaultdict = defaultdict(list)

    for i, row in enumerate(data.rows):
        if i in broken:
            continue
        name = (row.get("class_name") or "").strip()
        if not _class_exists(known, name, ""):
            out.add(data.title, BLOCKER,
                    f"Class {name} is not on the Classes sheet.",
                    fix="Add the class, or correct the spelling.",
                    row=data.excel_row(i), rule="fees:unknown_class")
            continue
        total = to_int(row.get("total_amount"))
        amount = to_int(row.get("amount"))
        if total is None:
            out.add(data.title, BLOCKER,
                    f"Class {name}: the total amount is not a number.",
                    fix="Write digits only, like 48000.",
                    row=data.excel_row(i), rule="fees:total_number")
            continue
        totals[(name.lower(), (row.get("category") or "").strip().lower(),
                total)].append(amount or 0)

    for (name, _category, total), amounts in totals.items():
        if sum(amounts) and sum(amounts) != total:
            out.add(data.title, WARNING,
                    f"Class {name}: the installments add up to {sum(amounts)} but "
                    f"the total says {total} — the difference would show as never "
                    f"collected.",
                    fix="Make the installments sum to the total.",
                    rule="fees:installments_sum")


# ── the whole pack ───────────────────────────────────────────────────────────
def validate(pack: ParsedPack) -> ValidationReport:
    """Everything wrong with this workbook, worst first, nothing written."""
    out = _Report()
    _structure(pack, out)
    _school(pack, out)
    terms = _terms(pack, out)
    staff = _staff(pack, out)
    known = _classes(pack, out, staff)
    capacity = _week_capacity(pack)
    offered, teachers = _assignments(pack, out, known, staff)
    _syllabus(pack, out, offered, known, set(terms))
    _students(pack, out, known)
    _timetable(pack, out, offered, teachers, known,
               to_int(pack.setting("periods_per_day")), capacity)
    _calendar(pack, out)
    _fees(pack, out, known)

    findings = out.close()
    order = {BLOCKER: 0, WARNING: 1, NOTE: 2}
    findings.sort(key=lambda f: (order[f.severity], f.sheet, f.row or 0))
    blocked = {(f.sheet, f.row) for f in findings
               if f.severity == BLOCKER and f.row}
    return ValidationReport(
        findings=findings,
        summaries=[
            SheetSummary(
                key=spec.key, title=spec.title,
                present=bool(pack.sheets.get(spec.key)
                             and pack.sheets[spec.key].present),
                rows=(pack.sheets[spec.key].row_count
                      if spec.key in pack.sheets else 0),
                blocked_rows=sum(1 for (title, _row) in blocked
                                 if title == spec.title))
            for spec in SHEETS
        ])
