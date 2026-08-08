"""The setup pack's sheet definitions — the single source of truth for both
directions (SETUP-REDESIGN-PLAN §4, D-1…D-8).

The blank workbook the school fills in and the parser that reads it back are
generated from *these* objects, so a template can never drift from its reader.
`templates.py` established that rule for the three standalone importers and
`test_setup_onboarding.py` asserts it; the pack keeps it.

Conventions every sheet obeys, stated once here and repeated to the school on the
Read Me:

  * **A blank cell means "not known yet"** — never zero, never one. A chapter with
    no `Periods` is unsized (`est_periods = NULL`), which is the honest reading of a
    Term-3 chapter in August. A school that has only planned half the year hands us
    half the year and adds the rest later (D-4).
  * **A blank `Section` means every section of that class.** A school with 6-A and
    6-B writes its syllabus once.
  * **Dates are day-first, dd/mm/yyyy** — what Indian registers write. `parse_dob`
    already refuses to silently swap day and month, and this pack does not change
    that (D-13).
  * **Every sheet carries an academic-year context**, because the pack is scoped to
    one year. The new-year rollover is deferred (D-8), not designed away.
"""

from dataclasses import dataclass, field

# Sheets are matched to the workbook by title, so these names are load-bearing.
# The parser normalises case, punctuation and dash variants before comparing —
# a school that renames "Read Me" to "READ-ME" is not an error worth failing on.
READ_ME = "Read Me"


@dataclass(frozen=True)
class Column:
    """One column of a table sheet.

    `hints` are the header spellings we accept. They exist because schools rename
    headers — the reference file calls a chapter "Chapter Name" and a teacher
    "Mentor". Order them most specific first: the mapper takes exact matches
    before substring matches, but among substrings the first hint wins.
    """

    key: str
    header: str
    hints: tuple[str, ...]
    note: str
    example: str = ""
    required: bool = False
    # A fixed value set becomes an Excel dropdown, which is worth more than any
    # amount of Read Me prose for a column like Role or Type.
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Setting:
    """One row of the key/value `School` sheet (Field | Value)."""

    key: str
    label: str
    hints: tuple[str, ...]
    note: str
    example: str = ""
    required: bool = False
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class SheetSpec:
    key: str
    title: str
    required: bool
    blurb: str
    columns: tuple[Column, ...] = ()
    settings: tuple[Setting, ...] = ()
    # Extra example rows for the sample pack (tests and test_doc/new_org). The
    # blank pack the school receives ships with headers only — a school that
    # returns our example rows would import "Aarav Sharma" into its register.
    samples: tuple[tuple[str, ...], ...] = ()

    @property
    def is_key_value(self) -> bool:
        return bool(self.settings)

    @property
    def required_keys(self) -> list[str]:
        source = self.settings or self.columns
        return [c.key for c in source if c.required]


