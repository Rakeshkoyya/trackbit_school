"use client";

// V1-7 — the suggestion feed and the **Approve this date** sheet (`D-57`/`D-58`).
//
// This sheet *is* the module. Three things are true of it and none of them are
// decoration:
//
//   1. **The date is editable**, pre-filled from the suggestion (`D-79`). A
//      suggestion is never a date, it is a prompt to pick one — which is what
//      removes the wrong-date risk structurally instead of accepting it, and
//      what lets Christmas the *holiday* (25 Dec, closed) and the Christmas
//      *celebration* (22 Dec, open) be two approvals from one row.
//   2. **The open/closed choice is the central act** (`D-58`), not a checkbox
//      further down. This is also the fix for the module's live defect: painting
//      a Celebration used to silently remove a teaching day from every forecast
//      in the school, because `affects_teaching` defaulted true and the UI never
//      sent it.
//   3. **The cost is shown before they commit** (`S-143`). `effective_periods`
//      is computed live, so locking three days for Diwali moves RAG colours
//      across the school the instant the row is written. A principal who is not
//      told concludes the product is broken.
//
// Dismissal is permanent and append-only (`S-148`) — hence the confirm wording.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Info, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import {
  eventsApi,
  type CalendarEventKind,
  type LockLevel,
  type Suggestion,
} from "@/lib/events-api";
import { cn } from "@/lib/utils";

const fmt = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
    weekday: "short", day: "numeric", month: "short",
  });

const LOCKS: { value: LockLevel; label: string; hint: string }[] = [
  { value: "closed", label: "School closed", hint: "The whole day leaves every plan's capacity." },
  { value: "periods", label: "Some periods", hint: "Only the periods you name are lost." },
  { value: "open", label: "Runs as usual", hint: "Marked on the calendar. Nothing is lost." },
];

const TYPES: { value: CalendarEventKind; label: string }[] = [
  { value: "holiday", label: "Holiday" },
  { value: "celebration", label: "Celebration" },
  { value: "event", label: "Event" },
  { value: "exam_block", label: "Exam" },
];

