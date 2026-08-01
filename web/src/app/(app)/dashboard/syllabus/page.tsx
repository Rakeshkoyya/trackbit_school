"use client";

// Syllabus — is the year's teaching where the plan said it would be (DASH3 §4.2).
//
// Two axes, and the page is laid out as a matrix of them: the checkpoint
// (year · term · exam) down, the scope (school → class → subject → teacher)
// across. Teacher is NOT a child of subject — one subject has several teachers
// across classes — so the scope is a switcher over the same class-subject rows,
// not a nested tree.
//
// Two rules the UI must not break:
//   * unplanned / unallocated / unestimated are STATES. They render as words in a
//     neutral chip, never as a colour on the RAG scale (V2-P11).
//   * a node below the minimum sample reads "not enough data yet" and is never
//     ranked. The sample size sits next to every rank so it can be checked.

import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, CalendarRange } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ChartCard, Donut, RowBars, StatTile, STATUS_COLOR, toneForPct, type ChartRow } from "@/components/charts";
import { BoardSkeleton, Empty, ScrollX, Section, StateChip } from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { insightsApi } from "@/lib/insights-api";
import { schoolApi } from "@/lib/school-api";
import type { SyllabusCheckpoint, SyllabusNode, SyllabusScope } from "@/lib/insights-types";
import { cn } from "@/lib/utils";

const SCOPES: { key: SyllabusScope; label: string }[] = [
  { key: "class", label: "By class" },
  { key: "subject", label: "By subject" },
  { key: "teacher", label: "By teacher" },
];

const CHECKPOINTS: { key: SyllabusCheckpoint; label: string }[] = [
  { key: "year", label: "Whole year" },
  { key: "term", label: "Term" },
  { key: "exam", label: "Next exams" },
];

/** green/amber/red are pace; everything else is a state and gets words. */
function StatusCell({ status, weeksBehind }: { status: string; weeksBehind: number }) {
  if (status === "green") return <Badge tone="success">on track</Badge>;
  if (status === "amber") return <Badge tone="warning">{weeksBehind}w behind</Badge>;
  if (status === "red") return <Badge tone="danger">{weeksBehind}w behind</Badge>;
  if (status === "unplanned") return <StateChip>nothing scheduled</StateChip>;
  if (status === "unallocated") return <StateChip>no periods/week</StateChip>;
  return <StateChip>no syllabus</StateChip>;
}

function Segments({ node }: { node: SyllabusNode }) {
  const parts = [
    { n: node.on_track, cls: "bg-[color:var(--chart-green)]", label: "on track" },
    { n: node.slipping, cls: "bg-[color:var(--chart-amber)]", label: "slipping" },
    { n: node.behind, cls: "bg-[color:var(--chart-red)]", label: "behind" },
    { n: node.unplanned + node.unallocated, cls: "bg-muted-foreground/30", label: "not planned" },
  ].filter((p) => p.n > 0);
  const total = parts.reduce((s, p) => s + p.n, 0) || 1;
  return (
    <span className="flex h-2 w-24 overflow-hidden rounded-full bg-muted">
      {parts.map((p, i) => (
        <span key={i} title={`${p.n} ${p.label}`} className={cn(p.cls)}
          style={{ width: `${(p.n / total) * 100}%`, marginRight: i < parts.length - 1 ? 2 : 0 }} />
      ))}
    </span>
  );
}

