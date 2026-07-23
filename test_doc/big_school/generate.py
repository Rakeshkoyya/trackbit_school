"""Generate the BIG-SCHOOL setup pack — 8 classes, 240 students, 24 teachers.

    cd api && uv run python ../test_doc/big_school/generate.py

Unlike `test_doc/new_org/generate.py` (which invents a *different* small school on
every run to fuzz the importers), this pack describes **one fixed school** —
Sunrise International School, a CBSE day-and-boarding school — at the size the
product is actually sold into. The school is deterministic so the walkthrough in
SETUP.md can quote exact numbers; only student names/phones come from a seeded
RNG, and the seed is pinned.

Four invariants make the pack *land* rather than merely import:

  I1  Every class's subject periods sum EXACTLY to the weekly capacity
      (6 working days x 8 periods = 48), so each class reads "48 of 48 allocated".
  I2  Every class-subject has exactly one teacher and no teacher is over-loaded
      (heaviest is 22 of a possible 46), so the timetable is solvable clash-free.
  I3  Every topic is sized, so `approve` can LOCK all 60 plans — an unsized topic
      is refused.
  I4  Each class-subject's syllabus is sized to ~72% of the periods the TRACKED
      window actually offers, so every forecast is green with visible slack and
      the exam-fit panel reads "perfect"/"spare time".

The school adopts TrackBit **mid-year** (the year opened 1 Jun 2026; tracking
starts Mon 20 Jul 2026), because that is how a real school arrives — and it is
what `academic_years.tracking_start_date` exists for. I4's "available periods"
are therefore counted from the tracking date, not the year start.

Outputs (under ./data, stale files cleared first):
  teachers_staff.xlsx              -> wizard step 5
  students_roster.xlsx             -> wizard step 8
  syllabus/class_<n>/syllabus_<n>_<subject>.xlsx   (60 files) -> wizard step 6
  calendar_events.csv              -> wizard step 7 (typed in by hand; no importer)
  fee_structures.csv               -> Fees > Structures (typed in by hand)
  hostel_sessions.csv              -> Plan > Hostel (typed in by hand)
and ./SCHOOL.md, the derived reference sheet for all of the above.
"""

from __future__ import annotations

import csv
import random
import shutil
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from content import CHAPTERS, TOPIC_TEMPLATE
from openpyxl import Workbook

HERE = Path(__file__).parent
DATA = HERE / "data"

STUDENT_SEED = 20260727

# ── the school on paper ──────────────────────────────────────────────────────
SCHOOL_NAME = "Sunrise International School"
SCHOOL_CITY = "Hyderabad"
ADMIN_NAME = "Vikram Rathore"
ADMIN_EMAIL = "principal@sunriseintl.edu.in"

YEAR_LABEL = "2026-27"
YEAR_START = date(2026, 6, 1)
YEAR_END = date(2027, 4, 10)
# The Monday the school goes live. Deliberately just BEHIND today (2026-07-23):
# a tracking date in the future leaves My Day, the plan and the daily report with
# nothing to show, which reads as "the product is empty" rather than "we start
# Monday". Push it forward if you set this school up much later.
TRACKING_START = date(2026, 7, 20)

WORKING_WEEKDAYS = [0, 1, 2, 3, 4, 5]   # Mon-Sat (Mon=0), the app's default
PERIODS_PER_DAY = 8
DAY_STARTS_AT = "08:00"
PERIOD_MINUTES = 40
LUNCH_AFTER_PERIOD = 5
LUNCH_MINUTES = 40

CAPACITY = len(WORKING_WEEKDAYS) * PERIODS_PER_DAY   # 48 periods/week per class
CLASSES = [str(g) for g in range(1, 9)]
STUDENTS_PER_CLASS = 30

# One teacher's ceiling — a class's week, minus headroom so the timetable
# generator can always find a free slot for them.
LOAD_CEILING = CAPACITY - 2

# How much of the available time the syllabus is allowed to claim (I4).
SYLLABUS_FILL = 0.72

# The org's subject list, in the order the wizard should be given them.
SUBJECTS = [
    "English", "Hindi", "Mathematics", "EVS", "Science", "Social Studies",
    "Sanskrit", "Computer Science", "Art & Craft", "Physical Education",
]

