"use client";

import { useLoopStep } from "./use-loop";

/**
 * "Evolves with you" — shown as the direction we're building, not a shipped
 * feature (founder call). An admin describes a tracker in plain words; a live
 * module materialises in the dashboard. The overlay label keeps the promise
 * honest: this is where the platform is heading.
 */

const PROMPT = "Track teacher workload daily";
const BARS = [72, 88, 54, 96, 63, 80];

// frames: typing the prompt (per char) → "Building" → module appears (hold)
const TYPE_STEPS = PROMPT.length;
const STEPS = TYPE_STEPS + 3;

export function GenerativeBuild() {
  const step = useLoopStep(STEPS, { interval: 120, hold: 3400 });

  const typed = PROMPT.slice(0, Math.min(step, TYPE_STEPS));
  const building = step === TYPE_STEPS + 1;
  const built = step >= TYPE_STEPS + 2;

  return (
    <div className="mk-browser" aria-hidden="true">
      <div className="mk-browser-bar">
        <span className="mk-browser-dots">
          <i />
          <i />
          <i />
        </span>
        <span className="mk-browser-url mk-mono">trackbit / build</span>
        <span className="mk-gen-badge mk-mono">Where we&apos;re heading</span>
      </div>

      <div className="mk-gen">
        <div className="mk-gen-prompt">
          <span className="mk-gen-caret-lead mk-mono">›</span>
          <span className="mk-gen-typed">
            {typed || <span className="mk-gen-placeholder">Describe what you want to track…</span>}
          </span>
          {step < TYPE_STEPS ? <span className="mk-caret" /> : null}
        </div>

        <div className={`mk-gen-stage ${building ? "is-building" : ""} ${built ? "is-built" : ""}`}>
          {building ? <p className="mk-gen-status mk-mono">Building module…</p> : null}

          <div className={`mk-gen-card ${built ? "is-on" : ""}`}>
            <p className="mk-gen-card-h mk-mono">TEACHER WORKLOAD · THIS WEEK</p>
            <div className="mk-gen-bars">
              {BARS.map((b, i) => (
                <span key={i} className="mk-gen-bar">
                  <i style={{ height: built ? `${b}%` : "0%" }} />
                </span>
              ))}
            </div>
            <div className="mk-gen-card-foot mk-mono">
              <span>Mon–Sat</span>
              <span>periods / teacher</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
