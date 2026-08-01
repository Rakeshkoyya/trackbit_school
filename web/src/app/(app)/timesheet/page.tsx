"use client";

// My time — the teacher's timesheet, at three altitudes (`D-18`/`S-64`).
//
//   **Month = shape · Week = edit · Day = do.** Three jobs, not three renderings
//   of one grid: a month of 8 periods × 25 days is 200 cells and unfillable on a
//   phone, so the month is one cell per DAY and works as a navigator.
//
// Half the grid is already filled: the timetable knows every period they teach,
// and those cells are locked because the grid owns them. The teacher fills in
// the gaps — notebook checking, exam work, an event, a student — and the school
// finally knows what its staff do with the time between classes.
//
// Tapping a free cell opens the picker, **pre-selected on what she usually
// records in that slot** (`S-75`) — one tap instead of two, and nothing is
// written until she saves, so no row exists that a human did not put there.
//
// `S-70`: the counters are hers, not the principal's — "27 taught · 6 recorded ·
// 3 covered · 4 evenings" is a record she can point at when she is asked to take
// a fourth cover this week. There is no completeness score here and never will
// be (`D-23`/`S-67`), and nothing on this screen reaches pay (`D-25`).
//
// Everything stays editable all day: a plan you cannot fix at 3pm is a plan
// nobody writes at 8am.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen, ChevronLeft, ChevronRight, Loader2, Moon, Plus, Trash2,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { TimesheetDay, TimesheetSlot } from "@/lib/school-types";

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

const iso = (d: Date) => d.toISOString().slice(0, 10);

function mondayOf(d: Date): string {
  const copy = new Date(d);
  copy.setDate(copy.getDate() - ((copy.getDay() + 6) % 7));
  return iso(copy);
}

function shiftWeek(weekStart: string, weeks: number): string {
  const d = new Date(`${weekStart}T00:00:00`);
  d.setDate(d.getDate() + weeks * 7);
  return iso(d);
}

