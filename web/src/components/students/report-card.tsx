"use client";

/**
 * The two report levels on a student's page (V1-8, `D-81`).
 *
 *   **Level 1 — the report card.** Standard, familiar, **numbers only**: the
 *   subjects, the exams they sat, the marks. No narrative, no advice, and
 *   **never a support tier** — this is the surface most likely to be printed
 *   and handed to a family (P4).
 *
 *   **Level 2 — the analysis.** Per subject: the same figures with a written
 *   paragraph over them, what was covered, and the topics taught while the
 *   child was away.
 *
 * Two rules the layout enforces rather than hopes for:
 *
 * - **Nothing is pooled across scale** (`S-114`). Minor tests and major exams
 *   get their own figure, side by side, with their own labels.
 * - **No average without its denominator** (`S-118`). The server hands back a
 *   `sentence` — *"61% across 5 of the 9 tests"* — and it is the sentence that
 *   is rendered, so a component author cannot drop the second half of it.
 *
 * `S-119`: every mark links to the child's own marked paper where one was
 * photographed, because *"can I see it?"* is the question a parent meeting
 * actually produces.
 */

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, FileText, Sparkles } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { schoolApi } from "@/lib/school-api";
import type { ScaleFigure } from "@/lib/school-types";

function Figures({ figures }: { figures: ScaleFigure[] }) {
  const shown = figures.filter((f) => f.tests_held > 0 || f.tests_taken > 0);
  if (!shown.length) return null;
  return (
    <div className="flex flex-wrap gap-x-6 gap-y-1">
      {shown.map((f) => (
        <span key={f.scale} className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{f.label}:</span> {f.sentence}
        </span>
      ))}
    </div>
  );
}

/** Level 1 — the card. Numbers only, and every figure with its denominator. */
export function ReportCardBlock({ studentId }: { studentId: string }) {
  const [open, setOpen] = useState(false);
  const { data } = useQuery({
    queryKey: ["report-card", studentId],
    queryFn: () => schoolApi.reportCard(studentId),
    enabled: open,
  });

  return (
    <section className="rounded-xl border border-border bg-card">
      <button type="button" onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left">
        <span className="flex items-center gap-2 text-sm font-semibold">
          <FileText className="h-4 w-4" /> Report card
        </span>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          subjects and marks, nothing else
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>
      {open ? (
        <div className="space-y-3 border-t border-border p-4">
          {!data ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
          {data && !data.subjects.length ? (
            <p className="text-sm text-muted-foreground">No marks recorded for this student yet.</p>
          ) : null}
          {data?.subjects.map((s) => (
            <div key={s.subject_id ?? s.subject_name} className="rounded-lg border border-border p-3">
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-semibold">{s.subject_name}</p>
                <Figures figures={s.figures} />
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="text-left text-xs text-muted-foreground">
                    <tr>
                      <th className="py-1 pr-2">Test</th>
                      <th className="py-1 pr-2">Type</th>
                      <th className="py-1 pr-2">Marks</th>
                      <th className="py-1 pr-2">%</th>
                      <th className="py-1">Paper</th>
                    </tr>
                  </thead>
                  <tbody>
                    {s.exams.map((e) => (
                      <tr key={e.cycle_id} className="border-t border-border">
                        <td className="py-1 pr-2">
                          {e.name}
                          <span className="ml-1.5 text-xs text-muted-foreground">{e.date}</span>
                        </td>
                        <td className="py-1 pr-2 text-xs">
                          <Badge tone="neutral">{e.type_label}</Badge>
                        </td>
                        <td className="py-1 pr-2 tabular-nums">{e.score}/{e.max_score}</td>
                        <td className="py-1 pr-2 tabular-nums text-muted-foreground">
                          {e.pct != null ? `${e.pct}%` : "—"}
                        </td>
                        <td className="py-1 text-xs">
                          {e.paper_url
                            ? <a href={e.paper_url} target="_blank" rel="noreferrer" className="underline">see it</a>
                            : <span className="text-muted-foreground">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

/** Level 2 — the analysis. The narrative sits over figures already computed;
 *  with AI off it is the deterministic paragraph, so it is never empty. */
export function AnalysisBlock({ studentId }: { studentId: string }) {
  const [open, setOpen] = useState(false);
  const { data } = useQuery({
    queryKey: ["student-analysis", studentId],
    queryFn: () => schoolApi.studentAnalysis(studentId),
    enabled: open,
  });

  return (
    <section className="rounded-xl border border-border bg-card">
      <button type="button" onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left">
        <span className="flex items-center gap-2 text-sm font-semibold">
          <Sparkles className="h-4 w-4" /> Detailed analysis
        </span>
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          per subject, per topic
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>
      {open ? (
        <div className="space-y-3 border-t border-border p-4">
          {!data ? <p className="text-sm text-muted-foreground">Writing the analysis…</p> : null}
          {data?.subjects.map((s) => {
            const missed = s.topics.filter((t) => t.missed_while_absent);
            return (
              <div key={s.subject_id ?? s.subject_name} className="rounded-lg border border-border p-3">
                <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-sm font-semibold">{s.subject_name}</p>
                  <span className="text-xs text-muted-foreground">
                    {s.coverage_total
                      ? `${s.coverage_taught} of ${s.coverage_total} topics taught`
                      : "syllabus not sized yet"}
                    {s.attendance_pct != null ? ` · ${s.attendance_pct}% present` : ""}
                  </span>
                </div>
                <p className="text-sm leading-relaxed">{s.summary}</p>
                <div className="mt-2"><Figures figures={s.figures} /></div>
                {missed.length ? (
                  <p className="mt-2 text-xs text-muted-foreground">
                    Taught while they were away: {missed.slice(0, 4).map((t) => t.title).join(", ")}
                    {missed.length > 4 ? ` and ${missed.length - 4} more` : ""}.
                  </p>
                ) : null}
              </div>
            );
          })}
          {data && !data.subjects.length ? (
            <p className="text-sm text-muted-foreground">
              Nothing recorded for this student yet — the analysis builds itself from
              the marks, the lesson logs and the register.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
