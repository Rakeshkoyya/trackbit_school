"use client";

import { useQuery } from "@tanstack/react-query";

import { parentApi, type ParentCalendarItem } from "@/lib/parent-api";
import { cn } from "@/lib/utils";

import { useParentPortal } from "../parent-context";

/** `Q-56` — *"Is school open on Monday?"*
 *
 *  The single most-asked question in a school office, answered from rows the
 *  school already maintains: read-only, zero new capture, probably the cheapest
 *  win available to this portal.
 *
 *  Two constraints, both enforced server-side in `parent_portal.py::calendar`:
 *  the same field-by-field allowlist as every other parent surface, and **only
 *  this child's birthday**. A list of classmates' birthdays is a roster leak
 *  wearing a party hat.
 *
 *  An agenda list, not a month grid: on a phone, "what's coming" is the
 *  question, and a grid makes a parent hunt for it.
 */
function fmt(iso: string): { day: string; date: string } {
  const d = new Date(iso + "T00:00:00");
  return {
    day: d.toLocaleDateString(undefined, { weekday: "short" }),
    date: d.toLocaleDateString(undefined, { day: "numeric", month: "short" }),
  };
}

function Item({ item }: { item: ParentCalendarItem }) {
  const { day, date } = fmt(item.date);
  const span = item.end_date ? ` – ${fmt(item.end_date).date}` : "";
  return (
    <li className="flex gap-3 px-3 py-3">
      <div className="w-14 shrink-0 text-center">
        <p className="text-[11px] uppercase text-muted-foreground">{day}</p>
        <p className="text-sm font-semibold">{date}</p>
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{item.title}</p>
        <p
          className={cn(
            "mt-0.5 text-xs",
            // "School closed" is the answer the parent came for, so it is the
            // one line allowed to stand out. Never a warning colour — a holiday
            // is good news.
            item.closed ? "font-medium text-foreground" : "text-muted-foreground",
          )}
        >
          {item.closed ? "School closed" : (item.detail ?? "School open")}
          {span}
        </p>
      </div>
    </li>
  );
}

export default function ParentCalendarPage() {
  const { child } = useParentPortal();
  const { data, isLoading } = useQuery({
    queryKey: ["parent", "calendar", child?.student_id],
    queryFn: () => parentApi.calendar(child!.student_id),
    enabled: !!child,
  });

  if (isLoading || !child) {
    return <p className="py-8 text-center text-sm text-muted-foreground">Loading…</p>;
  }

  const items = data?.items ?? [];
  if (items.length === 0) {
    return (
      <div className="rounded-lg border bg-card px-4 py-10 text-center">
        <p className="text-sm font-medium">Nothing coming up</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Holidays and school events will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">The next two months.</p>
      <ul className="divide-y overflow-hidden rounded-lg border bg-card">
        {items.map((i, idx) => (
          <Item key={`${i.date}-${idx}`} item={i} />
        ))}
      </ul>
    </div>
  );
}
