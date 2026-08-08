"use client";

/**
 * The public price table (`D-106`).
 *
 * **Fetched, not typed.** The founder's "the plan number and costing might
 * change regularly because we are just launching" is only true if changing a
 * price needs no deploy — so this reads `GET /marketing/plans`, which the
 * operator edits from `/platform`. Hardcoding the numbers here is exactly the
 * duplication that left the old page advertising ₹100 flat long after the
 * product had moved on.
 *
 * Falls back to the launch prices if the API is unreachable: a marketing page
 * that renders no prices at all is worse than one showing slightly stale ones.
 */

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api-client";
import type { PlanPrice, PlanTier } from "@/lib/types";

const FALLBACK: Record<PlanTier, number> = {
  free: 0,
  pro: 1000,
  max: 2500,
  ultra: 8000,
};

const TIERS: {
  plan: PlanTier;
  name: string;
  line: string;
  sells: string[];
}[] = [
  {
    plan: "free",
    name: "Free",
    line: "The record exists.",
    sells: [
      "Attendance, every period",
      "Homework and classwork logging",
      "Syllabus, plans and the timetable",
      "Events, birthdays, ABC support",
      "The daily report, written for you",
    ],
  },
  {
    plan: "pro",
    name: "Pro",
    line: "The record becomes a picture.",
    sells: [
      "The academic record over time",
      "Homework check-sheet and day book",
      "Exams, result sheets and trends",
      "Fee collection and ledgers",
      "Report cards",
    ],
  },
  {
    plan: "max",
    name: "Max",
    line: "The school runs itself.",
    sells: [
      "Staff, leave and timesheets",
      "Teacher workload",
      "Task management",
      "Parent portal and communications",
      "Lucy, the AI assistant",
    ],
  },
  {
    plan: "ultra",
    name: "Ultra",
    line: "The school connects.",
    sells: ["Agent connections (MCP)", "Connect TrackBit to your own tools"],
  },
];

function rupees(paise: number): string {
  return `₹${Math.round(paise / 100).toLocaleString("en-IN")}`;
}

export function PricingTiers() {
  const { data } = useQuery<PlanPrice[]>({
    queryKey: ["public-plans"],
    queryFn: () => api.get<PlanPrice[]>("/marketing/plans"),
    staleTime: 60 * 60 * 1000,
    retry: false,
  });

  const priceOf = (plan: PlanTier): number =>
    data?.find((p) => p.plan === plan)?.amount_paise_per_student ?? FALLBACK[plan];

  return (
    <div className="mk-tiers">
      {TIERS.map((tier) => {
        const paise = priceOf(tier.plan);
        return (
          <div key={tier.plan} className="mk-tier">
            <p className="mk-eyebrow">{tier.name}</p>
            <p className="mk-tier-line">{tier.line}</p>
            <div className="mk-price-rate">
              <strong>{paise === 0 ? "Free" : rupees(paise)}</strong>
              {paise > 0 ? <span>per student, per month</span> : <span>forever</span>}
            </div>
            <ul className="mk-includes">
              {tier.sells.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}
