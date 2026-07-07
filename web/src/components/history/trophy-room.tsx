"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Flame, Trophy } from "lucide-react";

import { DotCalendar } from "@/components/history/dot-calendar";
import { StatCard } from "@/components/reports/report-ui";
import { EmptyState } from "@/components/ui/empty-state";
import { appApi } from "@/lib/app-api";
import { timeLabel } from "@/lib/format";
import type { CompletedItem } from "@/lib/types";

function groupByDay(items: CompletedItem[]): [string, CompletedItem[]][] {
  const groups = new Map<string, CompletedItem[]>();
  for (const it of items) {
    const key = new Date(it.completed_at).toLocaleDateString(undefined, {
      weekday: "long",
      month: "short",
      day: "numeric",
    });
    const arr = groups.get(key) ?? [];
    arr.push(it);
    groups.set(key, arr);
  }
  return [...groups.entries()];
}

export function TrophyRoom() {
  const { data, isLoading } = useQuery({ queryKey: ["history"], queryFn: appApi.history });

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-8 w-32 rounded bg-muted" />
        <div className="h-24 rounded-xl bg-muted" />
        <div className="h-32 rounded-xl bg-muted" />
      </div>
    );
  }

  const hist = data;
  const hasHistory = (hist?.total_completed ?? 0) > 0;

  return (
    <div>
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Your record</h1>
        <p className="mt-1 text-sm text-muted-foreground">Every finish, kept.</p>
      </header>

      {!hasHistory ? (
        <EmptyState
          icon={CheckCircle2}
          title="Nothing finished yet"
          body="Tasks you complete will build your record here — a calendar of effort and your best weeks."
        />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="This week" value={hist!.this_week_count} sub="done" tone="success" />
            <StatCard label="Best week" value={hist!.personal_best} sub="your record" />
            <StatCard
              label="On a roll"
              value={hist!.current_run >= 2 ? `${hist!.current_run}d` : "—"}
              sub={hist!.current_run >= 2 ? "all-clear run" : "finish today"}
            />
          </div>

          {hist!.current_run >= 2 ? (
            <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-4 text-sm">
              <Flame className="h-5 w-5 text-warning" />
              <span>
                <strong>{hist!.current_run} days in a row</strong> finishing everything. Quietly
                excellent.
              </span>
            </div>
          ) : null}

          <section className="rounded-xl border border-border bg-card p-4">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Trophy className="h-4 w-4 text-muted-foreground" /> Last 10 weeks
            </h2>
            <DotCalendar dots={hist!.dots} />
          </section>

          {hist!.completions.length > 0 ? (
            <section>
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Completed
              </h2>
              <div className="space-y-5">
                {groupByDay(hist!.completions).map(([day, items]) => (
                  <div key={day}>
                    <p className="mb-2 text-xs font-medium text-muted-foreground">{day}</p>
                    <ul className="space-y-1.5">
                      {items.map((it) => (
                        <li
                          key={it.id}
                          className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2.5"
                        >
                          <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                          <span className="min-w-0 flex-1 truncate text-sm">{it.title}</span>
                          <span className="shrink-0 text-xs text-muted-foreground">
                            {it.board_name}
                            {timeLabel(it.completed_at) ? ` · ${timeLabel(it.completed_at)}` : ""}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </div>
  );
}
