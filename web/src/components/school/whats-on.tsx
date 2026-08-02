"use client";

// V1-7 — What's on. The read side the school calendar has never had.
//
// Built ONCE and mounted twice, because the admin and the teacher want the same
// feed at different depths (module §1) — a card and a strip, not two modules.
// Two components would be two answers to "is it anyone's birthday today", and
// that is `S-51`'s defect wearing a party hat.
//
// The rules this component exists to hold:
//   * `S-132` — on My Day this is the ONE thing that asks the teacher for
//     nothing. No tick, no amber, no to-do row. It gives; it never collects.
//     It is absent entirely when there is nothing on.
//   * `S-133` — the day, never the age. No DOB on a shared surface, no "turns
//     12 today" on a screen that gets shown to a room.
//   * `S-128` — a birthday that lands in a vacation is shown on the nearest
//     working day and SAYS SO. Quietly moving a child's birthday is worse than
//     not showing it.
//   * `S-124` — an empty card carries its denominator ("birthdays known for 41
//     of 486") and links to the import. That sentence is the difference between
//     a screen that looks broken and one that tells you how to fill it.
//   * `S-131` — this is *events & dates*, not "celebrations". `CelebrationProvider`
//     is the task-completion confetti layer and has nothing to do with it.

import Link from "next/link";
import { Cake, CalendarDays, PartyPopper } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { FeedItem, WhatsOn } from "@/lib/events-api";
import { cn } from "@/lib/utils";

const fmt = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

const weekday = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", { weekday: "long" });

function when(item: FeedItem) {
  if (item.days_away === 0) return "today";
  if (item.days_away === 1) return "tomorrow";
  return `${fmt(item.on_date)} · in ${item.days_away} days`;
}

function Icon({ item }: { item: FeedItem }) {
  if (item.source === "calendar") {
    return item.event_type === "celebration"
      ? <PartyPopper className="h-4 w-4 text-muted-foreground" />
      : <CalendarDays className="h-4 w-4 text-muted-foreground" />;
  }
  return <Cake className="h-4 w-4 text-muted-foreground" />;
}

function Row({ item, showWhen }: { item: FeedItem; showWhen?: boolean }) {
  const body = (
    <span className="flex min-w-0 items-center gap-2.5">
      <Icon item={item} />
      <span className="min-w-0">
        <span className="truncate text-sm font-medium">{item.title}</span>
        <span className="ml-1.5 text-xs text-muted-foreground">
          {item.class_label ? `${item.class_label} · ` : ""}
          {item.detail}
          {/* S-128 — say it, never hide the move. */}
          {item.actual_date
            ? ` · birthday on ${weekday(item.actual_date)} ${fmt(item.actual_date)}`
            : ""}
        </span>
      </span>
    </span>
  );
  const cls = "flex items-center justify-between gap-3 rounded-lg px-2 py-1.5";
  const tail = showWhen ? (
    <span className="shrink-0 text-xs text-muted-foreground">{when(item)}</span>
  ) : null;

  if (item.source === "birthday" && item.student_id) {
    return (
      <Link href={`/students/${item.student_id}`} className={cn(cls, "hover:bg-muted/50")}>
        {body}
        {tail}
      </Link>
    );
  }
  return <div className={cls}>{body}{tail}</div>;
}

/** The admin's card and the teacher's strip. `variant` changes the chrome and
 *  the depth, never the data — one computation, two renderings (ux §9). */
export function WhatsOnCard({
  data,
  variant = "card",
  onOpenCalendar,
}: {
  data: WhatsOn | undefined;
  variant?: "card" | "strip";
  onOpenCalendar?: string;
}) {
  if (!data) return null;
  const nothingToday = data.today.length === 0;
  const nothingAtAll = nothingToday && data.upcoming.length === 0;

  // S-132: on My Day, silence is the correct state. A strip with an empty state
  // is still a row asking for her attention.
  if (variant === "strip" && nothingToday) return null;

  if (variant === "strip") {
    return (
      <div className="rounded-xl border border-border bg-card px-3 py-2">
        <div className="space-y-0.5">
          {data.today.map((item, i) => <Row key={`${item.source}-${i}`} item={item} />)}
        </div>
      </div>
    );
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">What&apos;s on</h2>
        <div className="flex items-center gap-2">
          {data.pending_suggestions > 0 ? (
            <Link href="/plan">
              <Badge tone="warning">{data.pending_suggestions} to decide</Badge>
            </Link>
          ) : null}
          {onOpenCalendar ? (
            <Link href={onOpenCalendar} className="text-xs text-muted-foreground hover:underline">
              Year calendar →
            </Link>
          ) : null}
        </div>
      </div>

      {nothingAtAll ? (
        <p className="rounded-lg border border-dashed border-border px-3 py-5 text-center text-xs text-muted-foreground">
          Nothing on today or in the next three weeks.
        </p>
      ) : (
        <>
          {data.today.length ? (
            <div className="space-y-0.5">
              {data.today.map((item, i) => <Row key={`t-${i}`} item={item} />)}
            </div>
          ) : (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">Nothing on today.</p>
          )}

          {data.upcoming.length ? (
            <div className="mt-3 border-t border-border pt-2">
              <p className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Coming up
              </p>
              <div className="space-y-0.5">
                {data.upcoming.slice(0, 6).map((item, i) => (
                  <Row key={`u-${i}`} item={item} showWhen />
                ))}
              </div>
            </div>
          ) : null}
        </>
      )}

      {/* S-124 — the coverage sentence, with its denominator, and only when it
          is actually the reason the card is thin. */}
      {data.dob_known < data.dob_total ? (
        <p className="mt-3 border-t border-border pt-2 text-xs text-muted-foreground">
          Birthdays known for {data.dob_known} of {data.dob_total} students ·{" "}
          <Link href="/students" className="underline">add dates of birth</Link>
        </p>
      ) : null}
    </section>
  );
}
