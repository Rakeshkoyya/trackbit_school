"""Generate the new-org setup test pack (run: cd api && uv run python ../test_doc/new_org/generate.py).

A self-consistent set of documents for walking a FRESH organisation through the whole
setup wizard — including the V2-P12 features: x6 periods/week in staff assignments,
class allocation vs capacity, whole-school timetable generation, term-wise syllabus
with unsized Term-2 chapters, and the exam-gap fit panel.

Assumes the org will be set up with:
  year   2026-27 (2026-06-15 → 2027-04-15), Mon–Sat, 8 periods/day  → capacity 48/week
  terms  Term 1 (2026-06-15 → 2026-10-31) · Term 2 (2026-11-01 → 2027-04-15)
  classes  6-A · 6-B · 7-A
  subjects English · Mathematics · Science · Social Studies · Hindi
"""

from pathlib import Path

from openpyxl import Workbook

HERE = Path(__file__).parent


def sheet(path: str, header: list[str], rows: list[list]):
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(HERE / path)
    print(f"wrote {path} ({len(rows)} rows)")


# ── 1. staff: per class the x-numbers sum to exactly 48 (6 days × 8 periods) ──
sheet("teachers_staff.xlsx",
      ["Teacher Name", "Email", "Mobile", "Assignments"],
      [
          ["Suresh Menon", "suresh.menon@example.com", "9811100001",
           "6-A Mathematics x10; 6-B Mathematics x10; 7-A Mathematics x10"],
          ["Kavitha Rao", "kavitha.rao@example.com", "9811100002",
           "6-A Science x10; 6-B Science x10; 7-A Science x10"],
          ["Arjun Das", "arjun.das@example.com", "9811100003",
           "6-A English x10; 6-B English x10; 7-A English x10"],
          ["Meera Pillai", "meera.pillai@example.com", "9811100004",
           "6-A Social Studies x9; 6-B Social Studies x9; 7-A Social Studies x9"],
          ["Farhan Sheikh", "farhan.sheikh@example.com", "9811100005",
           "6-A Hindi x9; 6-B Hindi x9"],
          # 9-C Astronomy must come back in `unresolved`; 7-A Hindi still lands.
          ["Divya Nair", "divya.nair@example.com", "9811100006",
           "9-C Astronomy x4; 7-A Hindi x9"],
          # No name → must land in `errors`, everything else still imports.
          [None, "ghost@example.com", "9811100007", "6-A English x2"],
      ])

# ── 2. students: 10 per class + 3 deliberate failures ─────────────────────────
first = ["Aarav", "Diya", "Vihaan", "Ananya", "Kabir", "Ishita", "Reyansh", "Sara",
         "Advait", "Myra"]
last = ["Sharma", "Patel", "Reddy", "Iyer", "Khan", "Das", "Gupta", "Nair", "Mehta", "Roy"]
rows = []
n = 1
for cname, section in (("6", "A"), ("6", "B"), ("7", "A")):
    for i in range(10):
        rows.append([
            f"{first[i]} {last[(i + n) % 10]}", f"NG{1000 + n}", str(i + 1), cname, section,
            "Day Scholar" if i % 3 else "Hosteller",
            f"Mr {last[(i + n) % 10]}", f"98220{10000 + n}",
            f"Mrs {last[(i + n) % 10]}", f"98330{10000 + n}",
        ])
        n += 1
rows += [
    # Class 8-A doesn't exist → imports UNASSIGNED (visible in Students → no class).
    ["Zoya Ansari", "NG1901", "1", "8", "A", "Day Scholar",
     "Mr Ansari", "9822099001", "Mrs Ansari", "9833099001"],
    # Missing name → errors.
    [None, "NG1902", "2", "6", "A", "Day Scholar", "Mr X", "9822099002", None, None],
    # Missing admission no → errors.
    ["Rohan Kulkarni", None, "3", "6", "B", "Day Scholar", "Mr Kulkarni", "9822099003", None, None],
]
sheet("students_roster.xlsx",
      ["Student Name", "Admission No", "Roll No", "Class", "Section", "Category",
       "Father's Name", "Father's Mobile", "Mother's Name", "Mother's Mobile"],
      rows)

