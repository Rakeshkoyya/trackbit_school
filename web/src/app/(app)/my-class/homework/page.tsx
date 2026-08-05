"use client";

// My Class → Homework (founder, 2026-08-05; rebuilt as the day book same day).
//
// The tab used to be V1-17's funnel and nothing else: four figures and a track
// saying how much came back. That answers *how are we doing* and cannot answer
// the question a class teacher is actually asked at the gate — **what was
// given?** So the funnel stays, folded to a strip at the top, and the screen is
// now a day book: today's homework in full, and every earlier day as a row that
// opens.
//
// The arithmetic is unchanged and is `core/homework_verdict.py`'s, composed
// server-side so this tab, the funnel above it and the admin board cannot
// describe one evening differently:
//
//   · everything counts **student-homeworks** — one unit per child a homework
//     was given to — so the stages nest, `given ⊇ checked ⊇ graded`;
//   · `given − checked` is nobody having gone through it. That is the TEACHER's
//     gap (HW-1's load-bearing rule): it wears the dashed no-record texture the
//     register and the presence board already use, it is never a colour, never a
//     zero, and never rendered as a child's miss;
//   · `checked − graded` is `carried` (absent when it was set) plus `waived`.
//     Those leave the denominator entirely (`D-34`/`S-98`) and are reported in
//     words rather than absorbed into either side;
//   · completion divides by `graded`, never by `given`, so a class that checked
//     nothing can never read as a class that did nothing.

import { useQuery } from "@tanstack/react-query";
import {
  BookOpen, ChevronLeft, ChevronRight, ClipboardList, User,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { MyClassShell } from "@/components/school/my-class-shell";
import { Dropdown } from "@/components/school/student-table";
import { Badge } from "@/components/ui/badge";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import type {
  HomeworkDayRow, HomeworkItem, MyClassHomework, SchoolTone,
} from "@/lib/school-types";
import { cn } from "@/lib/utils";

const TONE_TEXT: Record<SchoolTone, string> = {
  neutral: "text-muted-foreground",
  green: "text-success",
  amber: "text-warning",
  red: "text-danger",
};

/** The five verdicts, in the module's own words. `late` reads as done because
 *  it IS done (`S-99`); `carried` and `waived` are pending, not failures. */
const VERDICT: Record<string, { label: string; tone: "danger" | "warning" | "neutral" }> = {
  not_done: { label: "not done", tone: "danger" },
  partial: { label: "part done", tone: "warning" },
  late: { label: "late", tone: "warning" },
  carried: { label: "was absent", tone: "neutral" },
  waived: { label: "waived", tone: "neutral" },
};

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    { weekday: "short", day: "2-digit", month: "short" });

// ── the funnel, kept as a strip ──────────────────────────────────────────────
function FunnelStrip({ h }: { h: MyClassHomework }) {
  if (!h.given) return null;
  const pctOf = (n: number) => `${(n / h.given) * 100}%`;
  return (
    <section className="mb-5 overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border px-4 py-2.5">
        <span className={cn("min-w-0 flex-1 text-[13px] font-medium leading-snug",
          TONE_TEXT[h.tone])}>
          {h.headline}
        </span>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          {h.from_date} → {h.to_date}
        </span>
      </header>
      <div className="px-4 py-3">
        <div className="flex h-5 w-full overflow-hidden rounded-md">
          <span style={{ width: pctOf(h.graded), background: "var(--hw-stage-3)" }}
            title={`${h.graded} graded`} />
          <span style={{ width: pctOf(Math.max(0, h.checked - h.graded)),
            background: "var(--hw-stage-2)" }}
            title={`${h.carried} carried · ${h.waived} waived — outside the figure`} />
          {/* Not a colour. "Nobody looked" is the absence of a record. */}
          <span style={{ width: pctOf(h.not_checked) }}
            title={`${h.not_checked} not checked yet`}
            className="border border-dashed border-muted-foreground/50 bg-muted/30" />
        </div>
        <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-muted-foreground">
          <span>
            <span className="mr-1 inline-block h-2 w-2 rounded-sm align-[-1px]"
              style={{ background: "var(--hw-stage-3)" }} />
            {h.graded} graded · {h.completion_pct != null ? `${h.completion_pct}% done` : "—"}
          </span>
          <span>
            <span className="mr-1 inline-block h-2 w-2 rounded-sm align-[-1px]"
              style={{ background: "var(--hw-stage-2)" }} />
            {h.carried} carried · {h.waived} waived
          </span>
          <span>
            <span className="mr-1 inline-block h-2 w-2 rounded-sm border border-dashed border-muted-foreground/50 align-[-1px]" />
            {h.not_checked} not checked yet
          </span>
        </div>
      </div>
    </section>
  );
}

