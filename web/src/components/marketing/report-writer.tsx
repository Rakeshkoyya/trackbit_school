"use client";

import { useLoopStep } from "./use-loop";

/**
 * The daily report writing itself.
 *
 * Lines land one after another under their headings, a cursor at the frontier,
 * then it resets and writes again. No one types this — it is composed from the
 * day's captured periods. That is the "nobody writes a report" claim, animated.
 */

type Line = { section?: string; tone?: "risk" | "amb" | "win"; text: string };

const LINES: Line[] = [
  { section: "risks", tone: "risk", text: "7B Science is 6 periods behind — half-yearly in 9 days." },
  { tone: "risk", text: "3 students absent 3+ days: Aarav, Meera, Kabir." },
  { section: "ambiguities", tone: "amb", text: "8C period 4 marked, but no topic logged." },
  { section: "wins", tone: "win", text: "Attendance 96% — best this term." },
  { tone: "win", text: "All Class 9 homework set and acknowledged." },
];

export function ReportWriter() {
  // One extra step at the end holds the finished report before it resets.
  const step = useLoopStep(LINES.length + 1, { interval: 900, hold: 3200 });
  const shown = Math.min(step, LINES.length);

  return (
    <div className="mk-report" aria-hidden="true">
      <div className="mk-report-head">
        <p className="mk-report-title">Daily Report</p>
        <p className="mk-report-date mk-mono">Tue · 22 Jul · 08:00</p>
      </div>

      <div className="mk-report-body">
        {LINES.map((line, i) => {
          const visible = i < shown;
          const writing = i === shown - 1 && step <= LINES.length;
          return (
            <div key={i}>
              {line.section ? (
                <p className={`mk-report-section mk-mono ${visible ? "is-on" : ""}`}>
                  {line.section === "risks"
                    ? "Risks"
                    : line.section === "ambiguities"
                      ? "Ambiguities"
                      : "Wins"}
                </p>
              ) : null}
              <p className={`mk-report-line ${visible ? "is-on" : ""}`} data-tone={line.tone}>
                <span className="mk-report-mark" />
                <span>{line.text}</span>
                {writing ? <span className="mk-caret" /> : null}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
