"use client";

// My week — the teacher's timesheet.
//
// Half the grid is already filled: the timetable knows every period they teach,
// and those cells are locked because the grid owns them. The teacher fills in
// the gaps — notebook checking, exam work, an event, a student — and the school
// finally knows what its staff do with the time between classes.
//
// Tapping a free cell opens the picker. Everything stays editable all day: a
// plan you cannot fix at 3pm is a plan nobody writes at 8am.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen, ChevronLeft, ChevronRight, Loader2, Trash2,
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

type CellTarget = { date: string; period_no: number; slot: TimesheetSlot };

function WorkSheet({ target, onClose }: { target: CellTarget | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [type, setType] = useState<string | null>(null);
  const [custom, setCustom] = useState("");
  const [note, setNote] = useState("");

  const { data: types = [] } = useQuery({ queryKey: ["work-types"], queryFn: schoolApi.workTypes });

  // Seed from the existing entry when a recorded cell is reopened.
  const effType = type ?? target?.slot.work_type ?? null;
  const effNote = note || (target?.slot.note ?? "");

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

function TimesheetInner() {
  const [week, setWeek] = useState(() => mondayOf(new Date()));
  const [target, setTarget] = useState<CellTarget | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["timesheet", "week", week],
    queryFn: () => schoolApi.timesheetWeek({ week_start: week }),
  });

  const days = data?.days ?? [];
  const periods = days[0]?.slots.map((s) => s.period_no) ?? [];
  const today = iso(new Date());

  return (
    <div className="pb-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="My week"
          subtitle="Your classes are already here. Fill in what the free periods are for." />
        <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
          <Button size="sm" variant="ghost" onClick={() => setWeek(shiftWeek(week, -1))}
            aria-label="Previous week">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-[8.5rem] text-center text-sm font-medium">{weekLabel(week)}</span>
          <Button size="sm" variant="ghost" onClick={() => setWeek(shiftWeek(week, 1))}
            aria-label="Next week">
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isLoading || !data ? (
        <div className="h-72 animate-pulse rounded-xl border border-border bg-card" />
      ) : periods.length === 0 ? (
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          Your school hasn’t set its timings yet, so there are no periods to fill in. An admin can
          add them in Plan → Timetable.
        </p>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-2">
            <Badge tone="success"><BookOpen className="h-3 w-3" /> {data.teaching_periods} teaching</Badge>
            <Badge tone="neutral">{data.work_periods} recorded</Badge>
            <Badge tone="outline">{data.free_periods} still open</Badge>
          </div>

          {/* Wide content scrolls in its own container; the page never does. */}
          <div className="overflow-x-auto rounded-xl border border-border bg-card p-2">
            <div className="min-w-[38rem]">
              <div className="grid gap-1"
                style={{ gridTemplateColumns: `3.25rem repeat(${days.length}, minmax(0, 1fr))` }}>
                <div />
                {days.map((d) => (
                  <div key={d.date}
                    className={`px-1 pb-1 text-center text-xs font-semibold ${d.date === today ? "text-foreground" : "text-muted-foreground"}`}>
                    {DAY_NAMES[d.weekday]}
                    <span className="block text-[10px] font-normal opacity-70">
                      {new Date(`${d.date}T00:00:00`).getDate()}
                    </span>
                  </div>
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
