"use client";

/**
 * Students → Academics (founder, 2026-08-05) — the roster of how each child is doing.
 *
 * Same shape as Directory next door, opposite content: not a field you correct
 * but a figure you read. One row per child, and every figure on it comes from a
 * roll-up a module already computes, so this table can never disagree with the
 * tab it links to (`S-51`).
 *
 * Four rules the row obeys, each of which was a defect somewhere else first:
 *
 *   · **Nothing recorded is a word, never a zero.** An unopened register renders
 *     the dashed no-record texture (the register's own device, V1-14) and the
 *     word "not marked" — a 0% would read as a class that never turned up.
 *   · **Minor and major never pool** (`S-114`). Standing is read from major and
 *     trajectory from minor; they sit side by side and are never added. Each
 *     carries its denominator, which is what `sentence` is for (`S-118`).
 *   · **`not_checked` is the teacher's gap, never the child's** (HW-1). The
 *     last-homework cell says "not checked yet" in muted text and is never a
 *     miss, on this surface as on every other.
 *   · **The band chip is staff-only** (P4) and never travels without its
 *     descriptor — `BandChip` is the one component that keeps both true.
 *
 * A teacher gets the same screen scoped by the SERVICE, not by this component:
 * `/students/records` returns her classes ∪ her homeroom, and asking for
 * someone else's class is a 403 with a sentence rather than an empty table.
 */

import { useQuery } from "@tanstack/react-query";
import { GraduationCap, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { PaceBar } from "@/components/charts";
import { BandChip } from "@/components/school/band-chip";
import { Dropdown } from "@/components/school/student-table";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";
import type {
  BandTier, RecordFigure, RecordHomework, StudentRecordRow,
} from "@/lib/school-types";
import { cn } from "@/lib/utils";

const GROUP_COLORS = ["#6b7fd7", "#3f8f6b", "#c98a3d", "#b05f8a", "#5b9aa9", "#8a6bbf"];

const attendanceTone = (pct: number | null) =>
  pct == null ? "neutral" : pct >= 90 ? "green" : pct >= 75 ? "amber" : "red";

/** The last homework, said honestly.
 *
 *  `not_checked` gets muted text and the word — it is the teacher not having
 *  opened the books, and rendering it beside "not done" would put a teacher's
 *  gap on a child's row. `late` is DONE (`S-99`) and says so separately;
 *  `carried` is a child who was absent when it was set and is never a miss. */
function HomeworkCell({ hw }: { hw: RecordHomework }) {
  if (!hw.assigned) {
    return <span className="text-xs text-muted-foreground">none set</span>;
  }
  const label: Record<string, { text: string; cls: string }> = {
    done: { text: "did it", cls: "text-success" },
    late: { text: "did it, late", cls: "text-success" },
    partial: { text: "part done", cls: "text-warning" },
    not_done: { text: "not done", cls: "text-danger font-medium" },
    carried: { text: "was absent", cls: "text-muted-foreground" },
    waived: { text: "waived", cls: "text-muted-foreground" },
    not_checked: { text: "not checked yet", cls: "text-muted-foreground italic" },
  };
  const l = label[hw.latest_status ?? ""] ?? { text: "—", cls: "text-muted-foreground" };
  return (
    <span className="flex flex-col gap-0.5">
      <span className={cn("text-xs", l.cls)}>{l.text}</span>
      <span className="text-[11px] text-muted-foreground">
        {hw.latest_subject}{hw.latest_date ? ` · ${hw.latest_date.slice(5)}` : ""}
      </span>
      {hw.streak >= 2 ? (
        <Badge tone="danger" className="mt-0.5 w-fit text-[10px]">
          missed {hw.streak} days
        </Badge>
      ) : null}
    </span>
  );
}

/** Both buckets, always — "no major exams yet" is information, and dropping the
 *  row is how a screen ends up implying there were none. */
function ExamCell({ figures }: { figures: RecordFigure[] }) {
  const by = new Map(figures.map((f) => [f.scale, f]));
  const rows: [string, RecordFigure | undefined][] = [
    ["Major", by.get("major")], ["Minor", by.get("minor")],
  ];
  return (
    <span className="flex flex-col gap-0.5">
      {rows.map(([name, f]) => (
        <span key={name} className="flex items-baseline gap-1.5 text-xs" title={f?.sentence}>
          <span className="w-9 shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground">
            {name}
          </span>
          {f?.pct == null ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            <>
              <span className="font-medium tabular-nums">{f.pct}%</span>
              <span className="text-[11px] text-muted-foreground">
                of {f.tests_held} test{f.tests_held === 1 ? "" : "s"}
              </span>
            </>
          )}
        </span>
      ))}
    </span>
  );
}

type GroupBy = "class" | "none";

