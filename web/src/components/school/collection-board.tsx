"use client";

/**
 * The collection board (V1-10, `D-64`/`S-152`/`S-155`).
 *
 * The old landing page led with four bare numbers on three different
 * denominators — two amounts, one amount-past-a-date, and a **count of
 * instalments** — with no sentence, nothing named, and nothing comparable to
 * anything. This replaces it in place (`S-152`): `/fees` already exists as an
 * area, and a second fee screen would immediately disagree with the first.
 *
 * The order is the plan's shape: **sentence → shape → named rows → action.**
 *
 * - `S-155` the sentence names the quarter and how it compares, not the total.
 * - `S-163` `collected` / `pending` / `overdue` are shown as three states and
 *   never added — pending is a forecast, overdue is a phone call.
 * - `S-159` every class row carries **both denominators**, and the list sorts by
 *   families, because a morning of phone calls is denominated in calls.
 * - `S-157` the defaulter row names the **family** and gives you the number.
 * - ux §7 the row remembers what already fired, so nobody is chased twice — and
 *   `S-161` it shows what the family *said*, not that a button was pressed.
 * - `D-88` dues carried from a previous year get their own labelled line and are
 *   never inside the figures above.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Phone, UserPlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ChartCard, TrendLine } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { DefaulterRow } from "@/lib/school-types";

const money = (n: number) =>
  `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

function AssignSheet({ row, onClose }: { row: DefaulterRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [member, setMember] = useState("");
  const { data: members } = useQuery({ queryKey: ["members"], queryFn: appApi.members });
  const teachers = (members?.members ?? []).filter((x) => x.member_id);

  const assign = useMutation({
    mutationFn: () => schoolApi.assignFeeFollowup(row!.student_fee_id, { member_id: member }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collection"] });
      toast.success("Assigned — the detail travels with the task");
      setMember(""); onClose();
    },
    onError: (e) => showApiError(e, "Could not assign"),
  });

  return (
    <Sheet open={!!row} onOpenChange={(v) => { if (!v) onClose(); }}
      title={row ? `Follow up — ${row.student_name}` : ""}>
      {row ? (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            The task carries the amount, the due date and what the family has already
            said — so whoever rings is not the fourth person this month to ask the
            same question. They see it for this family only.
          </p>
          <div>
            <Label htmlFor="who">Who should call?</Label>
            <select id="who" className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={member} onChange={(e) => setMember(e.target.value)}>
              <option value="">Choose…</option>
              {teachers.map((t) => (
                <option key={t.member_id!} value={t.member_id!}>{t.name}</option>
              ))}
            </select>
          </div>
          <Button className="w-full" disabled={!member || assign.isPending}
            onClick={() => assign.mutate()}>
            Assign the follow-up
          </Button>
        </div>
      ) : null}
    </Sheet>
  );
}

export function CollectionBoard({ yearId }: { yearId: string | null }) {
  const qc = useQueryClient();
  const [quarter, setQuarter] = useState<string | undefined>();
  const [assignFor, setAssignFor] = useState<DefaulterRow | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["collection", yearId, quarter],
    queryFn: () => schoolApi.collectionBoard({ yearId: yearId ?? undefined, quarter }),
  });
  const remind = useMutation({
    mutationFn: (sfId: string) => schoolApi.remindFee(sfId),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["collection"] });
      // A skip is not an error — "already reminded" is the feature working.
      if (res.sent) toast.success(res.message);
      else toast.message(res.message);
    },
    onError: (e) => showApiError(e, "Could not send the reminder"),
  });

  if (isLoading || !data) return <div className="h-56 animate-pulse rounded-xl bg-muted" />;

  const curve = data.curve.map((p) => ({
    x: p.day.slice(5), collected: p.collected, previous: p.previous }));

  return (
    <div className="space-y-5">
      {/* the sentence */}
      <div className="rounded-xl border border-border bg-card p-4">
        <p className="text-sm leading-relaxed">{data.headline}</p>
        <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs">
          <span><span className="font-semibold">{money(data.collected)}</span> collected</span>
          <span className="text-muted-foreground">
            <span className="font-semibold text-foreground">{money(data.pending)}</span> pending
          </span>
          <span className="text-muted-foreground">
            <span className="font-semibold text-foreground">{money(data.overdue)}</span> overdue
          </span>
          <span className="text-muted-foreground">of {money(data.billed)} billed</span>
        </div>
        {/* Three states, never one "outstanding" figure — one is a forecast and
            the other is a phone call. */}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {data.quarters.map((q) => (
            <button key={q.label} type="button"
              onClick={() => setQuarter(q.label === data.quarter ? undefined : q.label)}
              className={`rounded-md border px-3 py-1.5 text-xs transition ${
                q.label === data.quarter
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-border hover:bg-muted/40"}`}>
              {q.label} · {q.pct == null ? "nothing due" : `${q.pct}%`}
            </button>
          ))}
        </div>
        {data.unscheduled_note ? (
          <p className="mt-2 text-xs text-muted-foreground">{data.unscheduled_note}</p>
        ) : null}
        {data.carried ? (
          <p className="mt-2 rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            {data.carried.note}
          </p>
        ) : null}
      </div>

      {/* the shape */}
      {curve.length > 1 ? (
        <ChartCard title="Collection through the quarter"
          hint="Cumulative, with the previous quarter laid over it day for day.">
          <TrendLine rows={curve} yUnit="₹" height={200}
            series={[{ key: "collected", label: data.quarter ?? "This quarter" },
                     { key: "previous", label: "Previous quarter" }]} />
        </ChartCard>
      ) : null}

      {/* which class to push this week */}
      {data.by_class.length ? (
        <section>
          <h2 className="mb-2 text-sm font-semibold">Where it is concentrated</h2>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Class</th>
                  <th className="px-2 py-2">Families pending</th>
                  <th className="px-2 py-2">Overdue</th>
                  <th className="px-2 py-2">Collected</th>
                </tr>
              </thead>
              <tbody>
                {data.by_class.map((c) => (
                  <tr key={c.class_label} className="border-t border-border">
                    <td className="px-3 py-1.5 font-medium">{c.class_label}</td>
                    {/* Both denominators: ₹1.4L is one big defaulter or fourteen
                        small ones, and those need opposite actions. */}
                    <td className="px-2 py-1.5 tabular-nums">
                      {c.families_pending} of {c.families_total}
                    </td>
                    <td className="px-2 py-1.5 tabular-nums">{money(c.overdue)}</td>
                    <td className="px-2 py-1.5 tabular-nums text-muted-foreground">
                      {money(c.collected)}{c.pct != null ? ` · ${c.pct}%` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}

      {/* the named list — built since P0-D and, until now, called by nothing */}
      <section>
        <h2 className="mb-2 text-sm font-semibold">Who to ring</h2>
        {data.defaulters.length ? (
          <div className="space-y-2">
            {data.defaulters.map((d) => (
              <div key={d.student_fee_id}
                className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    <Link href={`/fees/${d.student_fee_id}`} className="hover:underline">
                      {d.student_name}
                    </Link>
                    {d.class_label ? (
                      <span className="ml-2 text-xs text-muted-foreground">{d.class_label}</span>
                    ) : null}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {money(d.overdue_amount)} overdue
                    {d.earliest_due_date ? ` since ${d.earliest_due_date}` : ""}
                    {d.guardian_name ? ` · ${d.guardian_name}` : ""}
                  </p>
                  {d.last_said ? (
                    <p className="mt-0.5 text-xs italic text-muted-foreground">
                      “{d.last_said}” · {d.last_said_on}
                    </p>
                  ) : null}
                </div>
                {d.reminded_on ? (
                  <Badge tone="neutral">reminded {d.reminded_on}</Badge>
                ) : null}
                {d.assigned_on ? <Badge tone="neutral">assigned</Badge> : null}
                {d.guardian_phone ? (
                  <a href={`tel:${d.guardian_phone}`}
                    className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1.5 text-xs hover:bg-muted/40">
                    <Phone className="h-3.5 w-3.5" /> call
                  </a>
                ) : null}
                <Button size="sm" variant="outline" disabled={remind.isPending}
                  onClick={() => remind.mutate(d.student_fee_id)}>
                  <CalendarClock className="h-4 w-4" /> Remind
                </Button>
                <Button size="sm" variant="outline" onClick={() => setAssignFor(d)}>
                  <UserPlus className="h-4 w-4" /> Assign
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <p className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
            Nobody is past a due date. Nothing to chase today.
          </p>
        )}
      </section>

      <AssignSheet row={assignFor} onClose={() => setAssignFor(null)} />
    </div>
  );
}
