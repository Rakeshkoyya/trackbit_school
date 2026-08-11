"use client";

/**
 * The syllabus grid (founder, SY-2) — one class-subject, edited like a sheet.
 *
 * The school already keeps this table. It is an .xlsx with a sheet per class
 * and these columns down it: Ch #, Chapter Name, Est. Periods, Difficulty,
 * Planned Start, Teaching Status, Mentor, Remarks. Plan → Syllabus rendered the
 * same facts as a *board* — groupable, filterable, sortable, and writable in
 * exactly two cells. Everything else meant opening a dialog, and the school
 * kept using the spreadsheet.
 *
 * So: **every cell is live.** Not "click the pencil to edit" — the input IS the
 * cell, always, and Tab walks the row the way it walks a spreadsheet. That is
 * the whole difference between a screen a school fills in and a screen it reads.
 *
 * Three things this grid refuses to do, all of them load-bearing:
 *
 *   · **A cell saves on blur, and only when it changed.** No Save button to
 *     forget, and no PATCH storm from arrow keys. A failed save puts the
 *     server's value back — the cell never keeps a number the database
 *     rejected.
 *   · **A typed status never moves a percentage.** `manual_status` is what
 *     somebody claimed; `completion_pct` stays what the lesson logs support,
 *     and where the two disagree the row says so. Letting a dropdown drive
 *     coverage would be the sixth definition of "syllabus covered".
 *   · **Not-captured stays a word.** An unsized chapter reads "not sized", an
 *     unscheduled one reads "not scheduled". Never `0`, never red — a gap in
 *     the record is not a failure by the person looking at it.
 *
 * Dates go through the planner's own `reschedule`, not a second date column of
 * this grid's own. The approved baseline stays frozen underneath (P2), so a
 * chapter moved into next month still shows its slip everywhere else.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Loader2, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { dayKey } from "@/lib/format";
import { schoolApi } from "@/lib/school-api";
import type {
  ChapterPatch, ChapterStatus, Difficulty, SyllabusBoard, SyllabusChapterRow,
  SyllabusSubjectGroup,
} from "@/lib/syllabus-types";
import { cn } from "@/lib/utils";

// ── vocabulary ───────────────────────────────────────────────────────────────
/** The three words a human may TYPE. `not_scheduled` is missing on purpose: it
 *  is a state of the plan, not a claim about teaching, and it is reached by
 *  taking the chapter out of scope rather than by picking it here. */
const TYPEABLE: { value: ChapterStatus; label: string }[] = [
  { value: "not_started", label: "Not started" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
];

const STATUS_LABEL: Record<ChapterStatus, string> = {
  not_scheduled: "Not scheduled",
  not_started: "Not started",
  in_progress: "In progress",
  completed: "Completed",
};

const STATUS_TONE: Record<ChapterStatus, string> = {
  completed: "border-success/40 bg-success-soft text-success",
  in_progress: "border-primary/40 bg-primary/10 text-primary",
  not_started: "border-border bg-card text-foreground",
  // The no-record texture (V1-14's register, V1-16's away cell): dashed, muted,
  // never red. Nobody has promised this chapter, so nobody has missed it.
  not_scheduled: "border-dashed border-border bg-transparent text-muted-foreground",
};

const DIFFICULTIES: { value: Difficulty | ""; label: string }[] = [
  { value: "", label: "—" },
  { value: "easy", label: "Easy" },
  { value: "moderate", label: "Moderate" },
  { value: "hard", label: "Hard" },
];

/**
 * Nine columns of real content do not fit a laptop, so the grid scrolls inside
 * its own box rather than shrinking to fit. Every flexible column carries a
 * `minmax` floor — without one the fixed columns ate the row and the chapter
 * name truncated to a single letter.
 */
const COLS = [
  "2.75rem",              // ch #
  "minmax(13rem,1.7fr)",  // chapter
  "5rem",                 // periods
  "7rem",                 // difficulty
  "9.5rem",               // planned from
  "9.5rem",               // planned to
  "8rem",                 // taught
  // Wide enough for the longest thing the cell can say, which is the default
  // option — "From logs · Not scheduled". A status that truncates to "Not
  // st…" is a status nobody can read at a glance, which is the only reason
  // the column exists.
  "12rem",                // status
  "minmax(10rem,1.1fr)",  // remarks
  "2rem",                 // remove
].join(" ");

const fmtDay = (iso: string | null) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    { day: "2-digit", month: "short" }) : "—";

