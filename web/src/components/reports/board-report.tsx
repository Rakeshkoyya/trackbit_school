"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BarChart3 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { MemberBars, RangeToggle, StatCard, TrendSparkline } from "@/components/reports/report-ui";
import { EmptyState } from "@/components/ui/empty-state";
import { appApi } from "@/lib/app-api";

export function BoardReport({ boardId }: { boardId: string }) {
  const router = useRouter();
  const [range, setRange] = useState<"today" | "week">("today");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["board-report", boardId, range],
    queryFn: () => appApi.boardReport(boardId, range),
  });

  return (
    <div>
      <header className="mb-5">
        <button
          onClick={() => router.push(`/boards/${boardId}`)}
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Board
        </button>
        <div className="flex items-center justify-between gap-3">
          <h1 className="truncate text-2xl font-semibold tracking-tight">
            {data?.board_name ?? "Report"}
          </h1>
          <RangeToggle value={range} onChange={setRange} />
        </div>
      </header>

      {isLoading ? (
        <ReportSkeleton />
      ) : isError || !data ? (
        <EmptyState title="Report unavailable" body="This board may be private or removed." />
      ) : data.total === 0 ? (
        <EmptyState
          icon={BarChart3}
          title={range === "today" ? "Nothing scheduled today" : "Nothing scheduled this week"}
          body="Once tasks here have due dates, completion and on-time numbers show up."
        />
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Completion" value={`${data.completion_pct}%`} sub={`${data.done}/${data.total} done`} tone="success" />
            <StatCard label="On time" value={`${data.on_time_pct}%`} sub={`${data.on_time}/${data.done} done`} />
            <StatCard label="Overdue" value={data.overdue} tone={data.overdue > 0 ? "warning" : "default"} sub="still open" />
            <StatCard label="Scheduled" value={data.total} sub={range === "today" ? "today" : "last 7 days"} />
          </div>

          <section className="rounded-xl border border-border bg-card p-4">
            <TrendSparkline trend={data.trend} />
          </section>

          <section>
            <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              By person
            </h2>
            <MemberBars members={data.members} />
          </section>
        </div>
      )}
    </div>
  );
}

function ReportSkeleton() {
  return (
    <div className="animate-pulse space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-20 rounded-xl bg-muted" />
        ))}
      </div>
      <div className="h-24 rounded-xl bg-muted" />
      <div className="h-32 rounded-xl bg-muted" />
    </div>
  );
}