# ── weekly period split, per class (I1: every row sums to 48) ────────────────
# Primary (1-4) runs EVS and Art & Craft; middle (5-8) splits EVS into Science +
# Social Studies and adds Sanskrit as the third language.
PERIODS: dict[str, dict[str, int]] = {
    "1": {"English": 11, "Hindi": 9, "Mathematics": 10, "EVS": 6,
          "Computer Science": 4, "Art & Craft": 4, "Physical Education": 4},
    "2": {"English": 11, "Hindi": 8, "Mathematics": 10, "EVS": 7,
          "Computer Science": 4, "Art & Craft": 4, "Physical Education": 4},
    "3": {"English": 10, "Hindi": 8, "Mathematics": 10, "EVS": 8,
          "Computer Science": 4, "Art & Craft": 4, "Physical Education": 4},
    "4": {"English": 10, "Hindi": 8, "Mathematics": 10, "EVS": 8,
          "Computer Science": 4, "Art & Craft": 4, "Physical Education": 4},
    "5": {"English": 8, "Hindi": 6, "Sanskrit": 4, "Mathematics": 9, "Science": 7,
          "Social Studies": 6, "Computer Science": 4, "Physical Education": 4},
    "6": {"English": 8, "Hindi": 6, "Sanskrit": 4, "Mathematics": 8, "Science": 8,
          "Social Studies": 6, "Computer Science": 4, "Physical Education": 4},
    "7": {"English": 8, "Hindi": 5, "Sanskrit": 4, "Mathematics": 8, "Science": 8,
          "Social Studies": 7, "Computer Science": 4, "Physical Education": 4},
    "8": {"English": 7, "Hindi": 5, "Sanskrit": 4, "Mathematics": 9, "Science": 9,
          "Social Studies": 7, "Computer Science": 4, "Physical Education": 3},
}

# ── staff (I2) ───────────────────────────────────────────────────────────────
# (name, username, subject, [classes]) — one row per teacher. Usernames carry a
# `sis.` prefix because `users.username` is GLOBAL across every school in the
# database: without it, "meena.iyer" could already be taken and the importer
# would silently hand out "meena.iyer2", making this document wrong.
STAFF: list[tuple[str, str, str, list[str]]] = [
    # primary (classes 1-4)
    ("Meena Iyer",       "sis.meena.iyer",       "English",            ["1", "2"]),
    ("Radhika Nair",     "sis.radhika.nair",     "English",            ["3", "4"]),
    ("Sunita Sharma",    "sis.sunita.sharma",    "Hindi",              ["1", "2"]),
    ("Kavita Joshi",     "sis.kavita.joshi",     "Hindi",              ["3", "4"]),
    ("Anita Reddy",      "sis.anita.reddy",      "Mathematics",        ["1", "2"]),
    ("Deepa Menon",      "sis.deepa.menon",      "Mathematics",        ["3", "4"]),
    ("Shalini Rao",      "sis.shalini.rao",      "EVS",                ["1", "2"]),
    ("Priya Desai",      "sis.priya.desai",      "EVS",                ["3", "4"]),
    # middle (classes 5-8)
    ("Rajesh Verma",     "sis.rajesh.verma",     "English",            ["5", "6"]),
    ("Nandini Bose",     "sis.nandini.bose",     "English",            ["7", "8"]),
    ("Manoj Tiwari",     "sis.manoj.tiwari",     "Hindi",              ["5", "6"]),
    ("Rekha Pillai",     "sis.rekha.pillai",     "Hindi",              ["7", "8"]),
    ("Vikram Singh",     "sis.vikram.singh",     "Mathematics",        ["5", "6"]),
    ("Lakshmi Kumar",    "sis.lakshmi.kumar",    "Mathematics",        ["7", "8"]),
    ("Suresh Babu",      "sis.suresh.babu",      "Science",            ["5", "6"]),
    ("Anjali Gupta",     "sis.anjali.gupta",     "Science",            ["7", "8"]),
    ("Prakash Mehta",    "sis.prakash.mehta",    "Social Studies",     ["5", "6"]),
    ("Geeta Chopra",     "sis.geeta.chopra",     "Social Studies",     ["7", "8"]),
    ("Ramesh Shastri",   "sis.ramesh.shastri",   "Sanskrit",           ["5", "6", "7", "8"]),
    # specialists, across both stages
    ("Arun Banerjee",    "sis.arun.banerjee",    "Computer Science",   ["1", "2", "3", "4"]),
    ("Farhan Khan",      "sis.farhan.khan",      "Computer Science",   ["5", "6", "7", "8"]),
    ("Sneha Kulkarni",   "sis.sneha.kulkarni",   "Art & Craft",        ["1", "2", "3", "4"]),
    ("Mohan Das",        "sis.mohan.das",        "Physical Education", ["1", "2", "3", "4"]),
    ("Imran Sheikh",     "sis.imran.sheikh",     "Physical Education", ["5", "6", "7", "8"]),
]

