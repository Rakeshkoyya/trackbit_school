"use client";

// Syllabus — will we finish the portion, and who is falling behind?
// (DASH3 §4.2, reworked by V1-6, redrawn by V1-15.)
//
// The page still leads with a SENTENCE (rule 3, `S-50`): schools manage against
// exams, so "Second Terminal in 24 days · 4 subjects short of portion" opens the
// page whatever tab is selected. What changed is everything under it.
//
// It used to answer "how much?" four times — four stat tiles, a bar chart of
// coverage, then a table of the same nodes with a percentage column — and never
// once answered "is that good for today?". So every figure now sits on a track
// carrying **the plan's own marker**, and the four questions an owner actually
// arrives with each get one block, in the order they get asked:
//
//   1. WHERE IS THE PORTION — the ring, and the portion split into finished,
//      part-taught and not started. A weighted percentage cannot say that.
//   2. WHY ARE WE BEHIND — `S-41`'s four causes, counted. Three of the four are
//      not about teaching, and the proportions between them are the finding.
//   3. WHO NEEDS SOMETHING DOING — the behind rows, each with its cause and the
//      one action that exists, plus the finish forecast the planner has always
//      computed and no screen ever drew.
//   4. HOW IS IT SPREAD — class, subject, and now teacher × class, where load
//      and pace can finally be read together.
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
  ChartCard, Donut, PaceRing, SERIES_COLORS, STATUS_COLOR, TrendLine,
  type ChartRow,
} from "@/components/charts";
import {
  BoardSkeleton, ColumnHead, Empty, Fraction, RailButton, RedRow, ScrollX, Section,
  StateChip,
} from "@/components/insights/shared";
import {
  CAUSE_LABEL, CauseSplit, FinishForecast, PaceLegend, PortionMeter,
  ScopeLedger, TeacherMatrix, TermSwitch,
} from "@/components/insights/syllabus";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
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

/**
 * Block 1 — where the portion stands.
 *
 * The ring is drawn on the whole-syllabus denominator, the same one the overview
 * block uses, so the two screens can never quote different numbers for the same
 * morning. The plan basis is right beside it, named, because they answer
 * different questions and `S-51` exists because four screens once picked one
 * each without saying which.
 */
