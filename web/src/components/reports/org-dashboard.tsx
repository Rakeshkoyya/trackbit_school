"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Bell, Check, Info, Repeat } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { MemberBars, ProgressBar, RangeToggle, StatCard } from "@/components/reports/report-ui";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";
import type { MemberBar } from "@/lib/types";

export function OrgDashboard() {
  const [range, setRange] = useState<"today" | "week">("today");
  const [nudged, setNudged] = useState<Set<string>>(new Set());

  const { data, isLoading, isError } = useQuery({
    queryKey: ["org-dashboard", range],
    queryFn: () => appApi.orgDashboard(range),
  });

  const nudge = useMutation({
    mutationFn: (userId: string) => appApi.nudge(userId),
    onSuccess: (res, userId) => {
      if (res.sent) {
        setNudged((s) => new Set(s).add(userId));
        toast.success("Nudge sent ✓");
      } else if (res.reason === "recently_nudged") {
        setNudged((s) => new Set(s).add(userId));
        toast("Already nudged in the last few hours");
      } else {
        toast("Nothing overdue for them right now 🙂");
      }
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not send nudge"),
  });

  const nudgeButton = (m: MemberBar) => {
    const open = m.total - m.done;
    const done = nudged.has(m.user_id);
    if (open <= 0) return null;
    return (
      <Button
        variant="ghost"
        size="sm"
        disabled={done || nudge.isPending}
        onClick={() => nudge.mutate(m.user_id)}
      >
        {done ? (
          <>
            <Check className="h-4 w-4 text-success" /> Sent
          </>
        ) : (
          <>
            <Bell className="h-4 w-4" /> Nudge
          </>
        )}
      </Button>
    );
  };

  return (
    <div>
      <header className="mb-5 flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <RangeToggle value={range} onChange={setRange} />
      </header>

      {isLoading ? (
        <DashboardSkeleton />
      ) : isError || !data ? (
        <EmptyState title="Dashboard unavailable" body="Please try again in a moment." />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Org completion" value={`${data.completion_pct}%`} sub={`${data.done}/${data.total} done`} tone="success" />
            <StatCard label="On time" value={`${data.on_time_pct}%`} sub={`${data.on_time}/${data.done}`} />
            <StatCard label="Still open" value={Math.max(0, data.total - data.done)} sub="across public boards" />
            <StatCard label="Overdue" value={data.overdue} tone={data.overdue > 0 ? "warning" : "default"} sub="past due" />
          </div>

          {data.orphaned_count > 0 ? (
            <p className="flex items-start gap-1.5 rounded-lg border border-warning/30 bg-warning-soft/40 p-3 text-sm text-foreground">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              {data.orphaned_count} {data.orphaned_count === 1 ? "task" : "tasks"} orphaned by a
              removal or board change — now unassigned and waiting to be picked up.
            </p>
          ) : null}

          <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            Private boards aren&apos;t included — these numbers cover public boards only.
          </p>

          <section>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              By person
            </h2>
            <MemberBars members={data.members} action={nudgeButton} />
          </section>

          {data.boards.length > 0 ? (
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                By board
              </h2>
              <ul className="space-y-3">
                {data.boards.map((b) => (
                  <li key={b.board_id}>
                    <Link href={`/boards/${b.board_id}/report`} className="block rounded-lg border border-border bg-card p-3 hover:bg-muted/40">
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="truncate text-sm font-medium">{b.name}</span>
                        <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                          {b.completion_pct}% · {b.done}/{b.total}
                        </span>
                      </div>
                      <div className="mt-2">
                        <ProgressBar done={b.done} total={b.total} />
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {data.hotspot_members.length > 0 || data.hotspot_tasks.length > 0 ? (
            <section className="rounded-xl border border-border bg-card p-4">
              <div className="mb-1 flex items-center gap-2">
                <Repeat className="h-4 w-4 text-muted-foreground" />
                <h2 className="text-sm font-semibold">Reassignment signal</h2>
              </div>
              <p className="mb-3 text-xs text-muted-foreground">
                Work that bounces between people — usually a sign a task is unclear or mis-routed, not
                that anyone&apos;s slacking. Last 14 days.
              </p>
              {data.hotspot_members.length > 0 ? (
                <ul className="mb-3 space-y-1.5">
                  {data.hotspot_members.map((m) => (
                    <li key={m.user_id} className="flex items-center justify-between text-sm">
                      <span className="truncate">{m.name}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {m.passes_received} passed their way
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {data.hotspot_tasks.length > 0 ? (
                <ul className="space-y-1.5 border-t border-border pt-3">
                  {data.hotspot_tasks.map((t) => (
                    <li key={t.id} className="flex items-center justify-between gap-2 text-sm">
                      <Link href={`/task/${t.id}`} className="truncate hover:underline">
                        {t.title}
                      </Link>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        ↩ {t.pass_count}× · {t.board_name}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl bg-muted" />
        ))}
      </div>
      <div className="h-32 rounded-xl bg-muted" />
    </div>
  );
}
