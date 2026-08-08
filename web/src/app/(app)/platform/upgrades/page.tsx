"use client";

/**
 * Platform → Upgrades (`D-106`, operator only).
 *
 * The commercial loop, end to end, on one screen: a school asked, you call
 * them, you take the money, you set the plan. There is no gateway — so this is
 * not a dashboard about payments, it is a worklist.
 *
 * Two things here are deliberate:
 *
 * - **`feature_id` is shown.** It is the wall the school actually hit, which is
 *   the one piece of product feedback nobody had to be asked for.
 * - **The notes are ours.** `upgrade_request_notes` is platform data with no
 *   `org_id`, so what you write here is unreachable from anything the school
 *   can read. Write plainly.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { ApiError } from "@/lib/api-client";
import { formatPaise } from "@/lib/features";
import { platformApi } from "@/lib/platform-api";
import type { PlanTier, UpgradeRequest } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUSES = ["new", "contacted", "won", "lost"] as const;
const PLANS: PlanTier[] = ["free", "pro", "max", "ultra"];

const STATUS_STYLE: Record<string, string> = {
  new: "bg-primary/10 text-primary",
  contacted: "bg-warning/12 text-warning",
  won: "bg-success/12 text-success",
  lost: "bg-muted text-muted-foreground",
};

function RequestRow({ row }: { row: UpgradeRequest }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [open, setOpen] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["upgrades"] });
    qc.invalidateQueries({ queryKey: ["platform-orgs"] });
  };

  const addNote = useMutation({
    mutationFn: (statusTo: string | null) =>
      platformApi.addUpgradeNote(row.id, {
        note: note.trim() || null,
        status_to: statusTo,
      }),
    onSuccess: () => {
      setNote("");
      invalidate();
      toast.success("Noted.");
    },
    onError: (e: unknown) =>
      toast.error(e instanceof ApiError ? e.message : "Could not save the note."),
  });

  // Setting the plan and closing the request are two separate decisions, so they
  // are two separate actions — "won" with the plan not actually moved is a state
  // we never want to reach by accident.
  const assign = useMutation({
    mutationFn: () =>
      platformApi.assignPlan(row.org_id, {
        plan: row.requested_plan,
        reason: `Upgrade request ${row.id}`,
      }),
    onSuccess: () => {
      invalidate();
      toast.success(`${row.org_name ?? "School"} moved to ${row.requested_plan}.`);
    },
    onError: (e: unknown) =>
      toast.error(e instanceof ApiError ? e.message : "Could not change the plan."),
  });

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-medium">{row.org_name ?? "—"}</p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {row.current_plan?.toUpperCase() ?? "—"} → {row.requested_plan.toUpperCase()}
            {row.monthly_paise != null ? (
              <>
                <span className="mx-2 text-border">·</span>
                {formatPaise(row.monthly_paise)}/month for {row.students} students
              </>
            ) : null}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Asked by {row.requested_by_name ?? "—"} on{" "}
            {new Date(row.created_at).toLocaleDateString("en-IN", {
              day: "numeric",
              month: "short",
            })}
            {row.feature_id ? (
              <>
                <span className="mx-2 text-border">·</span>
                hit <span className="font-mono">{row.feature_id}</span>
              </>
            ) : null}
          </p>
          {row.message ? (
            <p className="mt-2 rounded-lg bg-muted/50 px-3 py-2 text-sm">{row.message}</p>
          ) : null}
        </div>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            STATUS_STYLE[row.status],
          )}
        >
          {row.status}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Note / move"}
        </Button>
        <Button size="sm" disabled={assign.isPending} onClick={() => assign.mutate()}>
          {assign.isPending
            ? "Setting…"
            : `Set plan to ${row.requested_plan.toUpperCase()}`}
        </Button>
      </div>

      {open ? (
        <div className="mt-3 space-y-2">
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            placeholder="Called them, ringing back Tuesday…"
            className="w-full resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={addNote.isPending || !note.trim()}
              onClick={() => addNote.mutate(null)}
            >
              Add note
            </Button>
            {STATUSES.filter((s) => s !== row.status).map((s) => (
              <Button
                key={s}
                size="sm"
                variant="ghost"
                disabled={addNote.isPending}
                onClick={() => addNote.mutate(s)}
              >
                Mark {s}
              </Button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/**
 * Change any school's plan, request or no request.
 *
 * Founder, 2026-08-08: "sometimes I get request directly, they call me — in
 * that case I just open my super admin tab and search the school and upgrade
 * them as needed". So the queue below is a convenience, never the only door:
 * most upgrades will start as a phone call that left no row anywhere.
 *
 * Every tier is offered, not just the ones above the current plan — a school
 * that stops paying has to be moved back down, and that is the same action.
 */
