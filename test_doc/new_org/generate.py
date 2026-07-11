"""Generate the new-org setup test pack (run: cd api && uv run python ../test_doc/new_org/generate.py).

Clean, self-consistent mock data for walking a FRESH organisation through the whole
setup — no deliberate failure rows this time; every import should land 100%.

The org this pack assumes (see README.md for the step-by-step):
  year     2026-27 (2026-06-15 → 2027-04-15), Mon–Sat, 8 periods/day → 48 periods/week
  terms    Term 1 (2026-06-15 → 2026-10-31) · Term 2 (2026-11-01 → 2027-04-15)
  classes  5 · 6 · 7  (no sections)
  subjects Mathematics · Science · English · Social Studies · Hindi · IT

Periods/week per class: Math 9 + Sci 9 + Eng 8 + Soc 8 + Hin 7 + IT 7 = 48 (exactly full).
Five teachers, all weekly loads ≤ 48; Anil Kumar carries TWO subjects (Math + Science on
class 5). Every one of the 18 class-subjects has a teacher.
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


# ── 1. staff — 5 teachers · 18 assignments · every class sums to 48/48 ────────
sheet("teachers_staff.xlsx",
      ["Teacher Name", "Email", "Mobile", "Assignments"],
      [
          # THE two-subject teacher: Maths + Science on class 5 (18 periods/week).
          ["Anil Kumar", "anil.kumar@example.com", "9811100001",
           "5 Mathematics x9; 5 Science x9"],
          ["Sunita Verma", "sunita.verma@example.com", "9811100002",
           "6 Mathematics x9; 7 Mathematics x9"],
          ["Rajesh Gupta", "rajesh.gupta@example.com", "9811100003",
           "6 Science x9; 7 Science x9; 5 IT x7"],
          ["Priya Nair", "priya.nair@example.com", "9811100004",
           "5 English x8; 6 English x8; 7 English x8; 5 Hindi x7; 6 Hindi x7; 7 Hindi x7"],
          ["Mohan Reddy", "mohan.reddy@example.com", "9811100005",
           "5 Social Studies x8; 6 Social Studies x8; 7 Social Studies x8; 6 IT x7; 7 IT x7"],
      ])

# ── 2. students — exactly 10 per class, all rows valid ────────────────────────
first = ["Aarav", "Diya", "Vihaan", "Ananya", "Kabir", "Ishita", "Reyansh", "Sara",
         "Advait", "Myra"]
last = ["Sharma", "Patel", "Reddy", "Iyer", "Khan", "Das", "Gupta", "Nair", "Mehta", "Roy"]
rows = []
n = 1
for cname in ("5", "6", "7"):
    for i in range(10):
        rows.append([
            f"{first[i]} {last[(i + n) % 10]}", f"NG{1000 + n}", str(i + 1), cname, None,
            "Day Scholar" if i % 3 else "Hosteller",
            f"Mr {last[(i + n) % 10]}", f"98220{10000 + n}",
            f"Mrs {last[(i + n) % 10]}", f"98330{10000 + n}",
        ])
        n += 1
sheet("students_roster.xlsx",
      ["Student Name", "Admission No", "Roll No", "Class", "Section", "Category",
       "Father's Name", "Father's Mobile", "Mother's Name", "Mother's Mobile"],
      rows)


# ── 3. syllabus — one file per subject, reused on classes 5/6/7 ───────────────
# All topics sized so the final generate step locks everything cleanly. Each file
# carries a Term column (Term 1 / Term 2) so term-scoped planning has real data.
def syllabus(path: str, chapters: list[tuple[str, list[tuple[str, int]], str]]):
    body = []
    for ch, topics, term in chapters:
        for i, (t, p) in enumerate(topics):
            body.append([ch if i == 0 else None, t, p, term if i == 0 else None])
    sheet(path, ["Chapter", "Topic", "Periods", "Term"], body)


syllabus("syllabus_mathematics.xlsx", [  # 85 periods
    ("Knowing Our Numbers", [("Comparing large numbers", 4), ("Estimation", 3), ("Roman numerals", 2)], "Term 1"),
    ("Whole Numbers", [("Number line", 3), ("Properties of operations", 4)], "Term 1"),
    ("Playing with Numbers", [("Factors and multiples", 3), ("Divisibility rules", 3), ("HCF and LCM", 5)], "Term 1"),
    ("Basic Geometrical Ideas", [("Points, lines and curves", 3), ("Polygons and circles", 4)], "Term 1"),
    ("Integers", [("Negative numbers", 4), ("Operations on integers", 4)], "Term 1"),
    ("Fractions", [("Types of fractions", 5), ("Operations on fractions", 5)], "Term 2"),
    ("Decimals", [("Place value", 4), ("Operations on decimals", 4)], "Term 2"),
    ("Data Handling", [("Pictographs", 3), ("Bar graphs", 3)], "Term 2"),
    ("Mensuration", [("Perimeter", 4), ("Area", 4)], "Term 2"),
    ("Algebra", [("Variables", 3), ("Simple equations", 4)], "Term 2"),
    ("Ratio and Proportion", [("Ratio", 3), ("Unitary method", 3)], "Term 2"),
])

syllabus("syllabus_science.xlsx", [  # 82 periods
    ("Food: Where Does It Come From?", [("Food sources", 3), ("Plant and animal products", 3)], "Term 1"),
    ("Components of Food", [("Nutrients", 3), ("Balanced diet", 3), ("Deficiency diseases", 3)], "Term 1"),
    ("Fibre to Fabric", [("Plant fibres", 3), ("Spinning and weaving", 3)], "Term 1"),
    ("Sorting Materials", [("Properties of materials", 3), ("Grouping", 2)], "Term 1"),
    ("Separation of Substances", [("Sieving and winnowing", 3), ("Filtration and evaporation", 4)], "Term 1"),
    ("Changes Around Us", [("Reversible changes", 3), ("Irreversible changes", 3)], "Term 1"),
    ("Getting to Know Plants", [("Parts of a plant", 3), ("Leaf, stem and root", 3), ("Flower", 3)], "Term 2"),
    ("Body Movements", [("Joints", 3), ("Skeleton", 3), ("Animal movement", 2)], "Term 2"),
    ("Living Organisms", [("Habitats", 4), ("Adaptation", 3)], "Term 2"),
    ("Light, Shadows and Reflections", [("Sources of light", 3), ("Shadows", 3), ("Reflection", 3)], "Term 2"),
    ("Electricity and Circuits", [("Cells and bulbs", 4), ("Conductors and insulators", 4)], "Term 2"),
])

syllabus("syllabus_english.xlsx", [  # 70 periods
    ("Prose: A Tale of Two Birds", [("Reading and comprehension", 4), ("Vocabulary", 3)], "Term 1"),
    ("Grammar: Nouns and Pronouns", [("Kinds of nouns", 3), ("Pronoun usage", 3)], "Term 1"),
    ("Prose: The Friendly Mongoose", [("Reading and comprehension", 4), ("Character discussion", 3)], "Term 1"),
    ("Writing: Paragraphs", [("Structure of a paragraph", 3), ("Guided writing", 4)], "Term 1"),
    ("Poetry: A House, A Home", [("Recitation and meaning", 3), ("Appreciation", 2)], "Term 1"),
    ("Grammar: Verbs and Tenses", [("Simple tenses", 4), ("Subject-verb agreement", 3)], "Term 2"),
    ("Prose: The Shepherd's Treasure", [("Reading and comprehension", 4), ("Retelling", 3)], "Term 2"),
    ("Writing: Letters", [("Informal letters", 4), ("Formal letters", 4)], "Term 2"),
    ("Grammar: Adjectives and Adverbs", [("Degrees of comparison", 3), ("Adverb placement", 3)], "Term 2"),
    ("Poetry: The Kite", [("Recitation and meaning", 3), ("Imagery", 2)], "Term 2"),
])

syllabus("syllabus_social_studies.xlsx", [  # 72 periods
    ("History: What, Where, How and When", [("Sources of history", 3), ("Timelines", 3)], "Term 1"),
    ("History: Earliest Societies", [("Hunter-gatherers", 3), ("Tools and cave art", 3)], "Term 1"),
    ("Geography: The Earth in the Solar System", [("Planets and satellites", 3), ("The moon", 2)], "Term 1"),
    ("Geography: Globe — Latitudes and Longitudes", [("The grid", 4), ("Heat zones", 3)], "Term 1"),
    ("Civics: Understanding Diversity", [("Diversity around us", 3), ("Unity in diversity", 3)], "Term 1"),
    ("History: First Farmers and Herders", [("Beginnings of agriculture", 3), ("Settled life", 3)], "Term 2"),
    ("Geography: Motions of the Earth", [("Rotation and revolution", 4), ("Seasons", 3)], "Term 2"),
    ("Civics: Government", [("Levels of government", 3), ("Democratic government", 3)], "Term 2"),
    ("History: Kingdoms and an Early Republic", [("Janapadas", 3), ("Mahajanapadas", 3)], "Term 2"),
    ("Geography: Maps", [("Kinds of maps", 3), ("Map reading", 4)], "Term 2"),
    ("Civics: Panchayati Raj", [("Gram sabha", 3), ("Panchayat work", 3)], "Term 2"),
])

syllabus("syllabus_hindi.xlsx", [  # 62 periods
    ("Vah Chidiya Jo", [("Kavita vachan", 3), ("Bhavarth", 3)], "Term 1"),
    ("Bachpan", [("Path vachan", 3), ("Prashn uttar", 3)], "Term 1"),
    ("Vyakaran: Sangya aur Sarvanam", [("Sangya ke bhed", 3), ("Sarvanam prayog", 3)], "Term 1"),
    ("Nadaan Dost", [("Path vachan", 3), ("Charcha", 3)], "Term 1"),
    ("Lekhan: Anuchchhed", [("Anuchchhed lekhan", 3), ("Abhyas", 3)], "Term 1"),
    ("Chaand Se Thodi Si Gappe", [("Kavita vachan", 3), ("Bhavarth", 3)], "Term 2"),
    ("Vyakaran: Kriya aur Visheshan", [("Kriya ke bhed", 3), ("Visheshan prayog", 3)], "Term 2"),
    ("Saathi Haath Badhana", [("Geet vachan", 3), ("Charcha", 2)], "Term 2"),
    ("Lekhan: Patra", [("Anaupcharik patra", 4), ("Aupcharik patra", 4)], "Term 2"),
    ("Jo Dekhkar Bhi Nahin Dekhte", [("Path vachan", 3), ("Prashn uttar", 3)], "Term 2"),
])

syllabus("syllabus_it.xlsx", [  # 60 periods
    ("Introduction to Computers", [("Parts of a computer", 3), ("Uses of computers", 2)], "Term 1"),
    ("Operating the Computer", [("Desktop and files", 3), ("Keyboard and mouse skills", 3)], "Term 1"),
    ("Word Processing Basics", [("Creating a document", 4), ("Formatting text", 4)], "Term 1"),
    ("Paint and Drawing Tools", [("Drawing shapes", 3), ("Editing pictures", 3)], "Term 1"),
    ("Introduction to the Internet", [("What is the internet", 3), ("Safe browsing", 3)], "Term 2"),
    ("Spreadsheets Basics", [("Rows, columns and cells", 4), ("Simple formulas", 4)], "Term 2"),
    ("Presentations", [("Creating slides", 4), ("Presenting ideas", 3)], "Term 2"),
    ("Typing Practice", [("Home row practice", 3), ("Speed building", 3)], "Term 2"),
    ("Being Safe Online", [("Passwords and privacy", 3), ("Cyber etiquette", 2)], "Term 2"),
])