// ── one homework, in full ────────────────────────────────────────────────────
function ItemCard({ item }: { item: HomeworkItem }) {
  return (
    <article className="rounded-xl border border-border bg-card">
      <header className="flex flex-wrap items-baseline gap-1.5 border-b border-border px-4 py-2.5">
        <span className="text-sm font-semibold">{item.subject_name}</span>
        {item.student_name ? (
          <Badge tone="warning">
            <User className="h-3 w-3" /> {item.student_name} only
          </Badge>
        ) : null}
        {item.teacher_name ? (
          <span className="text-[11px] text-muted-foreground">· {item.teacher_name}</span>
        ) : null}
        <span className="ml-auto font-mono text-[10px] tabular-nums text-muted-foreground">
          {item.due_date ? `due ${fmtDay(item.due_date)}` : "no deadline"}
        </span>
      </header>

      {/* The thing this tab existed to show and never did. */}
      <p className="whitespace-pre-wrap px-4 py-3 text-[13px] leading-relaxed">
        {item.text}
      </p>

      <footer className="flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-border bg-muted/25 px-4 py-2 font-mono text-[10px] text-muted-foreground">
        {!item.checked ? (
          // HW-1's rule, made visible: nothing is said about the children.
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-sm border border-dashed border-muted-foreground/60" />
            Nobody has gone through this yet — {item.given} pupil
            {item.given === 1 ? "" : "s"} given it
          </span>
        ) : (
          <>
            <span>
              <span className="text-foreground">
                {item.completion_pct != null ? `${item.completion_pct}%` : "—"}
              </span>{" "}
              of {item.graded} came back done
            </span>
            {item.late ? <span>{item.late} late</span> : null}
            {item.carried ? <span>{item.carried} were absent</span> : null}
            {item.waived ? <span>{item.waived} waived</span> : null}
            {item.checked_by_name ? (
              <span className="ml-auto">checked by {item.checked_by_name}</span>
            ) : null}
          </>
        )}
      </footer>

      {item.misses.length ? (
        <div className="flex flex-wrap gap-1.5 border-t border-border px-4 py-2.5">
          {item.misses.map((r) => (
            <Badge key={r.student_id} tone={VERDICT[r.status]?.tone ?? "neutral"}>
              {r.full_name} · {VERDICT[r.status]?.label ?? r.status}
            </Badge>
          ))}
        </div>
      ) : null}
    </article>
  );
}

// ── the day book ─────────────────────────────────────────────────────────────
function DayRow({ row, classId, open, onToggle }: {
  row: HomeworkDayRow; classId: string; open: boolean; onToggle: () => void;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["my-class", "homework-day", classId, row.date],
    queryFn: () => schoolApi.myClassHomeworkDay(classId, row.date),
    enabled: open,
  });

  return (
    <>
      <button type="button" onClick={onToggle}
        aria-expanded={open}
        className="grid w-full grid-cols-[auto_7.5rem_1fr_auto] items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-muted/40">
        <ChevronRight className={cn("h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
          open && "rotate-90")} />
        <span className="font-mono text-[11px] tabular-nums">{fmtDay(row.date)}</span>
        <span className="min-w-0 truncate text-[13px]">
          {row.assignments} {row.assignments === 1 ? "homework" : "homeworks"}
          <span className="text-muted-foreground"> · {row.subjects.join(", ")}</span>
        </span>
        <span className="shrink-0 text-right font-mono text-[11px] tabular-nums">
          {row.completion_pct != null ? (
            <span className={TONE_TEXT[row.tone]}>{row.completion_pct}%</span>
          ) : (
            // Never a 0 and never red — the record is what is missing here.
            <span className="text-muted-foreground">not checked</span>
          )}
          {row.unchecked_assignments && row.completion_pct != null ? (
            <span className="ml-1.5 text-muted-foreground">
              +{row.unchecked_assignments} unchecked
            </span>
          ) : null}
        </span>
      </button>

      {open ? (
        <div className="space-y-2.5 border-t border-dashed border-border bg-muted/15 px-4 py-3">
          {isLoading ? (
            <p className="text-[12px] text-muted-foreground">Loading that day…</p>
          ) : data?.items.length ? (
            <>
              <p className="text-[12px] leading-snug text-muted-foreground">
                {data.headline}
              </p>
              {data.items.map((i) => (
                <ItemCard key={i.assignment_id} item={i} />
              ))}
            </>
          ) : (
            <p className="text-[12px] text-muted-foreground">
              Nothing was set on that day.
            </p>
          )}
        </div>
      ) : null}
    </>
  );
}

