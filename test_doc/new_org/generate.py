"""Generate a randomised, self-consistent setup pack for a FRESH organisation.

Run it from the api/ folder so the project venv is active:

    cd api && uv run python ../test_doc/new_org/generate.py
    cd api && uv run python ../test_doc/new_org/generate.py --seed 42   # reproducible

Every run invents a DIFFERENT school — name, grades, subjects, weekly period split,
teachers, students and syllabus chapters all change. What never changes is the set of
invariants that make the pack *valid*, because a fixture that imports at 99% teaches
you nothing:

  I1  Each class's subject periods sum EXACTLY to the weekly capacity
      (working_days x periods_per_day), so every class reads "N of N allocated".
  I2  Every class-subject has exactly one teacher, and no teacher's weekly load
      exceeds one human's week (minus headroom), so the timetable is solvable and
      no teacher is double-booked.
  I3  Every topic is sized (no blank Periods cell), so every plan can be approved
      and LOCKED — an unsized topic is refused by `approve`.
  I4  Each class-subject's syllabus fits comfortably inside the periods the year
      actually offers, so the exam-fit panel reads "perfect"/"spare time".

Output (written next to this script; stale files are cleared first):
  TrackBit-Setup-Pack-<school>.xlsx  -> Platform → the school → Setup → Upload
  README.md                          -> the walkthrough for THIS run's school

**One workbook, not twenty-two.** This used to emit a roster, a staff sheet and one
syllabus file per class-subject, because the old importers took them one at a time —
a four-class school produced twenty-two files and a twelve-class school would have
produced ninety-six. Setup is now a single pack the operator uploads, and its sheets
are generated against `app/services/setup_pack/specs.py`: School · Terms · Classes ·
Staff · Teaching Assignments · Syllabus · Students.

`--messy` adds rows built to fail, so the validator's blocker surfaces get exercised:
an unknown class, a subject nobody teaches, a duplicate admission number, two nameless
rows — plus one unsized chapter, which stays a NOTE, because a school that has planned
only half its year is still allowed to go live.
"""

from __future__ import annotations

import argparse
import random
import unicodedata
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).parent

# A teacher is one human with one week. Leave a little headroom below the class
# capacity so the timetable generator has room to place everyone without a clash.
LOAD_HEADROOM = 2
MIN_PERIODS_PER_SUBJECT = 4


# ─────────────────────────────────────────────────────────────────────────────
# Content banks — sampled from, never emitted whole, so two runs rarely match.
# ─────────────────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Diya", "Vihaan", "Ananya", "Kabir", "Ishita", "Reyansh", "Sara",
    "Advait", "Myra", "Arjun", "Kiara", "Vivaan", "Anika", "Aditya", "Navya",
    "Rohan", "Aisha", "Krishna", "Meera", "Dhruv", "Riya", "Ayaan", "Tara",
    "Ishaan", "Pari", "Kartik", "Saanvi", "Yuvan", "Avni", "Neel", "Zara",
    "Shaurya", "Prisha", "Atharv", "Kavya", "Rudra", "Anaya", "Veer", "Nitara",
]

LAST_NAMES = [
    "Sharma", "Patel", "Reddy", "Iyer", "Khan", "Das", "Gupta", "Nair", "Mehta",
    "Roy", "Verma", "Kumar", "Joshi", "Rao", "Menon", "Bose", "Chopra", "Pillai",
    "Sinha", "Kulkarni", "Desai", "Bhat", "Naidu", "Malhotra", "Banerjee", "Shetty",
]

TEACHER_FIRST = [
    "Anil", "Sunita", "Rajesh", "Priya", "Mohan", "Kavita", "Suresh", "Lakshmi",
    "Vikram", "Deepa", "Ramesh", "Anjali", "Prakash", "Rekha", "Sanjay", "Geeta",
    "Manoj", "Shalini", "Arun", "Nandini",
]

SCHOOL_NAMES = [
    "Greenfield Public School", "Sunrise Vidya Mandir", "Riverdale Academy",
    "Silver Oak High School", "Vidya Jyoti School", "Nalanda Public School",
    "Crescent Valley School", "Gurukul International", "Lotus Springs School",
    "Meridian Public School",
]

CATEGORIES = ["Day Scholar", "Hosteller"]


@dataclass(frozen=True)
class Chapter:
    """One chapter and its topics, tagged with the grades it suits."""

    title: str
    topics: tuple[str, ...]
    grades: tuple[int, ...]


def C(title: str, topics: list[str], lo: int, hi: int) -> Chapter:
    return Chapter(title, tuple(topics), tuple(range(lo, hi + 1)))