# ── calendar (type, title, start, end, blocks_periods or None) ───────────────
# blocks_periods = the periods an event eats. None = the whole day. A morning
# exam is a PARTIAL day: the school still teaches, just fewer periods.
CALENDAR: list[tuple[str, str, date, date, list[int] | None]] = [
    ("holiday",     "Muharram",                    date(2026, 6, 26), date(2026, 6, 26), None),
    ("holiday",     "Bonalu (local holiday)",      date(2026, 7, 13), date(2026, 7, 13), None),
    ("exam_block",  "Unit Test 1",                 date(2026, 8, 24), date(2026, 8, 28), [1, 2, 3]),
    ("holiday",     "Independence Day",            date(2026, 8, 15), date(2026, 8, 15), None),
    ("celebration", "Teachers' Day",               date(2026, 9, 5),  date(2026, 9, 5),  None),
    ("holiday",     "Ganesh Chaturthi",            date(2026, 9, 14), date(2026, 9, 14), None),
    ("holiday",     "Gandhi Jayanti",              date(2026, 10, 2), date(2026, 10, 2), None),
    ("exam_block",  "Half-Yearly Examinations",    date(2026, 10, 6), date(2026, 10, 15), None),
    ("holiday",     "Dussehra Break",              date(2026, 10, 19), date(2026, 10, 24), None),
    ("holiday",     "Diwali Break",                date(2026, 11, 7), date(2026, 11, 14), None),
    ("holiday",     "Guru Nanak Jayanti",          date(2026, 11, 24), date(2026, 11, 24), None),
    ("event",       "Annual Sports Day",           date(2026, 12, 11), date(2026, 12, 11), None),
    ("holiday",     "Christmas & New Year Break",  date(2026, 12, 24), date(2027, 1, 1), None),
    ("exam_block",  "Unit Test 2",                 date(2027, 1, 4),  date(2027, 1, 8), [1, 2, 3]),
    ("holiday",     "Sankranti Break",             date(2027, 1, 14), date(2027, 1, 16), None),
    ("holiday",     "Republic Day",                date(2027, 1, 26), date(2027, 1, 26), None),
    ("celebration", "Annual Day",                  date(2027, 2, 5),  date(2027, 2, 5), None),
    ("holiday",     "Holi",                        date(2027, 3, 3),  date(2027, 3, 4), None),
    ("exam_block",  "Annual Examinations",         date(2027, 3, 15), date(2027, 3, 27), None),
]

# ── fees (class band, category, total, installments) ─────────────────────────
FEES: list[tuple[list[str], str, int, int]] = [
    (["1", "2"],       "Day Scholar", 42000, 3),
    (["1", "2"],       "Hosteller",  108000, 3),
    (["3", "4"],       "Day Scholar", 46000, 3),
    (["3", "4"],       "Hosteller",  112000, 3),
    (["5", "6"],       "Day Scholar", 52000, 3),
    (["5", "6"],       "Hosteller",  120000, 3),
    (["7", "8"],       "Day Scholar", 58000, 3),
    (["7", "8"],       "Hosteller",  128000, 3),
]

# ── hostel blocks (name, kind, days, start, end, classes, hostellers_only, warden)
HOSTEL: list[tuple[str, str, str, str, str, str, str, str]] = [
    ("Morning Study",  "study",    "Mon-Sat", "06:00", "07:00", "5, 6, 7, 8",
     "yes", "Ramesh Shastri"),
    ("Homework Hour",  "homework", "Mon-Fri", "17:30", "18:30", "5, 6, 7, 8",
     "yes", "Farhan Khan"),
    ("Evening Prep (juniors)", "study", "Mon-Sat", "19:00", "20:00", "1, 2, 3, 4",
     "yes", "Shalini Rao"),
    ("Evening Prep (seniors)", "study", "Mon-Sat", "19:00", "20:30", "5, 6, 7, 8",
     "yes", "Vikram Singh"),
    ("Saturday Yoga",  "activity", "Sat",     "06:30", "07:30", "1, 2, 3, 4, 5, 6, 7, 8",
     "yes", "Imran Sheikh"),
    ("Sunday Games",   "activity", "Sun",     "16:30", "18:00", "1, 2, 3, 4, 5, 6, 7, 8",
     "yes", "Mohan Das"),
]

