"use client";

/**
 * The syllabus board (SY-1) — every chapter as one row.
 *
 * Plan → Syllabus was a one-class, one-subject editor: to answer "which
 * chapters are late?" an admin picked her way through class × subject, one plan
 * at a time, holding the comparison in her head. This is the same facts as a
 * table she can group, filter and sort.
 *
 * Three devices carried in from the rest of the app rather than invented here,
 * because the board has to read as part of the same document:
 *
 *   · **the pace bar** (V1-15) — the progress cell is a fill with the plan's own
 *     marker on it, so "40%" is legible without the reader carrying the
 *     calendar: arc past the tick is ahead, short of it is behind.
 *   · **the dashed no-record texture** (V1-14's register, V1-16's away cell,
 *     V1-17's unchecked homework) — a chapter nobody has scheduled is drawn as
 *     an absence of record. It is never red and never a 0%: it has not been
 *     missed, it has not been promised.
 *   · **mono figures and column heads** — periods, dates and drift are the
 *     document's data, and they line up.
 *
 * Mounted twice: the admin's whole-school board and the teacher's own-subjects
 * one. The scope difference is the SERVER's; this component renders whatever it
 * is handed.
 */

import { ChevronDown, ChevronRight, Pencil, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { PaceBar } from "@/components/charts";
import { Dropdown } from "@/components/school/student-table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type {
  ChapterStatus,
  Difficulty,
  SyllabusBoard,
  SyllabusChapterRow,
  SyllabusSubjectGroup,
} from "@/lib/syllabus-types";
import { cn } from "@/lib/utils";

// ── vocabulary ───────────────────────────────────────────────────────────────
const STATUS_LABEL: Record<ChapterStatus, string> = {
  completed: "Completed",
  in_progress: "In progress",
  not_started: "Not started",
  not_scheduled: "Not scheduled",
};

/** Difficulty is the school's own reading, so it is ordinal ink, not status
 *  ink — painting a hard chapter red would make it a problem rather than a
 *  chapter that needs more days. Unset stays visibly unset. */
const DIFFICULTY_STYLE: Record<Difficulty, string> = {
  easy: "border-transparent bg-muted text-muted-foreground",
  moderate: "border-transparent bg-accent text-accent-foreground",
  hard: "border-transparent bg-warning-soft text-warning",
};
const DIFFICULTY_ORDER: Record<string, number> = { easy: 1, moderate: 2, hard: 3 };

const fmtDay = (iso: string | null) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    { day: "2-digit", month: "short" }) : "—";

const GROUP_COLORS = ["#6b7fd7", "#3f8f6b", "#c98a3d", "#b05f8a", "#5b9aa9", "#8a6bbf"];

type GroupBy = "class" | "subject" | "term" | "status" | "none";
type SortBy = "syllabus" | "planned" | "progress" | "difficulty" | "status";

/** One flattened row: the chapter plus the subject it hangs off. */
interface Row extends SyllabusChapterRow {
  subject: SyllabusSubjectGroup;
}

function flatten(board: SyllabusBoard): Row[] {
  const out: Row[] = [];
  for (const group of board.classes) {
    for (const subject of group.subjects) {
      for (const chapter of subject.chapters) out.push({ ...chapter, subject });
    }
  }
  return out;
}

// ── the two editable cells ───────────────────────────────────────────────────
function DifficultyCell({ row, canEdit, onSaved }: {
  row: Row; canEdit: boolean; onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const save = async (value: Difficulty | "unset") => {
    setOpen(false);
    try {
      await schoolApi.patchChapter(row.unit_id, { difficulty: value });
      onSaved();
    } catch (e) { showApiError(e, "Could not set the difficulty"); }
  };

  const chip = row.difficulty ? (
    <span className={cn("rounded-full border px-2 py-0.5 text-xs capitalize",
      DIFFICULTY_STYLE[row.difficulty])}>{row.difficulty}</span>
  ) : (
    // Nobody has judged it. A dashed outline, never a defaulted "moderate".
    <span className="rounded-full border border-dashed border-border px-2 py-0.5 text-xs text-muted-foreground">
      not set
    </span>
  );
  if (!canEdit) return chip;
  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="rounded-full transition-opacity hover:opacity-80"
        aria-label={`Difficulty of ${row.title}`}>
        {chip}
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full z-50 mt-1 w-32 rounded-lg border border-border bg-card p-1 shadow-lg">
            {(["easy", "moderate", "hard"] as Difficulty[]).map((d) => (
              <button key={d} type="button" onClick={() => save(d)}
                className="block w-full rounded-md px-2.5 py-1.5 text-left text-sm capitalize hover:bg-muted">
                {d}
              </button>
            ))}
            <button type="button" onClick={() => save("unset")}
              className="block w-full rounded-md px-2.5 py-1.5 text-left text-sm text-muted-foreground hover:bg-muted">
              Clear
            </button>
          </div>
        </>
      ) : null}
    </div>
  );
}