# ── 1. School ────────────────────────────────────────────────────────────────
# Key/value rather than a table: fifteen one-off facts read far better down a
# page than across one very wide row.
SCHOOL = SheetSpec(
    key="school",
    title="School",
    required=True,
    blurb="The school itself, its academic year, and the daily bell schedule.",
    settings=(
        Setting("school_name", "School name", ("school name", "name of school", "school"),
                "As it should appear on every screen and report.",
                "Sunrise Public School", required=True),
        Setting("address", "Address", ("address", "school address", "location"),
                "Full postal address."),
        Setting("state", "State", ("state", "province"),
                "Used to pick the right public-holiday list. The school is never "
                "asked to declare a region or a religion.", "Karnataka"),
        Setting("board", "Board", ("board", "affiliation", "curriculum"),
                "CBSE / ICSE / State board.", "CBSE"),
        # The government/board code — and the code parents type to find the
        # school at login (founder, 2026-08-08). It replaces the random one we
        # used to mint: a parent does not know a random code, they know their
        # school's real one, and the login screen lets them search for it.
        # Entered ONCE, here. There is no edit screen anywhere by design — a
        # wrong code is fixed by re-uploading this pack, which only we can do.
        Setting("school_code", "School code",
                ("school code", "affiliation no", "affiliation number",
                 "udise", "udise code", "code"),
                "The school's official code — the one parents will type to find "
                "you at login. Must be unique. Leave blank and we mint one.",
                "KA1234567"),
        Setting("year_label", "Academic year", ("academic year", "year", "session"),
                "How the school writes it.", "2026-27", required=True),
        Setting("year_start", "Year starts", ("year starts", "start date", "session start",
                                              "from"),
                "First day of the academic year. dd/mm/yyyy.", "01/06/2026",
                required=True),
        Setting("year_end", "Year ends", ("year ends", "end date", "session end", "to"),
                "Last day of the academic year. dd/mm/yyyy.", "30/04/2027",
                required=True),
        Setting("tracking_start", "Tracking starts from",
                ("tracking starts", "tracking start", "go live", "start tracking"),
                "The day TrackBit begins capturing. Leave blank if that is the first "
                "day of the year. Fill it if the school is joining mid-year — a June "
                "school onboarded in August puts August here.", "10/08/2026"),
        Setting("working_days", "Working days", ("working days", "week days", "days"),
                "Which days the school runs. Mon-Sat or Mon-Fri.", "Mon-Sat",
                choices=("Mon-Fri", "Mon-Sat", "Mon-Sun")),
        Setting("periods_per_day", "Periods per day",
                ("periods per day", "no of periods", "periods", "number of periods"),
                "Teaching periods in one full day.", "8", required=True),
        Setting("first_period_start", "First period starts",
                ("first period starts", "school starts", "start time", "first period"),
                "24-hour clock.", "08:30"),
        Setting("period_minutes", "Period length (minutes)",
                ("period length", "period duration", "minutes per period", "duration"),
                "How many minutes one period runs.", "40"),
        Setting("lunch_after_period", "Lunch after period",
                ("lunch after period", "lunch after", "break after"),
                "Lunch falls after this period number.", "4"),
        Setting("lunch_minutes", "Lunch length (minutes)",
                ("lunch length", "lunch duration", "lunch minutes", "break length"),
                "How many minutes the lunch break runs.", "30"),
        Setting("parent_portal", "Parent portal",
                ("parent portal", "portal", "parent login"),
                "Should parents be able to log in and see their own child?", "Yes",
                choices=("Yes", "No")),
    ),
)

# ── 2. Terms ─────────────────────────────────────────────────────────────────
# A term IS its exam (founder, 2026-08-08). The school gives one date range —
# when the term exam runs — and everything else follows from it:
#
#   * the term ENDS on the exam's last day, and starts the day after the previous
#     term's exam ended (the first starts with the year);
#   * an `exam_block` sits on those dates, so the planner already treats them as
#     non-teaching and paces the syllabus into the days before;
#   * every chapter filed under the term is what that exam examines — the portion
#     needs no separate statement.
#
# Terms and exams used to be two sheets and two tables linked only by date
# overlap, which is why a school could read "2 terms" beside "5 exams" and both
# be right. One statement now, and the 31 modules that read `Term` inherit it
# without knowing anything changed.
TERMS = SheetSpec(
    key="terms",
    title="Terms",
    required=True,
    blurb="The year's terms, each ended by its exam. Give the exam's dates — the "
          "term is the stretch of teaching that leads up to it.",
    columns=(
        Column("term_name", "Term", ("term", "term name", "semester", "part"),
               "Exactly as the school says it. The Syllabus sheet must use the "
               "same spelling.", "Term 1", required=True),
        Column("exam_name", "Exam", ("exam", "exam name", "assessment", "test"),
               "What the school calls this term's exam. Left blank, the term's "
               "own name is used.", "Half-yearly"),
        Column("exam_start", "Exam starts",
               ("exam starts", "exam start", "exam from", "starts", "from"),
               "First day of the exam. dd/mm/yyyy.", "22/09/2026", required=True),
        Column("exam_end", "Exam ends",
               ("exam ends", "exam end", "exam to", "ends", "to"),
               "Last day of the exam — and the last day of the term. Teaching for "
               "the next term begins the day after.", "27/09/2026", required=True),
    ),
    samples=(
        ("Term 1", "Half-yearly", "22/09/2026", "27/09/2026"),
        ("Term 2", "Annual", "20/04/2027", "25/04/2027"),
    ),
)

# ── 3. Classes ───────────────────────────────────────────────────────────────
CLASSES = SheetSpec(
    key="classes",
    title="Classes",
    required=True,
    blurb="One row per class-and-section the school actually runs.",
    columns=(
        Column("class_name", "Class", ("class", "grade", "standard", "std"),
               "Just the number or name — 6, not 'Class 6'.", "6", required=True),
        Column("section", "Section", ("section", "sec", "division", "div"),
               "Leave blank if the class has no sections.", "A"),
        Column("class_teacher", "Class teacher",
               ("class teacher", "classteacher", "homeroom", "in charge", "incharge"),
               "The name exactly as written on the Staff sheet. The class teacher "
               "owns absence follow-ups for this class.", "Anita Desai"),
    ),
    samples=(
        ("6", "A", "Anita Desai"),
        ("6", "B", "Vikram Rao"),
        ("7", "A", "Sunita Iyer"),
    ),
)

