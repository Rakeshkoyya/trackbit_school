"use client";

// Homework — is it being done, and is anyone checking (DASH3 §4.4).
//
// The distinction this whole screen is built around: **a missing check is the
// teacher's gap, never the student's.** `not_checked` is counted separately,
// excluded from every completion figure, and never rendered as a miss — which is
// why "checking discipline" is its own block with the teacher named, and why the
// completion line's denominator is student-assignments under CHECKED homework.
//
// Recognition is a list, not a winner: in a healthy class dozens of students tie
// at zero misses, so picking one "best" would be arbitrary. Perfect-week is the
// list; most-improved is the real signal.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, MessageSquare, Sparkles, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ChartCard, PulseArea, RowBars, StatTile, toneForPct, type ChartRow } from "@/components/charts";
import { BoardSkeleton, Empty, RedRow, ScrollX, Section, StateChip, dayLabel } from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import type { StudentHomeworkRow } from "@/lib/school-types";

function HomeworkInner() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["insights", "homework"],
    queryFn: () => insightsApi.homework(),
  });

  const run = useMutation({
    mutationFn: ({ kind, row }: { kind: "guardian_reminded" | "followup_assigned"; row: StudentHomeworkRow }) =>
      insightsApi.action(kind, {
        student_id: row.student_id,
        title: kind === "followup_assigned"
          ? `${row.full_name} — homework not done ${row.not_done + row.partial}×`
          : undefined,
        message: kind === "guardian_reminded"
          ? `Homework has been missed ${row.not_done + row.partial} time(s) recently. Please check tonight's work with them.`
          : undefined,
      }),
    onSuccess: (res) => {
      if (res.already_done) toast.info(res.message);
      else toast.success(res.message);
      qc.invalidateQueries({ queryKey: ["insights", "homework"] });
    },
    onError: (e) => showApiError(e, "Could not complete that"),
  });

  if (isLoading || !data) {
    return <><PageHeader title="Homework" subtitle="Is it being done — and is anyone checking?" /><BoardSkeleton /></>;
  }

  const o = data.overview;
  const dailyRows: ChartRow[] = data.daily
    .filter((d) => d.completion != null)
    .map((d) => ({ x: dayLabel(d.date), pct: Math.round((d.completion ?? 0) * 100) }));
  const classRows: ChartRow[] = o.by_class
    .filter((c) => c.completion != null)
    .map((c) => ({ x: c.key, pct: Math.round((c.completion ?? 0) * 100) }));
  const subjectRows: ChartRow[] = o.by_subject
    .filter((c) => c.completion != null)
    .map((c) => ({ x: c.key, pct: Math.round((c.completion ?? 0) * 100) }));
  const unchecked = o.assigned - o.checked;

  return (
    <div>
      <PageHeader title="Homework" subtitle="Is it being done — and is anyone checking?" />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label={`Completed (${o.window_days}d)`}
          value={o.overall_completion != null ? `${Math.round(o.overall_completion * 100)}%` : "—"}
          sub="of homework that was actually checked"
          tone={o.overall_completion == null ? "neutral"
            : o.overall_completion >= 0.75 ? "green" : o.overall_completion >= 0.6 ? "amber" : "red"}
        />
        {/* Unchecked is its own number on purpose: folding it into completion
            would let a teacher who checks nothing show a perfect record. */}
        <StatTile
          label="Set but never checked"
          value={String(unchecked)}
          sub={o.check_rate != null ? `${Math.round(o.check_rate * 100)}% of homework gets checked` : "nothing set yet"}
          tone={unchecked > 5 ? "red" : unchecked ? "amber" : "green"}
        />
        <StatTile
          label="Students slipping"
          value={String(o.needs_attention.length)}
          sub={o.needs_attention.length ? "repeat misses" : "nobody is repeatedly missing it"}
          tone={o.needs_attention.length ? "red" : "green"}
        />
        <StatTile
          label="Perfect record"
          value={String(o.perfect.length)}
          sub="zero misses over the window"
          tone="green"
        />
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <ChartCard title="Completion over the window" className="lg:col-span-2"
          hint="Only days with checked homework appear — an unchecked day is not a 0% day.">
          {dailyRows.length > 1 ? (
            <PulseArea rows={dailyRows} dataKey="pct" label="Done" yUnit="%" yDomain={[0, 100]} height={170} />
          ) : (
            <Empty>Not enough checked days yet — the line starts once two days are checked.</Empty>
          )}
        </ChartCard>

        <ChartCard title="By class" hint="Done vs set, for homework the teacher went through.">
          {classRows.length ? (
            <RowBars rows={classRows} dataKey="pct" unit="%" max={100}
              height={Math.max(140, classRows.length * 26)}
              colorFor={(r) => toneForPct(r.pct as number, { good: 75, fair: 60 })} />
          ) : (
            <Empty>No homework has been checked yet.</Empty>
          )}
        </ChartCard>

        <ChartCard title="By subject" hint="Where homework lands, and where it doesn't.">
          {subjectRows.length ? (
            <RowBars rows={subjectRows} dataKey="pct" unit="%" max={100}
              height={Math.max(140, subjectRows.length * 26)}
              colorFor={(r) => toneForPct(r.pct as number, { good: 75, fair: 60 })} />
          ) : (
            <Empty>No homework has been checked yet.</Empty>
          )}
        </ChartCard>
      </div>

      <Section title="Students who keep missing it"
        hint="Two consecutive homework days missed, or three misses in the window. Unchecked homework never counts against a student.">
        {o.needs_attention.length ? (
          <div className="space-y-2">
            {o.needs_attention.map((s) => (
              <RedRow
                key={s.student_id}
                href={`/students/${s.student_id}`}
                title={<>{s.full_name} <span className="font-normal text-muted-foreground">· {s.class_label}</span></>}
                subtitle={
                  <>
                    {s.not_done + s.partial} missed of {s.assigned}
                    {s.streak ? ` · ${s.streak} day streak` : ""}
                    {s.subjects.length ? ` · ${s.subjects.join(", ")}` : ""}
                    {s.teachers.length ? ` · ${s.teachers.join(", ")}` : ""}
                  </>
                }
                meta={s.completion != null ? <Badge tone="danger">{Math.round(s.completion * 100)}%</Badge> : null}
                actions={
                  <>
                    <Button size="sm" variant="outline" disabled={run.isPending}
                      onClick={() => run.mutate({ kind: "guardian_reminded", row: s })}>
                      <MessageSquare className="h-3.5 w-3.5" /> Remind guardian
                    </Button>
                    <Button size="sm" variant="outline" disabled={run.isPending}
                      onClick={() => run.mutate({ kind: "followup_assigned", row: s })}>
                      <UserPlus className="h-3.5 w-3.5" /> Follow up
                    </Button>
                  </>
                }
              />
            ))}
          </div>
        ) : (
          <Empty>Nobody is repeatedly missing homework. That is the good case.</Empty>
        )}
      </Section>

      <Section title="Is homework being checked?"
        hint="A missing check is a fact about the teacher, not the class — a teacher who checks nothing would otherwise read as a class with perfect completion.">
        <ScrollX>
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Teacher</th>
                <th className="py-2 pr-3 text-right font-medium">Set</th>
                <th className="py-2 pr-3 text-right font-medium">Checked</th>
                <th className="py-2 pr-3 text-right font-medium">Overdue, unchecked</th>
                <th className="py-2 font-medium">Rate</th>
              </tr>
            </thead>
            <tbody>
              {o.teachers.map((t) => (
                <tr key={t.member_id ?? t.teacher_name} className="border-b border-border/60">
                  <td className="py-2 pr-3">{t.teacher_name}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{t.assigned}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{t.checked}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">
                    {t.unchecked_overdue ? <span className="text-danger">{t.unchecked_overdue}</span> : "0"}
                  </td>
                  <td className="py-2">
                    {t.check_rate == null ? <StateChip>nothing set</StateChip>
                      : <Badge tone={t.check_rate >= 0.8 ? "success" : t.check_rate >= 0.5 ? "warning" : "danger"}>
                          {Math.round(t.check_rate * 100)}%
                        </Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollX>
      </Section>

      <Section title="Worth saying out loud"
        hint="A single 'best' would be arbitrary — dozens tie at zero misses. These are the two that mean something.">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
              <Sparkles className="h-4 w-4 text-success" /> Perfect record ({o.perfect.length})
            </p>
            {o.perfect.length ? (
              <ul className="space-y-1 text-sm">
                {o.perfect.slice(0, 10).map((s) => (
                  <li key={s.student_id} className="flex justify-between gap-2">
                    <span className="truncate">{s.full_name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{s.class_label} · {s.done} done</span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted-foreground">Nothing checked yet this window.</p>}
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
              <CheckCircle2 className="h-4 w-4 text-success" /> Most improved
            </p>
            {o.most_improved.length ? (
              <ul className="space-y-1 text-sm">
                {o.most_improved.map((s) => (
                  <li key={s.student_id} className="flex justify-between gap-2">
                    <span className="truncate">{s.full_name}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {s.class_label} · {s.streak} fewer misses
                    </span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted-foreground">No change to report over this window.</p>}
          </div>
        </div>
      </Section>
    </div>
  );
}

export default function DashboardHomeworkPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <HomeworkInner />
    </AuthGuard>
  );
}