function RemarksCell({ row, canEdit, onSaved }: {
  row: Row; canEdit: boolean; onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(row.remarks ?? "");

  const save = async () => {
    setEditing(false);
    if ((row.remarks ?? "") === value.trim()) return;
    try {
      // "" clears it — an emptied box is a retraction, and keeping the old text
      // would make a remark impossible to take back.
      await schoolApi.patchChapter(row.unit_id, { remarks: value.trim() });
      onSaved();
      toast.success(value.trim() ? "Remark saved" : "Remark cleared");
    } catch (e) { showApiError(e, "Could not save the remark"); }
  };

  if (editing) {
    return (
      <form onSubmit={(e) => { e.preventDefault(); save(); }}>
        <Input autoFocus className="h-7 text-xs" value={value} onBlur={save}
          placeholder="Add a remark" onChange={(e) => setValue(e.target.value)} />
      </form>
    );
  }
  if (!canEdit) {
    return <span className="text-xs text-muted-foreground">{row.remarks || "—"}</span>;
  }
  return (
    <button type="button"
      onClick={() => { setValue(row.remarks ?? ""); setEditing(true); }}
      className="group/r flex w-full items-center gap-1 text-left text-xs text-muted-foreground hover:text-foreground">
      <span className="min-w-0 truncate">{row.remarks || "Add a remark"}</span>
      <Pencil className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover/r:opacity-60" />
    </button>
  );
}

// ── cells that are just rendering rules ──────────────────────────────────────
function StatusCell({ row }: { row: Row }) {
  if (row.overdue) {
    return <Badge tone="danger">Overdue</Badge>;
  }
  if (row.status === "not_scheduled") {
    // The board's worst-looking square must never be a hole in the record.
    return (
      <span className="inline-flex items-center rounded-full border border-dashed border-border px-2 py-0.5 text-xs text-muted-foreground">
        Not scheduled
      </span>
    );
  }
  const tone = row.status === "completed" ? "success"
    : row.status === "in_progress" ? "primary" : "outline";
  return <Badge tone={tone}>{STATUS_LABEL[row.status]}</Badge>;
}

/** Planned above, actual below — never merged into one column. The gap between
 *  them is the finding, and a single "date" would have to pick one. */
function DatesCell({ from, to, drift, muted }: {
  from: string | null; to: string | null; drift?: number | null; muted?: boolean;
}) {
  if (!from && !to) {
    return <span className="font-mono text-xs text-muted-foreground/70">—</span>;
  }
  return (
    <span className={cn("font-mono text-xs tabular-nums",
      muted ? "text-muted-foreground" : "")}>
      {fmtDay(from)}<span className="px-1 text-muted-foreground/50">→</span>{fmtDay(to)}
      {drift != null && drift !== 0 ? (
        <span className={cn("ml-1", drift > 0 ? "text-warning" : "text-success")}>
          {drift > 0 ? `+${drift}d` : `${drift}d`}
        </span>
      ) : null}
    </span>
  );
}

function ProgressCell({ row }: { row: Row }) {
  const tone = row.completion_pct == null ? "neutral"
    : row.overdue ? "red"
      : row.status === "completed" ? "green"
        : row.expected_pct != null && row.completion_pct + 12 < row.expected_pct
          ? "amber" : "green";
  return (
    <div className="w-full">
      <PaceBar
        pct={row.status === "not_scheduled" ? null : row.completion_pct}
        expectedPct={row.expected_pct} tone={tone} height={7} />
      <p className="mt-1 font-mono text-[11px] tabular-nums text-muted-foreground">
        {row.status === "not_scheduled" ? "not scheduled"
          : `${row.taught_full + row.taught_partial}⁄${row.topics_total} topics`}
      </p>
    </div>
  );
}

// ── the table ────────────────────────────────────────────────────────────────
/**
 * Nine columns of real content do not fit 1000px, so the table scrolls inside
 * its own box (the `contain` wrapper below) rather than shrinking to fit.
 *
 * Every flexible column carries a `minmax` floor. Without it the fixed columns
 * ate the row and the chapter and subject names truncated to a single letter —
 * a table whose first column reads "K…" is not a table.
 */
const COLUMNS = [
  "minmax(12rem,1.6fr)",   // chapter
  "4.5rem",                // periods
  "5.75rem",               // difficulty
  "9rem",                  // planned
  "9rem",                  // actually taught
  "7.5rem",                // progress
  "7rem",                  // status
  "minmax(9rem,1.2fr)",    // remarks
].join(" ");

/**
 * The second axis: whatever the group is NOT.
 *
 * Grouping by class already puts "6-A" on the card, so a Subject column
 * repeating "Mathematics" down eight rows spends the width that made the
 * chapter name readable. It becomes a heading between the rows instead — which
 * is also where the per-subject pace and the "Adjust plan" button belong.
 */
interface SubGroup {
  key: string;
  /** Empty = no heading (ungrouped), so each row names its own subject. */
  label: string;
  caption: string;
  /** Second line on the chapter cell when there is no heading above it. */
  rowHint: string;
  subject: SyllabusSubjectGroup | null;
}

function subGroups(rows: Row[], groupBy: GroupBy): [SubGroup, Row[]][] {
  const map = new Map<string, Row[]>();
  for (const r of rows) {
    map.set(r.subject.class_subject_id,
      [...(map.get(r.subject.class_subject_id) ?? []), r]);
  }
  return [...map.entries()].map(([key, subRows]) => {
    const s = subRows[0].subject;
    if (groupBy === "none") {
      // Ungrouped: there is no card heading to hang a subject off, so the row
      // carries it instead of losing it.
      return [{
        key, label: "", caption: "",
        rowHint: `${s.class_label} · ${s.subject_name}`, subject: null,
      }, subRows];
    }
    return [{
      key,
      // Grouped by subject, the class is what varies, so the heading says which.
      label: groupBy === "subject"
        ? `${s.class_label} · ${s.subject_name}` : s.subject_name,
      caption: [
        s.teacher_name,
        s.periods_per_week ? `${s.periods_per_week}/wk` : null,
        s.coverage_pct != null ? `${s.coverage_pct}% of the plan taught` : null,
      ].filter(Boolean).join(" · "),
      rowHint: "",
      subject: s,
    }, subRows];
  });
}

/** The chapter name stays put while the rest of the row scrolls. Nine columns
 *  do not fit any laptop, and a Status cell whose row you can no longer
 *  identify says nothing at all. */
const STICKY_COL = "sticky left-0 z-10 -ml-3 pl-3";

function ColHead({ children, className = "" }: {
  children: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn(
      "font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground",
      className)}>
      {children}
    </div>
  );
}

