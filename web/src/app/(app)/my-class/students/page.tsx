"use client";

// My Class → Students (founder, 2026-08-05).
//
// Her children as a table, and every row is a door: tapping one opens that
// child's full file at `/students/[id]` — the growth report that already joins
// attendance, chapters taught and missed, homework, observations and scores.
//
// Deliberately NOT a ranking. Every figure carries its own denominator, and a
// figure whose denominator is empty renders as a word rather than a zero: a
// class nobody marked must not read as a class of absentees, and a homework
// nobody checked must never render as a child's miss (HW-1).

import { useQuery } from "@tanstack/react-query";
import { NotebookPen, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { MyClassShell } from "@/components/school/my-class-shell";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import type { SchoolTone } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const RULE: Record<SchoolTone, string> = {
  neutral: "bg-muted-foreground/25",
  green: "bg-success",
  amber: "bg-warning",
  red: "bg-danger",
};

const COLS = "minmax(0,2fr) 7.5rem 7.5rem minmax(0,1.2fr) 6rem";

/** A percentage with the denominator it was computed over, or a WORD when
 *  there was no denominator at all. Never a bare number, never a zero standing
 *  in for "nobody has captured this" (ux §4, §5). */
function Figure({ pct, of, empty }: { pct: number | null; of: string; empty: string }) {
  if (pct == null) {
    return (
      <span className="block font-mono text-[11px] leading-snug text-muted-foreground/70">
        {empty}
      </span>
    );
  }
  return (
    <span className="block">
      <span className="font-mono text-[13px] tabular-nums">{pct}%</span>
      <span className="block font-mono text-[10px] text-muted-foreground">{of}</span>
    </span>
  );
}

function StudentsInner({ classId }: { classId: string }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["my-class", "students", classId],
    queryFn: () => schoolApi.myClassStudents(classId),
  });

  if (isLoading) return <PageLoading label="Loading your children…" />;
  if (!data) return null;

  const needle = q.trim().toLowerCase();
  const rows = needle
    ? data.rows.filter((r) =>
        r.full_name.toLowerCase().includes(needle)
        || (r.roll_no ?? "").toLowerCase().includes(needle)
        || (r.admission_no ?? "").toLowerCase().includes(needle)
        || r.band_chips.some((c) => c.toLowerCase().includes(needle)))
    : data.rows;

  return (
    <div>
      <p className="mb-3 text-[13px] leading-snug">{data.headline}</p>

      <div className="relative mb-3 max-w-sm">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input className="h-9 pl-8" placeholder="Search a child…" value={q}
          onChange={(e) => setQ(e.target.value)} />
      </div>

      <div className="overflow-x-auto rounded-xl border border-border bg-card"
        style={{ contain: "layout inline-size" }}>
        <div className="min-w-[720px]">
          <div style={{ display: "grid", gridTemplateColumns: COLS }}
            className="border-b border-border bg-muted/20 px-3 py-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
            <span>Child</span>
            <span>Attendance</span>
            <span>Homework</span>
            <span>Bands &amp; last exam</span>
            <span className="text-right">Log</span>
          </div>
          {rows.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">
              Nobody matches.
            </p>
          ) : rows.map((r) => (
            <div key={r.student_id}
              onClick={() => router.push(`/students/${r.student_id}`)}
              style={{ display: "grid", gridTemplateColumns: COLS, alignItems: "center" }}
              className="cursor-pointer border-b border-border/60 px-3 py-2 last:border-b-0 hover:bg-muted/40">
              <span className="flex min-w-0 items-start gap-2">
                <span className={cn("mt-[6px] h-3 w-[2px] shrink-0 rounded-full", RULE[r.tone])} />
                <span className="min-w-0">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate text-[13px] font-medium">{r.full_name}</span>
                    {r.absent_today ? <Badge tone="danger">away today</Badge> : null}
                  </span>
                  <span className="block truncate font-mono text-[10px] text-muted-foreground">
                    {[r.roll_no && `roll ${r.roll_no}`, r.admission_no, r.category]
                      .filter(Boolean).join(" · ") || "—"}
                  </span>
                </span>
              </span>

              <Figure pct={r.attendance_pct}
                of={`of ${r.marked_days}d marked`}
                empty="nothing marked" />

              {/* `not_checked` never becomes a child's miss — so a child whose
                  homework nobody has gone through has no figure at all here. */}
              <Figure pct={r.homework_pct}
                of={`of ${r.homework_graded} checked`}
                empty="nothing checked" />

              <span className="min-w-0 pr-2">
                {r.band_chips.length ? (
                  <span className="flex flex-wrap gap-1">
                    {r.band_chips.map((c) => (
                      <span key={c}
                        className="rounded-full border border-border px-1.5 py-0.5 font-mono text-[10px]">
                        {c}
                      </span>
                    ))}
                  </span>
                ) : (
                  <span className="font-mono text-[10px] text-muted-foreground/70">
                    not assessed
                  </span>
                )}
                {r.latest_exam_pct != null ? (
                  <span className="mt-0.5 block truncate font-mono text-[10px] text-muted-foreground">
                    {r.latest_exam_name} · {r.latest_exam_pct}%
                  </span>
                ) : null}
              </span>

              <span className="flex items-center justify-end gap-1 font-mono text-[11px] tabular-nums text-muted-foreground">
                <NotebookPen className="h-3.5 w-3.5" />
                {r.note_count || "—"}
              </span>
            </div>
          ))}
        </div>
      </div>

      <p className="mt-2 text-[11px] text-muted-foreground">
        Tap a child to open their full file — every subject, what was taught while
        they were away, their homework, their scores, and your log about them.
      </p>
    </div>
  );
}

export default function MyClassStudentsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyClassShell
        title={(k) => `${k.class_label} · her children`}
        subtitle={() => "Tap a name to open that child's file"}>
        {(k) => <StudentsInner classId={k.class_id} />}
      </MyClassShell>
    </AuthGuard>
  );
}
