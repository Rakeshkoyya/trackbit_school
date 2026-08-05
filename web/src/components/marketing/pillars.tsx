/**
 * The three pillars — the spine the whole product hangs off.
 *
 * A school owner does not think in modules; they think in the three things a
 * school is accountable for: the children, the staff, and the portion. So the
 * page states those three first, and the module grid below is read against
 * them.
 *
 * The block's inner shape is a ledger — captured on the left, computed on the
 * right — because that is the product's actual claim: nobody enters the right
 * column, it falls out of the left. Rendering it as two facing columns makes
 * the claim structural instead of a sentence someone has to believe.
 *
 * Server component: it is type, rules and lists, so it ships no JS.
 */

type Pillar = {
  n: string;
  name: string;
  line: string;
  captured: string[];
  computed: string[];
};

const PILLARS: Pillar[] = [
  {
    n: "01",
    name: "Students",
    line: "Every child's day, growth and support — built from work already done.",
    captured: [
      "Attendance, period by period",
      "Homework returned, and by whom",
      "Marks, with the paper behind them",
      "What the teacher noticed",
    ],
    computed: [
      "A report card per child",
      "Chapters missed while absent",
      "Strengths and growth areas",
      "A day-by-day timeline",
    ],
  },
  {
    n: "02",
    name: "Teachers",
    line: "Every teacher's load, time and cover — settled by the record, not by argument.",
    captured: [
      "The timetable, clash-checked",
      "Periods held, and periods not",
      "Work done in a free period",
      "Leave applied and approved",
    ],
    computed: [
      "Who is free right now",
      "Who covers an absence, and what it costs",
      "A month's record per person",
      "The school's slack profile",
    ],
  },
  {
    n: "03",
    name: "Syllabus",
    line: "Every chapter's plan, pace and proof — against the calendar, not a feeling.",
    captured: [
      "The portion, sized chapter by chapter",
      "The topic taught in each period",
      "Coverage: full, partial, not held",
      "Exam portions, chapter by chapter",
    ],
    computed: [
      "Pace against the approved plan",
      "Which chapters are overdue, and why",
      "Whether the portion finishes in time",
      "One coverage figure, everywhere",
    ],
  },
];

export function Pillars() {
  return (
    <div className="mk-pillars">
      {PILLARS.map((p) => (
        <article key={p.name} className="mk-pillar">
          <div className="mk-pillar-head">
            <p className="mk-pillar-n mk-mono">{p.n}</p>
            <h3 className="mk-pillar-name mk-display">{p.name}</h3>
            <p className="mk-pillar-line">{p.line}</p>
          </div>

          <div className="mk-pillar-ledger">
            <div className="mk-pillar-col" data-kind="captured">
              <p className="mk-pillar-col-h mk-mono">Captured in a tap</p>
              <ul>
                {p.captured.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
            <div className="mk-pillar-col" data-kind="computed">
              <p className="mk-pillar-col-h mk-mono">Written for you</p>
              <ul>
                {p.computed.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
