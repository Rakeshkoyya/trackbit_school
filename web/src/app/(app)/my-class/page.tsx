"use client";

// My Class → Overview (founder, 2026-08-05).
//
// Her six morning questions, each as a block: a sentence, the two or three
// figures it rests on, and named rows under them where there is somebody to
// act on. Everything is painted, not decided — the headline, the tone and
// whether a figure exists at all all arrive from `services/my_class.py`, so
// this block and the tab it links to cannot describe the day differently.
//
// The rule repeated in every block: **a denominator nobody filled in is a word,
// never a zero.** An unopened register is not an empty classroom; an unchecked
// homework is not a class that did nothing.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, CheckCircle2, ClipboardCheck, Layers, MessageSquare, NotebookPen,
} from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BAND_COLOR } from "@/components/charts";
import { MyClassShell } from "@/components/school/my-class-shell";
import { SubjectPaceList } from "@/components/school/subject-pace-list";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import { schoolApi } from "@/lib/school-api";
import type { MyClassOverview, SchoolTone } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const TONE_TEXT: Record<SchoolTone, string> = {
  neutral: "text-muted-foreground",
  green: "text-success",
  amber: "text-warning",
  red: "text-danger",
};

const TONE_BADGE: Record<SchoolTone, "neutral" | "success" | "warning" | "danger"> = {
  neutral: "neutral", green: "success", amber: "warning", red: "danger",
};

/** The payload's lowercase keys → the band letters the palette is keyed by.
 *  The ramp is ORDINAL (how much support a child needs), not the status
 *  palette: painting C red would turn a teaching group into a verdict. */
const TIER = { a: "A", b: "B", c: "C" } as const;

const RULE: Record<SchoolTone, string> = {
  neutral: "bg-muted-foreground/25",
  green: "bg-success",
  amber: "bg-warning",
  red: "bg-danger",
};

function Block({
  title, headline, tone = "neutral", href, hrefLabel, children,
}: {
  title: string;
  headline: string;
  tone?: SchoolTone;
  href?: string;
  hrefLabel?: string;
  children?: React.ReactNode;
}) {
  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-border bg-card">
      <header className="border-b border-border px-4 py-2.5">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          {title}
        </span>
      </header>
      <p className={cn("px-4 py-3 text-[13px] leading-snug", TONE_TEXT[tone])}>
        {headline}
      </p>
      {children}
      {href ? (
        <footer className="mt-auto border-t border-border bg-muted/25 px-4 py-2">
          <Link href={href}
            className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] text-primary hover:underline">
            {hrefLabel ?? "Open"} <ArrowRight className="h-3 w-3" />
          </Link>
        </footer>
      ) : null}
    </section>
  );
}

/** A figure with its denominator. There is deliberately no way to render one
 *  without the other — a bare percentage is unreadable (ux §4). */
function Metric({ label, value, of }: { label: string; value: React.ReactNode; of?: string }) {
  return (
    <div>
      <span className="block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </span>
      <span className="mt-0.5 block font-mono text-[17px] leading-none tabular-nums">
        {value}
        {of ? <span className="ml-1 text-[11px] text-muted-foreground">{of}</span> : null}
      </span>
    </div>
  );
}

