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


# ── 3. syllabus — one file PER CLASS PER SUBJECT (18 files) ───────────────────
# Grade-appropriate chapters for each class. All topics sized so the final
# generate step locks everything cleanly; every file carries a Term column
# (Term 1 / Term 2) so term-scoped planning has real data.
def syllabus(path: str, chapters: list[tuple[str, list[tuple[str, int]], str]]):
    body = []
    for ch, topics, term in chapters:
        for i, (t, p) in enumerate(topics):
            body.append([ch if i == 0 else None, t, p, term if i == 0 else None])
    sheet(path, ["Chapter", "Topic", "Periods", "Term"], body)


syllabus("syllabus_6_mathematics.xlsx", [  # 85 periods
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

syllabus("syllabus_6_science.xlsx", [  # 82 periods
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

syllabus("syllabus_6_english.xlsx", [  # 70 periods
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

syllabus("syllabus_6_social_studies.xlsx", [  # 72 periods
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

syllabus("syllabus_6_hindi.xlsx", [  # 62 periods
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

syllabus("syllabus_6_it.xlsx", [  # 60 periods
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

syllabus("syllabus_5_mathematics.xlsx", [  # 80 periods
    ("Numbers Up To Crores", [("Reading large numbers", 4), ("Place value", 3)], "Term 1"),
    ("Addition and Subtraction", [("Column methods", 3), ("Word problems", 4)], "Term 1"),
    ("Multiplication and Division", [("Multiplying big numbers", 4), ("Long division", 4)], "Term 1"),
    ("Factors and Multiples", [("Finding factors", 3), ("Common multiples", 3)], "Term 1"),
    ("Fractions", [("Equivalent fractions", 4), ("Adding fractions", 4)], "Term 1"),
    ("Decimals", [("Tenths and hundredths", 4), ("Money and measurement", 4)], "Term 2"),
    ("Shapes and Angles", [("Kinds of angles", 3), ("Measuring angles", 3)], "Term 2"),
    ("Area and Perimeter", [("Perimeter of rectangles", 4), ("Area by counting squares", 4)], "Term 2"),
    ("Data Handling", [("Tally marks", 3), ("Reading bar charts", 3)], "Term 2"),
    ("Patterns and Symmetry", [("Number patterns", 3), ("Lines of symmetry", 3)], "Term 2"),
])

syllabus("syllabus_5_science.xlsx", [  # 76 periods
    ("Super Senses", [("How animals sense", 3), ("Comparing senses", 3)], "Term 1"),
    ("Plants Around Us", [("Parts of a plant", 3), ("How seeds travel", 3)], "Term 1"),
    ("Water", [("Sources of water", 3), ("Saving water", 3)], "Term 1"),
    ("Food and Health", [("What we eat", 3), ("Good food habits", 3)], "Term 1"),
    ("Shelter", [("Kinds of houses", 3), ("Animals and shelter", 3)], "Term 1"),
    ("Air Around Us", [("Air is everywhere", 3), ("Clean and dirty air", 3)], "Term 2"),
    ("Simple Machines", [("Levers and wheels", 4), ("Machines at home", 3)], "Term 2"),
    ("Earth and Sky", [("Day and night", 3), ("The moon and stars", 3)], "Term 2"),
    ("Materials Around Us", [("Solids, liquids, gases", 4), ("Mixing and dissolving", 3)], "Term 2"),
    ("Keeping Safe", [("Safety at home and school", 3), ("First aid basics", 3)], "Term 2"),
])

syllabus("syllabus_5_english.xlsx", [  # 66 periods
    ("Prose: Wonderful Waste", [("Reading and comprehension", 4), ("New words", 3)], "Term 1"),
    ("Poetry: Ice-cream Man", [("Recitation", 3), ("Rhyme and rhythm", 2)], "Term 1"),
    ("Grammar: Nouns and Articles", [("Naming words", 3), ("A, an, the", 3)], "Term 1"),
    ("Prose: Flying Together", [("Reading and comprehension", 4), ("Story discussion", 3)], "Term 1"),
    ("Writing: Sentences", [("Making sentences", 3), ("Punctuation", 3)], "Term 1"),
    ("Grammar: Verbs and Tenses", [("Action words", 3), ("Past and present", 3)], "Term 2"),
    ("Prose: The Talkative Barber", [("Reading and comprehension", 4), ("Retelling", 3)], "Term 2"),
    ("Writing: Short Paragraphs", [("My family", 3), ("My school day", 3)], "Term 2"),
    ("Poetry: Class Discussion", [("Recitation", 3), ("Meaning", 2)], "Term 2"),
    ("Grammar: Describing Words", [("Adjectives", 3), ("Opposites", 2)], "Term 2"),
])

syllabus("syllabus_5_social_studies.xlsx", [  # 68 periods
    ("Maps and Globes", [("Reading a map", 4), ("Directions and symbols", 3)], "Term 1"),
    ("Our Country India", [("States and capitals", 4), ("Physical features", 3)], "Term 1"),
    ("Weather and Climate", [("Seasons of India", 3), ("Weather around us", 3)], "Term 1"),
    ("Natural Resources", [("Land and soil", 3), ("Forests and wildlife", 3)], "Term 1"),
    ("Transport and Communication", [("Means of transport", 3), ("Staying in touch", 3)], "Term 1"),
    ("Our Government", [("Local bodies", 3), ("Why rules matter", 3)], "Term 2"),
    ("Great Personalities", [("Freedom fighters", 4), ("Social reformers", 3)], "Term 2"),
    ("The Environment", [("Pollution", 3), ("Protecting nature", 3)], "Term 2"),
    ("Our Festivals and Culture", [("Festivals of India", 3), ("Unity in diversity", 3)], "Term 2"),
    ("Disasters and Safety", [("Floods and earthquakes", 3), ("Being prepared", 3)], "Term 2"),
])

syllabus("syllabus_5_hindi.xlsx", [  # 58 periods
    ("Raakh Ki Rassi", [("Kahani vachan", 3), ("Prashn uttar", 3)], "Term 1"),
    ("Fasalon Ke Tyohar", [("Path vachan", 3), ("Charcha", 3)], "Term 1"),
    ("Vyakaran: Varn aur Shabd", [("Varnamala", 3), ("Shabd rachna", 3)], "Term 1"),
    ("Khilonewala", [("Kavita vachan", 3), ("Bhavarth", 3)], "Term 1"),
    ("Lekhan: Chitra Varnan", [("Chitra dekh kar likhna", 3), ("Abhyas", 2)], "Term 1"),
    ("Nanha Fankar", [("Kahani vachan", 3), ("Prashn uttar", 3)], "Term 2"),
    ("Vyakaran: Ling aur Vachan", [("Ling badlo", 3), ("Vachan badlo", 3)], "Term 2"),
    ("Jahan Chah Wahan Raah", [("Path vachan", 3), ("Charcha", 2)], "Term 2"),
    ("Lekhan: Apathit Gadyansh", [("Gadyansh abhyas", 3), ("Prashn likhna", 3)], "Term 2"),
    ("Swami Ki Dadi", [("Kahani vachan", 3), ("Prashn uttar", 2)], "Term 2"),
])

syllabus("syllabus_5_it.xlsx", [  # 56 periods
    ("Meet the Computer", [("Parts of a computer", 3), ("Dos and don'ts", 2)], "Term 1"),
    ("Working with the Mouse and Keyboard", [("Mouse skills", 3), ("Typing letters", 3)], "Term 1"),
    ("Fun with Paint", [("Drawing shapes", 3), ("Colouring pictures", 3)], "Term 1"),
    ("Storing Our Work", [("Files and folders", 3), ("Saving and opening", 3)], "Term 1"),
    ("Word Processing for Kids", [("Typing a story", 4), ("Making it pretty", 3)], "Term 2"),
    ("Computers Around Us", [("Where computers help", 3), ("People who use them", 2)], "Term 2"),
    ("Introduction to the Internet", [("What is a website", 3), ("Searching safely", 3)], "Term 2"),
    ("Typing Practice", [("Home row keys", 3), ("Simple words", 3)], "Term 2"),
    ("Being Safe with Screens", [("Screen time rules", 3), ("Asking an adult", 2)], "Term 2"),
])

syllabus("syllabus_7_mathematics.xlsx", [  # 88 periods
    ("Integers", [("Properties of integers", 4), ("Multiplication and division", 4)], "Term 1"),
    ("Fractions and Decimals", [("Multiplying fractions", 4), ("Decimal operations", 4)], "Term 1"),
    ("Data Handling", [("Mean, median, mode", 4), ("Bar graphs and chance", 3)], "Term 1"),
    ("Simple Equations", [("Setting up equations", 4), ("Solving equations", 4)], "Term 1"),
    ("Lines and Angles", [("Pairs of angles", 3), ("Parallel lines", 3)], "Term 1"),
    ("The Triangle and Its Properties", [("Medians and altitudes", 3), ("Angle sum property", 4)], "Term 2"),
    ("Comparing Quantities", [("Percentages", 4), ("Profit, loss and interest", 4)], "Term 2"),
    ("Rational Numbers", [("On the number line", 3), ("Operations", 4)], "Term 2"),
    ("Perimeter and Area", [("Area of triangles", 4), ("Circles", 4)], "Term 2"),
    ("Algebraic Expressions", [("Terms and coefficients", 3), ("Adding expressions", 3)], "Term 2"),
    ("Exponents and Powers", [("Laws of exponents", 3), ("Standard form", 2)], "Term 2"),
])

syllabus("syllabus_7_science.xlsx", [  # 84 periods
    ("Nutrition in Plants", [("Photosynthesis", 4), ("Other modes of nutrition", 3)], "Term 1"),
    ("Nutrition in Animals", [("Digestion in humans", 4), ("Digestion in grass-eaters", 3)], "Term 1"),
    ("Heat", [("Hot and cold", 3), ("Transfer of heat", 4)], "Term 1"),
    ("Acids, Bases and Salts", [("Indicators", 3), ("Neutralisation", 3)], "Term 1"),
    ("Physical and Chemical Changes", [("Kinds of changes", 3), ("Rusting and crystallisation", 3)], "Term 1"),
    ("Weather, Climate and Adaptations", [("Weather vs climate", 3), ("Animals in extreme climates", 3)], "Term 1"),
    ("Winds, Storms and Cyclones", [("Air pressure", 3), ("Staying safe in storms", 3)], "Term 2"),
    ("Soil", [("Soil profile", 3), ("Soil and crops", 3)], "Term 2"),
    ("Respiration in Organisms", [("Why we breathe", 3), ("Breathing in animals", 3)], "Term 2"),
    ("Electric Current and Its Effects", [("Heating effect", 4), ("Magnetic effect", 3)], "Term 2"),
    ("Light", [("Reflection", 4), ("Images and mirrors", 4)], "Term 2"),
])

syllabus("syllabus_7_english.xlsx", [  # 72 periods
    ("Prose: Three Questions", [("Reading and comprehension", 4), ("Theme discussion", 3)], "Term 1"),
    ("Grammar: Determiners and Modals", [("Using determiners", 3), ("Modal verbs", 3)], "Term 1"),
    ("Prose: A Gift of Chappals", [("Reading and comprehension", 4), ("Character study", 3)], "Term 1"),
    ("Writing: Notice and Message", [("Notice writing", 3), ("Message writing", 3)], "Term 1"),
    ("Poetry: The Squirrel", [("Recitation and meaning", 3), ("Poetic devices", 2)], "Term 1"),
    ("Grammar: Active and Passive Voice", [("Forming the passive", 4), ("Practice", 3)], "Term 2"),
    ("Prose: Quality", [("Reading and comprehension", 4), ("Discussion", 3)], "Term 2"),
    ("Writing: Formal Letters", [("Applications", 4), ("Letters of complaint", 3)], "Term 2"),
    ("Grammar: Reported Speech", [("Statements", 3), ("Questions and commands", 3)], "Term 2"),
    ("Poetry: The Rebel", [("Recitation and meaning", 3), ("Tone and humour", 2)], "Term 2"),
])

syllabus("syllabus_7_social_studies.xlsx", [  # 74 periods
    ("History: Tracing Changes Through a Thousand Years", [("New maps and sources", 3), ("Time and periods", 3)], "Term 1"),
    ("History: New Kings and Kingdoms", [("Emergence of dynasties", 3), ("Warfare and forts", 3)], "Term 1"),
    ("Geography: Environment", [("Components of environment", 3), ("Human environment", 3)], "Term 1"),
    ("Geography: Inside Our Earth", [("Layers of the earth", 3), ("Rocks and minerals", 3)], "Term 1"),
    ("Civics: On Equality", [("Equal right to vote", 3), ("Struggles for equality", 3)], "Term 1"),
    ("History: The Delhi Sultans", [("Rulers of Delhi", 4), ("Administration", 3)], "Term 2"),
    ("Geography: Our Changing Earth", [("Earth movements", 3), ("Work of rivers and wind", 4)], "Term 2"),
    ("Civics: Role of the Government in Health", [("Public and private health", 3), ("Healthcare for all", 3)], "Term 2"),
    ("History: The Mughal Empire", [("Mughal rulers", 4), ("Mansabdars and jagirs", 3)], "Term 2"),
    ("Geography: Air", [("Composition of atmosphere", 3), ("Weather instruments", 3)], "Term 2"),
    ("Civics: How the State Government Works", [("MLAs and assemblies", 3), ("The executive", 3)], "Term 2"),
])

syllabus("syllabus_7_hindi.xlsx", [  # 64 periods
    ("Hum Panchhi Unmukt Gagan Ke", [("Kavita vachan", 3), ("Bhavarth", 3)], "Term 1"),
    ("Dadi Maa", [("Kahani vachan", 3), ("Prashn uttar", 3)], "Term 1"),
    ("Vyakaran: Sandhi Parichay", [("Swar sandhi", 3), ("Abhyas", 3)], "Term 1"),
    ("Himalaya Ki Betiyan", [("Path vachan", 3), ("Charcha", 3)], "Term 1"),
    ("Lekhan: Nibandh", [("Rooprekha banana", 3), ("Nibandh lekhan", 3)], "Term 1"),
    ("Kathputli", [("Kavita vachan", 3), ("Bhavarth", 3)], "Term 2"),
    ("Vyakaran: Muhavare", [("Muhavare arth sahit", 3), ("Vakya prayog", 3)], "Term 2"),
    ("Mithaiwala", [("Kahani vachan", 3), ("Prashn uttar", 3)], "Term 2"),
    ("Lekhan: Samvad", [("Samvad lekhan", 3), ("Abhyas", 3)], "Term 2"),
    ("Ek Tinka", [("Kavita vachan", 3), ("Bhavarth", 2)], "Term 2"),
])

syllabus("syllabus_7_it.xlsx", [  # 62 periods
    ("Computer Systems Revisited", [("Hardware and software", 3), ("Input-process-output", 3)], "Term 1"),
    ("Advanced Word Processing", [("Tables and images", 4), ("Page layout", 3)], "Term 1"),
    ("Spreadsheets", [("Formulas and functions", 4), ("Sorting and filtering", 3)], "Term 1"),
    ("Charts and Graphs", [("Making charts", 3), ("Choosing the right chart", 3)], "Term 1"),
    ("Presentations That Work", [("Slide design", 4), ("Presenting to the class", 3)], "Term 2"),
    ("Introduction to Coding", [("Block coding basics", 4), ("Making a small game", 4)], "Term 2"),
    ("Internet Research Skills", [("Finding reliable information", 3), ("Citing sources", 3)], "Term 2"),
    ("Email and Communication", [("Writing an email", 3), ("Netiquette", 2)], "Term 2"),
    ("Cyber Safety", [("Strong passwords", 3), ("Recognising scams", 4)], "Term 2"),
])
