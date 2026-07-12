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
  I3  Every topic is sized (no blank Periods cell), so the wizard's final step can
      approve and LOCK every plan — an unsized topic is refused by `approve`.
  I4  Each class-subject's syllabus fits comfortably inside the periods the year
      actually offers, so the exam-fit panel reads "perfect"/"spare time".

Output (all written next to this script; stale files are cleared first):
  teachers_staff.xlsx          -> Setup wizard, Teachers step
  students_roster.xlsx         -> Setup wizard, Students step
  syllabus_<class>_<subject>.xlsx  (one per class-subject) -> Syllabus step
  SETUP.md                     -> the step-by-step walkthrough for THIS run's school

The three sheets match the importers' expected headers exactly (roster_import.py,
staff_import.py, syllabus_import.py); the `x9` suffix in an Assignments cell is how a
staff sheet carries a subject's weekly period budget.
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

def sheet(path: str, header: list[str], rows: list[list]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(HERE / path)
    print(f"  wrote {path} ({len(rows)} rows)")


def clear_stale() -> None:
    """The class/subject set changes every run — old files would linger and mislead."""
    for f in HERE.glob("*.xlsx"):
        f.unlink()
    (HERE / "SETUP.md").unlink(missing_ok=True)


def write_pack(school: School, messy: bool = False) -> None:
    staff_rows = [
        [t.name, t.email, t.mobile,
         "; ".join(f"{a.class_name} {a.subject} x{a.periods}" for a in t.assignments)]
        for t in school.teachers
    ]
    students = [list(r) for r in school.students]

    if messy:
        # Rows engineered to FAIL, so the importers' errors/skipped/unresolved
        # surfaces get exercised. Never present in the default (clean) pack.
        staff_rows.append(["Bad Assignment Teacher", "bad.teacher@example.com", "9899900001",
                           "99 Astrophysics x5; Nonsense Row"])  # -> unresolved
        staff_rows.append(["", "no.name@example.com", "9899900002", ""])  # -> error: no name
        dupe = students[0][1]
        students.append(["Duplicate Admission", dupe, "99", school.classes[0], None,
                         "Day Scholar", "Mr X", "9800000001", "Mrs X", "9800000002"])  # -> skipped
        students.append(["", "NG_NO_NAME", "98", school.classes[0], None, "Day Scholar",
                         "Mr Y", "9800000003", "Mrs Y", "9800000004"])  # -> error: no name
        students.append(["No Admission No", "", "97", school.classes[0], None, "Day Scholar",
                         "Mr Z", "9800000005", "Mrs Z", "9800000006"])  # -> error: no adm no

    sheet("teachers_staff.xlsx",
          ["Teacher Name", "Email", "Mobile", "Assignments"], staff_rows)
    sheet("students_roster.xlsx",
          ["Student Name", "Admission No", "Roll No", "Class", "Section", "Category",
           "Father's Name", "Father's Mobile", "Mother's Name", "Mother's Mobile"],
          students)

    for (cname, subject), chapters in school.syllabus.items():
        body: list[list] = []
        for ch, topics, term in chapters:
            for i, (t, p) in enumerate(topics):
                # Chapter/Term only on the first row: merged cells export as blanks,
                # and the importer carries the previous value forward.
                body.append([ch if i == 0 else None, t, p, term if i == 0 else None])
        if messy and (cname, subject) == next(iter(school.syllabus)):
            # A blank Periods cell = "not sized yet" — approve() must REFUSE to lock it.
            body.append(["Unsized Chapter", "Topic with no period estimate", None, "Term 2"])
        sheet(f"syllabus_{cname}_{slug(subject)}.xlsx",
              ["Chapter", "Topic", "Periods", "Term"], body)


def write_readme(school: School, seed: int) -> None:
    cap = school.capacity
    days = "Mon-Sat" if school.working_days == 6 else "Mon-Fri"
    n_cs = len(school.classes) * len(school.subjects)
    multi = [t for t in school.teachers if len(t.subjects) > 1]
    busiest = max(school.teachers, key=lambda t: t.load)

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
        "Every row here is valid — imports should land **100%**, and the wizard's final",
        f"step should lock all **{n_cs} plans**.",
        "",
        "> Want to test the *failure* surfaces instead? Add `--messy` to inject rows built",
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
        "### 1. Academic year",
        f"Label **{school.year_label}**, from **{school.year_start}** to **{school.year_end}**.",
        "Add both terms (the syllabus files reference them by name — spell them exactly):",
        f"- **Term 1** — {school.year_start} → {school.term1_end}",
        f"- **Term 2** — {school.term1_end + timedelta(days=1)} → {school.year_end}",
        "",
        "### 2. School timings",
        f"Working days **{days}**, **{school.periods_per_day} periods/day**.",
        f"*This fixes each class's weekly capacity at {cap} — the staff file's `x` numbers",
        "are built to sum to exactly that.*",
        "",
        "### 3. Classes",
        f"Add **{'**, **'.join(school.classes)}**. Leave the section field **blank**",
        "(one section per grade, so no A/B duplication).",
        "",
        "### 4. Subjects",
        f"Add all {len(school.subjects)}: **{', '.join(school.subjects)}**",
        "(spell them exactly — the staff file's assignments resolve by name).",
        "",
        "### 5. Teachers & assignments",
        f"Import **`teachers_staff.xlsx`** → {len(school.teachers)} accounts, "
        f"{n_cs} assignments, zero errors.",
        "- ⚠️ **Write down the generated passwords** shown after import — you'll want them",
        "  to log in as a teacher later (e.g. to see My Day).",
        f"- Each class's panel should now read **\"{cap} of {cap} periods/week allocated\"**.",
    ]
    if multi:
        m = multi[0]
        lines.append(f"- {m.name} should show on {' and '.join(m.subjects)}.")

    lines += [
        "",
        "### 6. Syllabus",
        f"{n_cs} imports — one file per class per subject. Pick the class, pick the subject,",
        "import its file, review the draft (chapters split into Term 1/Term 2, every topic",
        "sized), then *Save to this subject*. The filename says exactly where each file goes:",
        "**`syllabus_<class>_<subject>.xlsx`**.",
        "",
        "*Note:* the \"Copy from…\" control is for true sibling **sections** (6-A → 6-B).",
        "Don't use it across grades — each grade has its own files.",
        "",
        "### 7. Calendar, holidays & exams",
        "Paint the exam windows and a holiday week on the calendar, then set **exam portions**",
        "per class (e.g. \"up to\" the last Term-1 chapter of each subject).",
        "",
        "**Watch the Exam fit panel**: every subject should read *perfect* or *spare time*.",
        "Now delete a term exam and repaint it 6–8 weeks earlier — verdicts flip toward",
        "*manageable / won't fit*. Repaint it back when done.",
        "",
        "### 8. Students",
        f"Import **`students_roster.xlsx`** → **created {len(school.students)}, skipped 0,",
        "errors 0**. Check the Students page: filter by class, click a row → **Edit details**.",
        "",
        "### 9. Timetable",
        "Tap **\"Generate the whole school's timetable\"** → preview should say",
        f"**{cap * len(school.classes)} periods across {len(school.classes)} classes**, every",
        "subject placed cleanly, no teacher double-booked. Apply, then spot-check a class grid.",
        "",
        "### 10. Generate & lock",
        "- The gap report should be **empty**. To see the blocking work, delete one subject's",
        "  syllabus first and come back — generation is blocked with a named gap. Restore it.",
        f"- **Generate every plan** → all {n_cs} come back clean (fits, in order, before exams).",
        f"- **Approve & lock {n_cs} plans** → done.",
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
        "",
        "## Files",
        "",
        "| File | Where | Expect |",
        "|---|---|---|",
        f"| `teachers_staff.xlsx` | Wizard → Teachers | {len(school.teachers)} created · "
        f"{n_cs} assignments · {cap}/{cap} per class |",
        f"| `students_roster.xlsx` | Wizard → Students | {len(school.students)} created, 0 errors |",
        f"| `syllabus_<class>_<subject>.xlsx` ({n_cs} files) | Syllabus → matching class+subject | "
        "termed, every topic sized |",
        "",
    ]
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
