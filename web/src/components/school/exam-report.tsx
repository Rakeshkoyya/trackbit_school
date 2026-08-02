"use client";

/**
 * The exam's **Report** tab (V1-8, `D-80`) — the analysis beside Score's numbers.
 *
 * The order on screen is the order the questions arrive in: a **sentence**, then
 * the **shape**, then **named rows** with what to do about them, then the
 * question detail, then what the class had actually been taught.
 *
 * What this component may not do:
 * - **No rank.** Rows are named with their mark and the *stated* criterion
 *   ("more than 15 points below the class"), never a position.
 * - **Question analysis absent is a word, never a zero** — an exam typed in by
 *   hand has no per-question marks, and the screen says exactly why.
 * - Every figure carries its denominator; the average never appears without
 *   how many of the class sat the paper.
 */

import { AlertTriangle, FileText, Sparkles, UserRound } from "lucide-react";

import { ChartCard, ColumnChart } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import type { ExamReport, ExamReportRow } from "@/lib/school-types";

function NamedRows({ title, hint, rows, tone }: {
  title: string; hint: string; rows: ExamReportRow[]; tone: "danger" | "success" | "neutral";
}) {
  if (!rows.length) return null;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-sm font-semibold">{title}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
      <ul className="mt-3 space-y-1.5">
        {rows.map((r) => (
          <li key={r.student_id} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex min-w-0 items-center gap-1.5">
              <UserRound className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{r.full_name}</span>
            </span>
            {r.pct != null ? (
              <Badge tone={tone === "danger" ? "danger" : tone === "success" ? "success" : "neutral"}>
                {r.score}/{r.max_score} · {r.pct}%
              </Badge>
            ) : <span className="text-xs text-muted-foreground">no mark recorded</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ExamReportView({ report }: { report: ExamReport }) {
  const dist = report.distribution.map((b) => ({ x: b.label, count: b.count }));
  const questions = report.questions.map((q) => ({
    x: `Q${q.q}`, pct: q.avg_pct ?? 0,
  }));

  return (
    <div className="space-y-4">
      {/* the sentence */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Badge tone="neutral">{report.type_label}</Badge>
          <Badge tone="neutral">{report.scale_label}</Badge>
          {report.exam_event_name ? <Badge tone="neutral">{report.exam_event_name}</Badge> : null}
          {report.locked ? <Badge tone="success">locked</Badge> : null}
        </div>
        <p className="flex items-start gap-2 text-sm leading-relaxed">
          <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <span>{report.summary}</span>
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>
            {report.avg_pct != null
              ? <><span className="font-semibold text-foreground">{report.avg_pct}%</span> average</>
              : "no marks recorded"}
            {" "}across {report.scored} of {report.roster} students
          </span>
          {report.topic ? <span>Topic: {report.topic}</span> : null}
          {report.coverage_note ? <span>{report.coverage_note}</span> : null}
        </div>
      </div>

      {/* the shape */}
      <ChartCard title="How the marks fell"
        hint={`${report.scored} papers · bucketed by percentage of the total`}>
        <ColumnChart rows={dist} series={[{ key: "count", label: "Students" }]} />
      </ChartCard>

      {/* named rows, each against a stated criterion — never a rank */}
      <div className="grid gap-3 md:grid-cols-2">
        <NamedRows title="Worth a conversation"
          hint={`More than ${report.gap_points} points below the class average.`}
          rows={report.struggling} tone="danger" />
        <NamedRows title="Well ahead"
          hint={`More than ${report.gap_points} points above the class average.`}
          rows={report.strong} tone="success" />
      </div>
      <NamedRows title="Did not sit this paper"
        hint="They are not in the average — which is why the average says how many did."
        rows={report.not_sat} tone="neutral" />

      {/* the question detail — or the honest word about why there is none */}
      {report.questions.length ? (
        <ChartCard title="Where the marks were lost"
          hint="Average per question, worst first — read off the marked papers, never a judgement about an answer.">
          <ColumnChart rows={questions} yUnit="%" yDomain={[0, 100]}
            series={[{ key: "pct", label: "% of the question's marks" }]} />
        </ChartCard>
      ) : (
        <div className="flex items-start gap-2 rounded-xl border border-dashed border-border p-4">
          <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">No question-level analysis</p>
            <p className="mt-0.5 text-xs text-muted-foreground">{report.question_note}</p>
          </div>
        </div>
      )}

      {report.questions.length ? (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Question</th>
                <th className="px-2 py-2">Average</th>
                <th className="px-2 py-2">Out of</th>
                <th className="px-2 py-2">Papers read</th>
              </tr>
            </thead>
            <tbody>
              {report.questions.map((q) => (
                <tr key={q.q} className="border-t border-border">
                  <td className="px-3 py-1.5 font-medium">Q{q.q}</td>
                  <td className="px-2 py-1.5">
                    {q.avg_score != null ? q.avg_score : "—"}
                    {q.avg_pct != null ? (
                      <span className="ml-1.5 text-xs text-muted-foreground">{q.avg_pct}%</span>
                    ) : null}
                  </td>
                  <td className="px-2 py-1.5 text-xs text-muted-foreground">
                    {q.max ?? <span className="inline-flex items-center gap-1">
                      <AlertTriangle className="h-3 w-3" /> not printed</span>}
                  </td>
                  <td className="px-2 py-1.5 text-xs text-muted-foreground">{q.attempted}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