function Pills<T extends string>({
  value, onChange, options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: string }[];
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cn(
            "rounded-full border px-3 py-1.5 text-xs transition-colors",
            value === o.value
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-card hover:bg-muted",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/** The form body. Kept separate and mounted with `key={suggestion.id}` so its
 *  state is *initialised* from the suggestion rather than synced to it in an
 *  effect — the admin's edits must survive a re-render, and a fresh row must
 *  start from its own date, not the previous one's. */
function ApproveForm({
  suggestion, yearId, periodsPerDay, onClose,
}: {
  suggestion: Suggestion;
  yearId: string;
  periodsPerDay: number;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const isHoliday = suggestion.kind === "holiday";
  const [title, setTitle] = useState(suggestion.name);
  const [start, setStart] = useState(suggestion.date);
  const [end, setEnd] = useState(suggestion.end_date ?? "");
  const [lock, setLock] = useState<LockLevel>(isHoliday ? "closed" : "open");
  const [periods, setPeriods] = useState<number[]>([]);
  const [type, setType] = useState<CalendarEventKind>(
    isHoliday ? "holiday" : "celebration");

  // `S-143` — priced on every change of the three inputs that can change it.
  const { data: cost, isFetching: pricing } = useQuery({
    queryKey: ["lock-cost", yearId, start, end, lock, periods.join(",")],
    queryFn: () => eventsApi.cost({
      academic_year_id: yearId, start_date: start, end_date: end || null,
      lock, blocks_periods: lock === "periods" ? periods : null,
    }),
    enabled: !!start && (lock !== "periods" || periods.length > 0),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["calendar"] });
    qc.invalidateQueries({ queryKey: ["suggestions"] });
    qc.invalidateQueries({ queryKey: ["whats-on"] });
    qc.invalidateQueries({ queryKey: ["exam-fit"] });
    qc.invalidateQueries({ queryKey: ["school-overview"] });
  };

  const approve = useMutation({
    mutationFn: () => eventsApi.approve(suggestion.id, {
      title: title.trim() || suggestion.name,
      start_date: start, end_date: end || null, lock,
      blocks_periods: lock === "periods" ? periods : null,
      event_type: type,
    }),
    onSuccess: () => {
      invalidate();
      toast.success(`${title.trim() || suggestion.name} added to the calendar`);
      onClose();
    },
    onError: (e) => showApiError(e, "Could not add that"),
  });

  const dismiss = useMutation({
    mutationFn: () => eventsApi.dismiss(suggestion.id),
    onSuccess: () => {
      invalidate();
      toast.success("Dismissed — we won't suggest it again");
      onClose();
    },
    onError: (e) => showApiError(e, "Could not dismiss that"),
  });

  return (
        <div className="space-y-4">
          {/* S-150 — the provenance the admin is being asked to trust. */}
          <p className="flex items-start gap-1.5 rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
            <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              Suggested · {suggestion.source}
              {suggestion.tradition ? ` · ${suggestion.tradition}` : ""}
              {suggestion.approved_count
                ? ` · you have already added this ${suggestion.approved_count} time(s)`
                : ""}
            </span>
          </p>

          <div>
            <Label htmlFor="ad-title">Call it</Label>
            <Input id="ad-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              {/* D-79 — the date is theirs, not the catalogue's. */}
              <Label htmlFor="ad-start">On</Label>
              <Input id="ad-start" type="date" value={start}
                     onChange={(e) => setStart(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="ad-end">Until (optional)</Label>
              <Input id="ad-end" type="date" value={end}
                     onChange={(e) => setEnd(e.target.value)} />
            </div>
          </div>
          {start !== suggestion.date ? (
            <p className="-mt-2 text-xs text-muted-foreground">
              Suggested for {fmt(suggestion.date)} — you&apos;ve moved it.
            </p>
          ) : null}

          <div>
            <Label>Is the school open?</Label>
            <div className="mt-1.5">
              <Pills value={lock} onChange={setLock} options={LOCKS} />
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {LOCKS.find((l) => l.value === lock)!.hint}
            </p>
          </div>

          {lock === "periods" ? (
            <div>
              <Label>Which periods?</Label>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {Array.from({ length: periodsPerDay }, (_, i) => i + 1).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPeriods((cur) =>
                      cur.includes(p) ? cur.filter((x) => x !== p) : [...cur, p].sort((a, b) => a - b))}
                    className={cn(
                      "h-8 w-8 rounded-md border text-xs transition-colors",
                      periods.includes(p)
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card hover:bg-muted",
                    )}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          ) : null}

          <div>
            <Label>Mark it as</Label>
            <div className="mt-1.5">
              <Pills value={type} onChange={setType} options={TYPES} />
            </div>
          </div>

          {/* S-143 — the sentence leads, the detail follows (ux §1). */}
          <div className="rounded-lg border border-border bg-muted/40 px-3 py-2.5">
            {pricing ? (
              <p className="text-xs text-muted-foreground">Working out what this costs…</p>
            ) : cost ? (
              <>
                <p className="text-sm">{cost.sentence}</p>
                {cost.moves.length ? (
                  <ul className="mt-1.5 space-y-0.5">
                    {cost.moves.slice(0, 6).map((mv, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs">
                        <span className="font-medium">{mv.class_label} {mv.subject_name}</span>
                        <Badge tone={mv.to_status === "red" ? "danger" : "warning"}>
                          {mv.from_status} → {mv.to_status}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </>
            ) : (
              <p className="text-xs text-muted-foreground">
                Pick a date to see what it costs.
              </p>
            )}
          </div>

          <div className="flex gap-2">
            <Button className="flex-1" disabled={approve.isPending || !start}
                    onClick={() => approve.mutate()}>
              <CalendarPlus className="h-4 w-4" />
              {approve.isPending ? "Adding…" : "Add to the calendar"}
            </Button>
            <Button variant="ghost" disabled={dismiss.isPending}
                    onClick={() => dismiss.mutate()}>
              <X className="h-4 w-4" /> We don&apos;t observe this
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Dismissing is permanent — we won&apos;t suggest it again, this year or next.
          </p>
        </div>
  );
}


export function ApproveDateSheet({
  suggestion, yearId, periodsPerDay, onClose,
}: {
  suggestion: Suggestion | null;
  yearId: string;
  periodsPerDay: number;
  onClose: () => void;
}) {
  return (
    <Sheet
      open={!!suggestion}
      onOpenChange={(v) => { if (!v) onClose(); }}
      title={suggestion ? `Approve · ${suggestion.name}` : ""}
    >
      {suggestion ? (
        <ApproveForm key={suggestion.id} suggestion={suggestion} yearId={yearId}
                     periodsPerDay={periodsPerDay} onClose={onClose} />
      ) : null}
    </Sheet>
  );
}

/** The feed of undecided dates, on Plan → Year beside the calendar it writes. */
export function SuggestionList({
  yearId, periodsPerDay,
}: { yearId: string; periodsPerDay: number }) {
  const [open, setOpen] = useState<Suggestion | null>(null);
  const { data } = useQuery({
    queryKey: ["suggestions"],
    queryFn: () => eventsApi.suggestions(),
  });

  if (!data?.length) return null;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <h2 className="mb-1 text-sm font-semibold">Dates to decide</h2>
      <p className="mb-2.5 text-xs text-muted-foreground">
        Nothing here is on your calendar yet. Approving is what puts it there.
      </p>
      <div className="space-y-1">
        {data.map((s) => (
          <button
            key={s.id}
            type="button"
            onClick={() => setOpen(s)}
            className="flex w-full items-center justify-between gap-3 rounded-lg border border-border px-3 py-2 text-left transition-colors hover:bg-muted/50"
          >
            <span className="min-w-0">
              <span className="block truncate text-sm font-medium">{s.name}</span>
              <span className="block truncate text-xs text-muted-foreground">
                {fmt(s.date)} · {s.source}
              </span>
            </span>
            <span className="shrink-0 text-xs text-muted-foreground">
              {s.approved_count ? "added" : s.days_away === 0 ? "today" : `in ${s.days_away}d`}
            </span>
          </button>
        ))}
      </div>
      <ApproveDateSheet suggestion={open} yearId={yearId} periodsPerDay={periodsPerDay}
                        onClose={() => setOpen(null)} />
    </div>
  );
}