# ── student name banks ───────────────────────────────────────────────────────
BOY_NAMES = [
    "Aarav", "Vihaan", "Kabir", "Reyansh", "Advait", "Arjun", "Vivaan", "Aditya",
    "Rohan", "Krishna", "Dhruv", "Ayaan", "Ishaan", "Kartik", "Yuvan", "Neel",
    "Shaurya", "Atharv", "Rudra", "Veer", "Aryan", "Nikhil", "Siddharth", "Rehan",
    "Aniruddh", "Harsh", "Tanish", "Devansh", "Yash", "Om", "Pranav", "Sarthak",
]
GIRL_NAMES = [
    "Diya", "Ananya", "Ishita", "Sara", "Myra", "Kiara", "Anika", "Navya",
    "Aisha", "Meera", "Riya", "Tara", "Pari", "Saanvi", "Avni", "Zara",
    "Prisha", "Kavya", "Anaya", "Nitara", "Aadhya", "Ira", "Trisha", "Nishka",
    "Vanya", "Shreya", "Mahika", "Aarohi", "Rithika", "Samaira", "Nyra", "Larisa",
]
SURNAMES = [
    "Sharma", "Patel", "Reddy", "Iyer", "Khan", "Das", "Gupta", "Nair", "Mehta",
    "Roy", "Verma", "Kumar", "Joshi", "Rao", "Menon", "Bose", "Chopra", "Pillai",
    "Sinha", "Kulkarni", "Desai", "Bhat", "Naidu", "Malhotra", "Banerjee", "Shetty",
    "Agarwal", "Chauhan", "Tiwari", "Mishra", "Saxena", "Prasad", "Ahuja", "Bhalla",
]
FATHER_NAMES = [
    "Rajiv", "Sanjay", "Amit", "Vinod", "Ashok", "Girish", "Naveen", "Sudhir",
    "Mahesh", "Rakesh", "Pankaj", "Vijay", "Sameer", "Alok", "Dinesh", "Harish",
]
MOTHER_NAMES = [
    "Sunita", "Rekha", "Nisha", "Poonam", "Swati", "Vandana", "Archana", "Bharti",
    "Madhuri", "Seema", "Kalpana", "Jyoti", "Neelam", "Suman", "Aparna", "Ritu",
]

# Hosteller share climbs with the grade — juniors mostly go home.
HOSTELLER_SHARE = {"1": 0.10, "2": 0.10, "3": 0.20, "4": 0.20,
                   "5": 0.35, "6": 0.35, "7": 0.45, "8": 0.45}


# ═════════════════════════════════════════════════════════════════════════════
# derived
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Teacher:
    name: str
    username: str
    email: str
    mobile: str
    subject: str
    classes: list[str]
    assignments: list[tuple[str, str, int]] = field(default_factory=list)

    @property
    def load(self) -> int:
        return sum(p for _, _, p in self.assignments)


