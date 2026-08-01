"use client";

// Syllabus — will we finish the portion, and who is falling behind?
// (DASH3 §4.2, reworked by V1-6.)
//
// The page leads with a SENTENCE, not a percentage (rule 3, `S-50`): schools
// manage against exams, so "Second Terminal in 24 days · 4 subjects short of
// portion" opens the page whatever tab is selected. Then the rows that need
// something doing, each saying WHY it is behind and carrying the one action
// that exists. Charts come after, because nothing above the fold should be one.
//
// Four rules the UI must not break:
//   * unplanned / unallocated / unestimated / unknown are STATES. They render as
//     words in a neutral chip, never as a colour on the RAG scale (V2-P11).
//   * `unknown` is not "on track" and not "behind" (`S-42`) — a subject nobody
//     logged a lesson against gets a word and a nudge about recording, never red.
//   * a node below the minimum sample reads "not enough data yet" and is never
//     ranked; where it IS ranked, the screen shows the SENTENCE the rank rests on
//     and never the raw score (`S-45`).
//   * every figure carries its denominator, and the two coverage bases are
//     labelled — "of the plan" and "of the whole syllabus" are different
//     questions and were the defect `S-51` existed to remove.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDownRight, ArrowUpRight, CalendarRange, MessageSquarePlus, Ruler,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  ChartCard, Donut, RowBars, StatTile, STATUS_COLOR, SERIES_COLORS, TrendLine,
  toneForPct, type ChartRow,
} from "@/components/charts";
import {
  BoardSkeleton, Empty, RailButton, RedRow, ScrollX, Section, StateChip,
} from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import { schoolApi } from "@/lib/school-api";
import type {
  SyllabusCheckpoint, SyllabusNode, SyllabusRow, SyllabusScope,
} from "@/lib/insights-types";
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

/** `S-41` — four causes, four different conversations. Only the last is about
 *  teaching, and the wording has to make that obvious at a glance. */
const CAUSE_LABEL: Record<string, string> = {
  not_logged: "nothing logged",
  periods_lost: "periods lost",
  never_sized: "chapters not sized",
  slower: "behind on teaching",
};

/** green/amber/red are pace; everything else is a state and gets words. */
function StatusCell({ status, weeksBehind }: { status: string; weeksBehind: number }) {
  if (status === "green") return <Badge tone="success">on track</Badge>;
  if (status === "amber") return <Badge tone="warning">{weeksBehind}w behind</Badge>;
  if (status === "red") return <Badge tone="danger">{weeksBehind}w behind</Badge>;
  // S-42: a plan with no lesson logs. Not a pace — we simply do not know.
  if (status === "unknown") return <StateChip>nothing logged yet</StateChip>;
  if (status === "unplanned") return <StateChip>nothing scheduled</StateChip>;
  if (status === "unallocated") return <StateChip>no periods/week</StateChip>;
  return <StateChip>no syllabus</StateChip>;
}

function Segments({ node }: { node: SyllabusNode }) {
  const parts = [
    { n: node.on_track, cls: "bg-[color:var(--chart-green)]", label: "on track" },
    { n: node.slipping, cls: "bg-[color:var(--chart-amber)]", label: "slipping" },
    { n: node.behind, cls: "bg-[color:var(--chart-red)]", label: "behind" },
    // Both of these are states, so both take the neutral fill — never a colour.
    { n: node.unknown, cls: "bg-muted-foreground/50", label: "nothing logged" },
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
            <li key={n.key} className="flex items-start gap-2 text-sm">
              <span className="min-w-0 flex-1">
                <span className="block truncate">{n.label}</span>
                {/* S-45: the sentence, never the composite score. If a rank can't
                    be explained to the teacher it is about, it doesn't belong. */}
                <span className="block text-xs text-muted-foreground">
                  {n.rank_reason ?? `${n.on_track}/${n.class_subjects} on track`}
                </span>
              </span>
              <Badge tone={tone === "green" ? "success" : "warning"}>
                {n.logged_periods} logs
              </Badge>
            </li>
          ))}
        </ul>
      ) : (
        // Q-18: a countdown, not a blank — say what is missing and how close it is.
        <p className="text-sm text-muted-foreground">
          Ranking starts once a node has {minCs} rated class-subjects
          {minLogged ? ` and ${minLogged} logged periods` : ""}. Nothing qualifies yet.
        </p>
      )}
    </div>
  );
}