function PortionBand({ school }: { school: SyllabusNode }) {
  return (
    <section className="mb-6 overflow-hidden rounded-xl border border-border bg-card">
      <header className="border-b border-border px-4 py-2.5">
        <ColumnHead tone={school.tone}>The portion</ColumnHead>
      </header>
      <div className="grid gap-x-6 gap-y-5 px-4 py-5 md:grid-cols-[auto_minmax(0,1fr)]">
        <div className="flex flex-col items-center justify-self-center">
          <PaceRing pct={school.syllabus_pct} expectedPct={school.expected_syllabus_pct}
            tone={school.tone} size={156} stroke={14}
            label="Syllabus taught, whole school">
            {school.syllabus_pct != null ? (
              <>
                <span className="font-mono text-[30px] font-semibold leading-none tabular-nums">
                  {Math.round(school.syllabus_pct)}
                  <span className="text-[15px] text-muted-foreground">%</span>
                </span>
                <span className="mt-1.5 max-w-[92px] text-center font-mono text-[9px] uppercase leading-tight tracking-[0.1em] text-muted-foreground">
                  of the whole syllabus
                </span>
              </>
            ) : (
              <span className="max-w-[92px] text-center text-[11px] leading-tight text-muted-foreground">
                no portion sized yet
              </span>
            )}
          </PaceRing>
          <p className="mt-3 text-center">
            <Fraction n={school.taught_topics} of={school.total_topics}
              className="text-[14px]" />
            <span className="mt-0.5 block font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              topics taught
            </span>
          </p>
        </div>

        <div className="min-w-0">
          <PortionMeter node={school} />

          {/* `S-51` — the other denominator, named, never left to be inferred. */}
          <dl className="mt-4 grid gap-x-4 gap-y-3 border-t border-border pt-3.5 sm:grid-cols-3">
            {[
              {
                label: "Of what is planned",
                value: school.coverage_pct != null ? `${school.coverage_pct}%` : "—",
                sub: `${school.taught_topics} of ${school.planned_topics} scheduled`,
              },
              {
                label: "Class-subjects",
                value: String(school.class_subjects),
                sub: school.pace_caption ?? "nothing rated yet",
              },
              {
                label: "Periods logged",
                value: String(school.logged_periods),
                sub: school.periods_not_held
                  ? `${school.periods_not_held} periods not held`
                  : "no periods called off",
              },
            ].map((cell) => (
              <div key={cell.label} className="min-w-0">
                <dt className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                  {cell.label}
                </dt>
                <dd className="mt-1 font-mono text-[19px] leading-none tabular-nums">
                  {cell.value}
                </dd>
                <dd className="mt-1.5 text-[11px] leading-snug text-muted-foreground">
                  {cell.sub}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
      <div className="border-t border-border bg-muted/25 px-4 py-2">
        <PaceLegend />
      </div>
    </section>
  );
}

function SyllabusInner() {
  const { yearId } = useYear();
  const qc = useQueryClient();
  const [scope, setScope] = useState<SyllabusScope>("class");
  const [checkpoint, setCheckpoint] = useState<SyllabusCheckpoint>("year");
  const [termId, setTermId] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["insights", "syllabus", yearId, scope, checkpoint, termId],
    queryFn: () => insightsApi.syllabus({
      yearId: yearId ?? undefined, scope, checkpoint,
      termId: checkpoint === "term" ? (termId || undefined) : undefined,
    }),
    // Switching scope re-pivots the same rows; blanking the page to a skeleton
    // for a re-pivot reads as a page load and loses the reader's place.
    placeholderData: (prev) => prev,
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

  const trendRows: ChartRow[] = data.trend.map((p) => ({
    x: p.week_start.slice(5), actual: p.actual, baseline: p.baseline,
  }));

  // The rows that need something doing, worst first. `unknown` is included —
  // "nobody has logged anything" is a real finding — but it is never red.
  const needsAction: SyllabusRow[] = data.rows
    .filter((r) => r.cause != null)
    .sort((a, b) => (b.behind_topics - a.behind_topics) || (b.weeks_behind - a.weeks_behind))
    .slice(0, 12);

  const scopeLabel = SCOPES.find((s) => s.key === scope)?.label ?? "Breakdown";

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
        {/* The terms come down with the board, so the running one is flagged
            against the school's clock and not the browser's. */}
        {checkpoint === "term" ? (
          <TermSwitch terms={data.terms} value={termId} onChange={setTermId} />
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

      {/* 1 — where the portion stands. */}
      {school ? <PortionBand school={school} /> : null}

      {/* 2 — why. Three of the four causes are not about teaching at all, which
          is the single most useful thing this board can tell an owner. */}
      <Section title="Why we are behind"
        hint="Every behind row carries a cause. Only the last of the four is a conversation about teaching — the others are capture, calendar and setup.">
        <CauseSplit causes={data.causes} />
      </Section>

      {/* 3 — the work: every behind row, why, and the one action that exists. */}
      <Section title="Needs a conversation"
        hint="Worst first, by topics genuinely behind. Each row carries the one action this board has — a meeting request, never a re-plan.">
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

      {/* The forecast the planner has always computed and nothing ever drew. */}
      <Section title="Will it finish?"
        hint="Projected finish against the plan's own baseline. A subject that lands past the end of the year is a decision — drop a chapter, add periods, move an exam — and it has to be visible while there is still year left to take it.">
        <FinishForecast rows={data.rows} />
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
                        <tr className="border-b border-border text-left font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
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
                            <td className="py-1.5 pr-3 text-right font-mono tabular-nums">{s.required_periods}</td>
                            <td className="py-1.5 pr-3 text-right font-mono tabular-nums">{s.capacity_periods}</td>
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

      {/* 4 — how it is spread. Teacher gets the extra view, because load and
          pace are one conversation and a list can only show one of them. */}
      {scope === "teacher" ? (
        <>
          <Section title="Who teaches what, and how far they have got"
            hint="A row's width is the load; the fill of its cells is the pace. Cells are class-subjects, never an average of them — a teacher's Maths and Hindi averaged into one number is a figure nobody can act on.">
            <TeacherMatrix rows={data.rows} />
          </Section>
          <div className="mb-6 grid gap-4 lg:grid-cols-2">
            <RankList title="Ahead of plan" nodes={data.ahead} tone="green"
              icon={<ArrowUpRight className="h-4 w-4 text-success" />}
              minCs={data.min_class_subjects} minLogged={data.min_logged_periods} />
            <RankList title="Needs support" nodes={data.needs_support} tone="amber"
              icon={<ArrowDownRight className="h-4 w-4 text-warning" />}
              minCs={data.min_class_subjects} minLogged={data.min_logged_periods} />
          </div>
        </>
      ) : null}

      <Section title={scopeLabel}
        hint="Coverage against the approved plan, with the plan's marker on every track. A rank is only shown where there is enough to rank on.">
        <ScopeLedger nodes={data.nodes} scope={scope}
          minCs={data.min_class_subjects} minLogged={data.min_logged_periods} />
      </Section>

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
                      <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
                        {r.taught_topics} of {r.planned_topics} planned
                      </span>
                      <span className="w-20 shrink-0 text-right font-mono tabular-nums">
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

      <Section title="Every class-subject" hint="The rows the roll-ups above are built from.">
        <ScrollX>
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="border-b border-border text-left font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
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
                  <td className="py-2 pr-3 text-right font-mono tabular-nums">
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
