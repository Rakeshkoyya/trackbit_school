"use client";

// Homework — is it being done, and is anyone checking (DASH3 §4.4, redrawn V1-17).
//
// The screen answers one question and the blocks sit in the order it gets
// asked: how much homework was there and what happened to it → where the low
// numbers live → who needs a conversation → who is not checking → what is worth
// saying out loud.
//
// What this replaces: four stat tiles over three charts that all drew the SAME
// measure (completion over time, completion by class, completion by subject).
// None of them said how much homework there was, and the two bar charts each
// collapsed a whole axis — so "6-B is low" and "Hindi is low" could not resolve
// into "6-B Hindi is where it happens", which is the only version an admin can
// act on.
//
// The rule the whole screen is built around, unchanged since HW-1: **a missing
// check is the teacher's gap, never the student's.** It is why the funnel's
// first gap wears a texture instead of a colour, why `completion` divides by
// what has a verdict and never by what was given, and why the checking ledger
// is its own block with the teacher named.
//
// And the one deliberate narrowing: classes and subjects get a highest and a
// lowest; people do not. Ranking teachers by their children's completion would
// make a person's standing a function of forty other people's evenings. The
// ledger rates a teacher on her own act — did she go through what she set —
// and that is the only thing on this screen that rates her at all (D-39/S-92).

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, MessageSquare, Sparkles, UserPlus } from "lucide-react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  CheckingLedger,
  ClassSubjectMatrix,
  FunnelFootnote,
  LoadLegend,
  LoadStrip,
  RANGES,
  RangeSwitch,
  ScopeRank,
  StageTrack,
  num,
  type RangeKey,
} from "@/components/insights/homework";
import { BoardSkeleton, Empty, Fraction, RedRow, Section } from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import type { StudentHomeworkRow } from "@/lib/school-types";