def slug(text: str) -> str:
    """'Social Studies' -> 'social_studies'; ASCII-only so filenames travel."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "_".join(part for part in
                    "".join(ch if ch.isalnum() else " " for ch in norm.lower()).split())


def build_teachers() -> list[Teacher]:
    out: list[Teacher] = []
    for i, (name, username, subject, classes) in enumerate(STAFF):
        email = f"{slug(name).replace('_', '.')}@sunriseintl.edu.in"
        t = Teacher(name, username, email, f"98{49000000 + i * 111:08d}"[:10],
                    subject, classes)
        for cname in classes:
            ppw = PERIODS[cname].get(subject)
            if ppw is None:
                raise ValueError(f"{name}: class {cname} does not run {subject}")
            t.assignments.append((cname, subject, ppw))
        out.append(t)
    return out


def check_invariants(teachers: list[Teacher]) -> None:
    for cname, split in PERIODS.items():
        total = sum(split.values())
        if total != CAPACITY:                                            # I1
            raise ValueError(f"class {cname} allocates {total}, not {CAPACITY}")
        for subject in split:
            if subject not in SUBJECTS:
                raise ValueError(f"class {cname}: {subject!r} is not in SUBJECTS")

    covered: dict[tuple[str, str], str] = {}
    for t in teachers:
        if t.load > LOAD_CEILING:                                        # I2
            raise ValueError(f"{t.name} carries {t.load} > {LOAD_CEILING}")
        for cname, subject, _ in t.assignments:
            key = (cname, subject)
            if key in covered:
                raise ValueError(f"{cname} {subject} taught by both "
                                 f"{covered[key]} and {t.name}")
            covered[key] = t.name
    for cname, split in PERIODS.items():
        for subject in split:
            if (cname, subject) not in covered:
                raise ValueError(f"{cname} {subject} has no teacher")

    for cname, split in PERIODS.items():
        for subject in split:
            if int(cname) not in CHAPTERS[subject]:                      # content
                raise ValueError(f"no chapters for grade {cname} {subject}")


# ── calendar arithmetic ──────────────────────────────────────────────────────

def _daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def blocked_map() -> dict[date, float]:
    """date -> fraction of the day the calendar removes (1.0 = whole day)."""
    out: dict[date, float] = {}
    for _type, _title, start, end, blocks in CALENDAR:
        share = 1.0 if blocks is None else len(blocks) / PERIODS_PER_DAY
        for d in _daterange(start, end):
            out[d] = max(out.get(d, 0.0), share)
    return out


def teaching_day_equivalents(start: date, end: date) -> float:
    """Working days in the window, net of what the calendar eats. Partial-day
    exams cost their periods, not the whole day — the same arithmetic the
    effective-days engine runs (`services/calendar.py`)."""
    blocked = blocked_map()
    total = 0.0
    for d in _daterange(start, end):
        if d.weekday() in WORKING_WEEKDAYS:
            total += 1.0 - blocked.get(d, 0.0)
    return total


TRACKED_DAYS = teaching_day_equivalents(TRACKING_START, YEAR_END)
TRACKED_WEEKS = TRACKED_DAYS / len(WORKING_WEEKDAYS)


def available_periods(ppw: int) -> float:
    """Periods this subject actually gets between going live and the year's end."""
    return ppw * TRACKED_WEEKS


# ── syllabus sizing (I3 + I4) ────────────────────────────────────────────────

