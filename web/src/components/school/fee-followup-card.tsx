"use client";

/**
 * The teacher's fee follow-up, **inside her task** (V1-10, `D-83`).
 *
 * This is the one place in the product where a teacher sees fee data, and the
 * narrowing is exact:
 *
 * - **only the student on this task**, and only while she is its assignee — the
 *   server re-checks both on every read;
 * - **no fees nav item**, no class list, no collection figure, no other family;
 * - **no fee field on any academic surface** — not the report card, not growth,
 *   not the timeline, not the daily report, not a Lucy tool.
 *
 * Why it exists at all (`Q-66`(b), against the original recommendation): the
 * person making the call cannot make it usefully while blind to the number. The
 * card renders nothing at all when the task is not a fee follow-up, so it costs
 * an ordinary task nothing.
 */

import { useQuery } from "@tanstack/react-query";
import { IndianRupee, Phone } from "lucide-react";

import { schoolApi } from "@/lib/school-api";

const money = (n: number) =>
  `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

export function FeeFollowupCard({ taskId, category }: { taskId: string; category?: string | null }) {
  // Only ask for a task the school filed as a fee follow-up — an ordinary task
  // never triggers a fee read at all.
  const enabled = (category ?? "").toLowerCase() === "fees";
  const { data } = useQuery({
    queryKey: ["fee-followup", taskId],
    queryFn: () => schoolApi.feeFollowup(taskId),
    enabled,
    retry: false,
  });
  if (!enabled || !data) return null;

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold">
        <IndianRupee className="h-4 w-4" /> {data.student_name}
        {data.class_label ? (
          <span className="font-normal text-muted-foreground">· {data.class_label}</span>
        ) : null}
      </h2>
      <p className="mt-1 text-sm">
        <span className="font-semibold">{money(data.pending_amount)}</span> outstanding
        {data.due_date ? ` · due ${data.due_date}` : ""}
      </p>
      <p className="mt-0.5 text-xs text-muted-foreground">
        {money(data.paid_so_far)} of {money(data.total_fee)} paid this year.
      </p>
      {data.guardian_phone ? (
        <a href={`tel:${data.guardian_phone}`}
          className="mt-3 inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted/40">
          <Phone className="h-4 w-4" /> Call {data.guardian_name ?? "the family"}
        </a>
      ) : null}

      {data.notes.length ? (
        <div className="mt-4 border-t border-border pt-3">
          <p className="text-xs font-medium">What the family has already said</p>
          <ul className="mt-1 space-y-1">
            {data.notes.slice(0, 5).map((n) => (
              <li key={n.id} className="text-xs text-muted-foreground">
                {String(n.created_at).slice(0, 10)} — {n.said}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="mt-3 text-xs text-muted-foreground">
        Please speak to the family and record what they say when you complete this task.
      </p>
    </section>
  );
}
