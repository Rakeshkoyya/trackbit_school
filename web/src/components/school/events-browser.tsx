"use client";

/**
 * **Show events** — the researched calendar, browsable (V1-20).
 *
 * The suggestions feed answers *"what should I act on"* and is deliberately
 * narrow: this school's state, the near horizon, major dates only. That is
 * right for a queue and useless for the question an admin actually arrives
 * with in August, which is *"what have you got for the year, and is my state's
 * stuff in there?"* — a question a queue of four rows cannot answer and that
 * ends with the admin assuming the product knows nothing about Onam.
 *
 * So this is the reference view: everything, every state, grouped by month,
 * with the school's own state preselected. Two things are load-bearing:
 *
 *   * **`applies_here`** is on every row. Without it a national list and a
 *     regional list look identical, and a principal in Kerala cannot tell which
 *     of these will ever reach her.
 *   * **Decided rows are labelled, not hidden.** An admin who dismissed Diwali
 *     by accident in April has no other way to find out; hiding it would make
 *     the table quietly disagree with the calendar.
 *
 * Dates are set in the mono face — the register/day-book habit (V1-14, V1-16):
 * a column of dates is a document of record, and mono keeps the digits aligned.
 */

import { useQuery } from "@tanstack/react-query";
import { CalendarSearch, Check, MapPin, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Modal } from "@/components/ui/modal";
import { eventsApi, type CatalogueRow } from "@/lib/events-api";
import { cn } from "@/lib/utils";

const ALL_STATES = "all";

const MONTH_KEY = (d: string) => d.slice(0, 7);

const monthLabel = (key: string) =>
  new Date(key + "-01T00:00:00").toLocaleDateString("en-IN", {
    month: "long", year: "numeric",
  });

const dayLabel = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
    weekday: "short", day: "2-digit", month: "short",
  });

const KIND_TONE: Record<string, string> = {
  holiday: "text-warning",
  festival: "text-primary",
  observance: "text-muted-foreground",
};

function Row({ row }: { row: CatalogueRow }) {
  return (
    <div
      className={cn(
        "grid grid-cols-[7.5rem_minmax(0,1fr)_auto] items-start gap-3 border-b border-border/60 px-4 py-2.5 last:border-0",
        !row.applies_here && "opacity-55",
      )}
    >
      <span className="font-mono text-xs tabular-nums text-muted-foreground">
        {dayLabel(row.date)}
        {row.end_date && row.end_date !== row.date ? (
          <span className="block text-[10px]">→ {dayLabel(row.end_date)}</span>
        ) : null}
      </span>

      <span className="min-w-0">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="truncate text-sm font-medium">{row.name}</span>
          <span className={cn("text-[10px] uppercase tracking-wide", KIND_TONE[row.kind])}>
            {row.kind}
          </span>
          {row.tier === "minor" ? (
            <Badge tone="outline">minor</Badge>
          ) : null}
        </span>
        <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <MapPin className="h-3 w-3 shrink-0" />
            {row.states?.length ? row.states.join(", ") : "All India"}
          </span>
          {row.tradition ? <span>· {row.tradition}</span> : null}
        </span>
        {row.note ? (
          <span className="mt-0.5 block text-xs text-muted-foreground/90">{row.note}</span>
        ) : null}
        {/* S-150 — provenance on the row. The admin approving a date is the
            last human in the chain; an unattributed date is one they either
            approve blindly or ignore entirely. */}
        <span className="mt-0.5 block truncate text-[11px] text-muted-foreground/70">
          {row.source}
        </span>
      </span>

      <span className="shrink-0 pt-0.5">
        {row.approved ? (
          <Badge tone="primary"><Check className="h-3 w-3" /> On your calendar</Badge>
        ) : row.decided ? (
          <Badge tone="neutral">Dismissed</Badge>
        ) : row.applies_here ? (
          <Badge tone="outline">Suggested</Badge>
        ) : (
          <Badge tone="outline">Other state</Badge>
        )}
      </span>
    </div>
  );
}

