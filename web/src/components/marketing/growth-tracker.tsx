import type { CSSProperties } from "react";

/**
 * One student, subject by subject — the per-child growth view.
 *
 * Each subject shows how much of the syllabus has actually been taught, how many
 * topics the child missed while absent (the number a parent and a class teacher
 * both want), and the test trend. The bars re-fill on a slow CSS loop so the
 * panel reads as live; reduced-motion just leaves them at their real width.
 */

const SUBJECTS = [
  { name: "Science", taught: 72, missed: 2, score: "78%", trend: [40, 52, 61, 78] },
  { name: "Mathematics", taught: 64, missed: 4, score: "61%", trend: [70, 58, 55, 61] },
  { name: "English", taught: 81, missed: 0, score: "88%", trend: [72, 80, 84, 88] },
  { name: "Social", taught: 58, missed: 1, score: "74%", trend: [60, 66, 70, 74] },
];

function spark(points: number[], w: number, h: number): string {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const span = max - min || 1;
  return points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p - min) / span) * h;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

export function GrowthTracker() {
  return (
    <div className="mk-browser" aria-hidden="true">
      <div className="mk-browser-bar">
        <span className="mk-browser-dots">
          <i />
          <i />
          <i />
        </span>
        <span className="mk-browser-url mk-mono">trackbit / students / aarav-sharma</span>
      </div>

      <div className="mk-grow">
        <div className="mk-grow-head">
          <div>
            <p className="mk-grow-name">Aarav Sharma</p>
            <p className="mk-grow-meta mk-mono">Class 7B · Roll 14</p>
          </div>
          <div className="mk-grow-att">
            <b>94%</b>
            <span>attendance</span>
          </div>
        </div>

        <div className="mk-grow-rows">
          {SUBJECTS.map((s, i) => (
            <div key={s.name} className="mk-grow-row">
              <span className="mk-grow-subj">{s.name}</span>
              <div className="mk-grow-bar">
                <i
                  style={{ "--w": `${s.taught}%`, animationDelay: `${i * 120}ms` } as CSSProperties}
                />
              </div>
              <span className="mk-grow-missed mk-mono" data-zero={s.missed === 0 ? "true" : "false"}>
                {s.missed === 0 ? "0 missed" : `${s.missed} missed`}
              </span>
              <svg className="mk-grow-spark" viewBox="0 0 48 18" preserveAspectRatio="none">
                <path d={spark(s.trend, 48, 18)} />
              </svg>
              <span className="mk-grow-score mk-mono">{s.score}</span>
            </div>
          ))}
        </div>

        <div className="mk-grow-foot">
          <span className="mk-grow-tag mk-mono">GROWTH AREAS</span>
          <span className="mk-chip">Fractions</span>
          <span className="mk-chip">Reading speed</span>
        </div>
      </div>
    </div>
  );
}