function TopicRows({ row }: { row: Row }) {
  return (
    <div className="border-t border-dashed border-border/70 bg-muted/20">
      {row.topics.map((t) => (
        <div key={t.id}
          className="grid items-center gap-2.5 px-3 py-1.5 pl-9"
          style={{ gridTemplateColumns: COLUMNS }}>
          <p className={cn("truncate bg-muted/20 text-xs text-muted-foreground",
            STICKY_COL)}>{t.title}</p>
          <span className="font-mono text-xs tabular-nums text-muted-foreground">
            {t.est_periods ?? "—"}
          </span>
          <span />
          <DatesCell from={t.planned_start} to={t.planned_end} muted />
          <DatesCell from={t.actual_start} to={t.actual_end} muted />
          <span className="text-xs text-muted-foreground">
            {t.coverage === "full" ? "Taught"
              : t.coverage === "partial" ? "Part-taught" : "—"}
          </span>
          <span className="text-xs text-muted-foreground">
            {STATUS_LABEL[t.status]}
          </span>
          <span />
        </div>
      ))}
    </div>
  );
}

export function SyllabusTable({ board, canEdit, onChanged, onAdjust,
  defaultGroupBy = "class" }: {
  board: SyllabusBoard;
  canEdit: boolean;
  onChanged: () => void;
  /** Offered per subject when the caller can re-plan (the teacher's screen). */
  onAdjust?: (subject: SyllabusSubjectGroup) => void;
  /** My Class mounts this for ONE class, where grouping by class is a single
   *  heading over everything — subject is the axis that separates rows there. */
  defaultGroupBy?: GroupBy;
}) {
  const [q, setQ] = useState("");
  const [groupBy, setGroupBy] = useState<GroupBy>(defaultGroupBy);
  const [sortBy, setSortBy] = useState<SortBy>("syllabus");
  const [status, setStatus] = useState<string>("all");
  const [difficulty, setDifficulty] = useState<string>("all");
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const rows = useMemo(() => flatten(board), [board]);

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let out = rows;
    if (needle) {
      out = out.filter((r) =>
        r.title.toLowerCase().includes(needle)
        || r.subject.subject_name.toLowerCase().includes(needle)
        || r.subject.class_label.toLowerCase().includes(needle)
        || (r.remarks ?? "").toLowerCase().includes(needle)
        || r.topics.some((t) => t.title.toLowerCase().includes(needle)));
    }
    if (status === "overdue") out = out.filter((r) => r.overdue);
    else if (status !== "all") out = out.filter((r) => r.status === status);
    if (difficulty === "unset") out = out.filter((r) => !r.difficulty);
    else if (difficulty !== "all") out = out.filter((r) => r.difficulty === difficulty);

    const sorted = [...out];
    sorted.sort((a, b) => {
      switch (sortBy) {
        case "planned":
          // Unplanned chapters sort last rather than to 1970 — they are not
          // "the oldest thing on the board", they have no date at all.
          if (!a.planned_start !== !b.planned_start) return a.planned_start ? -1 : 1;
          return (a.planned_start ?? "").localeCompare(b.planned_start ?? "");
        case "progress":
          return (a.completion_pct ?? -1) - (b.completion_pct ?? -1);
        case "difficulty":
          return (DIFFICULTY_ORDER[b.difficulty ?? ""] ?? 0)
            - (DIFFICULTY_ORDER[a.difficulty ?? ""] ?? 0);
        case "status":
          return Number(b.overdue) - Number(a.overdue)
            || a.status.localeCompare(b.status);
        default:
          return a.subject.class_label.localeCompare(b.subject.class_label,
            undefined, { numeric: true })
            || a.subject.subject_name.localeCompare(b.subject.subject_name)
            || a.position - b.position;
      }
    });
    return sorted;
  }, [rows, q, status, difficulty, sortBy]);

  const groups = useMemo(() => {
    const map = new Map<string, Row[]>();
    for (const r of visible) {
      const key = groupBy === "class" ? r.subject.class_label
        : groupBy === "subject" ? r.subject.subject_name
          : groupBy === "term" ? (r.term_name ?? "No term")
            : groupBy === "status" ? (r.overdue ? "Overdue" : STATUS_LABEL[r.status])
              : "";
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(r);
    }
    return [...map.entries()];
  }, [visible, groupBy]);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1 basis-44">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="h-9 pl-8" placeholder="Search chapters, subjects, remarks…"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Dropdown label="Group by" value={groupBy}
          options={[["class", "Class"], ["subject", "Subject"], ["term", "Term"],
            ["status", "Status"], ["none", "None"]]}
          onChange={(v) => setGroupBy(v as GroupBy)} />
        <Dropdown label="Status" value={status}
          options={[["all", "All"], ["overdue", "Overdue"], ["in_progress", "In progress"],
            ["not_started", "Not started"], ["completed", "Completed"],
            ["not_scheduled", "Not scheduled"]]}
          onChange={setStatus} />
        <Dropdown label="Difficulty" value={difficulty}
          options={[["all", "All"], ["hard", "Hard"], ["moderate", "Moderate"],
            ["easy", "Easy"], ["unset", "Not set"]]}
          onChange={setDifficulty} />
        <Dropdown label="Sort" value={sortBy}
          options={[["syllabus", "Syllabus order"], ["planned", "Planned date"],
            ["progress", "Progress"], ["difficulty", "Difficulty"],
            ["status", "Status"]]}
          onChange={(v) => setSortBy(v as SortBy)} />
      </div>

      {!visible.length ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          {rows.length
            ? "No chapters match those filters."
            : "No chapters recorded yet — import a syllabus in Setup to fill this in."}
        </p>
      ) : (
        <div className="space-y-4">
          {groups.map(([label, groupRows], gi) => (
            <div key={label || "all"}
              className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
              {groupBy !== "none" ? (
                <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
                  <span className="h-4 w-1 rounded-full"
                    style={{ background: GROUP_COLORS[gi % GROUP_COLORS.length] }} />
                  <p className="text-sm font-semibold">{label}</p>
                  <span className="font-mono text-xs text-muted-foreground">
                    {groupRows.length} chapter{groupRows.length === 1 ? "" : "s"}
                  </span>
                </div>
              ) : null}

              {/* The table scrolls inside its own box; the page never moves
                  sideways (V1-14's ScrollX rule — `contain` is load-bearing).
                  The fade says there is more to the right; without it the row
                  simply stops at the card edge and reads as a missing column. */}
              <div className="relative">
              <div className="pointer-events-none absolute inset-y-0 right-0 z-20 w-6 bg-gradient-to-l from-card to-transparent" />
              <div className="overflow-x-auto" style={{ contain: "layout inline-size" }}>
                <div className="min-w-[64rem]">
                  <div className="grid gap-2.5 border-b border-border bg-card px-3 py-2"
                    style={{ gridTemplateColumns: COLUMNS }}>
                    <ColHead className={cn(STICKY_COL, "bg-card")}>Chapter</ColHead>
                    <ColHead>Periods</ColHead>
                    <ColHead>Difficulty</ColHead>
                    <ColHead>Planned</ColHead>
                    <ColHead>Actually taught</ColHead>
                    <ColHead>Progress</ColHead>
                    <ColHead>Status</ColHead>
                    <ColHead>Remarks</ColHead>
                  </div>

                  {subGroups(groupRows, groupBy).map(([sub, subRows]) => (
                    <div key={sub.key}>
                      {/* The second axis is a heading, not a column. Grouping by
                          class already puts 6-A on the card, so a Subject cell
                          repeating "Mathematics" on eight rows spent the width
                          that made the chapter name readable. */}
                      {sub.label ? (
                        <div className="border-b border-border bg-muted/25 px-3 py-1.5">
                          {/* Pinned left with the chapter column: scrolled away,
                              the heading left fragments like "% of the plan
                              taught" floating over rows it no longer names. */}
                          <div className="sticky left-3 flex w-fit max-w-full flex-wrap items-center gap-x-2 gap-y-1">
                            <p className="text-xs font-semibold">{sub.label}</p>
                            {sub.caption ? (
                              <p className="font-mono text-[11px] text-muted-foreground">
                                {sub.caption}
                              </p>
                            ) : null}
                            {onAdjust && sub.subject ? (
                              <button type="button" onClick={() => onAdjust(sub.subject!)}
                                className="rounded-full border border-border bg-card px-2.5 py-0.5 text-[11px] font-medium transition-colors hover:bg-muted">
                                Adjust plan
                              </button>
                            ) : null}
                          </div>
                        </div>
                      ) : null}

                      {subRows.map((r) => {
                        const expanded = !!open[r.unit_id];
                        return (
                          <div key={r.unit_id} className="border-b border-border last:border-b-0">
                            <div className="group grid items-center gap-2.5 px-3 py-2.5 transition-colors hover:bg-muted/30"
                              style={{ gridTemplateColumns: COLUMNS }}>
                              <div className={cn(
                                "flex min-w-0 items-center gap-1.5 bg-card transition-colors group-hover:bg-muted/30",
                                STICKY_COL)}>
                                {r.has_topic_detail ? (
                                  <button type="button"
                                    onClick={() => setOpen((o) => ({ ...o, [r.unit_id]: !expanded }))}
                                    aria-expanded={expanded}
                                    aria-label={`${expanded ? "Hide" : "Show"} topics in ${r.title}`}
                                    className="shrink-0 rounded text-muted-foreground hover:text-foreground">
                                    {expanded ? <ChevronDown className="h-4 w-4" />
                                      : <ChevronRight className="h-4 w-4" />}
                                  </button>
                                ) : <span className="w-4 shrink-0" />}
                                <div className="min-w-0">
                                  <p className="truncate text-sm font-medium">{r.title}</p>
                                  <p className="truncate text-[11px] text-muted-foreground">
                                    {[r.term_name, sub.rowHint].filter(Boolean).join(" · ") || " "}
                                  </p>
                                </div>
                              </div>

                              <span className="font-mono text-sm tabular-nums">
                                {r.est_periods ?? (
                                  <span className="text-xs text-muted-foreground">not sized</span>
                                )}
                              </span>

                              <DifficultyCell row={r} canEdit={canEdit} onSaved={onChanged} />
                              <DatesCell from={r.planned_start} to={r.planned_end} />
                              <DatesCell from={r.actual_start} to={r.actual_end}
                                drift={r.finish_drift_days} />
                              <ProgressCell row={r} />
                              <StatusCell row={r} />
                              <RemarksCell row={r} canEdit={canEdit} onSaved={onChanged} />
                            </div>
                            {expanded ? <TopicRows row={r} /> : null}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
