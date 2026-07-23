"use client";

import { useState } from "react";

/**
 * Answers the buyer's first question — "what does this cost me?" — before they
 * have to ask a salesperson. ₹100 per student per month, floor of 500 students,
 * so the slider simply cannot go below the floor.
 */

const RATE = 100;
const MIN_STUDENTS = 500;
const MAX_STUDENTS = 3000;

const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

export function PricingCalculator() {
  const [students, setStudents] = useState(800);
  const monthly = students * RATE;

  return (
    <div className="mk-calc">
      <div className="mk-calc-out">
        <p className="mk-eyebrow">Your monthly cost</p>
        <p className="mk-calc-total">{inr(monthly)}</p>
        <p className="mk-calc-sub">
          {inr(monthly * 12)} a year · {students.toLocaleString("en-IN")} students × ₹100
        </p>
      </div>

      <label className="mk-calc-label" htmlFor="mk-students">
        Students
        <b>{students.toLocaleString("en-IN")}</b>
      </label>
      <input
        id="mk-students"
        className="mk-range"
        type="range"
        min={MIN_STUDENTS}
        max={MAX_STUDENTS}
        step={50}
        value={students}
        onChange={(e) => setStudents(Number(e.target.value))}
      />
      <div className="mk-range-ends mk-mono">
        <span>500 min</span>
        <span>3,000+</span>
      </div>

      <p className="mk-calc-note">
        Billed monthly on your active roll. Setup, data migration and staff training are done by us
        and included — there is nothing extra to buy.
      </p>
    </div>
  );
}