/** A borderless cell that only shows its edges when you are in it. The grid has
 *  to read as a table at rest and as a form under the cursor. */
const CELL =
  "h-8 w-full rounded-md border border-transparent bg-transparent px-1.5 text-sm " +
  "transition-colors hover:border-border focus:border-primary focus:bg-card " +
  "focus-visible:outline-none";

// ── the editable cells ───────────────────────────────────────────────────────
/** Text that commits on blur or Enter, reverts on Escape, and only PATCHes when
 *  the value actually moved. */
function TextCell({ value, onSave, placeholder, mono }: {
  value: string; onSave: (v: string) => Promise<void>;
  placeholder?: string; mono?: boolean;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? value;

  const commit = async () => {
    if (draft === null) return;
    const next = draft.trim();
    setDraft(null);
    if (next === value) return;      // nothing moved — no request
    await onSave(next);
  };

  return (
    <input value={shown} placeholder={placeholder}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        // Escape abandons the edit. Without it a half-typed chapter name is
        // committed by the click that was trying to cancel it.
        if (e.key === "Escape") { setDraft(null); (e.target as HTMLInputElement).blur(); }
      }}
      className={cn(CELL, mono && "font-mono tabular-nums",
        !shown && "placeholder:text-muted-foreground/70")} />
  );
}

/** Periods. Empty means UNSIZED — a real state, not a zero — so an emptied box
 *  clears the estimate rather than writing 0. */
function PeriodsCell({ row, onSave }: {
  row: SyllabusChapterRow; onSave: (p: ChapterPatch) => Promise<void>;
}) {
  const value = row.est_periods == null ? "" : String(row.est_periods);
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? value;

  // A chapter split into topics is sized topic by topic; the server refuses to
  // divide 8 periods over three of them, so the row shows the sum and says why
  // rather than offering a box that always fails.
  if (row.topics_total > 1) {
    return (
      <span className="px-1.5 font-mono text-xs tabular-nums text-muted-foreground"
        title={`${row.topics_total} topics — sized individually`}>
        {row.est_periods ?? "—"}
        <span className="ml-1 text-[10px]">Σ</span>
      </span>
    );
  }

  return (
    <input type="number" min={0} max={400} value={shown} placeholder="—"
      onChange={(e) => setDraft(e.target.value)}
      onBlur={async () => {
        if (draft === null) return;
        const next = draft.trim();
        setDraft(null);
        if (next === value) return;
        await onSave(next === ""
          ? { clear_est_periods: true }
          : { est_periods: Number(next) });
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") { setDraft(null); (e.target as HTMLInputElement).blur(); }
      }}
      className={cn(CELL, "font-mono tabular-nums",
        row.est_periods == null && "text-warning placeholder:text-warning")} />
  );
}

/** One end of the planned window. A native date input, because "click the
 *  planned date and pick one" is exactly what a date input is, and a bespoke
 *  calendar would lose keyboard entry and the phone's own picker. */
function DateCell({ value, min, max, onSave, disabled, hint }: {
  value: string | null; min?: string; max?: string;
  onSave: (iso: string) => Promise<void>; disabled?: boolean; hint?: string;
}) {
  if (disabled) {
    return (
      <span className="px-1.5 font-mono text-[11px] text-muted-foreground"
        title={hint}>{hint ?? "—"}</span>
    );
  }
  return (
    <input type="date" value={value ?? ""} min={min} max={max}
      onChange={(e) => { if (e.target.value) onSave(e.target.value); }}
      className={cn(CELL, "font-mono text-xs tabular-nums",
        !value && "text-muted-foreground")} />
  );
}

/**
 * The status cell.
 *
 * Two facts share it and must never be conflated: what the lesson logs OBSERVED
 * and what a human STATED. The dropdown writes the second; "From the logs"
 * clears it and hands the row back to the first. When a claim is standing, the
 * derived word is printed under it — so "Completed · logs: not started" is
 * legible as the disagreement it is, rather than the app silently preferring
 * one and hiding the other.
 */