function HomeworkInner({ classId }: { classId: string }) {
  const [days, setDays] = useState("14");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const { data: funnel } = useQuery({
    queryKey: ["my-class", "homework", classId, days],
    queryFn: () => schoolApi.myClassHomework(classId, Number(days)),
  });
  const { data, isLoading } = useQuery({
    queryKey: ["my-class", "homework-days", classId, page],
    queryFn: () => schoolApi.myClassHomeworkDays(classId, { page, size: 20 }),
  });

  if (isLoading && !data) return <PageLoading label="Loading homework…" />;
  if (!data) return null;

  const pages = Math.max(1, Math.ceil(data.total_days / data.size));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 text-[15px] font-medium leading-snug">
          {data.headline}
        </p>
        <Dropdown label="Window" value={days}
          options={[["7", "This week"], ["14", "Two weeks"], ["30", "This month"],
            ["90", "This term"]]}
          onChange={setDays} />
      </div>

      {funnel ? <FunnelStrip h={funnel} /> : null}

      {/* 1 · today, in full — no click needed for the day she is standing in. */}
      <h2 className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        Today · {fmtDay(data.today)}
      </h2>
      {data.today_items.length ? (
        <div className="mb-6 space-y-2.5">
          {data.today_items.map((i) => <ItemCard key={i.assignment_id} item={i} />)}
        </div>
      ) : (
        <p className="mb-6 rounded-xl border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
          <BookOpen className="mx-auto mb-2 h-5 w-5" />
          Nothing has gone home today yet.
        </p>
      )}

      {/* 2 · the day book */}
      <h2 className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        Earlier days
      </h2>
      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {data.rows.length ? (
          <div className="divide-y divide-border">
            {data.rows.map((row) => (
              <div key={row.date}>
                <DayRow row={row} classId={classId} open={!!open[row.date]}
                  onToggle={() => setOpen((s) => ({ ...s, [row.date]: !s[row.date] }))} />
              </div>
            ))}
          </div>
        ) : (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            <ClipboardList className="mx-auto mb-2 h-5 w-5" />
            No earlier homework recorded for this class.
          </p>
        )}

        {pages > 1 ? (
          <footer className="flex items-center justify-between gap-2 border-t border-border bg-muted/25 px-4 py-2">
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
              {data.total_days} days · page {data.page} of {pages}
            </span>
            <span className="flex gap-1.5">
              <button type="button" disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="inline-flex h-7 items-center gap-1 rounded-full border border-border px-2.5 text-xs disabled:opacity-40">
                <ChevronLeft className="h-3.5 w-3.5" /> Newer
              </button>
              <button type="button" disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex h-7 items-center gap-1 rounded-full border border-border px-2.5 text-xs disabled:opacity-40">
                Older <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </span>
          </footer>
        ) : null}
      </section>

      <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
        A day with no percentage is a day nobody has gone through yet — that is a
        gap in the record, not something the children did, and nothing about it
        is counted against them.{" "}
        <Link href="/homework" className="text-primary hover:underline">
          Open the homework desk
        </Link>
      </p>
    </div>
  );
}

export default function MyClassHomeworkPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyClassShell
        title={(k) => `${k.class_label} · homework`}
        subtitle={() => "What was given, what came back, and what nobody has looked at"}>
        {(k) => <HomeworkInner classId={k.class_id} />}
      </MyClassShell>
    </AuthGuard>
  );
}