function RankList({
  title, nodes, icon, tone, minCs, minLogged,
}: {
  title: string;
  nodes: SyllabusNode[];
  icon: React.ReactNode;
  tone: "green" | "amber";
  minCs: number;
  minLogged: number;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold">{icon} {title}</p>
      {nodes.length ? (
        <ul className="space-y-2">
          {nodes.map((n) => (
            <li key={n.key} className="flex items-center gap-2 text-sm">
              <span className="min-w-0 flex-1 truncate">{n.label}</span>
              <span className="shrink-0 text-xs text-muted-foreground">
                {n.on_track}/{n.class_subjects} on track · {n.coverage_pct ?? "—"}% covered
              </span>
              <Badge tone={tone === "green" ? "success" : "warning"}>{n.score}</Badge>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          Not enough data to rank anyone yet — a node needs {minCs} rated class-subjects
          {minLogged ? ` and ${minLogged} logged periods` : ""}.
        </p>
      )}
    </div>
  );
}

function SyllabusInner() {
  const { yearId } = useYear();
  const [scope, setScope] = useState<SyllabusScope>("class");
  const [checkpoint, setCheckpoint] = useState<SyllabusCheckpoint>("year");
  const [termId, setTermId] = useState<string>("");

  const { data: terms = [] } = useQuery({
    queryKey: ["terms", yearId],
    queryFn: () => schoolApi.terms(yearId ?? undefined),
    enabled: !!yearId,
  });
  const effTerm = checkpoint === "term" ? (termId || terms[0]?.id) : undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["insights", "syllabus", yearId, scope, checkpoint, effTerm],
    queryFn: () => insightsApi.syllabus({
      yearId: yearId ?? undefined, scope, checkpoint, termId: effTerm,
    }),
  });

  if (isLoading || !data) {
    return <><PageHeader title="Syllabus" subtitle="Is the teaching where the plan said it would be?" /><BoardSkeleton /></>;
  }

  const school = data.school;
  const ragSlices = school ? [
    { label: "On track", value: school.on_track, color: STATUS_COLOR.green },
    { label: "Slipping", value: school.slipping, color: STATUS_COLOR.amber },
    { label: "Behind", value: school.behind, color: STATUS_COLOR.red },
    { label: "Not planned", value: school.unplanned + school.unallocated, color: STATUS_COLOR.neutral },
  ].filter((s) => s.value > 0) : [];

  const nodeRows: ChartRow[] = data.nodes
    .filter((n) => n.coverage_pct != null)
    .slice(0, 16)
    .map((n) => ({ x: n.label, pct: n.coverage_pct }));

  return (
    <div>
      <PageHeader title="Syllabus" subtitle="Is the teaching where the plan said it would be?" />

      {/* Filters in one row above the charts. */}
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <div className="flex gap-1 rounded-lg border border-border p-0.5">
          {CHECKPOINTS.map((c) => (
            <button key={c.key} type="button" onClick={() => setCheckpoint(c.key)}
              className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                checkpoint === c.key ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground")}>
              {c.label}
            </button>
          ))}
        </div>
        {checkpoint === "term" && terms.length ? (
          <select value={effTerm ?? ""} onChange={(e) => setTermId(e.target.value)}
            className="rounded-md border border-border bg-card px-2 py-1.5 text-xs">
            {terms.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        ) : null}
        <div className="ml-auto flex gap-1 rounded-lg border border-border p-0.5">
          {SCOPES.map((s) => (
            <button key={s.key} type="button" onClick={() => setScope(s.key)}
              className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                scope === s.key ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground")}>
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {school ? (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile label="Class-subjects" value={String(school.class_subjects)}
            sub={`${school.on_track} on track · ${school.behind} behind`}
            tone={school.behind ? "red" : school.slipping ? "amber" : "green"} />
          <StatTile label="Syllabus covered"
            value={school.coverage_pct != null ? `${school.coverage_pct}%` : "—"}
            sub={`${school.taught_topics} of ${school.planned_topics} planned topics`}
            tone={school.coverage_pct == null ? "neutral"
              : school.coverage_pct >= 75 ? "green" : school.coverage_pct >= 50 ? "amber" : "red"} />
          <StatTile label="Worst slippage"
            value={school.weeks_behind_max ? `${school.weeks_behind_max}w` : "0w"}
            sub="behind baseline, worst class-subject"
            tone={school.weeks_behind_max > 2 ? "red" : school.weeks_behind_max ? "amber" : "green"} />
          <StatTile label="Not planned"
            value={String(school.unplanned + school.unallocated)}
            sub={school.unestimated_topics
              ? `${school.unestimated_topics} chapters not sized yet`
              : "every subject is scheduled"}
            tone={school.unplanned ? "amber" : "neutral"} />
        </div>
      ) : null}

      {checkpoint === "exam" ? (
        <Section title="Exam checkpoints"
          hint="Per exam: the syllabus each subject must newly cover, against the teaching periods in the gap.">
          {data.exams.length ? (
            <div className="space-y-3">
              {data.exams.map((ex) => (
                <div key={ex.exam_event_id} className="rounded-xl border border-border bg-card p-4">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="flex items-center gap-1.5 text-sm font-semibold">
                      <CalendarRange className="h-4 w-4" /> {ex.title}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {ex.days_to_exam >= 0 ? `in ${ex.days_to_exam} days` : "past"} ·
                      {" "}{ex.teaching_days_in_gap} teaching days in the gap
                    </span>
                    <span className="ml-auto flex gap-1.5">
                      {ex.short ? <Badge tone="danger">{ex.short} won’t fit</Badge> : null}
                      {ex.tight ? <Badge tone="warning">{ex.tight} tight</Badge> : null}
                      {ex.ok ? <Badge tone="success">{ex.ok} fine</Badge> : null}
                    </span>
                  </div>
                  <ScrollX>
                    <table className="w-full min-w-[520px] text-sm">
                      <thead>
                        <tr className="border-b border-border text-left text-xs text-muted-foreground">
                          <th className="py-1.5 pr-3 font-medium">Class</th>
                          <th className="py-1.5 pr-3 font-medium">Subject</th>
                          <th className="py-1.5 pr-3 text-right font-medium">Needs</th>
                          <th className="py-1.5 pr-3 text-right font-medium">Has</th>
                          <th className="py-1.5 font-medium">Verdict</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ex.subjects.slice(0, 24).map((s) => (
                          <tr key={s.class_subject_id} className="border-b border-border/60">
                            <td className="py-1.5 pr-3">{s.class_label}</td>
                            <td className="py-1.5 pr-3">{s.subject_name}</td>
                            <td className="py-1.5 pr-3 text-right tabular-nums">{s.required_periods}</td>
                            <td className="py-1.5 pr-3 text-right tabular-nums">{s.capacity_periods}</td>
                            <td className="py-1.5">
                              {s.verdict === "short" ? <Badge tone="danger">won’t fit</Badge>
                                : s.verdict === "tight" ? <Badge tone="warning">tight</Badge>
                                : s.verdict === "no_portion" ? <StateChip>no portion set</StateChip>
                                : s.verdict === "unallocated" ? <StateChip>no periods/week</StateChip>
                                : <Badge tone="success">{s.verdict}</Badge>}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </ScrollX>
                </div>
              ))}
            </div>
          ) : (
            <Empty>No exam blocks on the calendar yet — add them in Plan → Year.</Empty>
          )}
        </Section>
      ) : null}

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <ChartCard title="Pace across the school" hint="Every class-subject rated against its approved plan.">
          {ragSlices.length ? (
            <Donut slices={ragSlices} centerValue={String(school?.class_subjects ?? 0)} centerLabel="class-subjects" />
          ) : (
            <Empty>No plans approved yet.</Empty>
          )}
        </ChartCard>
        <ChartCard title={`Coverage ${SCOPES.find((s) => s.key === scope)?.label.toLowerCase()}`}
          hint="Topics taught against topics planned. Partial coverage counts as half.">
          {nodeRows.length ? (
            <RowBars rows={nodeRows} dataKey="pct" unit="%" max={100}
              height={Math.max(140, nodeRows.length * 26)}
              colorFor={(r) => toneForPct(r.pct as number, { good: 75, fair: 50 })} />
          ) : (
            <Empty>Nothing logged against a plan yet.</Empty>
          )}
        </ChartCard>
      </div>

      {scope === "teacher" ? (
        <div className="mb-6 grid gap-4 lg:grid-cols-2">
          <RankList title="Ahead of plan" nodes={data.ahead} tone="green"
            icon={<ArrowUpRight className="h-4 w-4 text-success" />}
            minCs={data.min_class_subjects} minLogged={data.min_logged_periods} />
          <RankList title="Needs support" nodes={data.needs_support} tone="amber"
            icon={<ArrowDownRight className="h-4 w-4 text-warning" />}
            minCs={data.min_class_subjects} minLogged={data.min_logged_periods} />
        </div>
      ) : null}

      <Section title={SCOPES.find((s) => s.key === scope)?.label ?? "Breakdown"}
        hint="A rank is only shown where there is enough to rank on — the sample sits beside it.">
        <ScrollX>
          <table className="w-full min-w-[620px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">{scope === "class" ? "Class" : scope === "subject" ? "Subject" : "Teacher"}</th>
                <th className="py-2 pr-3 font-medium">Pace</th>
                <th className="py-2 pr-3 text-right font-medium">Covered</th>
                <th className="py-2 pr-3 text-right font-medium">Worst slip</th>
                <th className="py-2 text-right font-medium">Sample</th>
              </tr>
            </thead>
            <tbody>
              {data.nodes.map((n) => (
                <tr key={n.key} className="border-b border-border/60">
                  <td className="py-2 pr-3">
                    <span className="block truncate">{n.label}</span>
                    {n.sublabel ? <span className="block text-xs text-muted-foreground">{n.sublabel}</span> : null}
                  </td>
                  <td className="py-2 pr-3"><Segments node={n} /></td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {n.coverage_pct != null ? `${n.coverage_pct}%` : <StateChip>nothing planned</StateChip>}
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {n.weeks_behind_max ? `${n.weeks_behind_max}w` : "—"}
                  </td>
                  <td className="py-2 text-right text-xs text-muted-foreground">
                    {n.rank_eligible
                      ? `${n.class_subjects} subjects · ${n.logged_periods} logs`
                      : <StateChip>not enough data yet</StateChip>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollX>
      </Section>

      <Section title="Every class-subject" hint="The rows the roll-ups above are built from.">
        <ScrollX>
          <table className="w-full min-w-[680px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Class</th>
                <th className="py-2 pr-3 font-medium">Subject</th>
                <th className="py-2 pr-3 font-medium">Teacher</th>
                <th className="py-2 pr-3 text-right font-medium">Taught / planned</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 font-medium">Finish</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.class_subject_id} className="border-b border-border/60">
                  <td className="py-2 pr-3">{r.class_label}</td>
                  <td className="py-2 pr-3">{r.subject_name}</td>
                  <td className="py-2 pr-3 text-muted-foreground">{r.teacher_name ?? <StateChip>unassigned</StateChip>}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {r.taught_topics}/{r.planned_topics}
                    {r.unestimated_topics
                      ? <span className="ml-1 text-xs text-muted-foreground">(+{r.unestimated_topics} unsized)</span>
                      : null}
                  </td>
                  <td className="py-2 pr-3"><StatusCell status={r.status} weeksBehind={r.weeks_behind} /></td>
                  <td className="py-2 text-xs text-muted-foreground">
                    {r.projected_finish ?? "—"}
                    {r.current_term_unplanned ? <span className="ml-1 text-warning">· term unplanned</span> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollX>
      </Section>
    </div>
  );
}

export default function DashboardSyllabusPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <SyllabusInner />
    </AuthGuard>
  );
}