function SchoolPlanPicker() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const { data: orgs } = useQuery({
    queryKey: ["platform-orgs"],
    queryFn: platformApi.orgs,
  });

  const assign = useMutation({
    mutationFn: (v: { orgId: string; plan: PlanTier }) =>
      platformApi.assignPlan(v.orgId, { plan: v.plan, reason: "Set by operator" }),
    onMutate: (v) => setBusy(`${v.orgId}:${v.plan}`),
    onSettled: () => setBusy(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform-orgs"] });
      qc.invalidateQueries({ queryKey: ["upgrades"] });
      toast.success("Plan changed.");
    },
    onError: (e: unknown) =>
      toast.error(e instanceof ApiError ? e.message : "Could not change the plan."),
  });

  const term = q.trim().toLowerCase();
  // Unfiltered this is every school we have; the list is only useful once it is
  // short, so an empty box shows the handful most recently created.
  const matches = (orgs ?? [])
    .filter((o) => !term || o.name.toLowerCase().includes(term))
    .slice(0, term ? 25 : 5);

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="font-medium">Change a school&apos;s plan</p>
      <p className="mt-0.5 text-sm text-muted-foreground">
        They rang instead of asking in the app? Find them and set it directly.
      </p>

      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search schools by name…"
        className="mt-3 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />

      <div className="mt-3 space-y-2">
        {!matches.length ? (
          <p className="text-sm text-muted-foreground">No schools match that.</p>
        ) : (
          matches.map((o) => (
            <div
              key={o.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-border px-3 py-2"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{o.name}</p>
                <p className="text-xs text-muted-foreground">
                  on {o.plan.toUpperCase()} · {o.student_count} students
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {PLANS.map((p) => (
                  <Button
                    key={p}
                    size="sm"
                    variant={o.plan === p ? "primary" : "outline"}
                    disabled={o.plan === p || busy !== null}
                    onClick={() => assign.mutate({ orgId: o.id, plan: p })}
                  >
                    {busy === `${o.id}:${p}` ? "…" : p}
                  </Button>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export default function UpgradesPage() {
  const [status, setStatus] = useState<string>("");
  const { data, isLoading } = useQuery({
    queryKey: ["upgrades", status],
    queryFn: () => platformApi.upgrades(status || undefined),
  });

  return (
    <AuthGuard requireSuperAdmin>
      <div className="space-y-5 p-4 sm:p-6">
        <PageHeader
          title="Plans & upgrades"
          subtitle="Set any school's plan directly, or work the requests that came in through the app."
        />

        <SchoolPlanPicker />

        <div className="flex flex-wrap gap-2">
          {["", ...STATUSES].map((s) => (
            <Button
              key={s || "all"}
              size="sm"
              variant={status === s ? "primary" : "outline"}
              onClick={() => setStatus(s)}
            >
              {s || "All"}
            </Button>
          ))}
        </div>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : !data?.length ? (
          <p className="rounded-xl border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
            No requests{status ? ` marked ${status}` : ""} yet.
          </p>
        ) : (
          <div className="space-y-3">
            {data.map((row) => (
              <RequestRow key={row.id} row={row} />
            ))}
          </div>
        )}
      </div>
    </AuthGuard>
  );
}
