"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "@/lib/api-client";
import type { PlanPrice, PlanTier } from "@/lib/types";

/**
 * Answers the buyer's first question — "what does this cost me?" — before they
 * have to ask a salesperson.
 *
 * `D-106`: the rate is **fetched, not typed**. This used to hardcode ₹100 and a
 * 500-student floor, which quietly went on being wrong after the product moved
 * to four per-student tiers. The floor is gone too: with a free tier, a small
 * school is a funnel rather than a misfit.
 */

const PAID: { plan: PlanTier; label: string }[] = [
  { plan: "pro", label: "Pro" },
  { plan: "max", label: "Max" },
  { plan: "ultra", label: "Ultra" },
];

const FALLBACK: Record<string, number> = { pro: 1000, max: 2500, ultra: 8000 };

const MIN_STUDENTS = 100;
const MAX_STUDENTS = 3000;

const inr = (n: number) => `₹${Math.round(n).toLocaleString("en-IN")}`;

export function PricingCalculator() {
  const [students, setStudents] = useState(800);
  const [plan, setPlan] = useState<PlanTier>("max");

  const { data } = useQuery<PlanPrice[]>({
    queryKey: ["public-plans"],
    queryFn: () => api.get<PlanPrice[]>("/marketing/plans"),
    staleTime: 60 * 60 * 1000,
    retry: false,
  });

  const paise =
    data?.find((p) => p.plan === plan)?.amount_paise_per_student ?? FALLBACK[plan];
  const rate = paise / 100;
  const monthly = students * rate;

  return (
    <div className="mk-calc">
      <div className="mk-calc-out">
        <p className="mk-eyebrow">Your monthly cost</p>
        <p className="mk-calc-total">{inr(monthly)}</p>
        <p className="mk-calc-sub">
          {inr(monthly * 12)} a year · {students.toLocaleString("en-IN")} students ×{" "}
          {inr(rate)}
        </p>
      </div>

      <div className="mk-calc-plans">
        {PAID.map((p) => (
          <button
            key={p.plan}
            type="button"
            aria-pressed={plan === p.plan}
            onClick={() => setPlan(p.plan)}
            className={plan === p.plan ? "is-on" : undefined}
          >
            {p.label}
          </button>
        ))}
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
        <span>100</span>
        <span>3,000+</span>
      </div>

      <p className="mk-calc-note">
        Billed monthly on your active roll. Setup, data migration and staff training are done by us
        and included — there is nothing extra to buy. Recording the day stays free whatever you
        choose.
      </p>
    </div>
  );
}
