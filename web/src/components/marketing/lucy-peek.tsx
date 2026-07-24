"use client";

import { useLoopStep } from "./use-loop";

/**
 * Lucy — the shipped half of the AI story. A staff question types itself in and
 * an answer built from live data renders, mini-chart and all. Answers ride the
 * asker's permissions and any change waits for a human's confirmation.
 */

const QUESTION = "Which classes are behind on Science before the half-yearly?";

const ROWS = [
  { cls: "8B", behind: 6, left: 4, w: 100 },
  { cls: "7A", behind: 4, left: 3, w: 66 },
  { cls: "9C", behind: 2, left: 1, w: 33 },
];

const TYPE_STEPS = QUESTION.length;
const STEPS = TYPE_STEPS + 3;

export function LucyPeek() {
  const step = useLoopStep(STEPS, { interval: 45, hold: 3600 });

  const typed = QUESTION.slice(0, Math.min(step, TYPE_STEPS));
  const thinking = step === TYPE_STEPS + 1;
  const answered = step >= TYPE_STEPS + 2;

  return (
    <div className="mk-lucy" aria-hidden="true">
      <div className="mk-lucy-q">
        <span className="mk-lucy-you mk-mono">You</span>
        <p>
          {typed}
          {step < TYPE_STEPS ? <span className="mk-caret" /> : null}
        </p>
      </div>

      {thinking ? <p className="mk-lucy-thinking mk-mono">Lucy is reading the plan…</p> : null}

      <div className={`mk-lucy-a ${answered ? "is-on" : ""}`}>
        <span className="mk-lucy-name mk-mono">Lucy</span>
        <p className="mk-lucy-say">Three of eight, against the approved plan:</p>
        <div className="mk-lucy-rows">
          {ROWS.map((r) => (
            <div key={r.cls} className="mk-lucy-row">
              <span className="mk-lucy-cls mk-mono">{r.cls}</span>
              <div className="mk-lucy-bar">
                <i style={{ width: answered ? `${r.w}%` : "0%" }} />
              </div>
              <span className="mk-lucy-val mk-mono">
                {r.behind}p · {r.left} left
              </span>
            </div>
          ))}
        </div>
        <p className="mk-lucy-follow">Make this a task for the Science coordinator?</p>
      </div>
    </div>
  );
}
