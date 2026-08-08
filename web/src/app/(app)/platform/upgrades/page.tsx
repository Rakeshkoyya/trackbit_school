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
import type { UpgradeRequest } from "@/lib/types";
import { cn } from "@/lib/utils";

const STATUSES = ["new", "contacted", "won", "lost"] as const;

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
          title="Upgrade requests"
          subtitle="A school asked to move up. Call them, take the payment, then set the plan here."
        />

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