def size_topics(target: int, n: int, lo: int = 2, hi: int = 8) -> list[int]:
    """Split `target` periods across `n` topics, evenly spread and exact.

    The remainder is handed out by index rather than to the first R topics, so
    the extra period lands across the year instead of bunching in chapter 1.
    """
    target = max(n * lo, min(target, n * hi))
    base, rem = divmod(target, n)
    return [base + (1 if (i * rem) // n != ((i + 1) * rem) // n else 0)
            for i in range(n)]


def topics_per_chapter(n_chapters: int, target: int, most: int, lo: int = 2) -> int:
    """How many topics a chapter can carry before they'd be worth <2 periods each.

    Class 7 Hindi has 19 chapters and 5 periods a week: four sub-topics per
    chapter would mean 76 topics sharing 98 periods, and the only way to write
    that down is to round every topic UP — inventing periods the year does not
    have (which is exactly how a fixture ends up 112% booked). Fewer, fatter
    topics are both honest and what the teacher actually logs.
    """
    for k in range(most, 0, -1):
        if n_chapters * k * lo <= target:
            return k
    return 1


def build_syllabus(cname: str, subject: str) -> list[tuple[str, list[tuple[str, int]]]]:
    chapters = CHAPTERS[subject][int(cname)]
    template = TOPIC_TEMPLATE[subject]

    target = round(available_periods(PERIODS[cname][subject]) * SYLLABUS_FILL)
    k = topics_per_chapter(len(chapters), target, len(template))
    total_topics = len(chapters) * k
    # Only when even one topic per chapter can't take 2 periods (it never does in
    # this pack) do we let a topic be a single period.
    lo = 2 if total_topics * 2 <= target else 1
    sizes = size_topics(target, total_topics, lo=lo)

    out: list[tuple[str, list[tuple[str, int]]]] = []
    cursor = 0
    for ci, chapter in enumerate(chapters):
        n = k
        block = sizes[cursor:cursor + n]
        cursor += n
        # Shape the chapter: opening period-block a little heavier than the last,
        # which is how a chapter actually runs. Sum is preserved.
        if n >= 2 and block[0] < 8 and block[-1] > lo and ci % 2 == 0:
            block[0] += 1
            block[-1] -= 1
        out.append((chapter, list(zip(template[:n], block, strict=True))))
    return out


# ── students ─────────────────────────────────────────────────────────────────

def build_students() -> list[list]:
    rng = random.Random(STUDENT_SEED)
    rows: list[list] = []
    adm = 0
    for cname in CLASSES:
        used: set[str] = set()
        hostellers = round(STUDENTS_PER_CLASS * HOSTELLER_SHARE[cname])
        flags = [True] * hostellers + [False] * (STUDENTS_PER_CLASS - hostellers)
        rng.shuffle(flags)
        for roll in range(1, STUDENTS_PER_CLASS + 1):
            while True:
                first = rng.choice(BOY_NAMES if rng.random() < 0.52 else GIRL_NAMES)
                last = rng.choice(SURNAMES)
                if f"{first} {last}" not in used:
                    used.add(f"{first} {last}")
                    break
            adm += 1
            rows.append([
                f"{first} {last}",
                f"SIS26{adm:04d}",
                str(roll),
                cname,
                None,  # Section — blank on purpose: one section per grade
                "Hosteller" if flags[roll - 1] else "Day Scholar",
                f"{rng.choice(FATHER_NAMES)} {last}",
                f"9{rng.randrange(100000000, 999999999)}",
                f"{rng.choice(MOTHER_NAMES)} {last}",
                f"8{rng.randrange(100000000, 999999999)}",
            ])
    return rows


# ═════════════════════════════════════════════════════════════════════════════
# writing
# ═════════════════════════════════════════════════════════════════════════════

def sheet(path: Path, header: list[str], rows: list[list]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def write_pack(teachers: list[Teacher], students: list[list],
               syllabus: dict[tuple[str, str], list]) -> int:
    sheet(DATA / "teachers_staff.xlsx",
          ["Teacher Name", "Username", "Email", "Mobile", "Assignments"],
          [[t.name, t.username, t.email, t.mobile,
            "; ".join(f"{c} {s} x{p}" for c, s, p in t.assignments)]
           for t in teachers])

    sheet(DATA / "students_roster.xlsx",
          ["Student Name", "Admission No", "Roll No", "Class", "Section", "Category",
           "Father's Name", "Father's Mobile", "Mother's Name", "Mother's Mobile"],
          students)

    files = 0
    for (cname, subject), chapters in syllabus.items():
        body: list[list] = []
        for chapter, topics in chapters:
            for i, (topic, periods) in enumerate(topics):
                # Chapter only on the first row — merged cells export as blanks and
                # the importer carries the previous value forward, so this is the
                # shape a real school's sheet has.
                body.append([chapter if i == 0 else None, topic, periods])
        sheet(DATA / "syllabus" / f"class_{cname}" /
              f"syllabus_{cname}_{slug(subject)}.xlsx",
              ["Chapter", "Topic", "Periods"], body)
        files += 1

    write_csv(DATA / "calendar_events.csv",
              ["Type", "Title", "Start", "End", "Blocks periods"],
              [[t, title, s.isoformat(), e.isoformat(),
                "whole day" if b is None else " ".join(map(str, b))]
               for t, title, s, e, b in sorted(CALENDAR, key=lambda r: r[2])])

    write_csv(DATA / "fee_structures.csv",
              ["Class", "Category", "Total amount", "Installments"],
              [[c, cat, amount, n] for band, cat, amount, n in FEES for c in band])

    write_csv(DATA / "hostel_sessions.csv",
              ["Block", "Kind", "Days", "Start", "End", "Classes",
               "Hostellers only", "Teacher"],
              [list(row) for row in HOSTEL])
    return files


def md_table(header: list[str], rows: list[list]) -> list[str]:
    return (["| " + " | ".join(header) + " |",
             "|" + "|".join(["---"] * len(header)) + "|"]
            + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def write_school_md(teachers: list[Teacher], students: list[list],
                    syllabus: dict[tuple[str, str], list]) -> None:
    hostellers = sum(1 for r in students if r[5] == "Hosteller")
    n_cs = len(syllabus)
    topics = sum(len(t) for ch in syllabus.values() for _, t in ch)
    units = sum(len(ch) for ch in syllabus.values())

    L: list[str] = [
        f"# {SCHOOL_NAME} — the school on paper",
        "",
        "Derived from `generate.py`; regenerate rather than editing by hand.",
        "This is the reference sheet — the click-by-click walkthrough is **SETUP.md**.",
        "",
        "## Identity",
        "",
        *md_table(["Field", "Value"], [
            ["School", SCHOOL_NAME],
            ["City", SCHOOL_CITY],
            ["Board", "CBSE"],
            ["Type", "Day school + boarding (hostel)"],
            ["Principal / admin", f"{ADMIN_NAME} · {ADMIN_EMAIL}"],
            ["Classes", "1 to 8, one section each"],
            ["Students", f"{len(students)} ({STUDENTS_PER_CLASS} per class) — "
                         f"{hostellers} hostellers, {len(students) - hostellers} day scholars"],
            ["Teaching staff", f"{len(teachers)}"],
            ["Subjects", f"{len(SUBJECTS)}"],
            ["Class-subjects", f"{n_cs} (= {n_cs} syllabus files, {n_cs} plans)"],
        ]),
        "",
        "## Academic year",
        "",
        *md_table(["Field", "Value"], [
            ["Label", YEAR_LABEL],
            ["First day", YEAR_START.isoformat()],
            ["Last day", YEAR_END.isoformat()],
            ["Tracking starts", f"{TRACKING_START.isoformat()} "
                                f"({TRACKING_START.strftime('%A')}) — mid-year adoption"],
            ["Working days", "Mon-Sat (the app's default; no UI, no change needed)"],
            ["Periods/day", str(PERIODS_PER_DAY)],
            ["Weekly capacity", f"{CAPACITY} periods per class"],
            ["Teaching days left after go-live",
             f"{TRACKED_DAYS:.1f} (~{TRACKED_WEEKS:.1f} weeks), net of holidays and exams"],
        ]),
        "",
        "> **Why mid-year.** The year opened on 1 June; the school buys the product in",
        "> late July. `tracking_start_date` tells the planner to ignore everything before",
        "> it — pre-adoption is *no data*, never a warning — so June and July do not show",
        "> up as two months of missing attendance. Every syllabus in this pack is sized",
        "> against the periods left **after** go-live, not the full year.",
        "",
        "## The school day",
        "",
        f"Start **{DAY_STARTS_AT}** · **{PERIODS_PER_DAY}** periods of "
        f"**{PERIOD_MINUTES} min** · lunch after period **{LUNCH_AFTER_PERIOD}** "
        f"for **{LUNCH_MINUTES} min**. The wizard builds the timings from exactly "
        "those five numbers:",
        "",
    ]

    cursor_h, cursor_m = (int(x) for x in DAY_STARTS_AT.split(":"))
    cursor = cursor_h * 60 + cursor_m
    day_rows = []
    for i in range(1, PERIODS_PER_DAY + 1):
        end = cursor + PERIOD_MINUTES
        day_rows.append([f"Period {i}", f"{cursor // 60:02d}:{cursor % 60:02d}",
                         f"{end // 60:02d}:{end % 60:02d}"])
        cursor = end
        if i == LUNCH_AFTER_PERIOD:
            lend = cursor + LUNCH_MINUTES
            day_rows.append(["Lunch", f"{cursor // 60:02d}:{cursor % 60:02d}",
                             f"{lend // 60:02d}:{lend % 60:02d}"])
            cursor = lend
    L += md_table(["Slot", "From", "To"], day_rows)

    L += [
        "",
        "## Subjects",
        "",
        "Add them in the wizard **spelled exactly like this** — the staff sheet's",
        "assignments resolve by name, and a mismatch lands in `unresolved`.",
        "",
        *md_table(["#", "Subject", "Runs in"], [
            [i + 1, s,
             ", ".join(c for c in CLASSES if s in PERIODS[c]) or "-"]
            for i, s in enumerate(SUBJECTS)
        ]),
        "",
        "## Weekly period split",
        "",
        f"Every row sums to **{CAPACITY}**, so each class panel reads "
        f"\"{CAPACITY} of {CAPACITY} periods/week allocated\".",
        "",
    ]
    L += md_table(["Class"] + SUBJECTS + ["Total"], [
        [f"**{c}**"] + [PERIODS[c].get(s, "-") for s in SUBJECTS]
        + [f"**{sum(PERIODS[c].values())}**"] for c in CLASSES
    ])

    L += [
        "",
        "## Teaching staff",
        "",
        f"{len(teachers)} teachers. The heaviest carries "
        f"**{max(t.load for t in teachers)}** of a possible {LOAD_CEILING} periods, so the",
        "timetable generator can always place everyone without a clash.",
        "",
        "Passwords are generated at import and shown **once** — copy them then.",
        "Usernames are pinned in the sheet (`sis.` prefix) because `users.username`",
        "is global across schools; without it the importer would quietly append a digit.",
        "",
        *md_table(["Teacher", "Username", "Subject", "Classes", "Periods/week"], [
            [t.name, f"`{t.username}`", t.subject, ", ".join(t.classes), t.load]
            for t in teachers
        ]),
        "",
        f"Total teaching load **{sum(t.load for t in teachers)}** = "
        f"{len(CLASSES)} classes x {CAPACITY} periods.",
        "",
        "## Syllabus",
        "",
        f"**{n_cs}** files — one per class-subject — holding **{units}** chapters and",
        f"**{topics}** topics, every one of them sized (I3). Chapter titles follow the",
        "NCERT books; topics are the three or four moves a teacher actually logs.",
        "",
        *md_table(["Class", "Files", "Chapters", "Topics", "Periods of content",
                   "Periods available", "Used"], [
            [c,
             sum(1 for (cn, _s) in syllabus if cn == c),
             sum(len(syllabus[(cn, s)]) for (cn, s) in syllabus if cn == c),
             sum(len(t) for (cn, s) in syllabus if cn == c
                 for _ch, t in syllabus[(cn, s)]),
             sum(p for (cn, s) in syllabus if cn == c
                 for _ch, tt in syllabus[(cn, s)] for _t, p in tt),
             round(sum(available_periods(PERIODS[c][s]) for s in PERIODS[c])),
             f"{SYLLABUS_FILL:.0%}"]
            for c in CLASSES
        ]),
        "",
        "## Calendar",
        "",
        "Typed in on wizard step 7 (paint the range, pick the kind). There is no",
        "calendar importer — `data/calendar_events.csv` is the list to copy from.",
        "",
        *md_table(["Kind", "Title", "From", "To", "Costs"], [
            [t, title, s.isoformat(), e.isoformat(),
             "whole day" if b is None else f"periods {', '.join(map(str, b))}"]
            for t, title, s, e, b in sorted(CALENDAR, key=lambda r: r[2])
        ]),
        "",
        "## Fee structures",
        "",
        "Office/admin only — teachers never see fees. Entered under **Fees > Structures**",
        "(one per class + category + year); `data/fee_structures.csv` is the same list.",
        "",
        *md_table(["Class", "Category", "Total (INR)", "Installments"], [
            [", ".join(band), cat, f"{amount:,}", n] for band, cat, amount, n in FEES
        ]),
        "",
        "## Hostel blocks",
        "",
        f"{hostellers} of {len(students)} students are hostellers. These blocks live",
        "under **Plan > Hostel**; the roster is computed from the linked classes, so a",
        "new admission joins with zero edits.",
        "",
        *md_table(["Block", "Kind", "Days", "From", "To", "Classes", "Warden"], [
            [n, k, d, s, e, c, w] for n, k, d, s, e, c, _h, w in HOSTEL
        ]),
        "",
    ]
    (HERE / "SCHOOL.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    teachers = build_teachers()
    check_invariants(teachers)
    students = build_students()
    syllabus = {(c, s): build_syllabus(c, s) for c in CLASSES for s in PERIODS[c]}

    if DATA.exists():
        shutil.rmtree(DATA)
    files = write_pack(teachers, students, syllabus)
    write_school_md(teachers, students, syllabus)

    # ASCII only: the founder's console is cp1252 and a stray arrow crashes the run.
    print(f"{SCHOOL_NAME} | {YEAR_LABEL} | live from {TRACKING_START}")
    print(f"  {len(CLASSES)} classes | {len(SUBJECTS)} subjects | "
          f"{len(syllabus)} class-subjects")
    print(f"  {len(teachers)} teachers (heaviest {max(t.load for t in teachers)}/"
          f"{LOAD_CEILING}) | {len(students)} students | "
          f"{CAPACITY} periods/week per class")
    print(f"  {TRACKED_DAYS:.1f} teaching days left after go-live "
          f"(~{TRACKED_WEEKS:.1f} weeks)")
    print(f"  wrote {files} syllabus files + roster + staff + 3 csv into {DATA}")
    print(f"  wrote {HERE / 'SCHOOL.md'}")


if __name__ == "__main__":
    main()
