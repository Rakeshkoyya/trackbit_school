"use client";

import { useLoopStep } from "./use-loop";

/**
 * The parent portal — parents log in and see their child's actual day.
 *
 * Login → the day's periods with the topic taught and homework set → and, when
 * the child was absent, exactly what they missed that period. This is the
 * transparency that stops the front office fielding "what happened today?"
 * calls. It deliberately shows the class record and missed topics — never the
 * private A/B/C tiers, which stay with staff.
 */

const PERIODS = [
  { p: "P1", subj: "English", topic: "Grammar — tenses", hw: null, absent: false },
  { p: "P2", subj: "Math", topic: "Fractions", hw: "Worksheet 3", absent: false },
  { p: "P3", subj: "Science", topic: "Photosynthesis", hw: "Read pg 44", absent: false },
  { p: "P5", subj: "Social", topic: "Chapter 4 — intro", hw: null, absent: true },
];

const STEPS = 2 + PERIODS.length; // login, header, then one per period

export function ParentPortal() {
  const step = useLoopStep(STEPS, { interval: 1050, hold: 3000 });
  const loggedIn = step >= 1;

  return (
    <div className="mk-phone" aria-hidden="true">
      <div className="mk-phone-notch" />
      <div className="mk-phone-screen">
        {!loggedIn ? (
          <div className="mk-par-login">
            <p className="mk-par-brand">
              TrackBit <span className="mk-mono">for parents</span>
            </p>
            <div className="mk-par-field mk-mono">meera.sharma@email.com</div>
            <div className="mk-par-field mk-mono">••••••••</div>
            <div className="mk-par-signin">Sign in</div>
            <p className="mk-par-hint">Aarav&apos;s parent · Class 7B</p>
          </div>
        ) : (
          <>
            <div className="mk-par-head">
              <div>
                <p className="mk-par-kicker mk-mono">TODAY · TUE 22 JUL</p>
                <p className="mk-par-title">Aarav · Class 7B</p>
              </div>
            </div>

            <div className="mk-par-rows">
              {PERIODS.map((row, i) => {
                const visible = step >= 2 + i;
                return (
                  <div
                    key={row.p}
                    className={`mk-par-row ${visible ? "is-on" : ""} ${row.absent ? "is-absent" : ""}`}
                  >
                    <span className="mk-par-p mk-mono">{row.p}</span>
                    <div className="mk-par-cell">
                      <p className="mk-par-subj">
                        {row.subj}
                        {row.absent ? <em className="mk-par-flag">Absent</em> : null}
                      </p>
                      <p className="mk-par-topic">
                        {row.absent ? `Missed: ${row.topic}` : row.topic}
                      </p>
                      {row.hw ? <p className="mk-par-hw mk-mono">HW · {row.hw}</p> : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