function AttendanceBlock({ board }: { board: MyClassOverview }) {
  const qc = useQueryClient();
  const a = board.attendance;
  const remind = useMutation({
    mutationFn: (studentId: string) =>
      insightsApi.action("guardian_reminded", { student_id: studentId }),
    onSuccess: (res) => {
      // `already_done` is the rail refusing to pester, not a failure.
      if (res.already_done) toast.info(res.message);
      else toast.success(res.message);
      qc.invalidateQueries({ queryKey: ["my-class", "overview"] });
    },
    onError: (e) => showApiError(e, "Could not send that"),
  });

  return (
    <Block title="Today's register" headline={a.headline} tone={a.tone}
      href={`/my-class/attendance?class=${board.class_id}`}
      hrefLabel={a.marked ? "Open the register" : "Take the register"}>
      <div className="grid grid-cols-3 gap-3 px-4 pb-3">
        <Metric label="On the roll" value={a.roster} />
        {/* Present is shown only when somebody marked. A 0 here would say the
            classroom was empty; the truth is that nobody has looked. */}
        <Metric label="In" value={a.marked ? a.present : "—"}
          of={a.marked ? `of ${a.roster}` : "not marked"} />
        <Metric label="This month"
          value={a.month_pct != null ? `${a.month_pct}%` : "—"}
          of={a.month_marked_days ? `over ${a.month_marked_days}d` : "no days marked"} />
      </div>
      {a.absentees.length ? (
        <ul className="border-t border-border">
          {a.absentees.map((s) => (
            <li key={s.student_id} className="border-t border-border/60 px-4 py-2.5 first:border-t-0">
              <div className="flex items-start gap-2">
                <span className={cn("mt-[5px] h-3 w-[2px] shrink-0 rounded-full", RULE[s.tone])} />
                <span className="min-w-0 flex-1">
                  <Link href={`/students/${s.student_id}`}
                    className="text-[13px] font-medium hover:underline">
                    {s.full_name}
                  </Link>
                  {s.streak > 1 ? (
                    <span className="ml-1.5 align-[2px]">
                      <Badge tone={TONE_BADGE[s.tone]}>{s.streak}d</Badge>
                    </span>
                  ) : null}
                  <span className="block text-[11px] leading-snug text-muted-foreground">
                    {s.reason_note || s.reason_code || "nobody has explained this"}
                    {s.guardian_name ? ` · ${s.guardian_name}` : ""}
                  </span>
                </span>
                {s.guardian_phone ? (
                  <a href={`tel:${s.guardian_phone}`}
                    className="shrink-0 font-mono text-xs text-primary hover:underline">
                    {s.guardian_phone}
                  </a>
                ) : null}
              </div>
              <div className="mt-1.5 pl-[10px]">
                {s.reminded_today ? (
                  <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-success">
                    <CheckCircle2 className="h-3 w-3" /> Reminded
                  </span>
                ) : (
                  <Button size="sm" variant="outline" className="h-7 px-2 text-xs"
                    disabled={remind.isPending}
                    onClick={() => remind.mutate(s.student_id)}>
                    <MessageSquare className="h-3.5 w-3.5" /> Remind the family
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </Block>
  );
}

function HomeworkBlock({ board }: { board: MyClassOverview }) {
  const h = board.homework;
  return (
    <Block title="Homework" headline={h.headline} tone={h.tone}
      href={`/my-class/homework?class=${board.class_id}`} hrefLabel="Open homework">
      <div className="grid grid-cols-3 gap-3 px-4 pb-3">
        <Metric label="Set" value={h.assignments}
          of={h.given ? `${h.given} pieces` : undefined} />
        {/* `not_checked` is the TEACHER's gap and is never folded into a
            completion figure — HW-1's load-bearing rule. */}
        <Metric label="Unchecked" value={h.unchecked_assignments}
          of={h.unchecked_assignments ? "still to go through" : "all checked"} />
        <Metric label="Came back"
          value={h.completion_pct != null ? `${h.completion_pct}%` : "—"}
          of={h.graded ? `of ${h.graded} checked` : "nothing checked yet"} />
      </div>
    </Block>
  );
}

function BandsBlock({ board }: { board: MyClassOverview }) {
  const b = board.bands;
  return (
    <Block title="Support tiers" headline={b.headline}
      href={`/my-class/bands?class=${board.class_id}`} hrefLabel="Open bands">
      {b.subjects.length ? (
        <div className="space-y-2 px-4 pb-3">
          {b.subjects.map((s) => (
            <div key={s.subject_id} className="flex items-center gap-2">
              <span className="w-24 shrink-0 truncate text-[12px]">{s.subject_name}</span>
              <span className="flex min-w-0 flex-1 overflow-hidden rounded-full">
                {/* The ramp is ordinal — how much support a child needs — and
                    "not assessed" is not a step on it, so it is the dashed
                    no-record texture the register and the funnel already use. */}
                {(["a", "b", "c"] as const).map((tier) => (
                  s[tier] ? (
                    <span key={tier}
                      style={{ flex: s[tier], background: BAND_COLOR[TIER[tier]] }}
                      title={`${s[tier]} in band ${TIER[tier]}`}
                      className="h-2.5" />
                  ) : null
                ))}
                {s.not_assessed ? (
                  <span style={{ flex: s.not_assessed }} title={`${s.not_assessed} not assessed`}
                    className="h-2.5 border border-dashed border-muted-foreground/40" />
                ) : null}
              </span>
              <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
                {s.assessed ? `${s.c}C` : "—"}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </Block>
  );
}

function ExamsBlock({ board }: { board: MyClassOverview }) {
  const e = board.exams;
  return (
    <Block title="Exams" headline={e.headline}>
      {e.recent.length ? (
        <ul className="border-t border-border">
          {e.recent.slice(0, 4).map((x) => (
            <li key={x.id} className="border-t border-border/60 first:border-t-0">
              <Link href={`/students/academics/exams/exam/${x.id}`}
                className="flex items-baseline gap-2 px-4 py-2 hover:bg-muted/40">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px]">{x.name}</span>
                  <span className="block text-[11px] text-muted-foreground">
                    {x.type_label}
                    {x.subject_name ? ` · ${x.subject_name}` : ""}
                  </span>
                </span>
                <span className="shrink-0 font-mono text-[12px] tabular-nums">
                  {x.avg_pct != null ? `${x.avg_pct}%` : "—"}
                  <span className="ml-1 text-[10px] text-muted-foreground">
                    {x.scored_count}/{x.roster_count}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </Block>
  );
}

function OverviewInner({ classId }: { classId: string }) {
  const { data } = useQuery({
    queryKey: ["my-class", "overview", classId],
    queryFn: () => schoolApi.myClassOverview(classId),
  });
  if (!data) return null;

  return (
    <div className="space-y-4">
      {/* The sentence first, always. The blocks are what it rests on (ux §7). */}
      <p className="text-[15px] font-medium leading-snug">{data.headline}</p>

      <div className="grid gap-4 lg:grid-cols-2">
        <AttendanceBlock board={data} />
        <HomeworkBlock board={data} />
        <BandsBlock board={data} />
        <ExamsBlock board={data} />
      </div>

      {data.syllabus ? (
        <section className="overflow-hidden rounded-xl border border-border bg-card">
          <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5">
            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Every subject this class takes
            </span>
            <Link href={`/my-class/syllabus?class=${classId}`}
              className="font-mono text-[10px] uppercase tracking-[0.1em] text-primary hover:underline">
              Open syllabus
            </Link>
          </header>
          <div className="px-4 py-3">
            <p className="mb-3 text-[13px] font-medium">{data.syllabus.headline}</p>
            <SubjectPaceList rows={data.syllabus.rows.slice(0, 4)} showTeacher
              emptyText="This class has no subjects set up yet." />
          </div>
        </section>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Link href={`/my-class/students?class=${classId}`}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted">
          <NotebookPen className="h-4 w-4" /> Her children, one by one
        </Link>
        <Link href={`/my-class/homework?class=${classId}`}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted">
          <ClipboardCheck className="h-4 w-4" /> Homework
        </Link>
        <Link href={`/my-class/bands?class=${classId}`}
          className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted">
          <Layers className="h-4 w-4" /> Who needs support
        </Link>
      </div>
    </div>
  );
}

export default function MyClassPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyClassShell
        title={(k) => `My Class · ${k.class_label}`}
        subtitle={(k) => `${k.roster} children — what needs you this morning`}>
        {(k) => <OverviewInner classId={k.class_id} />}
      </MyClassShell>
    </AuthGuard>
  );
}
