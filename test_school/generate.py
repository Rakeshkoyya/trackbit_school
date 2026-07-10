"""Generate the Green Valley sample-school import files.

One coherent school, so every file lines up: the classes in the roster, the classes
& subjects in the teacher assignments, and the subject names in the syllabus files
all match the same set — 6-A, 6-B, 7-A and {Mathematics, Science, English, Social
Studies, Hindi}.

Run from the api/ folder so openpyxl is on the path:

    cd api && uv run python ../test_school/generate.py

Nothing here is app code — it just writes .xlsx/.txt/.csv fixtures. Regenerate any
time; the content is stable.
"""

from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).parent
SYL = ROOT / "syllabus"
TT = ROOT / "timetable"
SYL.mkdir(exist_ok=True)
TT.mkdir(exist_ok=True)

CLASSES = [("6", "A"), ("6", "B"), ("7", "A")]
SUBJECTS = ["Mathematics", "Science", "English", "Social Studies", "Hindi"]


def _grid(path: Path, sheet: str, header: list[str], rows: list[list]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(header)
    for r in rows:
        ws.append(r)
    for i, h in enumerate(header, start=1):
        width = max(len(str(h)), *(len(str(r[i - 1])) if i - 1 < len(r) and r[i - 1] is not None
                                   else 0 for r in rows)) if rows else len(str(h))
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(12, width + 3)
    wb.save(path)


# ── teachers.xlsx ─────────────────────────────────────────────────────────────
# assignments resolve against the classes + subjects you created in the wizard.
# Format the importer understands: "6-A Mathematics; 6-B Mathematics" (split on ; , /).
TEACHERS = [
    ("Sunita Rao", "sunita.rao", "sunita.rao@greenvalley.edu", "+919810000001",
     "6-A Mathematics; 6-B Mathematics"),
    ("Deepak Iyer", "deepak.iyer", "deepak.iyer@greenvalley.edu", "+919810000002",
     "7-A Mathematics; 7-A Science"),
    ("Vikram Nair", "vikram.nair", "vikram.nair@greenvalley.edu", "+919810000003",
     "6-A Science; 6-B Science"),
    ("Lakshmi Menon", "lakshmi.menon", "lakshmi.menon@greenvalley.edu", "+919810000004",
     "6-A English; 6-B English; 7-A English"),
    ("Rahul Verma", "rahul.verma", "rahul.verma@greenvalley.edu", "+919810000005",
     "6-A Social Studies; 6-B Social Studies; 7-A Social Studies"),
    ("Anjali Gupta", "anjali.gupta", "anjali.gupta@greenvalley.edu", "+919810000006",
     "6-A Hindi; 6-B Hindi; 7-A Hindi"),
]
_grid(ROOT / "teachers.xlsx", "Teachers",
      ["Name", "Username", "Email", "Phone", "Assignments"],
      [list(t) for t in TEACHERS])


# ── students.xlsx ─────────────────────────────────────────────────────────────
FIRST = ["Aarav", "Diya", "Vihaan", "Ananya", "Arjun", "Saanvi", "Kabir", "Myra",
         "Reyansh", "Aadhya", "Vivaan", "Ishaan", "Anika", "Kiara", "Advik",
         "Navya", "Aryan", "Prisha", "Atharv", "Riya", "Dhruv", "Sara", "Yuvan",
         "Ira", "Ayaan", "Pari", "Kian", "Zara", "Rudra", "Aisha", "Veer",
         "Tara", "Neel", "Amaira", "Ekansh", "Larisa", "Hriday", "Mira", "Ved",
         "Kyra", "Reyaan", "Nitya", "Shaan", "Ahana", "Rehan"]
SURNAMES = ["Sharma", "Patel", "Reddy", "Iyer", "Nair", "Gupta", "Singh", "Desai",
            "Menon", "Rao", "Bose", "Chauhan", "Mehta", "Verma", "Pillai"]
CATEGORIES = ["Day Scholar", "Hosteller", "RTE"]

student_rows = []
adm = 2601
n = 0
for cls, sec in CLASSES:
    for roll in range(1, 16):
        first = FIRST[n % len(FIRST)]
        sur = SURNAMES[(n + roll) % len(SURNAMES)]
        cat = CATEGORIES[n % len(CATEGORIES)]
        base = 9820000000 + n * 2
        student_rows.append([
            f"GV{adm}", f"{first} {sur}", roll, cls, sec, cat,
            f"Mr. {sur}", f"+91{base}", f"Mrs. {sur}", f"+91{base + 1}",
        ])
        adm += 1
        n += 1

_grid(ROOT / "students.xlsx", "Students",
      ["Admission No", "Student Name", "Roll No", "Class", "Section", "Category",
       "Father Name", "Father Mobile", "Mother Name", "Mother Mobile"],
      student_rows)


# ── syllabus (grid: Chapter, Topic, Periods) ──────────────────────────────────
# Blank Chapter cell continues the chapter above (how merged cells export). A blank
# Periods cell means "not sized yet" — imported unsized, not as 1.
def _syllabus(path: Path, chapters: dict[str, list[tuple[str, int]]]) -> None:
    rows = []
    for chapter, topics in chapters.items():
        first = True
        for title, periods in topics:
            rows.append([chapter if first else None, title, periods])
            first = False
    _grid(path, "Syllabus", ["Chapter", "Topic", "Periods"], rows)


CLASS6_MATH = {
    "Knowing Our Numbers": [("Comparing numbers", 2), ("Large numbers in practice", 2),
                            ("Estimation and rounding", 2), ("Roman numerals", 1)],
    "Whole Numbers": [("Number line", 2), ("Properties of whole numbers", 3)],
    "Playing With Numbers": [("Factors and multiples", 3), ("Prime and composite", 2),
                             ("HCF and LCM", 4)],
    "Basic Geometrical Ideas": [("Points, lines, line segments", 2), ("Angles and polygons", 3)],
    "Understanding Elementary Shapes": [("Measuring line segments", 2), ("Types of angles", 2),
                                        ("Triangles and quadrilaterals", 3)],
    "Integers": [("Introduction to negatives", 2), ("Addition and subtraction", 3)],
    "Fractions": [("Types of fractions", 2), ("Equivalent fractions", 2),
                  ("Adding and subtracting fractions", 3)],
    "Decimals": [("Tenths and hundredths", 2), ("Comparing decimals", 2)],
}
CLASS6_SCIENCE = {
    "Food: Where Does It Come From?": [("Food variety and sources", 2),
                                       ("Herbivores, carnivores, omnivores", 2)],
    "Components of Food": [("Nutrients in food", 3), ("Balanced diet", 2),
                           ("Deficiency diseases", 2)],
    "Fibre to Fabric": [("Plant fibres: cotton and jute", 2),
                        ("Spinning and weaving", 3)],
    "Sorting Materials into Groups": [("Properties of materials", 3),
                                      ("Transparency and solubility", 2)],
    "Separation of Substances": [("Methods of separation", 3),
                                 ("Evaporation and condensation", 2)],
    "Getting to Know Plants": [("Herbs, shrubs and trees", 2), ("Parts of a plant", 3)],
    "Body Movements": [("Human body and joints", 3), ("Gait of animals", 2)],
    "Motion and Measurement of Distances": [("Standard units", 2), ("Types of motion", 2)],
}
CLASS6_SOCIAL = {
    "History: What, Where, How and When": [("Sources of history", 2), ("Dates and periods", 2)],
    "From Gathering to Growing Food": [("Early humans", 2), ("Beginnings of farming", 3)],
    "The Earth in the Solar System": [("The solar system", 2), ("Stars and constellations", 2)],
    "Globe: Latitudes and Longitudes": [("Latitudes", 2), ("Longitudes and time", 3)],
    "Understanding Diversity": [("Diversity in India", 2), ("Unity in diversity", 2)],
    "Rural and Urban Livelihoods": [("Life in villages", 2), ("Life in cities", 2)],
}
CLASS6_HINDI = {
    "वह चिड़िया जो": [("कविता का भावार्थ", 2), ("शब्दार्थ और अभ्यास", 2)],
    "बचपन": [("पाठ का सार", 3), ("प्रश्न-उत्तर", 2)],
    "नादान दोस्त": [("कहानी का सार", 2), ("चरित्र-चित्रण", 2)],
    "चाँद से थोड़ी-सी गप्पें": [("कविता की व्याख्या", 2), ("अभ्यास", 1)],
    "अक्षरों का महत्व": [("पाठ का सार", 2), ("व्याकरण", 2)],
    "व्याकरण: संज्ञा और सर्वनाम": [("संज्ञा के भेद", 3), ("सर्वनाम के भेद", 2)],
}

CLASS7_MATH = {
    "Integers": [("Properties of integers", 3), ("Multiplication and division", 3)],
    "Fractions and Decimals": [("Multiplication of fractions", 3),
                               ("Division of decimals", 3)],
    "Data Handling": [("Arithmetic mean, mode, median", 4), ("Bar graphs and probability", 3)],
    "Simple Equations": [("Setting up an equation", 2), ("Solving equations", 4)],
    "Lines and Angles": [("Pairs of angles", 3), ("Parallel lines", 2)],
    "The Triangle and Its Properties": [("Angle sum property", 2), ("Pythagoras theorem", 3)],
    "Comparing Quantities": [("Percentage", 3), ("Profit and loss", 3), ("Simple interest", 2)],
    "Rational Numbers": [("Introduction", 2), ("Operations on rational numbers", 3)],
}
CLASS7_SCIENCE = {
    "Nutrition in Plants": [("Photosynthesis", 3), ("Other modes of nutrition", 2)],
    "Nutrition in Animals": [("Human digestive system", 3), ("Digestion in ruminants", 2)],
    "Heat": [("Temperature and thermometers", 2), ("Conduction, convection, radiation", 3)],
    "Acids, Bases and Salts": [("Indicators", 2), ("Neutralisation", 3)],
    "Physical and Chemical Changes": [("Types of changes", 2), ("Rusting and crystallisation", 3)],
    "Respiration in Organisms": [("Breathing", 2), ("Respiration in plants and animals", 3)],
    "Motion and Time": [("Speed", 2), ("Distance-time graphs", 3)],
    "Electric Current and Its Effects": [("Heating effect", 2), ("Magnetic effect", 3)],
}
CLASS7_ENGLISH = {
    "Prose: Three Questions": [("Reading and comprehension", 2), ("Vocabulary", 1)],
    "Prose: A Gift of Chappals": [("Reading and comprehension", 2), ("Discussion", 2)],
    "Poetry: The Squirrel": [("Recitation and meaning", 1), ("Figures of speech", 2)],
    "Prose: Gopal and the Hilsa Fish": [("Reading", 2), ("Character sketch", 2)],
    "Grammar: Tenses": [("Present and past tense", 3), ("Future tense", 2)],
    "Writing: Informal Letters": [("Format and practice", 3)],
}
CLASS7_SOCIAL = {
    "History: Tracing Changes": [("Sources for the period", 2), ("New social groups", 2)],
    "History: New Kings and Kingdoms": [("Emergence of dynasties", 3), ("Warfare and administration", 2)],
    "Geography: Environment": [("Natural and human environment", 2), ("Ecosystem", 2)],
    "Geography: Inside Our Earth": [("Layers of the earth", 2), ("Rocks and minerals", 3)],
    "Civics: On Equality": [("Equality in democracy", 2), ("Challenges to equality", 2)],
    "Civics: Role of the Government in Health": [("Public and private services", 2), ("Healthcare access", 2)],
}
CLASS7_HINDI = {
    "हम पंछी उन्मुक्त गगन के": [("कविता का भावार्थ", 2), ("अभ्यास", 2)],
    "दादी माँ": [("कहानी का सार", 3), ("प्रश्न-उत्तर", 2)],
    "हिमालय की बेटियाँ": [("निबंध का सार", 2), ("शब्दार्थ", 2)],
    "कठपुतली": [("कविता की व्याख्या", 2), ("अभ्यास", 1)],
    "मिठाईवाला": [("कहानी का सार", 3), ("चरित्र-चित्रण", 2)],
    "व्याकरण: वाच्य और काल": [("वाच्य के भेद", 3), ("काल के भेद", 2)],
}

_syllabus(SYL / "class6_mathematics.xlsx", CLASS6_MATH)
_syllabus(SYL / "class6_science.xlsx", CLASS6_SCIENCE)
_syllabus(SYL / "class6_social_studies.xlsx", CLASS6_SOCIAL)
_syllabus(SYL / "class6_hindi.xlsx", CLASS6_HINDI)
_syllabus(SYL / "class7_mathematics.xlsx", CLASS7_MATH)
_syllabus(SYL / "class7_science.xlsx", CLASS7_SCIENCE)
_syllabus(SYL / "class7_social_studies.xlsx", CLASS7_SOCIAL)
_syllabus(SYL / "class7_hindi.xlsx", CLASS7_HINDI)

# English Class 6 as free text (tests the paste / .txt path). A trailing "(2)" is
# read as the period estimate; a line with none is left unsized.
(SYL / "class6_english.txt").write_text(
    """Chapter 1: A Tale of Two Birds
Reading and comprehension (2)
New words and meanings (1)

Chapter 2: The Friendly Mongoose
Reading the story (2)
Character discussion (2)

Chapter 3: Poem - The Kite
Recitation and meaning (1)
Rhyme and rhythm (1)

Chapter 4: The Shepherd's Treasure
Reading and comprehension (2)
Values in the story (2)

Chapter 5: Grammar - Nouns and Pronouns
Kinds of nouns (2)
Personal pronouns (2)

Chapter 6: Writing - Paragraph and Notice
Paragraph writing (2)
Notice writing (2)
""",
    encoding="utf-8",
)

# Optional / advanced: a term-wise Class 6 Maths syllabus. The "Term" column only
# resolves if Term 1 and Term 2 exist for the year; otherwise those chapters import
# untermed (still fine). Term 2 is left UNSIZED on purpose — that is the case the
# term-wise planning feature exists for.
term_rows = []
for term, chapter, topics in [
    ("Term 1", "Knowing Our Numbers", [("Comparing numbers", 2), ("Roman numerals", 1)]),
    ("Term 1", "Whole Numbers", [("Number line", 2), ("Properties", 3)]),
    ("Term 1", "Playing With Numbers", [("Factors and multiples", 3), ("HCF and LCM", 4)]),
    ("Term 2", "Integers", [("Introduction to negatives", None), ("Operations", None)]),
    ("Term 2", "Fractions", [("Types of fractions", None), ("Equivalent fractions", None)]),
    ("Term 2", "Decimals", [("Tenths and hundredths", None), ("Comparing decimals", None)]),
]:
    first = True
    for title, periods in topics:
        term_rows.append([term if first else None, chapter if first else None, title, periods])
        first = False
_grid(SYL / "class6_mathematics_TERMWISE.xlsx", "Syllabus",
      ["Term", "Chapter", "Topic", "Periods"], term_rows)


# ── timetable reference sheets (NOT machine-imported — see README) ─────────────
# The app's timetable "import" ignores the uploaded file and auto-fills the grid
# from each class's subjects. These sheets are a human reference / the layout you'd
# hand-enter, one per class.
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
WEEK = {
    ("6", "A"): [
        ["Mathematics", "Science", "English", "Social Studies", "Hindi", "Mathematics", "Science", "English"],
        ["English", "Mathematics", "Science", "Hindi", "Social Studies", "English", "Mathematics", "Science"],
        ["Science", "English", "Mathematics", "Social Studies", "Hindi", "Science", "English", "Mathematics"],
        ["Social Studies", "Hindi", "English", "Mathematics", "Science", "Social Studies", "Hindi", "English"],
        ["Hindi", "Social Studies", "Mathematics", "Science", "English", "Hindi", "Social Studies", "Mathematics"],
        ["Mathematics", "English", "Science", "Hindi", "Social Studies", "Mathematics", "English", "Science"],
    ],
}


def _timetable(cls: str, sec: str) -> None:
    grid = WEEK.get((cls, sec), WEEK[("6", "A")])
    header = ["Period", *DAYS]
    rows = []
    for p in range(8):
        rows.append([f"P{p + 1}", *[grid[d][p] for d in range(len(DAYS))]])
    _grid(TT / f"class{cls}{sec}_timetable.xlsx", f"{cls}-{sec}", header, rows)


for cls, sec in CLASSES:
    _timetable(cls, sec)


print("Wrote sample school files:")
for p in sorted(ROOT.rglob("*")):
    if p.is_file() and p.suffix in (".xlsx", ".txt", ".csv"):
        print(f"  {p.relative_to(ROOT)}")