function HomeworkInner() {
  const qc = useQueryClient();
  const [range, setRange] = useState<RangeKey>("week");
  const days = RANGES.find((r) => r.key === range)!.days;

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["insights", "homework", days],
    queryFn: () => insightsApi.homework(days),
    // No skeleton flash when the range changes: the previous slice holds at
    // reduced opacity rather than the page collapsing and jumping back.
    placeholderData: (prev) => prev,
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
  const f = o.funnel;

  return (
    <div className={isFetching ? "opacity-60 transition-opacity" : "transition-opacity"}>
      <PageHeader title="Homework" subtitle="Is it being done — and is anyone checking?" />

      {/* §2: lead with the sentence. Composed server-side so this tab, the
          overview block and Lucy cannot describe the same week differently. */}
      {data.headline ? <p className="mb-4 max-w-[75ch] text-base">{data.headline}</p> : null}

      {/* One filter row above everything it scopes — never a control inside a
          chart card, so every figure on the screen is the same slice. */}
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <RangeSwitch value={range} onChange={setRange} />
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
          {o.from_date} — {o.to_date}
        </span>
      </div>

      {/* ── 1 · what there was, and what happened to it ── */}
      <Section title="Set, checked, done"
        hint="One track, three stages, all counted in student-homeworks so they nest. The hatched zone is homework nobody has gone through — the teacher's gap, and never a score for the children.">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,360px)_minmax(0,1fr)]">
          <div className="rounded-xl border border-border bg-card p-4">
            <StageTrack funnel={f} />
            {f.given ? (
              <div className="mt-4 border-t border-border pt-3">
                <FunnelFootnote funnel={f} />
              </div>
            ) : null}
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <p className="text-sm font-semibold">The shape of it</p>
              <LoadLegend />
            </div>
            <LoadStrip days={data.daily} height={150} />
            <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
              Column height is how much was given, so a quiet day and a day where nothing came
              back are not the same short column. A band of hatch across the top is the checking
              backlog{days > 21 ? ", one column per week over this range" : ""}.
            </p>
          </div>
        </div>
      </Section>

      {/* ── 2 · where the low numbers actually live ── */}
      <Section title="Where it happens"
        hint="A class and a subject resolved into one cell. A pair nobody checked is drawn as a hole in the record, never as the worst square on the grid.">
        <div className="rounded-xl border border-border bg-card p-4">
          <ClassSubjectMatrix cells={o.matrix} classes={o.matrix_classes} subjects={o.matrix_subjects} />
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <ScopeRank rows={o.by_class} title="Classes"
            hint="Highest and lowest completion, of homework that has a verdict." />
          <ScopeRank rows={o.by_subject} title="Subjects"
            hint="The same figure, cut the other way." />
        </div>
      </Section>

      {/* ── 3 · who needs a conversation ── */}
      <Section title="Students who keep missing it"
        hint="Two consecutive homework days missed, or three misses in the range. Unchecked homework never counts against a student, and neither does homework set while they were away.">
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
                    {s.carried ? ` · ${s.carried} while away` : ""}
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

      {/* ── 4 · who is not checking ── */}
      <Section title="Is homework being checked?"
        hint="Counted in sets, because this is about the teacher's own act — a teacher who checks nothing would otherwise read as a class with perfect completion.">
        <CheckingLedger rows={o.teachers} />
      </Section>

      {/* D-85's two derived signals. They are different problems and get
          different rows: "nobody has checked anything" is a teacher's backlog,
          "this class WAS checked and N children missed it" is about a class.
          Neither writes anything into a child's record. */}
      <Section title="Nobody has checked this"
        hint="Counted only once the deadline has passed. The threshold is the school's own setting, not a number baked in here.">
        {o.delayed_teachers.length ? (
          <div className="space-y-2">
            {o.delayed_teachers.map((t) => (
              <RedRow key={t.member_id ?? t.teacher_name} tone="amber"
                title={t.teacher_name}
                subtitle={`${t.unchecked_overdue} past their due date with nothing recorded`}
                meta={<>
                  <Fraction n={t.checked} of={t.assigned} />
                  <span className="block text-xs text-muted-foreground">
                    {t.last_checked_at
                      ? `last checked ${new Date(t.last_checked_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}`
                      : "never checked"}
                  </span>
                </>} />
            ))}
          </div>
        ) : (
          <Empty>Everyone is going through what they set.</Empty>
        )}
      </Section>

      <Section title="Checked, and a lot of them missed it"
        hint="The other half of the picture: the teacher did her part, and the class did not. A different conversation from the one above.">
        {o.rough_classes.length ? (
          <div className="space-y-2">
            {o.rough_classes.map((r) => (
              <RedRow key={r.assignment_id} tone="red"
                title={<>{r.class_label}{r.subject_name ? ` · ${r.subject_name}` : ""}</>}
                subtitle={r.text}
                meta={<>
                  <Fraction n={r.missed} of={r.students_expected} />
                  <span className="block text-xs text-muted-foreground">
                    didn&rsquo;t · {r.teacher_name ?? "unassigned"} · {r.date.slice(5)}
                  </span>
                </>} />
            ))}
          </div>
        ) : (
          <Empty>No class has had a rough night this range.</Empty>
        )}
      </Section>

      {/* ── 5 · worth saying out loud ── */}
      <Section title="Worth saying out loud"
        hint="A single 'best student' would be arbitrary — dozens tie at zero misses. These are the two that mean something.">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
              <Sparkles className="h-4 w-4 text-success" /> Perfect record ({num(o.perfect.length)})
            </p>
            {o.perfect.length ? (
              <ul className="space-y-1 text-sm">
                {o.perfect.slice(0, 10).map((s) => (
                  <li key={s.student_id} className="flex justify-between gap-2">
                    <span className="truncate">{s.full_name}</span>
                    <span className="shrink-0 font-mono text-xs text-muted-foreground">
                      {s.class_label} · {s.done} done
                    </span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted-foreground">Nothing checked yet in this range.</p>}
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
                    <span className="shrink-0 font-mono text-xs text-muted-foreground">
                      {s.class_label} · {s.improvement} fewer misses
                    </span>
                  </li>
                ))}
              </ul>
            ) : <p className="text-sm text-muted-foreground">No change to report over this range.</p>}
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