# ── 4. Staff ─────────────────────────────────────────────────────────────────
STAFF = SheetSpec(
    key="staff",
    title="Staff",
    required=True,
    blurb="Everyone who logs in. Wardens and coordinators are teachers here — "
          "there are only two roles.",
    columns=(
        Column("full_name", "Name", ("teacher name", "staff name", "name", "full name",
                                     "employee name"),
               "Full name, spelled the same way everywhere else in this pack.",
               "Anita Desai", required=True),
        Column("employee_id", "Employee ID",
               ("employee id", "emp id", "staff id", "username", "code"),
               "The school's own staff code. Becomes the login username. Left blank, "
               "one is generated from the name.", "anita.desai"),
        Column("email", "Email", ("email", "e-mail", "mail id", "email id"),
               "Where the invitation and password resets go.",
               "anita@school.example"),
        Column("phone", "Phone", ("phone", "mobile", "contact", "mobile no"),
               "10-digit mobile.", "9876501234"),
        Column("date_of_birth", "Date of birth",
               ("date of birth", "dob", "d.o.b", "birth date", "born"),
               "dd/mm/yyyy. Feeds the staff birthday feed — optional.",
               "03/07/1988"),
        Column("role", "Role", ("role", "designation", "type", "post"),
               "Admin runs the school; Teacher covers all academic staff including "
               "wardens.", "Teacher", choices=("Teacher", "Admin")),
    ),
    samples=(
        ("Anita Desai", "anita.desai", "anita@school.example", "9876501234",
         "03/07/1988", "Teacher"),
        ("Vikram Rao", "vikram.rao", "vikram@school.example", "9876501235",
         "21/12/1990", "Teacher"),
        ("Sunita Iyer", "sunita.iyer", "sunita@school.example", "9876501236", "",
         "Teacher"),
    ),
)

# ── 5. Teaching assignments ──────────────────────────────────────────────────
# Replaces the packed "6-A Mathematics x6; 7-A Mathematics x6" string the old
# staff template asked for — a syntax schools mistype. One assignment, one row.
ASSIGNMENTS = SheetSpec(
    key="assignments",
    title="Teaching Assignments",
    required=True,
    blurb="Who teaches what, and how many periods a week it gets. This sheet "
          "creates the subject list — there is no separate Subjects sheet.",
    columns=(
        Column("class_name", "Class", ("class", "grade", "standard", "std"),
               "As on the Classes sheet.", "6", required=True),
        Column("section", "Section", ("section", "sec", "division", "div"),
               "Blank means every section of that class.", "A"),
        Column("subject", "Subject", ("subject", "subject name", "paper"),
               "Spelled the same way on the Syllabus and Timetable sheets.",
               "Mathematics", required=True),
        Column("teacher", "Teacher", ("teacher", "mentor", "faculty", "teacher name",
                                      "taught by"),
               "The name exactly as on the Staff sheet. Blank means nobody is "
               "assigned yet — that is a state we can hand over with.",
               "Anita Desai"),
        Column("periods_per_week", "Periods per week",
               ("periods per week", "periods", "per week", "weekly periods", "ppw"),
               "The weekly budget the plan paces against. Blank means not decided "
               "yet — never 0.", "6"),
    ),
    samples=(
        ("6", "A", "Mathematics", "Anita Desai", "6"),
        ("6", "A", "Science", "Vikram Rao", "5"),
        ("6", "B", "Mathematics", "Anita Desai", "6"),
    ),
)