# Each subject holds more chapters than any one class will use, spanning grades
# 5-8, so sampling produces a genuinely different (but grade-appropriate) syllabus
# for every class on every run.
BANK: dict[str, list[Chapter]] = {
    "Mathematics": [
        C("Numbers Up To Crores", ["Reading large numbers", "Place value"], 5, 5),
        C("Addition and Subtraction", ["Column methods", "Word problems"], 5, 5),
        C("Multiplication and Division", ["Multiplying big numbers", "Long division"], 5, 6),
        C("Knowing Our Numbers", ["Comparing large numbers", "Estimation", "Roman numerals"], 6, 6),
        C("Whole Numbers", ["Number line", "Properties of operations"], 6, 6),
        C("Playing with Numbers", ["Factors and multiples", "Divisibility rules", "HCF and LCM"], 5, 6),
        C("Basic Geometrical Ideas", ["Points, lines and curves", "Polygons and circles"], 6, 7),
        C("Integers", ["Negative numbers", "Operations on integers"], 6, 7),
        C("Fractions", ["Types of fractions", "Operations on fractions"], 5, 7),
        C("Decimals", ["Place value in decimals", "Operations on decimals"], 5, 7),
        C("Data Handling", ["Pictographs and tally marks", "Bar graphs"], 5, 8),
        C("Mensuration", ["Perimeter", "Area"], 6, 8),
        C("Algebra", ["Variables", "Simple equations"], 6, 8),
        C("Ratio and Proportion", ["Ratio", "Unitary method"], 6, 8),
        C("Simple Equations", ["Setting up equations", "Solving equations"], 7, 8),
        C("Lines and Angles", ["Pairs of angles", "Parallel lines"], 7, 8),
        C("The Triangle and Its Properties", ["Medians and altitudes", "Angle sum property"], 7, 8),
        C("Comparing Quantities", ["Percentages", "Profit, loss and interest"], 7, 8),
        C("Rational Numbers", ["On the number line", "Operations"], 7, 8),
        C("Exponents and Powers", ["Laws of exponents", "Standard form"], 7, 8),
        C("Squares and Square Roots", ["Square numbers", "Finding square roots"], 8, 8),
        C("Linear Equations in One Variable", ["Solving equations", "Word problems"], 8, 8),
    ],
    "Science": [
        C("Super Senses", ["How animals sense", "Comparing senses"], 5, 5),
        C("Plants Around Us", ["Parts of a plant", "How seeds travel"], 5, 5),
        C("Water", ["Sources of water", "Saving water"], 5, 6),
        C("Food: Where Does It Come From?", ["Food sources", "Plant and animal products"], 6, 6),
        C("Components of Food", ["Nutrients", "Balanced diet", "Deficiency diseases"], 5, 6),
        C("Fibre to Fabric", ["Plant fibres", "Spinning and weaving"], 6, 7),
        C("Sorting Materials", ["Properties of materials", "Grouping"], 6, 6),
        C("Separation of Substances", ["Sieving and winnowing", "Filtration and evaporation"], 6, 7),
        C("Changes Around Us", ["Reversible changes", "Irreversible changes"], 5, 7),
        C("Getting to Know Plants", ["Parts of a plant", "Leaf, stem and root", "Flower"], 6, 6),
        C("Body Movements", ["Joints", "Skeleton", "Animal movement"], 6, 7),
        C("Living Organisms", ["Habitats", "Adaptation"], 6, 7),
        C("Light, Shadows and Reflections", ["Sources of light", "Shadows", "Reflection"], 6, 8),
        C("Electricity and Circuits", ["Cells and bulbs", "Conductors and insulators"], 6, 8),
        C("Nutrition in Plants", ["Photosynthesis", "Other modes of nutrition"], 7, 8),
        C("Nutrition in Animals", ["Digestion in humans", "Digestion in grass-eaters"], 7, 8),
        C("Heat", ["Hot and cold", "Transfer of heat"], 7, 8),
        C("Acids, Bases and Salts", ["Indicators", "Neutralisation"], 7, 8),
        C("Physical and Chemical Changes", ["Kinds of changes", "Rusting and crystallisation"], 7, 8),
        C("Winds, Storms and Cyclones", ["Air pressure", "Staying safe in storms"], 7, 7),
        C("Respiration in Organisms", ["Why we breathe", "Breathing in animals"], 7, 8),
        C("Soil", ["Soil profile", "Soil and crops"], 7, 8),
        C("Force and Pressure", ["Kinds of forces", "Pressure in liquids"], 8, 8),
        C("Sound", ["How sound travels", "Noise and music"], 8, 8),
    ],
    "English": [
        C("Prose: Wonderful Waste", ["Reading and comprehension", "New words"], 5, 5),
        C("Poetry: Ice-cream Man", ["Recitation", "Rhyme and rhythm"], 5, 5),
        C("Prose: Flying Together", ["Reading and comprehension", "Story discussion"], 5, 6),
        C("Prose: A Tale of Two Birds", ["Reading and comprehension", "Vocabulary"], 6, 6),
        C("Prose: The Friendly Mongoose", ["Reading and comprehension", "Character discussion"], 6, 6),
        C("Poetry: A House, A Home", ["Recitation and meaning", "Appreciation"], 5, 6),
        C("Grammar: Nouns and Pronouns", ["Kinds of nouns", "Pronoun usage"], 5, 7),
        C("Grammar: Verbs and Tenses", ["Simple tenses", "Subject-verb agreement"], 5, 8),
        C("Grammar: Adjectives and Adverbs", ["Degrees of comparison", "Adverb placement"], 6, 8),
        C("Writing: Paragraphs", ["Structure of a paragraph", "Guided writing"], 5, 7),
        C("Writing: Letters", ["Informal letters", "Formal letters"], 6, 8),
        C("Prose: The Shepherd's Treasure", ["Reading and comprehension", "Retelling"], 6, 7),
        C("Poetry: The Kite", ["Recitation and meaning", "Imagery"], 6, 7),
        C("Prose: Three Questions", ["Reading and comprehension", "Theme discussion"], 7, 8),
        C("Prose: A Gift of Chappals", ["Reading and comprehension", "Character study"], 7, 7),
        C("Grammar: Determiners and Modals", ["Using determiners", "Modal verbs"], 7, 8),
        C("Grammar: Active and Passive Voice", ["Forming the passive", "Practice"], 7, 8),
        C("Grammar: Reported Speech", ["Statements", "Questions and commands"], 7, 8),
        C("Writing: Notice and Message", ["Notice writing", "Message writing"], 7, 8),
        C("Poetry: The Squirrel", ["Recitation and meaning", "Poetic devices"], 7, 7),
        C("Prose: The Best Christmas Present", ["Reading and comprehension", "Discussion"], 8, 8),
        C("Writing: Diary Entry", ["Format and tone", "Practice"], 8, 8),
    ],
    "Social Studies": [
        C("Maps and Globes", ["Reading a map", "Directions and symbols"], 5, 6),
        C("Our Country India", ["States and capitals", "Physical features"], 5, 6),
        C("Weather and Climate", ["Seasons of India", "Weather around us"], 5, 6),
        C("Natural Resources", ["Land and soil", "Forests and wildlife"], 5, 7),
        C("Transport and Communication", ["Means of transport", "Staying in touch"], 5, 6),
        C("History: What, Where, How and When", ["Sources of history", "Timelines"], 6, 6),
        C("History: Earliest Societies", ["Hunter-gatherers", "Tools and cave art"], 6, 6),
        C("Geography: The Earth in the Solar System", ["Planets and satellites", "The moon"], 6, 6),
        C("Geography: Globe - Latitudes and Longitudes", ["The grid", "Heat zones"], 6, 7),
        C("Civics: Understanding Diversity", ["Diversity around us", "Unity in diversity"], 6, 7),
        C("History: First Farmers and Herders", ["Beginnings of agriculture", "Settled life"], 6, 6),
        C("Geography: Motions of the Earth", ["Rotation and revolution", "Seasons"], 6, 7),
        C("Civics: Government", ["Levels of government", "Democratic government"], 6, 7),
        C("Geography: Maps", ["Kinds of maps", "Map reading"], 6, 7),
        C("History: Tracing Changes Through a Thousand Years", ["New maps and sources", "Time and periods"], 7, 8),
        C("History: New Kings and Kingdoms", ["Emergence of dynasties", "Warfare and forts"], 7, 7),
        C("Geography: Environment", ["Components of environment", "Human environment"], 7, 8),
        C("Geography: Inside Our Earth", ["Layers of the earth", "Rocks and minerals"], 7, 7),
        C("Civics: On Equality", ["Equal right to vote", "Struggles for equality"], 7, 8),
        C("History: The Delhi Sultans", ["Rulers of Delhi", "Administration"], 7, 8),
        C("History: The Mughal Empire", ["Mughal rulers", "Mansabdars and jagirs"], 7, 8),
        C("Geography: Our Changing Earth", ["Earth movements", "Work of rivers and wind"], 7, 8),
        C("Civics: How the State Government Works", ["MLAs and assemblies", "The executive"], 7, 8),
        C("The Environment", ["Pollution", "Protecting nature"], 5, 8),
    ],
    "Hindi": [
        C("Raakh Ki Rassi", ["Kahani vachan", "Prashn uttar"], 5, 5),
        C("Fasalon Ke Tyohar", ["Path vachan", "Charcha"], 5, 5),
        C("Khilonewala", ["Kavita vachan", "Bhavarth"], 5, 6),
        C("Vah Chidiya Jo", ["Kavita vachan", "Bhavarth"], 6, 6),
        C("Bachpan", ["Path vachan", "Prashn uttar"], 6, 6),
        C("Nadaan Dost", ["Path vachan", "Charcha"], 6, 7),
        C("Chaand Se Thodi Si Gappe", ["Kavita vachan", "Bhavarth"], 6, 7),
        C("Saathi Haath Badhana", ["Geet vachan", "Charcha"], 6, 7),
        C("Vyakaran: Varn aur Shabd", ["Varnamala", "Shabd rachna"], 5, 6),
        C("Vyakaran: Sangya aur Sarvanam", ["Sangya ke bhed", "Sarvanam prayog"], 5, 7),
        C("Vyakaran: Kriya aur Visheshan", ["Kriya ke bhed", "Visheshan prayog"], 6, 8),
        C("Vyakaran: Ling aur Vachan", ["Ling badlo", "Vachan badlo"], 5, 7),
        C("Vyakaran: Sandhi Parichay", ["Swar sandhi", "Abhyas"], 7, 8),
        C("Vyakaran: Muhavare", ["Muhavare arth sahit", "Vakya prayog"], 7, 8),
        C("Lekhan: Anuchchhed", ["Anuchchhed lekhan", "Abhyas"], 5, 7),
        C("Lekhan: Patra", ["Anaupcharik patra", "Aupcharik patra"], 6, 8),
        C("Lekhan: Nibandh", ["Rooprekha banana", "Nibandh lekhan"], 7, 8),
        C("Lekhan: Samvad", ["Samvad lekhan", "Abhyas"], 7, 8),
        C("Hum Panchhi Unmukt Gagan Ke", ["Kavita vachan", "Bhavarth"], 7, 7),
        C("Dadi Maa", ["Kahani vachan", "Prashn uttar"], 7, 7),
        C("Mithaiwala", ["Kahani vachan", "Prashn uttar"], 7, 8),
        C("Kathputli", ["Kavita vachan", "Bhavarth"], 7, 8),
    ],
    "IT": [
        C("Meet the Computer", ["Parts of a computer", "Dos and don'ts"], 5, 5),
        C("Working with the Mouse and Keyboard", ["Mouse skills", "Typing letters"], 5, 5),
        C("Fun with Paint", ["Drawing shapes", "Colouring pictures"], 5, 6),
        C("Storing Our Work", ["Files and folders", "Saving and opening"], 5, 6),
        C("Introduction to Computers", ["Parts of a computer", "Uses of computers"], 6, 6),
        C("Operating the Computer", ["Desktop and files", "Keyboard and mouse skills"], 6, 6),
        C("Word Processing Basics", ["Creating a document", "Formatting text"], 5, 7),
        C("Paint and Drawing Tools", ["Drawing shapes", "Editing pictures"], 6, 6),
        C("Introduction to the Internet", ["What is the internet", "Safe browsing"], 5, 8),
        C("Spreadsheets Basics", ["Rows, columns and cells", "Simple formulas"], 6, 7),
        C("Presentations", ["Creating slides", "Presenting ideas"], 6, 8),
        C("Typing Practice", ["Home row practice", "Speed building"], 5, 7),
        C("Being Safe Online", ["Passwords and privacy", "Cyber etiquette"], 5, 8),
        C("Advanced Word Processing", ["Tables and images", "Page layout"], 7, 8),
        C("Spreadsheets", ["Formulas and functions", "Sorting and filtering"], 7, 8),
        C("Charts and Graphs", ["Making charts", "Choosing the right chart"], 7, 8),
        C("Introduction to Coding", ["Block coding basics", "Making a small game"], 7, 8),
        C("Internet Research Skills", ["Finding reliable information", "Citing sources"], 7, 8),
        C("Email and Communication", ["Writing an email", "Netiquette"], 7, 8),
        C("Cyber Safety", ["Strong passwords", "Recognising scams"], 7, 8),
        C("Databases: First Look", ["What is a database", "Tables and records"], 8, 8),
    ],
}

