"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { parentApi, type ParentNotification } from "@/lib/parent-api";
import { cn } from "@/lib/utils";

/** `D-08` — where the school's messages actually live now.
 *
 *  WhatsApp is out of this version, so the absence alert, the homework note and
 *  the weekly summary are delivered here and woken up by web push (`D-14`).
 *
 *  `S-61`: this is the **archive, not the delivery mechanism**. Everything on it
 *  has already appeared on Today, so a parent who opens the app once a day has
 *  seen it all and nobody has to check two places. It exists for the parent who
 *  was out on Tuesday.
 *
 *  Deliberately not here: replies. A notification a parent can answer is a
 *  messaging product, and that is a different decision (`Q-01`).
 */
const KIND_WORDS: Record<string, string> = {
  absence: "Attendance",
  left_after_lunch: "Attendance",
  homework_set: "Homework",
  homework_pattern: "Homework",
  week_note: "Weekly note",
  fee_reminder: "Fees",
  general: "School",
};

function when(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  if (sameDay) {
    return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  }
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function Row({ n, showChild }: { n: ParentNotification; showChild: boolean }) {
  return (
    <li className={cn("px-3 py-3", !n.read && "bg-primary/[0.04]")}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm font-medium">{n.title}</p>
        <span className="shrink-0 text-[11px] text-muted-foreground">
          {when(n.created_at)}
        </span>
      </div>
      <p className="mt-0.5 text-sm text-muted-foreground">{n.body}</p>
      <p className="mt-1 text-[11px] text-muted-foreground">
        {KIND_WORDS[n.kind] ?? "School"}
        {/* With siblings on one login, a message that doesn't say whose it is
            is unreadable. */}
        {showChild ? ` · ${n.student_name}` : ""}
      </p>
    </li>
  );
}

export default function ParentNotificationsPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["parent", "notifications"],
    queryFn: parentApi.notifications,
  });

  // Opening the tab IS reading it. The one write a parent makes, and it is
  // session bookkeeping rather than content — an unread badge that cannot clear
  // is just a broken archive.
  useEffect(() => {
    if (!data || data.unread === 0) return;
    parentApi
      .markNotificationsRead()
      .then(() => qc.invalidateQueries({ queryKey: ["parent", "notifications"] }))
      .catch(() => {});
  }, [data, qc]);

  if (isLoading) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>;
  }

  const items = data?.items ?? [];
  if (items.length === 0) {
    return (
      <div className="rounded-lg border bg-card px-4 py-10 text-center">
        <p className="text-sm font-medium">Nothing from the school yet</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Attendance alerts, homework and the weekly note will appear here.
        </p>
      </div>
    );
  }

  const children = new Set(items.map((n) => n.student_id));
  return (
    <ul className="divide-y overflow-hidden rounded-lg border bg-card">
      {items.map((n) => (
        <Row key={n.id} n={n} showChild={children.size > 1} />
      ))}
    </ul>
  );
}