export function EventsBrowser({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  // `undefined` = the school's own state (the server preselects it);
  // ALL_STATES = every state, a deliberate choice the admin can make. A
  // sentinel rather than "" because `qs` drops empty params, which would turn
  // "All states" into "my state" without a word.
  const [state, setState] = useState<string | undefined>(undefined);
  const [year, setYear] = useState<number | undefined>(undefined);
  const [q, setQ] = useState("");
  const [majorOnly, setMajorOnly] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["events-catalogue", state, year, q, majorOnly],
    // `undefined` is NOT the same as `""` here and the server knows it:
    // omitting the param means "this school's own state" (what the dropdown
    // shows before anyone touches it), and an empty string means "every state".
    queryFn: () => eventsApi.browseCatalogue({
      state, year, q: q.trim() || undefined, includeMinor: !majorOnly,
    }),
    enabled: open,
  });

  // The server preselects the school's own state on first load; once the admin
  // touches the dropdown their choice wins.
  const effectiveState = state ?? data?.org_state ?? ALL_STATES;

  const grouped = useMemo(() => {
    const out = new Map<string, CatalogueRow[]>();
    for (const r of data?.rows ?? []) {
      const key = MONTH_KEY(r.date);
      const list = out.get(key);
      if (list) list.push(r);
      else out.set(key, [r]);
    }
    return [...out.entries()];
  }, [data]);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Holidays and events"
      description="Dates we hold for Indian schools. Tap a suggested date on the calendar to add it to your year."
      size="xl"
    >
      <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-border bg-card px-4 py-3">
        <div className="relative min-w-[10rem] flex-1">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search a festival"
            className="pl-8"
          />
        </div>

        <select
          value={effectiveState}
          onChange={(e) => setState(e.target.value)}
          className="h-9 rounded-md border border-border bg-card px-2 text-sm"
          aria-label="State"
        >
          <option value={ALL_STATES}>All states</option>
          {(data?.states ?? []).map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>

        <select
          value={year ?? ""}
          onChange={(e) => setYear(e.target.value ? Number(e.target.value) : undefined)}
          className="h-9 rounded-md border border-border bg-card px-2 text-sm"
          aria-label="Year"
        >
          <option value="">All years</option>
          {(data?.years ?? []).map((y) => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>

        <button
          type="button"
          onClick={() => setMajorOnly((v) => !v)}
          className={cn(
            "h-9 rounded-full border px-3 text-xs transition-colors",
            majorOnly
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-card hover:bg-muted",
          )}
        >
          Major only
        </button>
      </div>

      {data?.org_state && data.filter_state === data.org_state ? (
        <p className="border-b border-border bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
          Showing what a school in <strong className="font-medium">{data.org_state}</strong> observes,
          plus the national dates. Change the state to see anywhere else.
        </p>
      ) : null}
      {!data?.org_state && !isLoading ? (
        <p className="border-b border-border bg-warning-soft px-4 py-2 text-xs text-warning">
          No state is set for this school, so nothing regional is being suggested.
          Set it in Setup → Settings.
        </p>
      ) : null}

      {isLoading ? (
        <p className="px-4 py-10 text-center text-sm text-muted-foreground">Loading…</p>
      ) : !grouped.length ? (
        <div className="px-4 py-12 text-center">
          <CalendarSearch className="mx-auto mb-2 h-6 w-6 text-muted-foreground" />
          <p className="text-sm font-medium">Nothing matches that</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Try clearing the search, or pick “All states”.
          </p>
        </div>
      ) : (
        <div>
          {grouped.map(([month, rows]) => (
            <section key={month}>
              <h3 className="sticky top-[3.25rem] z-[5] border-y border-border bg-muted/60 px-4 py-1.5 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                {monthLabel(month)}
                <span className="ml-2 normal-case tracking-normal">
                  {rows.length} date{rows.length === 1 ? "" : "s"}
                </span>
              </h3>
              {rows.map((r) => <Row key={r.id} row={r} />)}
            </section>
          ))}
          <p className="px-4 py-3 text-xs text-muted-foreground">
            {data?.total} dates shown.
          </p>
        </div>
      )}
    </Modal>
  );
}
