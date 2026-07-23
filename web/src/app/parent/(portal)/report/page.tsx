"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Loader2, Sparkles, TrendingUp } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { parentApi, type ParentChapter } from "@/lib/parent-api";
import { cn } from "@/lib/utils";

import { useParentPortal } from "../parent-context";

function Chapter({ c }: { c: ParentChapter }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-border">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm"
      >
        <span className="min-w-0 truncate font-medium">{c.title}</span>
        <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
          <span className="tabular-nums">
            {c.topics_taught}/{c.topics_total}
          </span>
          {c.topics_missed > 0 ? (
            <Badge tone="warning">{c.topics_missed} missed</Badge>
          ) : null}
          <ChevronDown className={cn("h-4 w-4 transition-transform", open && "rotate-180")} />
        </span>
      </button>
      {open ? (
        <ul className="space-y-1.5 border-t border-border px-3 py-2">
          {c.topics.map((t) => (
            <li key={t.topic_id} className="flex items-center justify-between gap-2 text-xs">
              <span
                className={cn(
                  "min-w-0 truncate",
                  t.status === "pending" && "text-muted-foreground",
                )}
              >
                {t.title}
              </span>
              <span className="shrink-0 text-muted-foreground">
                {t.status === "pending"
                  ? "Not taught yet"
                  : t.student_attendance === "absent"
                    ? "Taught while absent"
                    : t.taught_on ?? "Taught"}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export default function ParentReportPage() {
  const { child } = useParentPortal();
  const { data, isLoading } = useQuery({
    queryKey: ["parent", "report", child?.student_id],
    queryFn: () => parentApi.report(child!.student_id),
    enabled: !!child,
  });

  if (!child || isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!data) return null;

  const scores = data.subjects
    .flatMap((s) => s.scores.map((sc) => ({ ...sc, subject: s.subject_name })))
    .sort((a, b) => (a.date < b.date ? 1 : -1));

  return (
    <div className="space-y-4">
      {/* Overall attendance */}
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">Overall attendance</p>
            <p className="mt-0.5 text-2xl font-semibold tabular-nums">
              {data.attendance.pct != null ? `${data.attendance.pct}%` : "—"}
            </p>
          </div>
          <p className="text-right text-xs text-muted-foreground">
            {data.attendance.present} present · {data.attendance.absent} absent
            {data.attendance.late ? ` · ${data.attendance.late} late` : ""}
          </p>
        </div>
      </section>

      {/* Strengths & growth areas — derived phrases, the curated cut. */}
      {data.strengths.length > 0 || data.growth_areas.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.strengths.length ? (
            <section className="rounded-xl border border-border bg-card p-4">
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <Sparkles className="h-4 w-4 text-success" /> Doing well
              </h2>
              <ul className="list-inside space-y-1 text-sm">
                {data.strengths.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {data.growth_areas.length ? (
            <section className="rounded-xl border border-border bg-card p-4">
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                <TrendingUp className="h-4 w-4 text-warning" /> Needs attention
              </h2>
              <ul className="list-inside space-y-1 text-sm">
                {data.growth_areas.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}

      {/* Chapter drill-down per subject */}
      {data.subjects.map((s) =>
        s.chapters.length ? (
          <section key={s.subject_name} className="rounded-xl border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-semibold">{s.subject_name}</h2>
            <div className="space-y-2">
              {s.chapters.map((c) => (
                <Chapter key={c.unit_id} c={c} />
              ))}
            </div>
          </section>
        ) : null,
      )}

      {/* Test history */}
      {scores.length ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 text-sm font-semibold">Test results</h2>
          <ul className="space-y-2">
            {scores.map((sc, i) => (
              <li key={i} className="flex items-center justify-between gap-2 text-sm">
                <span className="min-w-0 truncate">
                  {sc.cycle_name}
                  <span className="ml-1.5 text-xs text-muted-foreground">{sc.subject}</span>
                </span>
                <span className="shrink-0 tabular-nums">
                  {sc.score}/{sc.max_score}
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
