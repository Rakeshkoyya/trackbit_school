"use client";

import { useLoopStep } from "./use-loop";

/**
 * What the director finally sees at 8 AM.
 *
 * Two things they can never get today: the syllabus pace of every class-subject
 * at a glance (the RAG board), and a feed of exactly what needs a person. The
 * loop turns one alert into a task — the "gaps become tasks" claim, shown.
 */

const CLASSES = ["6A", "7B", "8C", "9A"];
const SUBJECTS = ["Eng", "Math", "Sci", "Soc"];

// pace per class × subject: g = on track, a = slipping, r = behind
const PACE: Record<string, string[]> = {
  "6A": ["g", "g", "g", "a"],
  "7B": ["g", "a", "r", "g"],
  "8C": ["g", "g", "g", "g"],
  "9A": ["a", "g", "g", "g"],
};

const ALERTS = [
  { who: "7B · Science", what: "6 periods behind the plan" },
  { who: "Aarav S · 7B", what: "absent 3 days running" },
  { who: "Fees · Class 9", what: "12 instalments overdue" },
];

export function DirectorDashboard() {
  // 0: alert highlighted, 1: converting, 2: task created (hold), then loop
  const step = useLoopStep(3, { interval: 1500, hold: 2600 });

  return (
    <div className="mk-browser" aria-hidden="true">
      <div className="mk-browser-bar">
        <span className="mk-browser-dots">
          <i />
          <i />
          <i />
        </span>
        <span className="mk-browser-url mk-mono">trackbit / dashboard</span>
      </div>

      <div className="mk-dash">
        <div className="mk-dash-kpis">
          <div className="mk-kpi">
            <b>142/144</b>
            <span>periods held today</span>
          </div>
          <div className="mk-kpi">
            <b>6/8</b>
            <span>classes on syllabus</span>
          </div>
          <div className="mk-kpi">
            <b>82%</b>
            <span>fees collected</span>
          </div>
        </div>

        <div className="mk-dash-grid">
          <div className="mk-dash-panel">
            <p className="mk-dash-h mk-mono">SYLLABUS PACE</p>
            <div className="mk-rag">
              <div className="mk-rag-row mk-rag-head mk-mono">
                <span />
                {SUBJECTS.map((s) => (
                  <span key={s}>{s}</span>
                ))}
              </div>
              {CLASSES.map((cls) => (
                <div key={cls} className="mk-rag-row">
                  <span className="mk-rag-cls mk-mono">{cls}</span>
                  {PACE[cls].map((p, i) => (
                    <span key={i} className="mk-rag-cell">
                      <i data-pace={p} />
                    </span>
                  ))}
                </div>
              ))}
            </div>
          </div>

          <div className="mk-dash-panel">
            <p className="mk-dash-h mk-mono">NEEDS YOU</p>
            <div className="mk-alerts">
              {ALERTS.map((a, i) => {
                const active = i === 0;
                const asTask = active && step >= 2;
                return (
                  <div key={a.who} className={`mk-alert ${active && step >= 1 ? "is-active" : ""}`}>
                    <div className="mk-alert-body">
                      <p className="mk-alert-who">{a.who}</p>
                      <p className="mk-alert-what">{a.what}</p>
                    </div>
                    <span className={`mk-alert-tag mk-mono ${asTask ? "is-task" : ""}`}>
                      {asTask ? "→ Task ✓" : "Alert"}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
