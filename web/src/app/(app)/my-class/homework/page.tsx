"use client";

// My Class → Homework (founder, 2026-08-05).
//
// V1-17's funnel, for one class. The stages NEST — `given ⊇ checked ⊇ graded` —
// because everything here counts **student-homeworks**: one unit per child a
// homework was given to. Counting sets of homework in one stage and children in
// the next is what made the old board's three headline figures unreadable.
//
// The two gaps are two different findings and are never the same colour:
//
//   · `given − checked` is nobody having gone through it. That is the TEACHER's
//     gap (HW-1's load-bearing rule), so it wears the dashed no-record texture
//     the register and the presence board already use — never a colour, never a
//     zero, and never rendered as a child's miss on any surface.
//   · `checked − graded` is `carried` (absent when it was set) plus `waived`.
//     Those leave the denominator entirely (`D-34`/`S-98`) and are reported in
//     words rather than absorbed into either side.
//
// And `completion` divides by `graded`, never by `given`: a class that checked
// nothing can never read as a class that did nothing.

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { MyClassShell } from "@/components/school/my-class-shell";
import { Dropdown } from "@/components/school/student-table";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import type { MyClassHomework, SchoolTone } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const TONE_TEXT: Record<SchoolTone, string> = {
  neutral: "text-muted-foreground",
  green: "text-success",
  amber: "text-warning",
  red: "text-danger",
};

/** The funnel as one track: three nested stages, the unchecked tail hatched.
 *  Stage colour is an ORDINAL ramp — the stages are ordered and nested, so one
 *  hue deepening is the honest encoding (V1-17). */
function Funnel({ h }: { h: MyClassHomework }) {
  if (!h.given) return null;
  const pctOf = (n: number) => `${(n / h.given) * 100}%`;
  return (
    <div className="px-4 pb-3">
      <div className="flex h-6 w-full overflow-hidden rounded-md">
        <span style={{ width: pctOf(h.graded), background: "var(--hw-stage-3)" }}
          title={`${h.graded} graded`} />
        <span style={{ width: pctOf(Math.max(0, h.checked - h.graded)),
          background: "var(--hw-stage-2)" }}
          title={`${h.carried} carried · ${h.waived} waived — outside the figure`} />
        {/* Not a colour. "Nobody looked" is the absence of a record, and the
            grid's worst-looking square must not be a hole in the record. */}
        <span style={{ width: pctOf(h.not_checked) }}
          title={`${h.not_checked} not checked yet`}
          className="border border-dashed border-muted-foreground/50 bg-muted/30" />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-muted-foreground">
        <span><span className="mr-1 inline-block h-2 w-2 rounded-sm align-[-1px]"
          style={{ background: "var(--hw-stage-3)" }} />
          {h.graded} graded
        </span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-sm align-[-1px]"
          style={{ background: "var(--hw-stage-2)" }} />
          {h.carried} carried · {h.waived} waived
        </span>
        <span><span className="mr-1 inline-block h-2 w-2 rounded-sm border border-dashed border-muted-foreground/50 align-[-1px]" />
          {h.not_checked} not checked yet
        </span>
      </div>
    </div>
  );
}

function Metric({ label, value, of }: { label: string; value: React.ReactNode; of?: string }) {
  return (
    <div>
      <span className="block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </span>
      <span className="mt-0.5 block font-mono text-[19px] leading-none tabular-nums">
        {value}
      </span>
      {of ? (
        <span className="mt-0.5 block font-mono text-[10px] text-muted-foreground">{of}</span>
      ) : null}
    </div>
  );
}

function HomeworkInner({ classId }: { classId: string }) {
  const [days, setDays] = useState("14");
  const { data, isLoading } = useQuery({
    queryKey: ["my-class", "homework", classId, days],
    queryFn: () => schoolApi.myClassHomework(classId, Number(days)),
  });

  if (isLoading) return <PageLoading label="Loading homework…" />;
  if (!data) return null;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <p className={cn("min-w-0 flex-1 text-[15px] font-medium leading-snug",
          TONE_TEXT[data.tone])}>
          {data.headline}
        </p>
        <Dropdown label="Window" value={days}
          options={[["7", "This week"], ["14", "Two weeks"], ["30", "This month"],
            ["90", "This term"]]}
          onChange={setDays} />
      </div>

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <header className="flex items-baseline justify-between gap-2 border-b border-border px-4 py-2.5">
          <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            What was set, what came back
          </span>
          <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
            {data.from_date} → {data.to_date}
          </span>
        </header>

        <div className="grid grid-cols-2 gap-4 px-4 py-3 sm:grid-cols-4">
          <Metric label="Set" value={data.assignments}
            of={`${data.given} pieces of work`} />
          <Metric label="Gone through" value={data.checked}
            of={data.not_checked ? `${data.not_checked} not yet` : "all of it"} />
          {/* The figure that must never be a 0 when nothing was checked. */}
          <Metric label="Came back done"
            value={data.completion_pct != null ? `${data.completion_pct}%` : "—"}
            of={data.graded ? `of ${data.graded} checked` : "nothing checked yet"} />
          <Metric label="Late" value={data.late}
            of={data.late ? "done, after the deadline" : "none"} />
        </div>

        <Funnel h={data} />

        <footer className="border-t border-border bg-muted/25 px-4 py-2 text-[11px] leading-snug text-muted-foreground">
          {data.unchecked_assignments ? (
            <>
              <span className="font-medium text-foreground">
                {data.unchecked_assignments}{" "}
                {data.unchecked_assignments === 1 ? "homework has" : "homeworks have"}
              </span>{" "}
              not been gone through. That is a gap in the record, not something the
              children did — nothing about it is counted against them.{" "}
              <Link href="/homework" className="text-primary hover:underline">
                Check homework
              </Link>
            </>
          ) : (
            <>
              Everything set in this window has been gone through.{" "}
              <Link href="/homework" className="text-primary hover:underline">
                Open the homework desk
              </Link>
            </>
          )}
        </footer>
      </section>

      <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
        Six teachers each set a reasonable amount of work; nobody else adds it up.
        This is the one screen that does, and it is informational — never a cap,
        because a limit turns into &ldquo;whose turn is it to set homework&rdquo;.
      </p>
    </div>
  );
}

export default function MyClassHomeworkPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyClassShell
        title={(k) => `${k.class_label} · homework`}
        subtitle={() => "What was set, what came back, and what nobody has looked at"}>
        {(k) => <HomeworkInner classId={k.class_id} />}
      </MyClassShell>
    </AuthGuard>
  );
}
