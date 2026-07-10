"""Regenerate the import test fixtures in this folder.

Run from the repo root (openpyxl comes from the api venv):

    cd api && uv run python ../test_doc/generate_fixtures.py

Every header below is chosen to hit a real hint in the importers' FieldSpecs:
  students  -> app/services/roster_import.py   FIELD_HINTS
  teachers  -> app/services/staff_import.py    SPECS
  syllabus  -> app/services/syllabus_import.py SPECS

The fixtures deliberately include bad rows (missing name, missing admission no,
an unresolvable class-subject) so the importers' error/unresolved surfaces are
exercised, not just the happy path.
"""

from pathlib import Path

from openpyxl import Workbook

OUT = Path(__file__).parent


def sheet(name: str, header: list[str], rows: list[list]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = name
    ws.append(header)
    for r in rows:
        ws.append(r)
    for i, h in enumerate(header, start=1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = max(14, len(h) + 4)
    return wb


# ── students ────────────────────────────────────────────────────────────────
# Seeded classes are 6-A, 6-B, 7-A (api/scripts/seed.py). Anything else stays
# unassigned (class_id = NULL), which is itself worth seeing on the Students screen.
STUDENT_HEADER = [
    "Adm. No", "Student Name", "Roll No", "Class", "Section", "Category",
    "Father's Name", "Father's Mobile", "Mother's Name", "Mother's Mobile",
]

_S = [
    # (adm, name, roll, class, section, category, father, f_mob, mother, m_mob)
    ("TB1001", "Aarav Sharma", "1", "6", "A", "General", "Rajesh Sharma", "+919812000101", "Sunita Sharma", "+919812000102"),
    ("TB1002", "Diya Patel", "2", "6", "A", "General", "Nikhil Patel", "+919812000103", "Meera Patel", "+919812000104"),
    ("TB1003", "Vihaan Reddy", "3", "6", "A", "RTE", "Suresh Reddy", "+919812000105", "Lakshmi Reddy", "+919812000106"),
    ("TB1004", "Ananya Iyer", "4", "6", "A", "General", "Krishnan Iyer", "+919812000107", "Radha Iyer", "+919812000108"),
    ("TB1005", "Arjun Nair", "5", "6", "A", "General", "Mohan Nair", "+919812000109", "Priya Nair", "+919812000110"),
    ("TB1006", "Ishaan Gupta", "6", "6", "A", "Staff Ward", "Amit Gupta", "+919812000111", "Kavita Gupta", "+919812000112"),
    ("TB1007", "Saanvi Joshi", "7", "6", "A", "General", "Deepak Joshi", "+919812000113", "Neha Joshi", "+919812000114"),
    ("TB1008", "Kabir Singh", "8", "6", "A", "General", "Harpreet Singh", "+919812000115", "Simran Singh", "+919812000116"),
    ("TB1009", "Myra Desai", "9", "6", "A", "RTE", "Paresh Desai", "+919812000117", "Bhavna Desai", "+919812000118"),
    ("TB1010", "Reyansh Kulkarni", "10", "6", "A", "General", "Sandeep Kulkarni", "+919812000119", "Anjali Kulkarni", "+919812000120"),
    ("TB1011", "Aadhya Menon", "11", "6", "A", "General", "Vivek Menon", "+919812000121", "Divya Menon", "+919812000122"),
    ("TB1012", "Vivaan Rao", "12", "6", "A", "General", "Prakash Rao", "+919812000123", "Shanti Rao", "+919812000124"),

    ("TB1013", "Anika Bose", "1", "6", "B", "General", "Subhash Bose", "+919812000125", "Mitali Bose", "+919812000126"),
    ("TB1014", "Advik Chauhan", "2", "6", "B", "General", "Ranveer Chauhan", "+919812000127", "Pooja Chauhan", "+919812000128"),
    ("TB1015", "Kiara Mehta", "3", "6", "B", "RTE", "Jayesh Mehta", "+919812000129", "Rekha Mehta", "+919812000130"),
    ("TB1016", "Shaurya Verma", "4", "6", "B", "General", "Alok Verma", "+919812000131", "Nisha Verma", "+919812000132"),
    ("TB1017", "Navya Pillai", "5", "6", "B", "General", "Ganesh Pillai", "+919812000133", "Latha Pillai", "+919812000134"),
    ("TB1018", "Aryan Malhotra", "6", "6", "B", "Staff Ward", "Rohit Malhotra", "+919812000135", "Sonia Malhotra", "+919812000136"),
    ("TB1019", "Prisha Ghosh", "7", "6", "B", "General", "Anirban Ghosh", "+919812000137", "Rupa Ghosh", "+919812000138"),
    ("TB1020", "Atharv Bhatt", "8", "6", "B", "General", "Kunal Bhatt", "+919812000139", "Trupti Bhatt", "+919812000140"),
    ("TB1021", "Riya Chopra", "9", "6", "B", "General", "Vikram Chopra", "+919812000141", "Nandini Chopra", "+919812000142"),
    ("TB1022", "Dhruv Saxena", "10", "6", "B", "RTE", "Manoj Saxena", "+919812000143", "Preeti Saxena", "+919812000144"),
    ("TB1023", "Sara Fernandes", "11", "6", "B", "General", "Joseph Fernandes", "+919812000145", "Maria Fernandes", "+919812000146"),
    ("TB1024", "Yuvan Krishnan", "12", "6", "B", "General", "Balaji Krishnan", "+919812000147", "Gayatri Krishnan", "+919812000148"),

    ("TB1025", "Ira Banerjee", "1", "7", "A", "General", "Sourav Banerjee", "+919812000149", "Piyali Banerjee", "+919812000150"),
    ("TB1026", "Ayaan Qureshi", "2", "7", "A", "General", "Imran Qureshi", "+919812000151", "Farah Qureshi", "+919812000152"),
    ("TB1027", "Pari Agarwal", "3", "7", "A", "RTE", "Sunil Agarwal", "+919812000153", "Ritu Agarwal", "+919812000154"),
    ("TB1028", "Kian Deshmukh", "4", "7", "A", "General", "Nitin Deshmukh", "+919812000155", "Snehal Deshmukh", "+919812000156"),
    ("TB1029", "Zara Sheikh", "5", "7", "A", "General", "Arif Sheikh", "+919812000157", "Nazia Sheikh", "+919812000158"),
    ("TB1030", "Rudra Thakur", "6", "7", "A", "Staff Ward", "Bhupendra Thakur", "+919812000159", "Seema Thakur", "+919812000160"),
    ("TB1031", "Aisha Khan", "7", "7", "A", "General", "Salim Khan", "+919812000161", "Yasmin Khan", "+919812000162"),
    ("TB1032", "Veer Sinha", "8", "7", "A", "General", "Rakesh Sinha", "+919812000163", "Archana Sinha", "+919812000164"),
    ("TB1033", "Tara Mishra", "9", "7", "A", "General", "Ashok Mishra", "+919812000165", "Vandana Mishra", "+919812000166"),
    ("TB1034", "Neel Kapoor", "10", "7", "A", "RTE", "Rajiv Kapoor", "+919812000167", "Shalini Kapoor", "+919812000168"),
    ("TB1035", "Amaira Jain", "11", "7", "A", "General", "Mukesh Jain", "+919812000169", "Sheetal Jain", "+919812000170"),
    ("TB1036", "Ekansh Dubey", "12", "7", "A", "General", "Ramakant Dubey", "+919812000171", "Sarita Dubey", "+919812000172"),

    # A class the demo org does not have -> imports fine, lands unassigned.
    ("TB1037", "Hriday Shetty", "1", "8", "A", "General", "Ganpat Shetty", "+919812000173", "Asha Shetty", "+919812000174"),
    # Only a mother on record -> single guardian row.
    ("TB1038", "Larisa Dsouza", "13", "7", "A", "General", "", "", "Glenda Dsouza", "+919812000175"),
    # --- rows the importer should REJECT (they land in `errors`) ---
    ("TB1039", "", "14", "7", "A", "General", "No Name", "+919812000176", "", ""),           # missing name
    ("", "Missing Admission No", "15", "7", "A", "General", "Someone", "+919812000177", "", ""),  # missing adm
    # --- rows the importer should SKIP as duplicates of the seed (A601/A602) ---
    ("A601", "Seed Duplicate One", "90", "6", "A", "General", "", "", "", ""),
    ("A602", "Seed Duplicate Two", "91", "6", "A", "General", "", "", "", ""),
]

sheet("Students", STUDENT_HEADER, [list(r) for r in _S]).save(OUT / "students_roster.xlsx")


# ── teachers ────────────────────────────────────────────────────────────────
# `assignments` resolves against classes+subjects that ALREADY exist. Tokens are
# split on ; , / | and newline; each must look like "<class><sep><section> <Subject>".
TEACHER_HEADER = ["Teacher Name", "Employee ID", "Email", "Mobile", "Assignments"]

_T = [
    ("Sunita Rao", "EMP101", "sunita.rao@demo.trackbit.app", "+919820000001",
     "6-A Mathematics; 6-B Mathematics"),
    ("Vikram Desai", "EMP102", "vikram.desai@demo.trackbit.app", "+919820000002",
     "6-A Science; 6-B Science; 7-A Science"),
    ("Lakshmi Narayan", "EMP103", "lakshmi.narayan@demo.trackbit.app", "+919820000003",
     "6-A English; 7-A English"),
    ("Farhan Ahmed", "EMP104", "farhan.ahmed@demo.trackbit.app", "+919820000004",
     "6-B English; 6-A Hindi"),
    ("Meera Krishnan", "EMP105", "meera.krishnan@demo.trackbit.app", "+919820000005",
     "7-A Mathematics; 7-A Social Studies"),
    ("Rohit Bhandari", "EMP106", "rohit.bhandari@demo.trackbit.app", "+919820000006",
     "6-A Social Studies; 6-B Social Studies"),
    # Names a class (9-C) and a subject (Astronomy) the org does not have ->
    # the teacher IS created, the assignment comes back in `unresolved`.
    ("Neha Bhatnagar", "EMP107", "neha.bhatnagar@demo.trackbit.app", "+919820000007",
     "7-A Hindi; 9-C Astronomy"),
    # No assignment column value at all -> account only.
    ("Anand Pillai", "EMP108", "anand.pillai@demo.trackbit.app", "+919820000008", ""),
    # Same name as a seeded member -> counted in `skipped`, no second account.
    ("Ramesh", "EMP109", "ramesh.dup@demo.trackbit.app", "+919820000009", "6-B Hindi"),
    # No name -> lands in `errors`.
    ("", "EMP110", "ghost@demo.trackbit.app", "+919820000010", "6-A English"),
]

sheet("Teachers", TEACHER_HEADER, [list(r) for r in _T]).save(OUT / "teachers_staff.xlsx")


# ── syllabus (grid) ─────────────────────────────────────────────────────────
# A blank Chapter cell continues the previous chapter — that is how a real sheet
# with merged cells exports, and `rows_to_units` relies on it.
SYL_HEADER = ["Chapter", "Topic", "Periods"]

_SCIENCE_6 = [
    ("Food: Where Does It Come From?", "Food variety and sources", 2),
    ("", "Plant parts and animal products as food", 2),
    ("", "Herbivores, carnivores, omnivores", 2),
    ("Components of Food", "Nutrients in food", 3),
    ("", "Balanced diet", 2),
    ("", "Deficiency diseases", 2),
    ("Fibre to Fabric", "Variety in fabrics", 2),
    ("", "Plant fibres: cotton and jute", 2),
    ("", "Spinning, weaving and knitting", 3),
    ("Sorting Materials into Groups", "Objects around us and their materials", 2),
    ("", "Properties: appearance, hardness, solubility", 3),
    ("", "Transparency and floating", 2),
    ("Separation of Substances", "Methods of separation", 3),
    ("", "Handpicking, threshing, winnowing, sieving", 3),
    ("", "Evaporation and condensation", 2),
    ("Changes Around Us", "Reversible and irreversible changes", 3),
    ("", "Expansion on heating", 2),
    ("Getting to Know Plants", "Herbs, shrubs and trees", 2),
    ("", "Stem, leaf, root, flower", 4),
    ("", "Photosynthesis and transpiration", 3),
    ("Body Movements", "Human body and its movements", 3),
    ("", "Ball and socket, pivotal, hinge joints", 3),
    ("", "Gait of animals", 2),
    ("The Living Organisms and Their Surroundings", "Habitat and adaptation", 3),
    ("", "Biotic and abiotic components", 2),
    ("", "Characteristics of living things", 3),
    ("Motion and Measurement of Distances", "Story of transport", 2),
    ("", "Standard units of measurement", 3),
    ("", "Types of motion", 2),
    ("Light, Shadows and Reflections", "Transparent, opaque, translucent", 2),
    ("", "Shadows and pinhole camera", 3),
    ("", "Mirrors and reflection", 2),
]
sheet("Syllabus", SYL_HEADER, [list(r) for r in _SCIENCE_6]).save(
    OUT / "syllabus_6A_science.xlsx")


# ── syllabus (grid, with a Term column the importer does NOT map) ───────────
# There is no `term` FieldSpec, so "Term" comes back in `unmapped_columns` and the
# term boundaries are silently dropped on commit. Useful for testing the gap.
_MATHS_6_TERMWISE = [
    ("Term 1", "Knowing Our Numbers", "Comparing numbers", 3),
    ("Term 1", "", "Large numbers in practice", 3),
    ("Term 1", "", "Estimation and rounding", 2),
    ("Term 1", "", "Roman numerals", 2),
    ("Term 1", "Whole Numbers", "Predecessor and successor", 2),
    ("Term 1", "", "Number line operations", 3),
    ("Term 1", "", "Properties of whole numbers", 3),
    ("Term 1", "Playing With Numbers", "Factors and multiples", 3),
    ("Term 1", "", "Prime and composite numbers", 3),
    ("Term 1", "", "HCF and LCM", 4),
    ("Term 1", "Basic Geometrical Ideas", "Points, lines, line segments", 3),
    ("Term 1", "", "Curves, polygons, angles", 3),
    ("Term 1", "", "Triangles, quadrilaterals, circles", 3),
    # Term 2 chapters: the portion is FIXED and known now, but the teacher has not
    # yet decided how many periods each takes. There is no way to say that today,
    # so these carry a placeholder the forecast will believe.
    ("Term 2", "Understanding Elementary Shapes", "Measuring line segments", None),
    ("Term 2", "", "Angles and their types", None),
    ("Term 2", "", "Classification of triangles", None),
    ("Term 2", "Integers", "Introduction to negative numbers", None),
    ("Term 2", "", "Ordering integers on a number line", None),
    ("Term 2", "", "Addition and subtraction of integers", None),
    ("Term 2", "Fractions", "Types of fractions", None),
    ("Term 2", "", "Equivalent fractions", None),
    ("Term 2", "", "Addition and subtraction of fractions", None),
    ("Term 2", "Decimals", "Tenths and hundredths", None),
    ("Term 2", "", "Comparing decimals", None),
    ("Term 2", "", "Using decimals with money and length", None),
]
sheet("Syllabus", ["Term", "Chapter", "Topic", "Periods"],
      [list(r) for r in _MATHS_6_TERMWISE]).save(OUT / "syllabus_6A_maths_termwise.xlsx")


# ── syllabus (free text) ────────────────────────────────────────────────────
# The heuristic reads "Chapter N: Title" / ALL CAPS / trailing ':' as a chapter,
# and a trailing "(3)" or "- 3 periods" on a topic line as its period estimate.
(OUT / "syllabus_7A_maths.txt").write_text(
    """Chapter 1: Integers
Properties of addition and subtraction of integers (3)
Multiplication of integers (3)
Division of integers (2)

Chapter 2: Fractions and Decimals
Multiplication of fractions (3)
Division of fractions (3)
Multiplication of decimal numbers (2)
Division of decimal numbers (2)

Chapter 3: Data Handling
Collection and organisation of data (2)
Arithmetic mean, mode and median (4)
Use of bar graphs (3)
Chance and probability (2)

Chapter 4: Simple Equations
Setting up an equation (2)
Solving an equation (4)
Applications of simple equations (3)

Chapter 5: Lines and Angles
Related angles (3)
Pairs of lines (3)
Checking parallel lines (2)

Chapter 6: The Triangle and Its Properties
Medians and altitudes (3)
Exterior angle property (2)
Angle sum property (2)
Pythagoras theorem (3)
""",
    encoding="utf-8",
)


# ── syllabus (messy sheet, no recognisable Topic column) ────────────────────
# `analyze_file` finds no topic_title, so it falls back to reading column 1 as
# free text ("heuristic-text-fallback"). This is what a typed-out list looks like.
_MESSY = [
    ("UNIT 1 - THE SOLAR SYSTEM",),
    ("The sun and the planets (3)",),
    ("Motions of the earth (2)",),
    ("The moon and eclipses (2)",),
    ("UNIT 2 - GLOBE AND MAPS",),
    ("Latitudes and longitudes (3)",),
    ("Types of maps (2)",),
    ("Map symbols and scale (2)",),
    ("UNIT 3 - CLIMATE AND VEGETATION",),
    ("Weather and climate (2)",),
    ("Major climate zones (3)",),
    ("Natural vegetation belts (3)",),
]
sheet("Sheet1", ["Syllabus Outline"], [list(r) for r in _MESSY]).save(
    OUT / "syllabus_messy_freetext.xlsx")

print("wrote:")
for p in sorted(OUT.iterdir()):
    if p.suffix in (".xlsx", ".txt"):
        print(f"  {p.name}")