# ── 6. Syllabus ──────────────────────────────────────────────────────────────
# ONE sheet for the whole school (D-5). The founder's reference file keeps one
# sheet per class with a Subject column and no Topic column at all — so Topic is
# optional here, and a chapter with no topics becomes one topic named for the
# chapter, carrying the chapter's periods.
SYLLABUS = SheetSpec(
    key="syllabus",
    title="Syllabus",
    required=True,
    blurb="Every chapter the school will teach this year, for every class and "
          "subject, on one sheet. Half a year is fine — add the rest later.",
    columns=(
        Column("class_name", "Class", ("class", "grade", "standard", "std"),
               "As on the Classes sheet.", "6", required=True),
        Column("section", "Section", ("section", "sec", "division", "div"),
               "Blank means every section of that class — most schools teach the "
               "same syllabus to 6-A and 6-B, so leave it blank.", ""),
        Column("subject", "Subject", ("subject", "subject name", "paper"),
               "As on the Teaching Assignments sheet.", "Mathematics",
               required=True),
        Column("term", "Term", ("term", "semester", "part"),
               "Exactly as named on the Terms sheet. Blank continues the term "
               "above. A term the school has not planned yet is simply absent.",
               "Term 1"),
        Column("chapter_no", "Ch #", ("ch #", "ch no", "chapter no", "chapter number",
                                      "sr no", "no"),
               "The chapter's number in the book. Optional.", "1"),
        Column("chapter", "Chapter", ("chapter", "chapter name", "unit", "unit name",
                                      "lesson", "lesson name"),
               "Chapter or unit name. Blank continues the chapter above, which is "
               "how merged cells arrive.", "Number Systems", required=True),
        # No Topic column (founder, 2026-08-08). Schools plan by chapter — the
        # reference tracker has no topic column at all — and asking for one got
        # blank cells or the chapter name typed twice. Each chapter becomes one
        # topic internally, carrying the chapter's periods, so `core/coverage.py`
        # weights exactly as before and the syllabus board is unaffected.
        Column("periods", "Est. periods", ("est periods", "estimated periods",
                                           "periods", "no of periods", "days",
                                           "duration"),
               "How many periods this chapter needs. LEAVE BLANK if it has not "
               "been sized yet — blank means 'not sized', never 1.", "4"),
    ),
    samples=(
        ("6", "", "Mathematics", "Term 1", "1", "Number Systems", "4"),
        ("6", "", "Mathematics", "Term 1", "2", "Polynomials", "5"),
        ("6", "", "Science", "Term 1", "1", "Food and Nutrition", "3"),
    ),
)

# ── 7. Students ──────────────────────────────────────────────────────────────
STUDENTS = SheetSpec(
    key="students",
    title="Students",
    required=True,
    blurb="The register. Date of birth becomes the parent's portal password, so "
          "it matters more than it looks.",
    columns=(
        Column("full_name", "Student name",
               ("student name", "name", "student", "full name", "child name"),
               "The child's full name.", "Aarav Sharma", required=True),
        Column("admission_no", "Admission no",
               ("admission no", "admission", "adm no", "adm", "scholar no", "sr no",
                "enrollment"),
               "The school's admission / scholar number. Must be unique — it is how "
               "a re-upload recognises the same child.", "1021", required=True),
        Column("roll_no", "Roll no", ("roll no", "roll number", "roll"),
               "Roll number within the class.", "12"),
        Column("class_name", "Class", ("class", "grade", "standard", "std"),
               "As on the Classes sheet. A child with no class appears on no "
               "register.", "6"),
        Column("section", "Section", ("section", "sec", "division", "div"),
               "", "A"),
        Column("date_of_birth", "Date of birth",
               ("date of birth", "dob", "d.o.b", "birth date", "born"),
               "dd/mm/yyyy. This becomes the parent's login password — a child "
               "without it has a parent who cannot log in.", "14/06/2014"),
        Column("category", "Category", ("category", "student category", "type"),
               "The school's own grouping.", "Day scholar"),
        Column("father_name", "Father name", ("father's name", "father name", "father"),
               "", "Rajesh Sharma"),
        Column("father_phone", "Father phone",
               ("father's mobile", "father mobile", "father's phone", "father phone"),
               "10-digit mobile. Absence alerts and homework notes go here.",
               "9876543210"),
        Column("mother_name", "Mother name", ("mother's name", "mother name", "mother"),
               "", "Priya Sharma"),
        Column("mother_phone", "Mother phone",
               ("mother's mobile", "mother mobile", "mother's phone", "mother phone"),
               "", "9876543211"),
    ),
    samples=(
        ("Aarav Sharma", "1021", "12", "6", "A", "14/06/2014", "Day scholar",
         "Rajesh Sharma", "9876543210", "Priya Sharma", "9876543211"),
        ("Diya Patel", "1022", "13", "6", "A", "02/11/2013", "Hosteller",
         "Amit Patel", "9876543212", "Meena Patel", "9876543213"),
        ("Rohan Verma", "1023", "14", "6", "B", "23/01/2014", "Day scholar",
         "Suresh Verma", "9876543214", "Lakshmi Verma", "9876543215"),
    ),
)

