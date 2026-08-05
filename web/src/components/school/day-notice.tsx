"use client";

// The day's notice — events and birthdays, in one dismissible row.
//
// Founder call (2026-08-05), replacing `WhatsOnCard`. The feed was a section on
// two screens: a card on the dashboard with a "Coming up" list under it, and a
// strip on My Day. Both spent real vertical space every day on something nobody
// has to *do*, and the teacher's copy showed her the whole school — the office's
// exam block, a colleague's birthday, another class's children.
//
// So it becomes ONE line at the top of the screen, dismissible for the day, and
// it opens into a popover rather than pushing the page down. The rules it keeps:
//
//   * `S-132` — it asks for nothing. No tick, no amber, no to-do row. It is
//     absent entirely when there is nothing on, never an empty state.
//   * `S-133` — the day, never the age.
//   * `S-128` — a birthday that lands in a vacation shows on the nearest working
//     day and SAYS SO. Quietly moving a child's birthday is worse than not
//     showing it.
//   * `S-124` — the coverage sentence with its denominator, and only when it is
//     the reason the notice is thin.
//   * `S-126` — a big date surfaces early. There is no separate "upcoming"
//     section: the horizon is a week, so Independence Day joins the notice seven
//     days out and leaves it the day after (founder — "everyday we check and
//     present it, and any event shows up a week before").
//
// Dismissal is per DAY, not forever: the key holds the feed's own date, so
// tomorrow's notice is a new notice. It is the one thing on these screens that
// gives rather than collects, so it wears the green wash and the accent rule
// instead of the card-and-border language of the work around it.

import { useQuery } from "@tanstack/react-query";
import { Cake, CalendarDays, ChevronDown, PartyPopper, X } from "lucide-react";
import Link from "next/link";
import { useRef, useState, useSyncExternalStore } from "react";

import { Popover } from "@/components/ui/popover";
import { eventsApi, type FeedItem, type WhatsOn } from "@/lib/events-api";
import { cn } from "@/lib/utils";

// ── dismissal, as an external store ─────────────────────────────────────────
// It lives in localStorage, which is neither React state nor available on the
// server, so it is subscribed to rather than read into state — and the
// in-memory map means a browser with storage blocked still dismisses for the
// session instead of a button that visibly does nothing.
const memory = new Map<string, string>();
const listeners = new Set<() => void>();

function readDismissal(key: string): string | null {
  const held = memory.get(key);
  if (held !== undefined) return held;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeDismissal(key: string, value: string) {
  memory.set(key, value);
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Private mode. It holds for this session; that is the honest maximum.
  }
  listeners.forEach((fn) => fn());
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  window.addEventListener("storage", fn);
  return () => {
    listeners.delete(fn);
    window.removeEventListener("storage", fn);
  };
}

const fmt = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

const weekday = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short" });

/** When it is, said inside a sentence. */
function whenPhrase(item: FeedItem) {
  if (item.days_away === 0) return "today";
  if (item.days_away === 1) return "tomorrow";
  return `on ${weekday(item.on_date)} ${fmt(item.on_date)}`;
}

/** When it is, as a stamp in the right-hand column. Mono and uppercase, like
 *  every other date in this product since V1-14 — the notice is a record of the
 *  day, and it reads as one. */
function whenStamp(item: FeedItem) {
  if (item.days_away === 0) return "today";
  if (item.days_away === 1) return "tomorrow";
  return `${weekday(item.on_date)} ${fmt(item.on_date)}`;
}

/** What it is. A birthday is spoken in lower case because it sits inside a
 *  sentence; a calendar row keeps the school's own words for it. */
function what(item: FeedItem, { withClass = true } = {}) {
  if (item.source === "calendar") return item.detail ?? "";
  // `S-128` — say the move, never hide it.
  const moved = item.actual_date
    ? ` · birthday on ${weekday(item.actual_date)} ${fmt(item.actual_date)}`
    : "";
  const who = withClass && item.class_label ? `${item.class_label} · ` : "";
  const kind = item.source === "staff_birthday" ? "staff birthday" : "birthday";
  return `${who}${kind}${moved}`;
}

function Icon({ item, className }: { item: FeedItem; className?: string }) {
  const cls = cn("h-4 w-4 shrink-0", className);
  if (item.source === "calendar") {
    return item.event_type === "celebration"
      ? <PartyPopper className={cls} />
      : <CalendarDays className={cls} />;
  }
  return <Cake className={cls} />;
}