function AcademicsRoster() {
  const router = useRouter();
  const { yearId } = useYear();
  const [query, setQuery] = useState("");
  const [classFilter, setClassFilter] = useState("all");
  const [groupBy, setGroupBy] = useState<GroupBy>("class");

  const { data, isLoading } = useQuery({
    queryKey: ["student-records", query],
    queryFn: () => schoolApi.studentRecords({ q: query.trim() || undefined }),
  });
  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId, "mine"],
    queryFn: () => schoolApi.classes(yearId ?? undefined),
    enabled: !!yearId,
  });

  if (isLoading) return <PageLoading />;
  const all = data?.rows ?? [];
  const rows = all.filter((r) => classFilter === "all" || r.class_id === classFilter);

  const groups = new Map<string, StudentRecordRow[]>();
  for (const r of rows) {
    const k = groupBy === "class" ? (r.class_label ?? "Unassigned") : "";
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(r);
  }
  const ordered = [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));

  const table = (list: StudentRecordRow[]) => (
    <div className="overflow-x-auto">
      {/* `table-fixed` + an explicit colgroup, because each class group is its
          own <table>: with auto layout every group sized its columns to its own
          content, so "Attendance" sat at a different x in 6-A than in 6-B and
          the eye could not scan down a column at all. */}
      <table className="w-full min-w-[760px] table-fixed text-sm">
        <colgroup>
          <col className="w-[30%]" />
          <col className="w-[10%]" />
          <col className="w-[18%]" />
          <col className="w-[21%]" />
          <col className="w-[21%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">Name</th>
            <th className="px-3 py-2 font-medium">Class</th>
            <th className="px-3 py-2 font-medium">Attendance</th>
            <th className="px-3 py-2 font-medium">Exams</th>
            <th className="px-3 py-2 font-medium">Last homework</th>
          </tr>
        </thead>
        <tbody>
          {list.map((r) => (
            <tr
              key={r.student_id}
              onClick={() => router.push(`/students/${r.student_id}`)}
              className="cursor-pointer border-b border-border/60 bg-card last:border-0 hover:bg-muted/40"
            >
              <td className="px-3 py-2.5">
                <span className="flex items-center gap-2">
                  <Avatar name={r.full_name} />
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate font-medium">{r.full_name}</span>
                    <span className="text-[11px] text-muted-foreground">{r.admission_no}</span>
                  </span>
                  {/* Staff-only, and never a bare letter (`S-186`). */}
                  {r.band_chip ? (
                    <BandChip
                      tier={r.band_chip.charAt(0) as BandTier}
                      descriptor={r.band_chip}
                      className="ml-1 shrink-0"
                    />
                  ) : null}
                </span>
              </td>
              <td className="px-3 py-2.5 text-muted-foreground">{r.class_label ?? "—"}</td>
              <td className="px-3 py-2.5">
                {r.attendance.marked_periods === 0 ? (
                  <span className="flex flex-col gap-1">
                    <PaceBar pct={null} />
                    <span className="text-[11px] text-muted-foreground">not marked</span>
                  </span>
                ) : (
                  <span className="flex flex-col gap-1">
                    <PaceBar pct={r.attendance.pct}
                      tone={attendanceTone(r.attendance.pct)} />
                    <span className="text-[11px] text-muted-foreground tabular-nums">
                      {r.attendance.pct}% of {r.attendance.marked_periods} periods
                      {r.attendance.late ? ` · ${r.attendance.late} late` : ""}
                    </span>
                  </span>
                )}
              </td>
              <td className="px-3 py-2.5"><ExamCell figures={r.figures} /></td>
              <td className="px-3 py-2.5"><HomeworkCell hw={r.homework} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Academics ({rows.length})</h1>
        <p className="text-sm text-muted-foreground">
          How each child is doing — attendance, exams and homework over the last{" "}
          {data?.window_days ?? 30} days.
          {data?.scoped
            ? ` Your ${data.class_count} class${data.class_count === 1 ? "" : "es"}.`
            : ""}
        </p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1 basis-48">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Search by name or admission no.…"
            value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <Dropdown label="Group by" value={groupBy}
          options={[["class", "Class"], ["none", "None"]]}
          onChange={(v) => setGroupBy(v as GroupBy)} />
        <Dropdown label="Class" value={classFilter}
          options={[["all", "All"], ...classes.map((c): [string, string] =>
            [c.id, c.name + (c.section ? `-${c.section}` : "")])]}
          onChange={setClassFilter} />
      </div>

      {rows.length === 0 ? (
        <EmptyState icon={GraduationCap} title="No students here yet"
          body="Once a class has children in it, this table fills itself from the register, the homework and the exams — nobody types into it." />
      ) : groupBy === "none" ? (
        <div className="overflow-hidden rounded-xl border border-border shadow-sm">
          {table(rows)}
        </div>
      ) : (
        <div className="space-y-4">
          {ordered.map(([label, list], gi) => (
            <div key={label} className="overflow-hidden rounded-xl border border-border shadow-sm">
              <div className="flex items-center gap-2 border-b border-border bg-card px-3 py-2">
                <span className="h-4 w-1 rounded-full"
                  style={{ background: GROUP_COLORS[gi % GROUP_COLORS.length] }} />
                <p className="text-sm font-semibold">{label}</p>
                <span className="text-xs text-muted-foreground">{list.length}</span>
              </div>
              {table(list)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function StudentsAcademicsPage() {
  return (
    <AuthGuard>
      <AcademicsRoster />
    </AuthGuard>
  );
}