function weekLabel(weekStart: string): string {
  const start = new Date(`${weekStart}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 5);
  const f = (d: Date) => d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
  return `${f(start)} – ${f(end)}`;
}

function shiftDays(dateStr: string, days: number): string {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setDate(d.getDate() + days);
  return iso(d);
}

function dayLabel(dateStr: string): string {
  if (dateStr === iso(new Date())) return "Today";
  return new Date(`${dateStr}T00:00:00`).toLocaleDateString("en-IN", {
    weekday: "short", day: "numeric", month: "short" });
}

/** Month arithmetic on the YYYY-MM string, so a 31st never rolls into March. */
function shiftMonth(month: string, by: number): string {
  const [y, m] = month.split("-").map(Number);
  const total = y * 12 + (m - 1) + by;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

function monthLabel(month: string): string {
  return new Date(`${month}-01T00:00:00`).toLocaleDateString("en-IN", {
    month: "long", year: "numeric" });
}

type CellTarget = { date: string; period_no: number; slot: TimesheetSlot };

function WorkSheet({ target, onClose }: { target: CellTarget | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [type, setType] = useState<string | null>(null);
  const [custom, setCustom] = useState("");
  const [note, setNote] = useState("");

  const { data: types = [] } = useQuery({ queryKey: ["work-types"], queryFn: schoolApi.workTypes });

  // Seed from the existing entry when a recorded cell is reopened, and from
  // S-75's suggestion when a free one is — the picker opens on what she usually
  // records here. Still nothing written: `save` is the only writer.
  const effType = type ?? target?.slot.work_type ?? target?.slot.suggested_work_type ?? null;
  const effNote = note || (target?.slot.note ?? "");
  const isSuggested = !type && !target?.slot.work_type && !!target?.slot.suggested_work_type;

  const done = () => {
    qc.invalidateQueries({ queryKey: ["timesheet"] });
    qc.invalidateQueries({ queryKey: ["staff-today"] });
    setType(null); setCustom(""); setNote("");
    onClose();
  };

  const save = useMutation({
    mutationFn: () => schoolApi.setTimesheetEntry({
      date: target!.date, period_no: target!.period_no,
      work_type: effType === "other" && custom.trim() ? custom.trim() : (effType ?? "other"),
      note: effNote.trim() || null,
    }),
    onSuccess: () => { toast.success("Saved to your timesheet"); done(); },
    onError: (e) => showApiError(e, "Could not save"),
  });

  const clear = useMutation({
    mutationFn: () => schoolApi.clearTimesheetEntry({
      on_date: target!.date, period_no: target!.period_no }),
    onSuccess: () => { toast.success("Cleared"); done(); },
    onError: (e) => showApiError(e, "Could not clear"),
  });

  const label = target
    ? `${DAY_NAMES[new Date(`${target.date}T00:00:00`).getDay() === 0 ? 6 : new Date(`${target.date}T00:00:00`).getDay() - 1]} · Period ${target.period_no}`
    : "";

  return (
    <Sheet open={!!target} onOpenChange={(v) => { if (!v) { setType(null); setCustom(""); setNote(""); onClose(); } }}
      title="What is this period for?">
      {target ? (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {label}
            {target.slot.start ? ` · ${target.slot.start}–${target.slot.end}` : ""}
          </p>

          {isSuggested ? (
            <p className="text-xs text-muted-foreground">
              Pre-selected from what you usually do in this slot — nothing is saved
              until you tap Save.
            </p>
          ) : null}

          <div className="grid grid-cols-2 gap-1.5">
            {types.map((t) => {
              const active = effType === t.key;
              return (
                <button key={t.key} type="button" onClick={() => setType(t.key)}
                  aria-pressed={active}
                  className={`rounded-lg border px-3 py-2.5 text-left text-sm transition-colors active:scale-[0.99] ${active ? "border-primary bg-accent text-accent-foreground" : "border-border bg-card hover:bg-muted/50"}`}>
                  {t.label}
                </button>
              );
            })}
          </div>

          {effType === "other" ? (
            <div>
              <Label htmlFor="ts-custom">Name the work</Label>
              <Input id="ts-custom" autoFocus value={custom}
                onChange={(e) => setCustom(e.target.value)}
                placeholder="e.g. Sports duty" />
            </div>
          ) : null}

          <div>
            <Label htmlFor="ts-note">Note (optional)</Label>
            <Input id="ts-note" value={effNote} onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. 6-A science books" />
          </div>

          <Button className="w-full" disabled={!effType || save.isPending}
            onClick={() => save.mutate()}>
            {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Save
          </Button>
          {target.slot.kind === "work" ? (
            <Button className="w-full" variant="ghost" disabled={clear.isPending}
              onClick={() => clear.mutate()}>
              <Trash2 className="h-4 w-4" /> Clear this period
            </Button>
          ) : null}
        </div>
      ) : null}
    </Sheet>
  );
}

function cellClass(kind: TimesheetSlot["kind"]): string {
  if (kind === "class") return "bg-[color:var(--success,#234a37)]/12 text-foreground cursor-default";
  if (kind === "cover") return "bg-primary/10 text-foreground cursor-default";
  if (kind === "work") return "bg-muted text-foreground hover:bg-muted/70";
  return "bg-background text-muted-foreground/50 hover:bg-muted/40";
}

function Cell({ day, slot, onPick }: {
  day: TimesheetDay; slot: TimesheetSlot; onPick: (t: CellTarget) => void;
}) {
  // Q-37: a period she covered for a colleague is her record too — read-only,
  // like a teaching period. Before this, covering three periods showed three
  // free cells on her own grid.
  const locked = slot.kind === "class" || slot.kind === "cover";
  return (
    <button type="button" disabled={locked}
      onClick={() => onPick({ date: day.date, period_no: slot.period_no, slot })}
      title={locked ? `${slot.class_label} · ${slot.subject_name}` : slot.note ?? undefined}
      className={`h-full w-full rounded-md border border-border px-1.5 py-2 text-left text-[11px] leading-tight transition-colors ${cellClass(slot.kind)}`}>
      {slot.kind === "class" || slot.kind === "cover" ? (
        <>
          <span className="block truncate font-medium">{slot.subject_name}</span>
          <span className="block truncate opacity-70">
            {slot.kind === "cover" ? `⟳ ${slot.class_label} · cover` : slot.class_label}
          </span>
        </>
      ) : slot.kind === "work" ? (
        <>
          <span className="block truncate font-medium">{slot.work_label}</span>
          {slot.note ? <span className="block truncate opacity-70">{slot.note}</span> : null}
        </>
      ) : (
        <span className="block text-center opacity-60">+</span>
      )}
    </button>
  );
}

/** The day view (D-18) — a vertical timeline including the breaks, which is the
 *  surface people actually fill in as the day goes. */
function DayView({ date, onPick }: { date: string; onPick: (t: CellTarget) => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["timesheet", "day", date],
    queryFn: () => schoolApi.timesheetDay({ on_date: date }),
  });

  if (isLoading || !data) {
    return <div className="h-72 animate-pulse rounded-xl border border-border bg-card" />;
  }
  if (!data.slots.length) {
    return (
      <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
        Your school hasn’t set its timings yet, so there are no periods to fill in.
      </p>
    );
  }

  // Breaks belong between the periods they follow — the day is a timeline, not
  // a list of teaching slots with the gaps deleted.
  const breaksAfter = new Map<number, typeof data.breaks>();
  for (const b of data.breaks) {
    breaksAfter.set(b.after_period_no, [...(breaksAfter.get(b.after_period_no) ?? []), b]);
  }

  return (
    <div className="space-y-1.5">
      {(breaksAfter.get(0) ?? []).map((b) => <BreakRow key={`b0-${b.start}`} label={b.label} start={b.start} end={b.end} />)}
      {data.slots.map((slot) => (
        <div key={slot.period_no}>
          <button type="button"
            disabled={slot.kind === "class" || slot.kind === "cover" || slot.kind === "away"}
            onClick={() => onPick({ date, period_no: slot.period_no, slot })}
            className={`flex w-full items-center gap-3 rounded-lg border px-3 py-3 text-left ${slot.kind === "free" ? "border-dashed border-border bg-background hover:bg-muted/40" : "border-border bg-card"}`}>
            <span className="w-16 shrink-0 text-xs text-muted-foreground">
              <span className="block font-medium text-foreground">P{slot.period_no}</span>
              {slot.start ? <span className="block">{slot.start}</span> : null}
            </span>
            <span className="min-w-0 flex-1">
              {slot.kind === "class" || slot.kind === "cover" ? (
                <>
                  <span className="block truncate text-sm font-medium">{slot.subject_name}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {slot.kind === "cover" ? `⟳ ${slot.class_label} · covering` : slot.class_label}
                  </span>
                </>
              ) : slot.kind === "work" ? (
                <>
                  <span className="block truncate text-sm font-medium">{slot.work_label}</span>
                  {slot.note ? (
                    <span className="block truncate text-xs text-muted-foreground">{slot.note}</span>
                  ) : null}
                </>
              ) : slot.kind === "away" ? (
                <span className="text-sm text-muted-foreground">{slot.note ?? "Away"}</span>
              ) : (
                <span className="text-sm text-muted-foreground">
                  Free{slot.suggested_work_label ? ` · usually ${slot.suggested_work_label}` : ""}
                </span>
              )}
            </span>
            {slot.kind === "free" ? (
              <Plus className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : null}
          </button>
          {(breaksAfter.get(slot.period_no) ?? []).map((b) => (
            <BreakRow key={`b${slot.period_no}-${b.start}`} label={b.label} start={b.start} end={b.end} />
          ))}
        </div>
      ))}

      {/* S-68 — the evening is hers too, and it is read-only here. */}
      {data.evening_labels.length ? (
        <div className="rounded-lg border border-border bg-muted/30 px-3 py-2.5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            This evening
          </p>
          {data.evening_labels.map((label) => (
            <p key={label} className="mt-0.5 text-sm">{label}</p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function BreakRow({ label, start, end }: { label: string; start: string; end: string }) {
  return (
    <p className="my-1 flex items-center gap-3 px-3 text-xs text-muted-foreground">
      <span className="w-16 shrink-0">{start}</span>
      <span className="h-px flex-1 bg-border" />
      <span>{label}{end ? ` · ends ${end}` : ""}</span>
    </p>
  );
}

const MONTH_STATE: Record<string, string> = {
  working: "bg-card",
  future: "bg-card opacity-60",
  off: "bg-muted/40 text-muted-foreground",
  holiday: "bg-muted/40 text-muted-foreground",
  leave: "bg-warning-soft text-warning",
  away: "bg-warning-soft text-warning",
};

/** The month (D-18/S-64) — one cell per DAY, carrying the day's state. A
 *  navigator, not an editor: tapping a day opens it. Holidays and leave come
 *  from the calendar, so a closed school never reads as a month of holes. */
function MonthView({ month, onOpenDay }: { month: string; onOpenDay: (d: string) => void }) {
  const { data, isLoading } = useQuery({
    queryKey: ["timesheet", "month", month],
    queryFn: () => schoolApi.timesheetMonth({ month }),
  });

  if (isLoading || !data) {
    return <div className="h-72 animate-pulse rounded-xl border border-border bg-card" />;
  }
  // Pad to the first cell's weekday so the columns line up under Mon…Sun.
  const pad = data.days.length ? data.days[0].weekday : 0;

  return (
    <>
      <div className="rounded-xl border border-border bg-card p-2">
        <div className="grid grid-cols-7 gap-1">
          {DAY_NAMES.map((n) => (
            <div key={n} className="pb-1 text-center text-[10px] font-semibold uppercase text-muted-foreground">
              {n}
            </div>
          ))}
          {Array.from({ length: pad }, (_, i) => <div key={`pad${i}`} />)}
          {data.days.map((d) => {
            const busy = d.teaching + d.work + d.cover;
            const total = Math.max(1, busy + d.free);
            return (
              <button key={d.date} type="button" onClick={() => onOpenDay(d.date)}
                title={d.label ?? undefined}
                className={`rounded-md border border-border px-1 pb-1.5 pt-1 text-left ${MONTH_STATE[d.state] ?? "bg-card"}`}>
                <span className="block text-[11px] font-medium">
                  {new Date(`${d.date}T00:00:00`).getDate()}
                </span>
                {d.state === "working" || d.state === "future" ? (
                  <span className="mt-1 block h-1 w-full overflow-hidden rounded-full bg-muted">
                    <span className="block h-full rounded-full bg-[color:var(--chart-green)]"
                      style={{ width: `${(busy / total) * 100}%` }} />
                  </span>
                ) : (
                  <span className="mt-0.5 block truncate text-[9px] leading-tight">
                    {d.state === "off" ? "—" : d.state === "holiday" ? "holiday" : "leave"}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <Badge tone="success"><BookOpen className="h-3 w-3" /> {data.teaching_periods} taught</Badge>
        <Badge tone="neutral">{data.work_periods} recorded</Badge>
        {data.covered_periods ? <Badge tone="outline">{data.covered_periods} covered for others</Badge> : null}
        {data.evening_sessions ? <Badge tone="outline">{data.evening_sessions} evenings</Badge> : null}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Tap a day to open it. Holidays and leave come from the school calendar — they are
        closed days, not gaps in your record.
      </p>
    </>
  );
}

type View = "day" | "week" | "month";

function TimesheetInner() {
  const [view, setView] = useState<View>("week");
  const [week, setWeek] = useState(() => mondayOf(new Date()));
  const [day, setDay] = useState(() => iso(new Date()));
  const [month, setMonth] = useState(() => iso(new Date()).slice(0, 7));
  const [target, setTarget] = useState<CellTarget | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["timesheet", "week", week],
    queryFn: () => schoolApi.timesheetWeek({ week_start: week }),
    enabled: view === "week",
  });

  const days = data?.days ?? [];
  const periods = days[0]?.slots.map((s) => s.period_no) ?? [];
  const today = iso(new Date());

  return (
    <div className="pb-8">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="My time"
          subtitle="Your classes are already here. Fill in what the free periods are for." />
        <div className="flex rounded-lg border border-border bg-card p-1">
          {(["day", "week", "month"] as const).map((v) => (
            <button key={v} type="button" onClick={() => setView(v)} aria-pressed={view === v}
              className={`rounded-md px-3 py-1 text-sm font-medium capitalize transition-colors ${view === v ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"}`}>
              {v}
            </button>
          ))}
        </div>
      </div>

      {/* One stepper, three units — the arrows always move the thing on screen. */}
      <div className="mb-4 flex items-center gap-1 rounded-lg border border-border bg-card p-1 w-fit">
        <Button size="sm" variant="ghost" aria-label="Previous"
          onClick={() => {
            if (view === "week") setWeek(shiftWeek(week, -1));
            else if (view === "day") setDay(shiftDays(day, -1));
            else setMonth(shiftMonth(month, -1));
          }}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="min-w-[9.5rem] text-center text-sm font-medium">
          {view === "week" ? weekLabel(week)
            : view === "day" ? dayLabel(day)
              : monthLabel(month)}
        </span>
        <Button size="sm" variant="ghost" aria-label="Next"
          onClick={() => {
            if (view === "week") setWeek(shiftWeek(week, 1));
            else if (view === "day") setDay(shiftDays(day, 1));
            else setMonth(shiftMonth(month, 1));
          }}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {view === "day" ? (
        <DayView date={day} onPick={setTarget} />
      ) : view === "month" ? (
        <MonthView month={month} onOpenDay={(d) => { setDay(d); setView("day"); }} />
      ) : isLoading || !data ? (
        <div className="h-72 animate-pulse rounded-xl border border-border bg-card" />
      ) : periods.length === 0 ? (
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          Your school hasn’t set its timings yet, so there are no periods to fill in. An admin can
          add them in Plan → Timetable.
        </p>
      ) : (
        <>
          {/* S-70 — her numbers, in her words. No completeness score (D-23). */}
          <div className="mb-4 flex flex-wrap gap-2">
            <Badge tone="success"><BookOpen className="h-3 w-3" /> {data.teaching_periods} taught</Badge>
            <Badge tone="neutral">{data.work_periods} recorded</Badge>
            {data.covered_periods ? (
              <Badge tone="outline">{data.covered_periods} covered for colleagues</Badge>
            ) : null}
            {data.evening_sessions ? (
              <Badge tone="outline"><Moon className="h-3 w-3" /> {data.evening_sessions} evenings</Badge>
            ) : null}
            <Badge tone="outline">{data.free_periods} still open</Badge>
          </div>

          {/* Wide content scrolls in its own container; the page never does. */}
          <div className="overflow-x-auto rounded-xl border border-border bg-card p-2">
            <div className="min-w-[38rem]">
              <div className="grid gap-1"
                style={{ gridTemplateColumns: `3.25rem repeat(${days.length}, minmax(0, 1fr))` }}>
                <div />
                {days.map((d) => (
                  <button key={d.date} type="button"
                    onClick={() => { setDay(d.date); setView("day"); }}
                    className={`px-1 pb-1 text-center text-xs font-semibold ${d.date === today ? "text-foreground" : "text-muted-foreground"}`}>
                    {DAY_NAMES[d.weekday]}
                    <span className="block text-[10px] font-normal opacity-70">
                      {new Date(`${d.date}T00:00:00`).getDate()}
                    </span>
                  </button>
                ))}

                {periods.map((p) => (
                  <FragmentRow key={p} periodNo={p} days={days} onPick={setTarget} />
                ))}
              </div>
            </div>
          </div>

          <p className="mt-2 text-xs text-muted-foreground">
            Tap any open period to say what it is for. Classes come from the timetable and can’t be
            changed here.
          </p>
        </>
      )}

      <WorkSheet target={target} onClose={() => setTarget(null)} />
    </div>
  );
}

/** One period across the week — kept as its own component so the grid stays a
 *  flat CSS grid rather than nested rows that break column alignment. */
function FragmentRow({ periodNo, days, onPick }: {
  periodNo: number; days: TimesheetDay[]; onPick: (t: CellTarget) => void;
}) {
  const first = days[0]?.slots.find((s) => s.period_no === periodNo);
  return (
    <>
      <div className="flex flex-col justify-center py-1 pr-1 text-right">
        <span className="text-xs font-medium text-muted-foreground">P{periodNo}</span>
        {first?.start ? (
          <span className="text-[10px] text-muted-foreground/70">{first.start}</span>
        ) : null}
      </div>
      {days.map((d) => {
        const slot = d.slots.find((s) => s.period_no === periodNo);
        if (!slot) return <div key={d.date} />;
        return <Cell key={d.date} day={d} slot={slot} onPick={onPick} />;
      })}
    </>
  );
}

export default function TimesheetPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <TimesheetInner />
    </AuthGuard>
  );
}