# ── 3. syllabus: maths, term-wise — Term 2 deliberately UNSIZED ───────────────
# Import against each class's Mathematics. Term 1 ≈ 52 periods; Term 2 has blank
# Periods cells → est_periods NULL → V6 reports them, forecast says `unplanned`,
# and the wizard finishes with those plans open (size them when Term 2 begins).
maths = [
    ("Knowing Our Numbers", ["Comparing large numbers", "Estimation", "Roman numerals"],
     [4, 3, 2], "Term 1"),
    ("Whole Numbers", ["Number line", "Properties of operations"], [3, 4], "Term 1"),
    ("Playing with Numbers", ["Factors and multiples", "Divisibility rules", "HCF and LCM"],
     [3, 3, 5], "Term 1"),
    ("Basic Geometrical Ideas", ["Points, lines, curves", "Polygons and circles"], [3, 4], "Term 1"),
    ("Integers", ["Negative numbers", "Addition and subtraction of integers"], [4, 4], "Term 1"),
    ("Fractions", ["Types of fractions", "Operations on fractions"], [5, 5], "Term 1"),
    ("Decimals", ["Place value", "Operations on decimals"], [None, None], "Term 2"),
    ("Data Handling", ["Pictographs", "Bar graphs"], [None, None], "Term 2"),
    ("Mensuration", ["Perimeter", "Area"], [None, None], "Term 2"),
    ("Algebra", ["Variables", "Simple equations"], [None, None], "Term 2"),
    ("Ratio and Proportion", ["Ratio", "Unitary method"], [None, None], "Term 2"),
]
sheet("syllabus_maths_termwise.xlsx",
      ["Chapter", "Topic", "Periods", "Term"],
      [[ch if i == 0 else None, t, p, term if i == 0 else None]
       for ch, topics, per, term in maths
       for i, (t, p) in enumerate(zip(topics, per))])

# ── 4. syllabus: science — fully sized, whole year (≈84 periods) ──────────────
science = [
    ("Food: Where Does It Come From?", ["Food sources", "Plant and animal products"], [3, 3]),
    ("Components of Food", ["Nutrients", "Balanced diet", "Deficiency diseases"], [3, 3, 3]),
    ("Fibre to Fabric", ["Plant fibres", "Spinning and weaving"], [3, 3]),
    ("Sorting Materials", ["Properties of materials", "Grouping"], [3, 2]),
    ("Separation of Substances", ["Sieving and winnowing", "Filtration and evaporation"], [3, 4]),
    ("Changes Around Us", ["Reversible changes", "Irreversible changes"], [3, 3]),
    ("Getting to Know Plants", ["Parts of a plant", "Leaf, stem and root", "Flower"], [3, 3, 3]),
    ("Body Movements", ["Joints", "Skeleton", "Animal movement"], [3, 3, 2]),
    ("Living Organisms", ["Habitats", "Adaptation"], [4, 3]),
    ("Light, Shadows and Reflections", ["Sources of light", "Shadows", "Reflection"], [3, 3, 3]),
    ("Electricity and Circuits", ["Cells and bulbs", "Conductors and insulators"], [4, 4]),
]
sheet("syllabus_science.xlsx",
      ["Chapter", "Topic", "Periods"],
      [[ch if i == 0 else None, t, p]
       for ch, topics, per in science for i, (t, p) in enumerate(zip(topics, per))])

# ── 5. syllabus: generic, reusable for English / Social Studies / Hindi ───────
generic = [
    ("Unit 1", ["Introduction and reading", "Vocabulary building", "Writing practice"], [4, 3, 3]),
    ("Unit 2", ["Comprehension", "Grammar focus", "Speaking activity"], [4, 3, 3]),
    ("Unit 3", ["Reading and discussion", "Grammar focus", "Writing practice"], [4, 3, 3]),
    ("Unit 4", ["Comprehension", "Vocabulary building", "Project work"], [4, 3, 4]),
    ("Unit 5", ["Reading and discussion", "Grammar focus", "Revision"], [4, 3, 3]),
    ("Unit 6", ["Comprehension", "Writing practice", "Assessment prep"], [4, 3, 3]),
    ("Unit 7", ["Reading and discussion", "Speaking activity", "Revision"], [4, 3, 3]),
]
sheet("syllabus_generic.xlsx",
      ["Chapter", "Topic", "Periods"],
      [[ch if i == 0 else None, t, p]
       for ch, topics, per in generic for i, (t, p) in enumerate(zip(topics, per))])

# ── 6. syllabus paste-text path: trailing (n) → est_periods ───────────────────
(HERE / "syllabus_hindi.txt").write_text("""Chapter 1: Varnamala
Swar aur vyanjan (3)
Matra parichay (4)
Chapter 2: Shabd Rachna
Shabd banana (3)
Vakya rachna (4)
Chapter 3: Kahani Path
Kahani vachan (4)
Prashn uttar (3)
Chapter 4: Vyakaran
Sangya (3)
Sarvanam (3)
Kriya (3)
Chapter 5: Rachnatmak Lekhan
Patra lekhan (4)
Anuchchhed lekhan (4)
""", encoding="utf-8")
print("wrote syllabus_hindi.txt")
