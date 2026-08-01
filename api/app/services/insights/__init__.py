"""The admin operating board (DASH3) — six read modules and one write spine.

Each module answers one question the admin actually arrives with, at three
depths: the shape (charts at school level), the drill-down (class → subject →
teacher/student), and the red rows that carry an action.

    attendance.py   who is missing — students and staff — and what it breaks
    syllabus.py     is the year's teaching where the plan said it would be
    workload.py     who is teaching, working or free, right now and this week
    homework.py     is homework being done, and is anyone checking
    tasks.py        assigned work + the daily classroom duties
    exams.py        results, school → class → subject, across cycles
    actions.py      the shared action rail (§5) — every write on the board
    overview.py     the summary of all six, plus what is waiting on the admin

`DashboardService` is untouched: the briefing and its charts keep working exactly
as they did, and these boards are strictly additive.

**Query discipline.** Every roll-up here is grouped SQL with `IN()` batching. The
database is a remote hop, so a per-class or per-teacher loop costs one round-trip
per row and is the single failure mode this file set exists to avoid.
"""