# ── 8. Timetable ─────────────────────────────────────────────────────────────
TIMETABLE = SheetSpec(
    key="timetable",
    title="Timetable",
    required=False,
    blurb="Optional. Without it, teachers see no periods on My Day — but TrackBit "
          "can also generate a grid from the weekly period budgets.",
    columns=(
        Column("class_name", "Class", ("class", "grade", "standard", "std"),
               "As on the Classes sheet.", "6", required=True),
        Column("section", "Section", ("section", "sec", "division", "div"), "", "A"),
        Column("day", "Day", ("day", "week day", "weekday"),
               "Monday … Saturday.", "Monday", required=True,
               choices=("Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                        "Saturday", "Sunday")),
        Column("period", "Period", ("period", "period no", "period number", "slot"),
               "Period number within the day, starting at 1.", "1", required=True),
        Column("subject", "Subject", ("subject", "subject name", "paper"),
               "As on the Teaching Assignments sheet.", "Mathematics", required=True),
    ),
    samples=(
        ("6", "A", "Monday", "1", "Mathematics"),
        ("6", "A", "Monday", "2", "Science"),
        ("6", "A", "Tuesday", "1", "Mathematics"),
    ),
)

# ── 9. Calendar ──────────────────────────────────────────────────────────────
CALENDAR = SheetSpec(
    key="calendar",
    title="Calendar",
    required=False,
    blurb="Optional. Public holidays for the school's state are already known — "
          "list only what is specific to this school, plus exam weeks.",
    columns=(
        Column("start_date", "From", ("from", "date", "start date", "starts"),
               "dd/mm/yyyy. For a single day, fill this and leave 'To' blank.",
               "15/08/2026", required=True),
        Column("end_date", "To", ("to", "end date", "ends", "till"),
               "dd/mm/yyyy. Only for something spanning several days.",
               "17/08/2026"),
        Column("title", "Name", ("name", "title", "occasion", "event", "description"),
               "What it is called.", "Founder's Day", required=True),
        Column("type", "Type", ("type", "kind", "category"),
               "Holiday closes the school; Event is a working day with something "
               "on it. Exams are NOT here — a term exam's dates go on the Terms "
               "sheet, because the exam is what ends the term.",
               "Holiday", required=True, choices=("Holiday", "Event")),
        Column("classes", "Classes", ("classes", "class", "applies to", "for"),
               "Blank means the whole school. Otherwise list classes separated by "
               "commas.", ""),
    ),
    samples=(
        ("15/08/2026", "", "Independence Day", "Holiday", ""),
        ("02/10/2026", "", "Gandhi Jayanti", "Holiday", ""),
        ("05/09/2026", "", "Teachers' Day", "Event", ""),
    ),
)

# ── 10. Fees ─────────────────────────────────────────────────────────────────
FEES = SheetSpec(
    key="fees",
    title="Fees",
    required=False,
    blurb="Optional. One row per installment. Teachers never see any of this.",
    columns=(
        Column("class_name", "Class", ("class", "grade", "standard", "std"),
               "Which class this fee structure applies to.", "6", required=True),
        Column("category", "Category", ("category", "student category", "type"),
               "Blank means every student of that class. Otherwise the category "
               "name from the Students sheet.", ""),
        Column("total_amount", "Total amount",
               ("total amount", "total", "annual fee", "amount", "total fee"),
               "The full year's fee for this class. Repeat it on every installment "
               "row of the same structure.", "36000", required=True),
        Column("installment_no", "Installment no",
               ("installment no", "instalment no", "installment", "sr no", "no"),
               "1, 2, 3 … in due-date order.", "1"),
        Column("installment_name", "Installment name",
               ("installment name", "instalment name", "quarter", "term", "label"),
               "What the school calls it.", "Quarter 1"),
        Column("due_date", "Due date", ("due date", "due", "payable by", "date"),
               "dd/mm/yyyy. This is what puts the money in a quarter — the fee "
               "screen groups by due-date window, never by installment number.",
               "15/06/2026"),
        Column("amount", "Amount", ("amount", "installment amount", "value", "fee"),
               "This installment's share of the total.", "12000"),
    ),
    # The three installments sum to the total on purpose: the filled example is
    # something an operator shows a school, so it must not model a mistake.
    samples=(
        ("6", "", "36000", "1", "Quarter 1", "15/06/2026", "12000"),
        ("6", "", "36000", "2", "Quarter 2", "15/09/2026", "12000"),
        ("6", "", "36000", "3", "Quarter 3", "15/12/2026", "12000"),
    ),
)


SHEETS: tuple[SheetSpec, ...] = (
    SCHOOL, TERMS, CLASSES, STAFF, ASSIGNMENTS, SYLLABUS, STUDENTS,
    TIMETABLE, CALENDAR, FEES,
)

BY_KEY: dict[str, SheetSpec] = {s.key: s for s in SHEETS}

# Commit order is the wizard's dependency chain (schemas/wizard.py), which does
# not disappear just because the ten steps became one upload — it moves into the
# order of writes inside one transaction. Kept here so the committer and the
# validator read it from the same place.
COMMIT_ORDER: tuple[str, ...] = (
    "school",       # year + terms hang off nothing
    "terms",
    # Staff moves AHEAD of classes, which the wizard's chain did not do. There it
    # had to follow classes because a staff sheet's "6-A Mathematics" hint could
    # only resolve once classes and subjects existed. The pack puts assignments on
    # their own sheet, so staff needs nothing — and going first means a class's
    # `class_teacher_member_id` resolves in the same pass that creates the class,
    # instead of a second pass to fill it in.
    "staff",
    "classes",      # a class needs a year, and names its class teacher
    "assignments",  # creates subjects + class_subjects (teacher + weekly budget)
    "syllabus",     # units hang off class_subject_id
    "calendar",     # holidays first: the plan paces around non-teaching days
    "students",
    "timetable",    # needs classes, assignments and timings
    "fees",
)

# After every sheet above is in, the committer generates and approves each
# class-subject's plan. It is NOT a sheet — nothing in the workbook describes it,
# it is computed from the syllabus, the calendar and the weekly period budgets —
# but it is the last step of setup and skipping it is what leaves a freshly
# imported school opening on a dashboard full of "has no plan yet". The wizard's
# tenth step did this; one upload has to do it too.
PLANS_KEY = "plans"
PLANS_TITLE = "Plans"

# Likewise the exam portions. A term IS its exam, so the exam block comes off the
# Terms sheet and what it examines is that term's syllabus — neither is a sheet
# of its own, but both are worth reporting to the operator by name.
EXAMS_KEY = "exams"
EXAMS_TITLE = "Term exams"


def sheet(key: str) -> SheetSpec:
    return BY_KEY[key]


def required_sheets() -> list[SheetSpec]:
    return [s for s in SHEETS if s.required]


@dataclass
class PackNote:
    """One line of the Read Me's conventions block, kept in code so the sheet
    comments and the Read Me cannot say different things."""

    heading: str
    body: str
    lines: tuple[str, ...] = field(default_factory=tuple)


READ_ME_NOTES: tuple[PackNote, ...] = (
    PackNote(
        "How to fill this in",
        "Fill one sheet at a time, in the order the tabs appear. Nothing here is "
        "urgent enough to guess at — leave a cell blank rather than invent a value.",
        (
            "Do not rename the sheets or the column headers.",
            "Do not delete columns you are not using — leave them blank.",
            "Add as many rows as you need; there is no limit.",
            "Names must be spelled the same way on every sheet. 'Anita Desai' on "
            "Staff and 'A. Desai' on Classes are two different people to us.",
        ),
    ),
    PackNote(
        "A blank cell means 'not known yet'",
        "It never means zero and never means one.",
        (
            "A chapter with no Periods is one nobody has sized yet.",
            "A subject with no Teacher is one nobody has been assigned to yet.",
            "Both are states we can hand the school over with. A wrong number is "
            "worse than a blank, because nobody thinks to check it.",
        ),
    ),
    PackNote(
        "Dates are day-first",
        "Write 14/06/2014 for the 14th of June. dd/mm/yyyy everywhere.",
        (),
    ),
    PackNote(
        "A blank Section means every section",
        "On the Teaching Assignments and Syllabus sheets, leaving Section blank "
        "applies the row to 6-A, 6-B and 6-C alike.",
        ("Most schools teach the same syllabus to every section, so leave it blank "
         "and fill the syllabus once.",),
    ),
    PackNote(
        "Half a year is fine",
        "If only Term 1 and Term 2 have been planned, send those. The school can "
        "start using TrackBit on Monday and add Term 3 whenever it is ready.",
        ("The same is true if the school is joining part-way through the year — "
         "put the joining date in 'Tracking starts from' on the School sheet.",),
    ),
    PackNote(
        "Topics are optional",
        "Most schools plan by chapter. Leave the Topic column blank and each "
        "chapter is planned as one unit.",
        ("Fill Topic only if the school genuinely tracks progress inside a "
         "chapter.",),
    ),
)