CORE_SUBJECTS = ["Mathematics", "Science", "English"]
OPTIONAL_SUBJECTS = ["Social Studies", "Hindi", "IT"]


# ─────────────────────────────────────────────────────────────────────────────
# The school this run invents
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Assignment:
    class_name: str
    subject: str
    periods: int


@dataclass
class Teacher:
    name: str
    email: str
    mobile: str
    assignments: list[Assignment] = field(default_factory=list)

    @property
    def load(self) -> int:
        return sum(a.periods for a in self.assignments)

    @property
    def subjects(self) -> list[str]:
        return sorted({a.subject for a in self.assignments})


@dataclass
class School:
    name: str
    year_label: str
    year_start: date
    year_end: date
    term1_end: date
    working_days: int
    periods_per_day: int
    classes: list[str]
    subjects: list[str]
    # class -> subject -> periods/week
    periods: dict[str, dict[str, int]]
    teachers: list[Teacher]
    students: list[list]
    # (class, subject) -> [(chapter, [(topic, periods)], term)]
    syllabus: dict[tuple[str, str], list[tuple[str, list[tuple[str, int]], str]]]

    @property
    def capacity(self) -> int:
        """Periods in one class's week — and the most one teacher could ever take."""
        return self.working_days * self.periods_per_day

    @property
    def teaching_weeks(self) -> int:
        return max(1, ((self.year_end - self.year_start).days - 30) // 7)


def slug(text: str) -> str:
    """'Social Studies' -> 'social_studies'; strips accents so filenames stay ASCII."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return "".join(ch if ch.isalnum() else "_" for ch in norm.lower()).strip("_")


def split_periods(rng: random.Random, subjects: list[str], capacity: int) -> dict[str, int]:
    """Partition the week EXACTLY among the subjects (invariant I1).

    Everyone starts at the floor, then the remainder is handed out one period at a
    time with a bias toward Maths/Science/English — the shape a real timetable has.
    """
    alloc = {s: MIN_PERIODS_PER_SUBJECT for s in subjects}
    remaining = capacity - MIN_PERIODS_PER_SUBJECT * len(subjects)
    if remaining < 0:
        raise ValueError(
            f"{len(subjects)} subjects x {MIN_PERIODS_PER_SUBJECT} min periods "
            f"exceeds the {capacity}-period week. Use fewer subjects or more periods/day."
        )
    weights = [3 if s in CORE_SUBJECTS else 2 for s in subjects]
    for _ in range(remaining):
        alloc[rng.choices(subjects, weights=weights, k=1)[0]] += 1
    assert sum(alloc.values()) == capacity  # I1
    return alloc


def build_teachers(rng: random.Random, school_classes: list[str], subjects: list[str],
                   periods: dict[str, dict[str, int]], capacity: int) -> list[Teacher]:
    """Bin-pack every class-subject onto teachers (invariant I2).

    Walk subject by subject, filling one teacher until adding the next class would
    break their weekly ceiling, then open a new teacher. A subject that doesn't fill
    a teacher leaves room for the next subject to share them — which is exactly how
    the real two-subject teacher appears, without us forcing one.
    """
    ceiling = capacity - LOAD_HEADROOM
    names = rng.sample(TEACHER_FIRST, k=len(TEACHER_FIRST))
    surnames = rng.sample(LAST_NAMES, k=len(LAST_NAMES))
    teachers: list[Teacher] = []
    used_emails: set[str] = set()

    def new_teacher() -> Teacher:
        i = len(teachers)
        first, last = names[i % len(names)], surnames[i % len(surnames)]
        base = f"{slug(first)}.{slug(last)}"
        email, n = f"{base}@example.com", 1
        while email in used_emails:
            n += 1
            email = f"{base}{n}@example.com"
        used_emails.add(email)
        t = Teacher(f"{first} {last}", email, f"98111{10000 + i:05d}"[:10])
        teachers.append(t)
        return t

    current = new_teacher()
    # Shuffle subject order so which teacher ends up double-subject varies per run.
    for subject in rng.sample(subjects, k=len(subjects)):
        for cname in school_classes:
            ppw = periods[cname][subject]
            if current.load + ppw > ceiling:
                current = new_teacher()
            current.assignments.append(Assignment(cname, subject, ppw))

    for t in teachers:
        assert t.load <= ceiling, f"{t.name} over ceiling"  # I2
    return teachers


def build_students(rng: random.Random, school_classes: list[str]) -> list[list]:
    rows: list[list] = []
    adm = rng.randrange(1000, 9000)
    for cname in school_classes:
        for roll in range(1, rng.randint(8, 14) + 1):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            adm += 1
            rows.append([
                f"{first} {last}",
                f"NG{adm}",
                str(roll),
                cname,
                None,  # Section — blank on purpose: one section per grade
                rng.choices(CATEGORIES, weights=[7, 3], k=1)[0],
                f"Mr {last}", f"9{rng.randrange(100000000, 999999999)}",
                f"Mrs {last}", f"9{rng.randrange(100000000, 999999999)}",
            ])
    return rows


def build_syllabus(rng: random.Random, grade: int, subject: str, ppw: int,
                   teaching_weeks: int) -> list[tuple[str, list[tuple[str, int]], str]]:
    """Sample a grade-appropriate, fully-sized, term-split syllabus (I3 + I4)."""
    pool = [c for c in BANK[subject] if grade in c.grades]
    if not pool:  # a subject with no chapters for this grade would be a silent hole
        raise ValueError(f"content bank has no grade-{grade} chapters for {subject}")

    available = ppw * teaching_weeks  # periods the year actually offers this subject
    picked = rng.sample(pool, k=min(len(pool), rng.randint(8, 11)))

    chapters: list[tuple[str, list[tuple[str, int]], str]] = []
    total = 0
    # Term 1 takes a little over half the chapters — the usual shape.
    split_at = max(1, round(len(picked) * rng.uniform(0.5, 0.6)))
    for i, ch in enumerate(picked):
        topics = [(t, rng.randint(2, 5)) for t in ch.topics]  # I3: always sized
        cost = sum(p for _, p in topics)
        # I4: stop before the syllabus outgrows the year (keep it under ~45% so the
        # exam-fit panel has real slack to show).
        if total + cost > available * 0.45 and chapters:
            break
        chapters.append((ch.title, topics, "Term 1" if i < split_at else "Term 2"))
        total += cost

    # A term with no chapters at all would make the term-scoped planner look broken.
    if not any(term == "Term 2" for _, _, term in chapters):
        title, topics, _ = chapters[-1]
        chapters[-1] = (title, topics, "Term 2")
    return chapters


def invent_school(rng: random.Random) -> School:
    periods_per_day = rng.choice([7, 8])
    working_days = rng.choice([5, 6])
    capacity = working_days * periods_per_day

    subjects = CORE_SUBJECTS + rng.sample(OPTIONAL_SUBJECTS, k=rng.randint(2, 3))
    # Guard the partition before we build anything on top of it.
    while MIN_PERIODS_PER_SUBJECT * len(subjects) > capacity:
        subjects.pop()

    lowest = rng.randint(5, 6)
    classes = [str(g) for g in range(lowest, lowest + rng.randint(3, 4))]
    classes = [c for c in classes if int(c) <= 8]  # the content bank stops at grade 8

    start_year = rng.randint(2026, 2028)
    year_start = date(start_year, rng.choice([4, 6]), rng.choice([1, 10, 15]))
    year_end = date(start_year + 1, 4, rng.choice([10, 15, 20]))
    term1_end = year_start + timedelta(days=(year_end - year_start).days // 2)

    school = School(
        name=rng.choice(SCHOOL_NAMES),
        year_label=f"{start_year}-{str(start_year + 1)[2:]}",
        year_start=year_start,
        year_end=year_end,
        term1_end=term1_end,
        working_days=working_days,
        periods_per_day=periods_per_day,
        classes=classes,
        subjects=subjects,
        periods={c: split_periods(rng, subjects, capacity) for c in classes},
        teachers=[],
        students=[],
        syllabus={},
    )
    school.teachers = build_teachers(rng, classes, subjects, school.periods, capacity)
    school.students = build_students(rng, classes)
    school.syllabus = {
        (c, s): build_syllabus(rng, int(c), s, school.periods[c][s], school.teaching_weeks)
        for c in classes for s in subjects
    }
    return school


# ─────────────────────────────────────────────────────────────────────────────
# Writing
# ─────────────────────────────────────────────────────────────────────────────

def _dmy(d: date) -> str:
    """Day-first, the way the pack and every Indian register write it."""
    return d.strftime("%d/%m/%Y")


def _dob_for(rng: random.Random, class_name: str) -> str:
    """A plausible birthday for a child in this class.

    The old generator had no date-of-birth column at all, so every school it
    produced handed over with "N parents cannot log in" — the readiness report's
    loudest warning, on synthetic data, every run. A date of birth is the
    parent's portal password, so a pack without one cannot exercise the portal.
    """
    grade = int("".join(ch for ch in class_name if ch.isdigit()) or 6)
    born = date(2026 - (grade + 5), rng.randint(1, 12), rng.randint(1, 28))
    return _dmy(born)


def clear_stale() -> None:
    """The class/subject set changes every run — old files would linger and mislead.

    A pack open in Excel cannot be deleted on Windows, and that is the normal
    case: you look at last run's pack, then generate the next one. Losing the
    whole run to a file lock is a worse outcome than one stale file, so say which
    ones survived and carry on.
    """
    locked: list[str] = []
    for f in HERE.glob("*.xlsx"):
        try:
            f.unlink()
        except PermissionError:
            locked.append(f.name)
    try:
        (HERE / "SETUP.md").unlink(missing_ok=True)
    except PermissionError:
        locked.append("SETUP.md")
    if locked:
        print("  ! still open elsewhere, not replaced: " + ", ".join(locked))
        print("    close them in Excel if you want them cleared.")


def _class_teachers(school: School) -> dict[str, str]:
    """One teacher per class — whoever takes the most periods there. A class with
    no class teacher has no owner for its absence follow-ups, which the readiness
    report calls out, so the generated school should not have that hole."""
    best: dict[str, tuple[int, str]] = {}
    for teacher in school.teachers:
        for a in teacher.assignments:
            if a.periods > best.get(a.class_name, (0, ""))[0]:
                best[a.class_name] = (a.periods, teacher.name)
    return {cname: name for cname, (_p, name) in best.items()}


def write_pack(school: School, messy: bool = False) -> None:
    """One workbook, the shape `app/services/setup_pack/specs.py` defines.

    This used to write twenty-two files — a roster, a staff sheet and one
    syllabus file per class-subject — because that is what the old importers
    took, one at a time. A twelve-class school would have produced ninety-six.
    """
    rng = random.Random(school.name)
    homerooms = _class_teachers(school)
    weeks = {"5": "Mon-Fri", "6": "Mon-Sat", "7": "Mon-Sun"}

    wb = Workbook()
    wb.remove(wb.active)

    def add(title: str, header: list[str], rows: list[list]) -> None:
        ws = wb.create_sheet(title)
        ws.append(header)
        for r in rows:
            ws.append(r)
        print(f"  {title}: {len(rows)} rows")

    add("School", ["Field", "Value"], [
        ["School name", school.name],
        ["Academic year", school.year_label],
        ["Year starts", _dmy(school.year_start)],
        ["Year ends", _dmy(school.year_end)],
        ["Working days", weeks.get(str(school.working_days), "Mon-Sat")],
        ["Periods per day", school.periods_per_day],
        ["First period starts", "08:30"],
        ["Period length (minutes)", 40],
        ["Lunch after period", max(1, school.periods_per_day // 2)],
        ["Lunch length (minutes)", 30],
        ["Parent portal", "Yes"],
    ])

    # A term IS its exam: give the exam window and the term is the teaching that
    # leads up to it. Term 1 ends when the half-yearly ends; Term 2 with the annual.
    add("Terms", ["Term", "Exam", "Exam starts", "Exam ends"], [
        ["Term 1", "Half-yearly",
         _dmy(school.term1_end - timedelta(days=5)), _dmy(school.term1_end)],
        ["Term 2", "Annual",
         _dmy(school.year_end - timedelta(days=5)), _dmy(school.year_end)],
    ])

    add("Classes", ["Class", "Section", "Class teacher"],
        [[cname, "", homerooms.get(cname, "")] for cname in school.classes])

    staff = [[t.name, "", t.email, t.mobile, "", "Teacher"] for t in school.teachers]
    # TT-3: no periods column. The weekly load is COUNTED off the Timetable
    # sheet below (`services/period_load.py` does the same at import), so
    # emitting it here would be emitting a number the importer ignores — and
    # the invariant "periods sum to weekly capacity" is now enforced by the
    # grid this generator lays down, not by a column beside it.
    assignments = [
        [a.class_name, "", a.subject, t.name]
        for t in school.teachers for a in t.assignments
    ]

    # One row per CHAPTER (founder, 2026-08-08). The sheet carries chapter and
    # est. periods and nothing else, so a chapter's estimate is the sum of the
    # work inside it rather than a row per topic.
    syllabus: list[list] = []
    for (cname, subject), chapters in school.syllabus.items():
        for n, (ch, topics, term) in enumerate(chapters, start=1):
            syllabus.append([cname, "", subject, term, n, ch,
                             sum(p for _t, p in topics)])

    students = [
        [r[0], r[1], r[2], r[3], r[4] or "", _dob_for(rng, str(r[3])),
         r[5], r[6], r[7], r[8], r[9]]
        for r in school.students
    ]

    if messy:
        # Rows engineered to FAIL, so the validator's blocker surfaces get
        # exercised. Never present in the default (clean) pack.
        first_class = school.classes[0]
        assignments.append(["99", "", "Astrophysics", "Nobody At All", 5])
        staff.append(["", "", "no.name@example.com", "9899900002", "", "Teacher"])
        syllabus.append([first_class, "", "Astrophysics", "Term 1", 1,
                         "Chapter nobody teaches", "", 3])
        # A blank Periods cell means "not sized yet" — a NOTE, never a blocker.
        syllabus.append([first_class, "", school.subjects[0], "Term 2", 99,
                         "Unsized Chapter", "", None])
        dupe = students[0][1]
        students.append(["Duplicate Admission", dupe, "99", first_class, "",
                         "01/01/2015", "Day Scholar", "Mr X", "9800000001",
                         "Mrs X", "9800000002"])
        students.append(["", "NG_NO_NAME", "98", first_class, "", "01/01/2015",
                         "Day Scholar", "Mr Y", "9800000003", "Mrs Y", "9800000004"])
        students.append(["No Admission No", "", "97", first_class, "", "01/01/2015",
                         "Day Scholar", "Mr Z", "9800000005", "Mrs Z", "9800000006"])

    add("Staff", ["Name", "Employee ID", "Email", "Phone", "Date of birth", "Role"],
        staff)
    add("Teaching Assignments",
        ["Class", "Section", "Subject", "Teacher"], assignments)
    add("Syllabus",
        ["Class", "Section", "Subject", "Term", "Ch #", "Chapter",
         "Est. periods"], syllabus)
    add("Students",
        ["Student name", "Admission no", "Roll no", "Class", "Section",
         "Date of birth", "Category", "Father name", "Father phone",
         "Mother name", "Mother phone"], students)

    # Four instalments a year, due one per quarter. The due DATE is the whole
    # point: `core/collection.py` buckets a quarter by due-date window, not by
    # instalment number — juniors paying in 2 and seniors in 4 would otherwise
    # make "instalment 1" a different quarter per class. A pack with structures
    # but no dated instalments leaves the admin's fee screen empty.
    fees: list[list] = []
    span = (school.year_end - school.year_start).days
    for cname in school.classes:
        grade = int("".join(ch for ch in cname if ch.isdigit()) or 6)
        total = 24000 + (grade - 5) * 3000
        share = total // 4
        for n in range(4):
            due = school.year_start + timedelta(days=int(span * n / 4) + 14)
            fees.append([cname, "", total, n + 1, f"Quarter {n + 1}",
                         _dmy(due), share])
    add("Fees",
        ["Class", "Category", "Total amount", "Installment no",
         "Installment name", "Due date", "Amount"], fees)

    name = f"TrackBit-Setup-Pack-{slug(school.name)}.xlsx"
    wb.save(HERE / name)
    print(f"  wrote {name}")


def write_readme(school: School, seed: int) -> None:
    cap = school.capacity
    days = "Mon-Sat" if school.working_days == 6 else "Mon-Fri"
    n_cs = len(school.classes) * len(school.subjects)
    multi = [t for t in school.teachers if len(t.subjects) > 1]
    busiest = max(school.teachers, key=lambda t: t.load)

    pack_name = f"TrackBit-Setup-Pack-{slug(school.name)}.xlsx"
    lines = [
        f"# Setup pack - {school.name}",
        "",
        f"Generated by `generate.py` with **seed {seed}**. Every run invents a different",
        "school; rerun to get a fresh one, or reproduce this exact pack with:",
        "",
        "```bash",
        f"cd api && uv run python ../test_doc/new_org/generate.py --seed {seed}",
        "```",
        "",
        "Every row here is valid — the review should read **ready to import** with no",
        f"blockers, and all **{n_cs} plans** should lock afterwards.",
        "",
        "> Want to test the *failure* surfaces instead? Add `--messy` to inject rows built",
        "> (see 'Upload the pack' below for exactly what the review then reports).",
        "> to break: an unresolvable class-subject, a duplicate admission no, a row with no",
        "> name, and an unsized topic. Imports will then report errors / skipped /",
        "> unresolved, and `approve` will refuse to lock the unsized chapter.",
        "",
        "## The school this pack describes",
        "",
        f"- **Academic year** {school.year_label} — {school.year_start} to {school.year_end}",
        f"- **Terms** — Term 1: {school.year_start} to {school.term1_end} · "
        f"Term 2: {school.term1_end + timedelta(days=1)} to {school.year_end}",
        f"- **Working days** {days}, **{school.periods_per_day} periods/day** "
        f"→ **{cap} periods/week** per class",
        f"- **Classes** — {' · '.join(school.classes)} (leave Section blank everywhere)",
        f"- **Subjects** — {', '.join(school.subjects)}",
        f"- **Teachers** — {len(school.teachers)}"
        + (f" ({multi[0].name} carries {len(multi[0].subjects)} subjects)" if multi else ""),
        f"- **Students** — {len(school.students)} across {len(school.classes)} classes",
        f"- Every class's week is exactly full: **{cap} of {cap} periods allocated**",
        "",
        "### Weekly period split",
        "",
        "| Class | " + " | ".join(school.subjects) + " | Total |",
        "|---|" + "---|" * (len(school.subjects) + 1),
    ]
    for c in school.classes:
        row = [str(school.periods[c][s]) for s in school.subjects]
        lines.append(f"| **{c}** | " + " | ".join(row) + f" | **{cap}** |")

    lines += [
        "",
        "### Teacher loads",
        "",
        "| Teacher | Subjects | Periods/week |",
        "|---|---|---|",
    ]
    for t in school.teachers:
        lines.append(f"| {t.name} | {', '.join(t.subjects)} | {t.load} |")

    lines += [
        "",
        f"No teacher exceeds {cap - LOAD_HEADROOM} periods (one human's week, minus",
        f"headroom), so the timetable is solvable with nobody double-booked. "
        f"{busiest.name} carries the tightest load at {busiest.load}.",
        "",
        "---",
        "",
        "## Step-by-step",
        "",
        "Setup is one workbook now, and only the operator runs it",
        "(`SETUP-REDESIGN-PLAN`). The ten-step wizard is gone.",
        "",
        "### 1. Create the school",
        "**Platform → New school**. Name it whatever you like — the pack overwrites",
        f"the name with **{school.name}** on import.",
        "",
        "### 2. Open its setup screen",
        "**Platform → the school’s card → Setup**.",
        "",
        "### 3. Upload the pack",
        f"Choose **`{pack_name}`**. The review runs immediately and writes nothing.",
        "",
        "Expect **ready to import**, with these notes and no blockers:",
        f"- {len(school.students)} students, {n_cs} class-subjects, every chapter sized",
        "  (invariant I3), so nothing reads *not sized yet*;",
        f"- every class allocated **{cap} of {cap} periods a week** (I1), so no",
        "  over-capacity warning;",
        f"- no teacher past {cap - LOAD_HEADROOM} periods (I2), so nobody is overloaded.",
        "",
        "Run it again with `--messy` to see the other side: six blockers — an unknown",
        "class, a subject nobody teaches, a duplicate admission number, two nameless",
        "rows — plus one unsized chapter, which stays a **note**, because a school",
        "that has planned only half its year is still allowed to go live.",
        "",
        "### 4. Import, then check readiness",
        "**Import everything** builds the school in one transaction. Copy the staff",
        "logins it shows — they are hashed on the way in and cannot be read back.",
        "",
        "Then **Readiness & handover**: every check should read ok. Students have",
        "dates of birth, so no *parents cannot log in* warning.",
        "",
        "---",
        "",
        "## After setup — what to verify",
        "",
        "1. **Plan → Week plan**: pick a class → the week grid shows every period with its topic.",
        "2. **Plan → Year**: exam fit panel + calendar live here.",
        "3. **Log in as a teacher** (a generated password): **My Day** shows their periods from",
        "   the timetable; take attendance, log a topic. Back in Plan → Week plan as admin,",
        "   that cell is now green (actual).",
        "4. **Plan → Classes**: every subject **on track** — none `unallocated` / `not sized`.",
        "5. **Students**: filter, search, edit — open a student for their timeline.",
        "6. **Hand it over**, then try to add a class as the school’s own admin:",
        "   it is refused. Structure is ours once a school is live.",
        "",
        "## Files",
        "",
        "| File | Where | Expect |",
        "|---|---|---|",
        f"| `{pack_name}` | Platform → school → Setup | {len(school.teachers)} staff · "
        f"{len(school.classes)} classes · {n_cs} class-subjects · "
        f"{len(school.students)} students |",
        "",
    ]
    if multi:
        m = multi[0]
        lines.append(f"- {m.name} should show on {' and '.join(m.subjects)}.")

    (HERE / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print("  wrote README.md")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seed", type=int, default=None,
                    help="reproduce a previous pack exactly (default: a new random school)")
    ap.add_argument("--messy", action="store_true",
                    help="also inject rows engineered to FAIL (bad assignment, duplicate "
                         "admission no, missing name, unsized topic) to exercise the "
                         "importers' errors/skipped/unresolved surfaces")
    args = ap.parse_args()

    seed = args.seed if args.seed is not None else random.randrange(1, 1_000_000)
    rng = random.Random(seed)

    school = invent_school(rng)
    # ASCII only in console output: the Windows console is cp1252 and a stray arrow
    # would crash the generator on the founder's own machine.
    print(f"seed {seed} -> {school.name}")
    print(f"  {len(school.classes)} classes | {len(school.subjects)} subjects | "
          f"{len(school.teachers)} teachers | {len(school.students)} students | "
          f"{school.capacity} periods/week")
    if args.messy:
        print("  --messy: injecting deliberate failure rows (imports will NOT be clean)")
    clear_stale()
    write_pack(school, messy=args.messy)
    write_readme(school, seed)
    print(f"\nDone. Walkthrough for this school: {HERE / 'README.md'}")


if __name__ == "__main__":
    main()
