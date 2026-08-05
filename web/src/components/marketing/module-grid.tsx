/**
 * The ten modules — the breadth argument.
 *
 * The showcases below prove depth on five screens; this grid is the only place
 * a visitor learns that fees, exams, events and the support programme exist at
 * all. So every claim here is one that has actually shipped — a school owner
 * who books a demo on the strength of a line in this grid must find it in the
 * product on the call.
 *
 * Each cell is tagged with the pillar it serves, so the grid is read against
 * the spine above it rather than as a flat feature list. Fees, tasks, the
 * calendar and the parent portal sit outside the three pillars, and say so.
 *
 * The last cell spans the full row on wide screens: the parent portal is the
 * one module that faces outside the school, and it closes the grid.
 *
 * Server component — no JS.
 */

type Module = {
  tag: string;
  name: string;
  line: string;
  points: string[];
};

const MODULES: Module[] = [
  {
    tag: "Students",
    name: "Attendance",
    line: "All present in one tap. Record only who wasn't.",
    points: [
      "Per-period, or once a day — your school's rule",
      "Guardians told the morning it happens",
      "A month's register you can read down a column",
    ],
  },
  {
    tag: "Syllabus",
    name: "Syllabus",
    line: "The year planned to the period, then paced against the calendar.",
    points: [
      "Chapters sized per term; plans approved and locked",
      "Pace measured against the plan's own marker",
      "Every overdue chapter says why it is behind",
    ],
  },
  {
    tag: "Teachers",
    name: "Teacher load",
    line: "Who is teaching, who is free, who is covering.",
    points: [
      "Timetable built and clash-checked",
      "Free-period work recorded, never inferred",
      "Cover arranged from the absence itself",
    ],
  },
  {
    tag: "Students",
    name: "Student record",
    line: "One page that answers how a child is actually doing.",
    points: [
      "Attendance, coverage, marks and homework in one record",
      "The topics they missed while absent, named",
      "Strengths beside growth areas — never only deficits",
    ],
  },
  {
    tag: "Students",
    name: "Exams",
    line: "Record the paper, verify it, lock it. Then read it.",
    points: [
      "Photograph marked scripts — marks are read off the page",
      "Small tests and term exams never pooled into one number",
      "A locked mark is the record, not something to overwrite",
    ],
  },
  {
    tag: "Students",
    name: "ABC bands",
    line: "A support programme — not a letter stamped on a child.",
    points: [
      "Banded per subject, against a written standard",
      "Every child has one owner and a weekly check-in",
      "Movement is the measure — and parents never see a tier",
    ],
  },
  {
    tag: "Operations",
    name: "Tasks",
    line: "Every gap becomes a job with somebody's name on it.",
    points: [
      "Boards, recurring duties, and one-tap alert-to-task",
      "Append-only history: who did what, and when",
      "Follow-ups that stop one parent being called twice",
    ],
  },
  {
    tag: "Operations",
    name: "Fee collection",
    line: "Collection read against the calendar, not as a bare total.",
    points: [
      "Due-by-today beside collected — what makes a % readable",
      "Defaulters listed with the family and the phone number",
      "Every conversation logged, so the next caller knows",
    ],
  },
  {
    tag: "School-wide",
    name: "Events & birthdays",
    line: "The school's calendar, already filled in.",
    points: [
      "India's observances by state and board, ready to approve",
      "Birthdays derived from date of birth — no list to maintain",
      "See what a holiday costs the plan before you declare it",
    ],
  },
  {
    tag: "School-wide",
    name: "Parent communication",
    line: "Parents stop calling the office. They log in and look.",
    points: [
      "A login per family: today, progress, report card, calendar",
      "Absence and homework reach them the day it happens",
      "A curated view — support tiers never leave the staff room",
    ],
  },
];

export function ModuleGrid() {
  return (
    <div className="mk-modules">
      {MODULES.map((m, i) => (
        <article
          key={m.name}
          className="mk-module"
          data-wide={i === MODULES.length - 1 ? "true" : "false"}
        >
          <div className="mk-module-top">
            <p className="mk-module-tag mk-mono">{m.tag}</p>
            <h3>{m.name}</h3>
            <p>{m.line}</p>
          </div>
          <ul>
            {m.points.map((pt) => (
              <li key={pt}>{pt}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