function Row({ item, withClass }: { item: FeedItem; withClass?: boolean }) {
  const body = (
    <>
      <Icon item={item} className="text-muted-foreground" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{item.title}</span>
        <span className="block truncate text-xs text-muted-foreground">
          {what(item, { withClass })}
        </span>
      </span>
      <span className="shrink-0 font-mono text-[11px] uppercase tracking-wide text-muted-foreground">
        {whenStamp(item)}
      </span>
    </>
  );
  const cls = "flex items-center gap-2.5 rounded-lg px-2 py-1.5";
  return item.student_id ? (
    <Link href={`/students/${item.student_id}`} className={cn(cls, "hover:bg-muted")}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

/** The teacher's row: this class's birthdays, and nothing else.
 *
 *  Mounted on the period card and across My Class — the two places she is
 *  standing in front of the children it is about. It reads its own feed so the
 *  three mounts share one query key and one cache entry, and so a page that
 *  wants it does not have to know it is a calendar read at all. */
export function ClassDayNotice({ classId }: { classId: string }) {
  const { data } = useQuery({
    queryKey: ["whats-on", "class", classId],
    queryFn: () => eventsApi.whatsOn({ horizon: 7, classId }),
    enabled: !!classId,
  });
  return <DayNotice data={data} scope={classId} withClass={false} />;
}

export function DayNotice({
  data,
  scope,
  calendarHref,
  withClass = true,
}: {
  data: WhatsOn | undefined;
  /** Dismissal namespace — "school" for the admin's notice, the class id for a
   *  class row, so dismissing one class's birthdays never hides another's. */
  scope: string;
  /** Admin only: where the year calendar lives. */
  calendarHref?: string;
  /** Off on a class row: she is standing in 6-A, so "6-A ·" on every line is a
   *  word that carries nothing. */
  withClass?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const anchor = useRef<HTMLButtonElement>(null);
  const key = `day-notice:${scope}`;
  // The server has no localStorage, so it renders as not-dismissed and the
  // client corrects it on hydration. Nothing flashes: the feed itself arrives
  // from the query well after that.
  const dismissed = useSyncExternalStore(
    subscribe, () => readDismissal(key), () => null);

  const items = data ? [...data.today, ...data.upcoming] : [];
  const thin = data && data.dob_known < data.dob_total ? data : null;

  if (!data) return null;
  // Dismissal holds for the DAY, not forever — the key stores the feed's own
  // date, so tomorrow's notice is a new notice.
  if (dismissed === data.date) return null;
  // S-132 — silence is the correct state. The coverage sentence is a footnote on
  // a notice, never a reason to draw one.
  if (items.length === 0) return null;

  const lead = items[0];
  const rest = items.length - 1;

  const dismiss = () => {
    setOpen(false);
    writeDismissal(key, data.date);
  };

  return (
    <div className="flex items-center gap-2.5 rounded-xl border border-border border-l-2 border-l-primary bg-accent px-3 py-2 text-accent-foreground">
      <Icon item={lead} className="text-primary" />
      <p className="min-w-0 flex-1 truncate text-sm">
        <span className="font-medium">{lead.title}</span>
        <span className="text-muted-foreground">
          {" "}· {what(lead, { withClass })} {whenPhrase(lead)}
        </span>
      </p>

      {rest > 0 ? (
        <button
          type="button"
          ref={anchor}
          onClick={() => {
            // Anchored to the control that opens it, not to the whole bar: a
            // panel that appears at the far left of a full-width row reads as
            // belonging to something else.
            setRect(anchor.current?.getBoundingClientRect() ?? null);
            setOpen((v) => !v);
          }}
          aria-expanded={open}
          className="flex shrink-0 items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          +{rest}<span className="hidden sm:inline"> more</span>
          <ChevronDown className={cn("h-3 w-3 transition-transform", open && "rotate-180")} />
        </button>
      ) : null}

      {/* The one actionable thing here, and admin-only: dates the catalogue has
          suggested and nobody has decided yet. It stays a quiet link — the
          notice is not a to-do row (`S-132`), it is a pointer to the queue that
          owns them. */}
      {calendarHref && data.pending_suggestions > 0 ? (
        <Link
          href="/plan"
          className="hidden shrink-0 rounded-md px-1.5 py-0.5 font-mono text-[11px] text-muted-foreground hover:bg-muted hover:text-foreground sm:block"
        >
          {data.pending_suggestions} to decide
        </Link>
      ) : null}

      <button
        type="button"
        onClick={dismiss}
        aria-label="Dismiss for today"
        className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <X className="h-3.5 w-3.5" />
      </button>

      <Popover open={open} onClose={() => setOpen(false)} rect={rect} width={320}>
        <div className="space-y-0.5">
          {items.map((item, i) => (
            <Row key={`${item.source}-${i}`} item={item} withClass={withClass} />
          ))}
        </div>
        {thin || calendarHref ? (
          <div className="mt-1 space-y-1 border-t border-border px-2 pt-1.5">
            {/* S-124 — the figure with its denominator, and the way to fix it. */}
            {thin ? (
              <p className="text-xs text-muted-foreground">
                Birthdays known for {thin.dob_known} of {thin.dob_total} students ·{" "}
                <Link href="/students" className="underline">add dates of birth</Link>
              </p>
            ) : null}
            {calendarHref ? (
              <Link href={calendarHref} className="block text-xs text-muted-foreground hover:underline">
                Year calendar →
              </Link>
            ) : null}
          </div>
        ) : null}
      </Popover>
    </div>
  );
}
