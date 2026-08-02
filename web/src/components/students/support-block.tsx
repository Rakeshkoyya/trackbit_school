"use client";

/**
 * The support programme on a child's report card (V1-9, `S-180` fix #3).
 *
 * `schoolApi.studentInterventions` has existed since P3 and **no component ever
 * called it** — the fourth instance of "built, wired into the client, called by
 * nothing" the brainstorm found. So the report card showed a child's tier and
 * the tier history and never showed the plan attached to it: the one screen
 * where somebody asks *"and what are we doing about it?"*
 *
 * What it renders, and what it refuses to:
 *
 * - the plan **per subject** (`D-77`), with its owner by name and the exit
 *   criterion written when the child entered (`S-167`);
 * - closed plans stay visible — this is the only place the work pays off;
 * - **no tier on its own.** The band chip lives in the identity band above and
 *   carries its subject ("C · Hindi", `S-186`).
 *
 * Staff-only, like everything band-shaped (P4).
 */

import { useQuery } from "@tanstack/react-query";
import { HeartHandshake } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { schoolApi } from "@/lib/school-api";

export function SupportBlock({ studentId }: { studentId: string }) {
  const { data = [] } = useQuery({
    queryKey: ["student-interventions", studentId],
    queryFn: () => schoolApi.studentInterventions(studentId),
  });
  if (!data.length) return null;

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold">
        <HeartHandshake className="h-4 w-4" /> Support programme
      </h2>
      <p className="mt-0.5 text-xs text-muted-foreground">
        Staff-only — never shown to a parent.
      </p>
      <div className="mt-3 space-y-2">
        {data.map((iv) => (
          <div key={iv.id} className="rounded-lg border border-border p-3">
            <div className="flex flex-wrap items-center gap-2">
              {iv.subject_name ? <Badge tone="neutral">{iv.subject_name}</Badge> : null}
              <Badge tone={iv.status === "active" ? "warning" : "success"}>
                {iv.status === "active" ? "in the programme" : iv.status}
              </Badge>
              {iv.owner_name ? (
                <span className="text-xs text-muted-foreground">owner {iv.owner_name}</span>
              ) : (
                <span className="text-xs text-muted-foreground">no owner yet</span>
              )}
            </div>
            <p className="mt-1.5 text-sm">{iv.goal_text}</p>
            {iv.exit_criterion ? (
              <p className="mt-0.5 text-xs text-muted-foreground">
                Moves to {iv.target_tier} when: {iv.exit_criterion}
              </p>
            ) : null}
            {iv.outcome_note ? (
              <p className="mt-0.5 text-xs text-muted-foreground">{iv.outcome_note}</p>
            ) : null}
            {iv.items.length ? (
              <ul className="mt-2 space-y-0.5 text-xs text-muted-foreground">
                {iv.items.map((i) => (
                  <li key={i.id}>{i.done ? "✓" : "•"} {i.text}</li>
                ))}
              </ul>
            ) : null}
            {iv.status === "active" ? (
              <Link href={`/support/${iv.id}`}
                className="mt-2 inline-block text-xs font-medium text-primary hover:underline">
                open the check-in →
              </Link>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}