function StatusCell({ row, onSave }: {
  row: SyllabusChapterRow; onSave: (p: ChapterPatch) => Promise<void>;
}) {
  // Out of scope outranks everything (the server enforces it too) — offering a
  // status for a chapter the school has dropped would invite a claim that
  // cannot take effect.
  if (row.not_planned) {
    return (
      <button type="button"
        onClick={() => onSave({ not_planned: false })}
        title="Put this chapter back in scope"
        className={cn("h-8 w-full rounded-md border px-2 text-left text-xs",
          STATUS_TONE.not_scheduled)}>
        Not planned
      </button>
    );
  }

  const stated = row.manual_status != null;
  return (
    <div className="min-w-0">
      <select value={row.manual_status ?? ""}
        onChange={(e) => onSave({
          status: (e.target.value || "unset") as ChapterStatus | "unset",
        })}
        aria-label={`Status of ${row.title}`}
        className={cn(
          "h-8 w-full rounded-md border px-1.5 text-xs transition-colors",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          STATUS_TONE[row.status])}>
        {/* The derived word is the default option, and it NAMES itself — an
            empty option would read as "no status" when it means "whatever the
            record says". */}
        <option value="">From logs · {STATUS_LABEL[row.derived_status]}</option>
        {TYPEABLE.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </select>
      {stated && row.manual_status !== row.derived_status ? (
        <p className="mt-0.5 truncate px-0.5 font-mono text-[10px] text-muted-foreground"
          title="You set this. The lesson logs say something else.">
          stated · logs: {STATUS_LABEL[row.derived_status].toLowerCase()}
        </p>
      ) : null}
    </div>
  );
}

// ── the add row ──────────────────────────────────────────────────────────────
function AddChapterRow({ csId, terms, onAdded }: {
  csId: string; terms: { id: string; name: string }[]; onAdded: () => void;
}) {
  const [title, setTitle] = useState("");
  const [termId, setTermId] = useState("");

  const add = useMutation({
    mutationFn: async () => {
      const unit = await schoolApi.addUnit({
        class_subject_id: csId, title: title.trim(), term_id: termId || null,
      });
      // A chapter with no topic can never be scheduled or sized, and the
      // importer's shape is one topic mirroring its chapter — so the row the
      // grid draws is complete the moment she presses Enter, rather than
      // arriving unsizable and needing a second, invisible step.
      await schoolApi.addTopic({ unit_id: unit.id, title: title.trim() });
      return unit;
    },
    onSuccess: () => { setTitle(""); onAdded(); toast.success("Chapter added"); },
    onError: (e) => showApiError(e, "Could not add the chapter"),
  });

  return (
    <form className="flex flex-wrap items-center gap-2 border-t border-border px-3 py-2"
      onSubmit={(e) => { e.preventDefault(); if (title.trim()) add.mutate(); }}>
      <Plus className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      <Input className="h-8 max-w-md" placeholder="Add a chapter — its name"
        value={title} onChange={(e) => setTitle(e.target.value)} />
      {terms.length ? (
        <select value={termId} onChange={(e) => setTermId(e.target.value)}
          aria-label="Term for the new chapter"
          className="h-8 rounded-md border border-border bg-card px-2 text-xs">
          <option value="">No term</option>
          {terms.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      ) : null}
      <Button size="sm" type="submit" disabled={!title.trim() || add.isPending}>
        {add.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Add"}
      </Button>
      <span className="text-[11px] text-muted-foreground">
        It starts unsized and unscheduled — that is a state, not a gap.
      </span>
    </form>
  );
}

/**
 * The subject's mentor, and its weekly load READ OUT (TT-3).
 *
 * Mentor is editable here: it is the tracker spreadsheet's own column, it is
 * per subject rather than per chapter, and the person noticing "nobody owns
 * this" is the person looking at this header.
 *
 * Periods a week is NOT editable, here or anywhere. It is counted off the
 * timetable (`services/period_load.py`) and recomputed on every grid change,
 * because a school does not know in April what June's timetable will give
 * Class 5 English — the founder's point, and the reason the column was blank
 * or wrong for every school that filled in the setup pack.
 *
 * It still has to be VISIBLE, because it is the reason the Planned cells below
 * are live or inert, and "0 /wk" with no explanation is the most confusing
 * possible state. So it reads as a fact with a link to where it comes from.
 */
function SubjectHead({ subject, canEdit, onSaved }: {
  subject: SyllabusSubjectGroup; canEdit: boolean; onSaved: () => void;
}) {
  const { data: members } = useQuery({
    queryKey: ["members"], queryFn: appApi.members, enabled: canEdit,
  });
  const staff = (members?.members ?? []).filter(
    (mm) => mm.member_id && !(mm.email ?? "").endsWith("@trackbit.app"));
  const current = staff.find((mm) => mm.name === subject.teacher_name);

  const save = useMutation({
    mutationFn: (b: { teacher_member_id?: string | null }) =>
      schoolApi.updateClassSubject(subject.class_subject_id, b),
    onSuccess: () => { onSaved(); toast.success("Mentor updated"); },
    onError: (e) => showApiError(e, "Could not update the subject"),
  });

  return (
    <>
      {canEdit ? (
        <select
          value={current?.member_id ?? ""}
          aria-label={`Mentor for ${subject.subject_name}`}
          onChange={(e) => save.mutate({ teacher_member_id: e.target.value || null })}
          className={cn(
            "h-7 rounded-md border bg-card px-1.5 text-xs",
            subject.teacher_name
              ? "border-border" : "border-dashed border-warning text-warning")}>
          <option value="">no mentor assigned</option>
          {staff.map((mm) => (
            <option key={mm.member_id!} value={mm.member_id!}>{mm.name}</option>
          ))}
        </select>
      ) : (
        <span className="font-mono text-[11px] text-muted-foreground">
          {subject.teacher_name ?? "no mentor assigned"}
        </span>
      )}

      {subject.periods_per_week ? (
        <Link href="/plan/timetable"
          title="Counted from the timetable — open the grid to change it"
          className="font-mono text-[11px] text-muted-foreground hover:text-foreground hover:underline">
          {subject.periods_per_week}/wk from the timetable
        </Link>
      ) : (
        // Never a bare "0": the school has not drawn this subject into the
        // grid, which is a state of the setup, not a weekly load of zero.
        <Link href="/plan/timetable"
          className="inline-flex items-center gap-1 rounded-md border border-dashed border-warning px-1.5 py-0.5 font-mono text-[11px] text-warning hover:bg-warning-soft/40">
          <CalendarClock className="h-3 w-3" /> not on the timetable yet
        </Link>
      )}
    </>
  );
}

function ColHead({ children, className }: {
  children?: React.ReactNode; className?: string;
}) {
  return (
    <div className={cn(
      "font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground",
      className)}>
      {children}
    </div>
  );
}

// ── the grid ─────────────────────────────────────────────────────────────────
export function SyllabusGrid({ csId, board, canEdit, onChanged, yearStart, yearEnd }: {
  csId: string;
  board: SyllabusBoard;
  canEdit: boolean;
  onChanged: () => void;
  yearStart?: string;
  yearEnd?: string;
}) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<string | null>(null);

  const subject: SyllabusSubjectGroup | undefined =
    board.classes.flatMap((g) => g.subjects).find((s) => s.class_subject_id === csId);
  const rows = subject?.chapters ?? [];

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["syllabus-board"] });
    qc.invalidateQueries({ queryKey: ["forecast"] });
    qc.invalidateQueries({ queryKey: ["exam-map"] });
    onChanged();
  };

  const patch = async (unitId: string, body: ChapterPatch) => {
    if (!Object.keys(body).length) return;
    setBusy(unitId);
    try {
      await schoolApi.patchChapter(unitId, body);
      refresh();
    } catch (e) {
      // Put the server's value back rather than leaving a rejected number in
      // the cell — a grid that keeps what the database refused is lying.
      showApiError(e, "Could not save that");
      refresh();
    } finally { setBusy(null); }
  };

  /**
   * One end of the planned window moved.
   *
   * Both ends always go to the planner together, because `reschedule` takes a
   * RANGE — sending only the end a person touched would silently reset the
   * other. A chapter with no window yet is given a one-week one from the date
   * she picked, which is the smallest honest interpretation of dropping a date
   * onto an unscheduled chapter.
   */
  const setWindow = async (row: SyllabusChapterRow, which: "start" | "end",
    iso: string) => {
    const weekAfter = (from: string) => dayKey(new Date(
      new Date(`${from}T00:00:00`).getTime() + 6 * 86_400_000));
    let start = which === "start" ? iso : (row.planned_start ?? iso);
    let end = which === "end" ? iso : (row.planned_end ?? weekAfter(iso));
    // A range that ends before it starts is a slip of the finger, not a
    // request. Carry the other end with it instead of posting a 422.
    if (end < start) { if (which === "start") end = start; else start = end; }

    setBusy(row.unit_id);
    try {
      const res = await schoolApi.reschedulePlan(csId, [{
        unit_id: row.unit_id, start_date: start, end_date: end,
      }]);
      refresh();
      // V2-P5: a range too small for what she put in it is REPORTED and still
      // saved. She is the one who knows whether she can go faster.
      for (const v of res.violations ?? []) toast.warning(v.message);
    } catch (e) {
      showApiError(e, "Could not move the chapter");
      refresh();
    } finally { setBusy(null); }
  };

  const remove = async (row: SyllabusChapterRow) => {
    if (!confirm(`Remove “${row.title}” and everything logged against it?`)) return;
    setBusy(row.unit_id);
    try {
      await schoolApi.deleteUnit(row.unit_id);
      refresh();
      toast.success("Chapter removed");
    } catch (e) {
      showApiError(e, "Could not remove the chapter");
    } finally { setBusy(null); }
  };

  const noPeriods = subject != null && subject.periods_per_week === 0;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      {/* The subject's own line: mentor, load, and how much of it is taught.
          Read from the board, never recomputed here. */}
      {subject ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3 py-2">
          <p className="text-sm font-semibold">
            {subject.class_label} · {subject.subject_name}
          </p>
          <SubjectHead subject={subject} canEdit={canEdit} onSaved={refresh} />
          {subject.coverage_pct != null ? (
            <Badge tone="neutral">{subject.coverage_pct}% of the plan taught</Badge>
          ) : null}
          <span className="ml-auto font-mono text-[11px] text-muted-foreground">
            {rows.length} chapter{rows.length === 1 ? "" : "s"}
          </span>
        </div>
      ) : null}

      {noPeriods ? (
        <p className="border-b border-border bg-warning-soft/40 px-3 py-1.5 text-[11px] text-warning">
          This subject is not on the timetable yet, so it has no weekly period
          count and dates cannot be worked out.{" "}
          <Link href="/plan/timetable" className="underline">Put it on the grid</Link>
          {" "}and every Planned cell below comes alive. Chapters, sizes,
          status and remarks all still record in the meantime.
        </p>
      ) : null}

      <div className="relative">
        {/* Says there is more to the right; without it the row just stops at
            the card edge and reads as a missing column. */}
        <div className="pointer-events-none absolute inset-y-0 right-0 z-20 w-6 bg-gradient-to-l from-card to-transparent" />
        <div className="overflow-x-auto" style={{ contain: "layout inline-size" }}>
          <div className="min-w-[72rem]">
            <div className="grid items-center gap-2 border-b border-border px-3 py-2"
              style={{ gridTemplateColumns: COLS }}>
              <ColHead>#</ColHead>
              <ColHead>Chapter</ColHead>
              <ColHead>Periods</ColHead>
              <ColHead>Difficulty</ColHead>
              <ColHead>Planned from</ColHead>
              <ColHead>Planned to</ColHead>
              <ColHead>Taught</ColHead>
              <ColHead>Status</ColHead>
              <ColHead>Remarks</ColHead>
              <ColHead />
            </div>

            {rows.length ? rows.map((row, i) => (
              <div key={row.unit_id}
                className={cn(
                  "grid items-center gap-2 border-b border-border px-3 py-1 transition-colors last:border-b-0",
                  busy === row.unit_id ? "opacity-60" : "hover:bg-muted/25",
                  row.not_planned && "bg-muted/20")}
                style={{ gridTemplateColumns: COLS }}>
                <span className="font-mono text-xs tabular-nums text-muted-foreground">
                  {i + 1}
                </span>

                {canEdit ? (
                  <TextCell value={row.title} placeholder="Chapter name"
                    onSave={(v) => patch(row.unit_id,
                      // An emptied name is a slip, never a request — a chapter
                      // with no title is unfindable on every other screen.
                      v ? { title: v } : {})} />
                ) : (
                  <span className="truncate px-1.5 text-sm">{row.title}</span>
                )}

                {canEdit ? (
                  <PeriodsCell row={row} onSave={(p) => patch(row.unit_id, p)} />
                ) : (
                  <span className="px-1.5 font-mono text-sm tabular-nums">
                    {row.est_periods ?? (
                      <span className="text-xs text-muted-foreground">not sized</span>
                    )}
                  </span>
                )}

                {canEdit ? (
                  <select value={row.difficulty ?? ""}
                    aria-label={`Difficulty of ${row.title}`}
                    onChange={(e) => patch(row.unit_id, {
                      difficulty: (e.target.value || "unset") as Difficulty | "unset",
                    })}
                    className={cn(CELL, "cursor-pointer")}>
                    {DIFFICULTIES.map((d) => (
                      <option key={d.value} value={d.value}>{d.label}</option>
                    ))}
                  </select>
                ) : (
                  <span className="px-1.5 text-sm capitalize">
                    {row.difficulty ?? "—"}
                  </span>
                )}

                <DateCell value={row.planned_start} min={yearStart} max={yearEnd}
                  disabled={!canEdit || noPeriods || row.est_periods == null}
                  hint={row.est_periods == null ? "size it first"
                    : noPeriods ? "no periods/week" : fmtDay(row.planned_start)}
                  onSave={(iso) => setWindow(row, "start", iso)} />
                <DateCell value={row.planned_end} min={yearStart} max={yearEnd}
                  disabled={!canEdit || noPeriods || row.est_periods == null}
                  hint={row.est_periods == null ? "size it first"
                    : noPeriods ? "no periods/week" : fmtDay(row.planned_end)}
                  onSave={(iso) => setWindow(row, "end", iso)} />

                {/* The record, never editable: this is when it was actually
                    logged. The gap between it and the planned window is the
                    finding, and a writable cell here would erase it. */}
                <span className="px-1.5 font-mono text-[11px] tabular-nums text-muted-foreground">
                  {row.actual_end ? fmtDay(row.actual_end)
                    : row.actual_start ? `${fmtDay(row.actual_start)}→`
                      : <span className="text-muted-foreground/70">not yet</span>}
                  {row.finish_drift_days ? (
                    <span className={row.finish_drift_days > 0
                      ? "ml-1 text-warning" : "ml-1 text-success"}>
                      {row.finish_drift_days > 0
                        ? `+${row.finish_drift_days}d` : `${row.finish_drift_days}d`}
                    </span>
                  ) : null}
                </span>

                {canEdit ? (
                  <StatusCell row={row} onSave={(p) => patch(row.unit_id, p)} />
                ) : (
                  <span className="px-1.5 text-xs">{STATUS_LABEL[row.status]}</span>
                )}

                {canEdit ? (
                  <TextCell value={row.remarks ?? ""} placeholder="Add a remark"
                    onSave={(v) => patch(row.unit_id, { remarks: v })} />
                ) : (
                  <span className="truncate px-1.5 text-xs text-muted-foreground">
                    {row.remarks || "—"}
                  </span>
                )}

                {canEdit ? (
                  <button type="button" onClick={() => remove(row)}
                    aria-label={`Remove ${row.title}`}
                    className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-danger-soft hover:text-danger">
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                ) : <span />}
              </div>
            )) : (
              <p className="px-3 py-10 text-center text-sm text-muted-foreground">
                No chapters in this subject yet.
                {canEdit ? " Add the first one below." : ""}
              </p>
            )}
          </div>
        </div>
      </div>

      {canEdit ? (
        <AddChapterRow csId={csId}
          terms={board.terms.map((t) => ({ id: t.id, name: t.name }))}
          onAdded={refresh} />
      ) : null}
    </div>
  );
}
