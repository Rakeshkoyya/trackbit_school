"use client";

import { Check } from "lucide-react";

import { useLoopStep } from "./use-loop";

/**
 * The teacher's whole job, looping in a phone.
 *
 * Six frames: an open period → one tap says the class is present → one absentee
 * flagged → topic logged → homework set → closed. The tap counter is the point:
 * a full period on the record in four taps, under half a minute. This is the
 * "teachers won't do data entry" objection, answered by showing there is none.
 */

const FRAMES = 6;

export function PeriodCard() {
  const step = useLoopStep(FRAMES, { interval: 1250, hold: 2800 });

  const taps = Math.min(step, 4);
  const present = step >= 1;
  const absentee = step >= 2;
  const topic = step >= 3;
  const homework = step >= 4;
  const closed = step >= 5;

  return (
    <div className="mk-phone" aria-hidden="true">
      <div className="mk-phone-notch" />
      <div className="mk-phone-screen">
        <div className="mk-pc-head">
          <div>
            <p className="mk-pc-kicker mk-mono">PERIOD 3 · 10:40</p>
            <p className="mk-pc-title">Science · Class 7B</p>
          </div>
          <span className={`mk-pc-status mk-mono ${closed ? "is-done" : ""}`}>
            {closed ? "Closed" : "Open"}
          </span>
        </div>

        {/* Attendance */}
        <div className={`mk-pc-block ${present ? "is-on" : ""}`}>
          <div className="mk-pc-block-top">
            <span className="mk-pc-label mk-mono">Attendance</span>
            {present ? (
              <span className="mk-pc-check">
                <Check className="mk-ic" strokeWidth={3} />
              </span>
            ) : null}
          </div>
          <button className={`mk-pc-allpresent ${present ? "is-on" : ""}`} type="button">
            {present ? "All present" : "Tap: all present"}
          </button>
          <div className={`mk-pc-exc ${absentee ? "is-on" : ""}`}>
            <span className="mk-pc-dot" /> Aarav S — absent
          </div>
        </div>

        {/* Topic */}
        <div className={`mk-pc-row ${topic ? "is-on" : ""}`}>
          <span className="mk-pc-label mk-mono">Topic</span>
          <span className="mk-pc-val">{topic ? "Photosynthesis ✓" : "—"}</span>
        </div>

        {/* Homework */}
        <div className={`mk-pc-row ${homework ? "is-on" : ""}`}>
          <span className="mk-pc-label mk-mono">Homework</span>
          <span className="mk-pc-val">{homework ? "Read pg 44" : "—"}</span>
        </div>

        <div className="mk-pc-foot mk-mono">
          <span className="mk-pc-taps">
            {[0, 1, 2, 3].map((i) => (
              <i key={i} className={i < taps ? "is-on" : ""} />
            ))}
          </span>
          <span>{closed ? "Done · 22s" : `${taps} ${taps === 1 ? "tap" : "taps"}`}</span>
        </div>
      </div>
    </div>
  );
}
