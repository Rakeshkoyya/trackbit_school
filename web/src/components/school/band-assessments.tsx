"use client";

/**
 * ABC bands → Assessments (founder 2026-08-05) — the feed of every check she has
 * set, and the door to recording one.
 *
 * **Paginated and grouped by class on purpose.** A weekly check on six children
 * is 40 rows a term and hundreds across a year; a screen that loads all of them
 * is a screen that stops opening. Grouping is by class because that is how she
 * arrives — she is about to see 6-A, not "everything in date order".
 *
 * `status` is DERIVED from the results, never stored, so a row can never claim
 * to be evaluated when the numbers say otherwise. And **`pending` is a state,
 * not an empty score**: an assessment nobody has marked shows the word and the
 * button that fixes it, never a bold 0%.
 *
 * The one figure on a row is the server's `caption` — the average with its own
 * denominator, in its own metric's words. It is rendered, never recomposed: a
 * client dividing `average / max_marks` for itself is how the browser grew the
 * two `.reduce()` calls `S-51` had to hunt down.
 *
 * Never on this screen (`S-170`): how much of her roster she has got through as
 * a percentage, a comparison against another owner, or a streak.
 */

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, ClipboardCheck, Plus } from "lucide-react";
import { useState } from "react";

import { BandAssessmentCreate } from "@/components/school/band-assessment-create";
import { BandAssessmentSheetDialog } from "@/components/school/band-assessment-sheet";
import { ColumnHead, Empty, Section } from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import type { BandAssessmentRow } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const STATUS_TONE: Record<string, "neutral" | "warning" | "success"> = {
  // `pending` is neutral, never a warning: not-captured is never red (ux §5).
  pending: "neutral",
  partial: "warning",
  evaluated: "success",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "not evaluated",
  partial: "part evaluated",
  evaluated: "evaluated",
};

const FILTERS: { key: string | undefined; label: string }[] = [
  { key: undefined, label: "All" },
  { key: "pending", label: "To evaluate" },
  { key: "partial", label: "Part done" },
  { key: "evaluated", label: "Done" },
];

function Row({ r, onOpen }: { r: BandAssessmentRow; onOpen: () => void }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 border-t border-border px-3 py-2.5 first:border-t-0 sm:grid-cols-[minmax(0,2fr)_minmax(0,1.4fr)_auto]">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{r.name}</p>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {r.given_on}
          {r.subject_name ? ` · ${r.subject_name}` : ""}
          {r.due_date ? ` · due ${r.due_date}` : ""}
          {r.author_name ? ` · ${r.author_name}` : ""}
          {/* A frozen list and a live one behave differently a month later, so
              the row says which it is. */}
          {r.covers_all ? "" : " · fixed list"}
        </p>
      </div>

      {/* The server's sentence, rendered — the figure with its denominator, in
          this metric's own words. */}
      <p className="text-xs text-muted-foreground">{r.caption}</p>

      <div className="flex shrink-0 items-center gap-2">
        <Badge tone={STATUS_TONE[r.status] ?? "neutral"}>
          {STATUS_LABEL[r.status] ?? r.status}
        </Badge>
        <Button size="sm" variant={r.status === "evaluated" ? "outline" : "primary"} onClick={onOpen}>
          {r.status === "evaluated" ? "Open" : "Evaluate"}
        </Button>
      </div>
    </div>
  );
}

export function BandAssessments() {
  const [classId, setClassId] = useState<string | undefined>(undefined);
  const [status, setStatus] = useState<string | undefined>(undefined);
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(false);
  const [openId, setOpenId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["band-assessments", classId ?? "all", status ?? "all", page],
    queryFn: () => schoolApi.bandAssessments({ classId, status, page, perPage: 20 }),
  });

  if (isLoading || !data) return <PageLoading label="Loading assessments…" />;

  const byClass = new Map<string, BandAssessmentRow[]>();
  for (const r of data.rows) {
    byClass.set(r.class_label, [...(byClass.get(r.class_label) ?? []), r]);
  }

  return (
    <>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <p className="min-w-0 flex-1 rounded-xl border border-border bg-card p-4 text-sm leading-relaxed">
          {data.headline}
        </p>
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> New assessment
        </Button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => {
              setStatus(f.key);
              setPage(1);
            }}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              status === f.key
                ? "border-primary bg-primary/10 font-medium text-primary"
                : "border-border hover:bg-muted/50",
            )}
          >
            {f.label}
            {f.key === "pending" && data.open_count ? (
              <span className="ml-1 text-muted-foreground">{data.open_count}</span>
            ) : null}
          </button>
        ))}

        {data.classes.length > 1 ? (
          <>
            <span className="mx-1 h-4 w-px bg-border" />
            <button
              type="button"
              onClick={() => {
                setClassId(undefined);
                setPage(1);
              }}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                classId === undefined
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-border hover:bg-muted/50",
              )}
            >
              All classes
            </button>
            {data.classes.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => {
                  setClassId(c.id);
                  setPage(1);
                }}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs transition-colors",
                  classId === c.id
                    ? "border-primary bg-primary/10 font-medium text-primary"
                    : "border-border hover:bg-muted/50",
                )}
              >
                {c.label} <span className="text-muted-foreground">{c.count}</span>
              </button>
            ))}
          </>
        ) : null}
      </div>

      <div className="mt-4">
        {data.rows.length ? (
          [...byClass.entries()].map(([label, rows]) => (
            <Section key={label} title={label} className="mb-4">
              <div className="rounded-xl border border-border bg-card">
                <div className="border-b border-border px-3 py-2">
                  <ColumnHead count={rows.length}>Assessments</ColumnHead>
                </div>
                {rows.map((r) => (
                  <Row key={r.id} r={r} onOpen={() => setOpenId(r.id)} />
                ))}
              </div>
            </Section>
          ))
        ) : (
          <Empty>
            <span className="flex flex-col items-center gap-2">
              <ClipboardCheck className="h-5 w-5" />
              {data.total || data.classes.length
                ? "Nothing matches those filters."
                : "No assessments yet. Set one to record how your children do on the work you give them."}
            </span>
          </Empty>
        )}
      </div>

      {data.pages > 1 ? (
        <div className="mt-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span className="font-mono tabular-nums">
            Page {data.page} of {data.pages} · {data.total} in all
          </span>
          <div className="flex gap-1.5">
            <Button
              size="sm"
              variant="outline"
              disabled={data.page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" /> Newer
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={data.page >= data.pages}
              onClick={() => setPage((p) => p + 1)}
            >
              Older <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : null}

      <BandAssessmentCreate
        open={creating}
        onOpenChange={setCreating}
        // Straight into the sheet: the moment after setting one is the only
        // moment she is thinking about it, and a "created" toast that leads
        // nowhere is a second navigation she has to remember to make.
        onCreated={(id) => setOpenId(id)}
      />
      {openId ? (
        <BandAssessmentSheetDialog assessmentId={openId} onClose={() => setOpenId(null)} />
      ) : null}
    </>
  );
}