function SyllabusInner() {
  const { yearId } = useYear();
  const qc = useQueryClient();
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

  // D-16 — a meeting request, not a directive. The admin never reschedules from
  // this board; `extend_plan` stays on the plan screen, used after the talk.
  const catchup = useMutation({
    mutationFn: (csId: string) =>
      insightsApi.action("catchup_requested", { class_subject_id: csId }),
    onSuccess: (r) => {
      toast.success(r.message);
      qc.invalidateQueries({ queryKey: ["insights", "syllabus"] });
    },
    onError: (e) => showApiError(e, "Could not ask for a catch-up plan"),
  });

  if (isLoading || !data) {
    return <><PageHeader title="Syllabus" subtitle="Is the teaching where the plan said it would be?" /><BoardSkeleton /></>;
  }

  const school = data.school;
  const ragSlices = school ? [
    { label: "On track", value: school.on_track, color: STATUS_COLOR.green },
    { label: "Slipping", value: school.slipping, color: STATUS_COLOR.amber },
    { label: "Behind", value: school.behind, color: STATUS_COLOR.red },
    { label: "Nothing logged", value: school.unknown, color: STATUS_COLOR.neutral },
    { label: "Not planned", value: school.unplanned + school.unallocated, color: STATUS_COLOR.neutral },
  ].filter((s) => s.value > 0) : [];

  const nodeRows: ChartRow[] = data.nodes
    .filter((n) => n.coverage_pct != null)
    .slice(0, 16)
    .map((n) => ({ x: n.label, pct: n.coverage_pct }));

  const trendRows: ChartRow[] = data.trend.map((p) => ({
    x: p.week_start.slice(5), actual: p.actual, baseline: p.baseline,
  }));

  // The rows that need something doing, worst first. `unknown` is included —
  // "nobody has logged anything" is a real finding — but it is never red.
  const needsAction: SyllabusRow[] = data.rows
    .filter((r) => r.cause != null)
    .sort((a, b) => (b.behind_topics - a.behind_topics) || (b.weeks_behind - a.weeks_behind))
    .slice(0, 12);

  return (
    <div>
      <PageHeader title="Syllabus" subtitle="Is the teaching where the plan said it would be?" />

      {/* S-50 / rule 3 — the page opens with a sentence, and the exam the school
          is actually managing against sits right under it whatever tab is
          selected. It used to be computed only on the tab most people never
          pressed. */}
      {data.headline ? (
        <p className="mb-2 text-base font-medium">{data.headline}</p>
      ) : null}
      {data.next_exam && checkpoint !== "exam" ? (
        <button type="button" onClick={() => setCheckpoint("exam")}
          className="mb-4 inline-flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-left text-xs hover:bg-accent">
          <CalendarRange className="h-3.5 w-3.5" />
          <span className="font-medium">{data.next_exam.title}</span>
          <span className="text-muted-foreground">
            in {data.next_exam.days_to_exam} days ·
            {" "}{data.next_exam.teaching_days_in_gap} teaching days left
          </span>
          {data.next_exam.short ? (
            <Badge tone="danger">{data.next_exam.short} short of portion</Badge>
          ) : data.next_exam.tight ? (
            <Badge tone="warning">{data.next_exam.tight} tight</Badge>
          ) : (
            <Badge tone="success">portion on course</Badge>
          )}
        </button>
      ) : null}

      {/* Filters in one row above everything else. */}
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
          {/* S-51: both denominators, each naming itself. */}
          <StatTile label="Of the whole syllabus"
            value={school.syllabus_pct != null ? `${school.syllabus_pct}%` : "—"}
            sub={`${school.taught_topics} of ${school.total_topics} topics in the portion`}
            tone="neutral" />
          <StatTile label="Of what is planned"
            value={school.coverage_pct != null ? `${school.coverage_pct}%` : "—"}
            sub={`${school.taught_topics} of ${school.planned_topics} scheduled topics`}
            tone={school.coverage_pct == null ? "neutral"
              : school.coverage_pct >= 75 ? "green" : school.coverage_pct >= 50 ? "amber" : "red"} />
          <StatTile label="Nothing logged yet"
            value={String(school.unknown)}
            sub={school.unplanned || school.unallocated
              ? `${school.unplanned + school.unallocated} also have no plan`
              : "class-subjects with a plan but no lessons recorded"}
            tone="neutral" />
        </div>
      ) : null}

      {/* The work: every behind row, why, and the one action that exists. */}
      <Section title="Needs a conversation"
        hint="Each row says why — periods lost, nothing logged, chapters never sized, or genuinely slower. They are four different conversations.">
        {needsAction.length ? (
          <div className="space-y-2">
            {needsAction.map((r) => {
              const asked = r.catchup_task_id != null && r.catchup_outcome == null;
              const settled = r.catchup_outcome != null;
              return (
                <RedRow key={r.class_subject_id}
                  tone={r.status === "red" ? "red" : r.status === "amber" ? "amber" : "neutral"}
                  title={<>{r.class_label} {r.subject_name}
                    {r.teacher_name ? <span className="font-normal text-muted-foreground"> · {r.teacher_name}</span> : null}
                  </>}
                  subtitle={<>
                    <span className="mr-1.5 inline-block"><StateChip>{CAUSE_LABEL[r.cause ?? ""] ?? r.cause}</StateChip></span>
                    {r.cause_detail}
                    {settled ? <span className="mt-0.5 block text-success">Outcome: {r.catchup_outcome}</span> : null}
                  </>}
                  meta={<>
                    {r.taught_topics} of {r.planned_topics} planned
                    <span className="block">{r.logged_periods} lessons logged</span>
                  </>}
                  actions={<>
                    {/* S-44b — a deep link, not an action: it schedules nothing,
                        so it survives D-16. Highest-yield fix on the board. */}
                    {r.unestimated_topics ? (
                      <a href={`/plan/syllabus?class_subject_id=${r.class_subject_id}`}
                        className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs hover:bg-accent">
                        <Ruler className="h-3.5 w-3.5" /> Size {r.unestimated_topics} chapters
                      </a>
                    ) : null}
                    <RailButton
                      label="Ask for a catch-up plan"
                      doneLabel={settled ? "Outcome recorded" : "Asked — awaiting the meeting"}
                      done={asked || settled}
                      pending={catchup.isPending}
                      icon={<MessageSquarePlus className="mr-1 h-3.5 w-3.5" />}
                      onClick={() => catchup.mutate(r.class_subject_id)} />
                  </>} />
              );
            })}
          </div>
        ) : (
          <Empty>
            {data.rows.length
              ? "Every subject is on track, and every one of them has lessons logged against it."
              : "No plans yet — coverage appears once chapters are sized and a plan is approved."}
          </Empty>
        )}
      </Section>

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

      {/* S-40 — the one chart the board lacked: is this getting better or worse? */}
      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <ChartCard title="Coverage over time"
          hint="Topics taught, cumulative, against what the approved plan had scheduled by that week. The gap between the lines is the story.">
          {trendRows.length > 1 ? (
            <TrendLine rows={trendRows} height={200} series={[
              { key: "actual", label: "Taught", color: SERIES_COLORS[0] },
              { key: "baseline", label: "Planned by then", color: SERIES_COLORS[1] },
            ]} />
          ) : (
            <Empty>Not enough weeks logged yet to draw a trend.</Empty>
          )}
        </ChartCard>
        <ChartCard title="Pace across the school" hint="Every class-subject rated against its approved plan.">
          {ragSlices.length ? (
            <Donut slices={ragSlices} centerValue={String(school?.class_subjects ?? 0)} centerLabel="class-subjects" />
          ) : (
            <Empty>No plans approved yet.</Empty>
          )}
        </ChartCard>
      </div>

      {/* S-43 — the fairest comparison in a school. */}
      {data.sections.length ? (
        <Section title="Sections of the same grade"
          hint="Same syllabus, same weeks, same exam, different teacher — which is why this comparison is worth making and a school-wide one often isn't.">
          <div className="space-y-3">
            {data.sections.slice(0, 6).map((s) => (
              <div key={`${s.grade}-${s.subject_name}`} className="rounded-xl border border-border bg-card p-4">
                <p className="mb-2 text-sm font-semibold">
                  Class {s.grade} · {s.subject_name}
                  {s.spread_pct != null ? (
                    <span className="ml-2 text-xs font-normal text-muted-foreground">
                      {s.spread_pct} points between the highest and lowest
                    </span>
                  ) : null}
                </p>
                <div className="space-y-1.5">
                  {s.rows.map((r) => (
                    <div key={r.class_subject_id} className="flex items-center gap-3 text-sm">
                      <span className="w-16 shrink-0 font-medium">{r.class_label}</span>
                      <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                        {r.teacher_name ?? "unassigned"}
                      </span>
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {r.taught_topics} of {r.planned_topics} planned
                      </span>
                      <span className="w-20 shrink-0 text-right tabular-nums">
                        {r.status === "unknown"
                          ? <StateChip>nothing logged</StateChip>
                          : r.coverage_pct != null ? `${r.coverage_pct}%` : "—"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

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

      <div className="mb-6">
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

      <Section title={SCOPES.find((s) => s.key === scope)?.label ?? "Breakdown"}
        hint="A rank is only shown where there is enough to rank on — the sample sits beside it.">
        <ScrollX>
          <table className="w-full min-w-[680px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">{scope === "class" ? "Class" : scope === "subject" ? "Subject" : "Teacher"}</th>
                <th className="py-2 pr-3 font-medium">Pace</th>
                <th className="py-2 pr-3 text-right font-medium">Of plan</th>
                <th className="py-2 pr-3 text-right font-medium">Of syllabus</th>
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
                  <td className="py-2 pr-3 text-right tabular-nums text-muted-foreground">
                    {n.syllabus_pct != null ? `${n.syllabus_pct}%` : "—"}
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
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Class</th>
                <th className="py-2 pr-3 font-medium">Subject</th>
                <th className="py-2 pr-3 font-medium">Teacher</th>
                <th className="py-2 pr-3 text-right font-medium">Taught / planned</th>
                <th className="py-2 pr-3 font-medium">Status</th>
                <th className="py-2 pr-3 font-medium">Why</th>
                <th className="py-2 font-medium">Next up</th>
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
                  <td className="py-2 pr-3 text-xs text-muted-foreground">
                    {r.cause ? (CAUSE_LABEL[r.cause] ?? r.cause) : "—"}
                  </td>
                  <td className="py-2 text-xs text-muted-foreground">
                    {r.next_topic_title ?? "—"}
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
