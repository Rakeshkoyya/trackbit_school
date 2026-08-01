"use client";

import { Archive, Clock3 } from "lucide-react";
import { useState } from "react";

import { TaskTable, type ColumnKey } from "@/components/boards/board-table";
import { Button } from "@/components/ui/button";
import type { BoardRow } from "@/lib/types";

export type DoneRange = { doneFrom?: string; doneTo?: string };

/** D-44: the board windows done rows to 7 days — and the date filter SHIPS with
 *  the window. A window with no way to look further back is data loss from the
 *  user's side, so the hidden count is always spoken and always actionable. */
export function OlderDoneBar({
  hiddenCount,
  range,
  onRange,
}: {
  hiddenCount: number;
  range: DoneRange | null;
  onRange: (r: DoneRange | null) => void;
}) {
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  if (range) {
    return (
      <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm">
        <Archive className="h-4 w-4 text-muted-foreground" />
        <span>
          Showing completed tasks{range.doneFrom ? ` from ${range.doneFrom}` : ""}
          {range.doneTo ? ` to ${range.doneTo}` : ""}
        </span>
        <button
          onClick={() => onRange(null)}
          className="ml-auto text-xs font-medium text-primary hover:underline"
        >
          Back to the last 7 days
        </button>
      </div>
    );
  }
  if (hiddenCount === 0) return null;
  return (
    <div className="mb-3 rounded-lg border border-border bg-muted/30 px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Archive className="h-4 w-4 text-muted-foreground" />
        <span className="text-muted-foreground">
          {hiddenCount} completed task{hiddenCount === 1 ? "" : "s"} older than 7 days
        </span>
        <button
          onClick={() => setOpen((v) => !v)}
          className="ml-auto text-xs font-medium text-primary hover:underline"
        >
          {open ? "Cancel" : "Show older…"}
        </button>
      </div>
      {open ? (
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <label className="text-xs text-muted-foreground">
            From
            <input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
              className="mt-0.5 block rounded-md border border-input bg-card px-2 py-1 text-sm"
            />
          </label>
          <label className="text-xs text-muted-foreground">
            To
            <input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              className="mt-0.5 block rounded-md border border-input bg-card px-2 py-1 text-sm"
            />
          </label>
          <Button
            size="sm"
            disabled={!from && !to}
            onClick={() => {
              onRange({ doneFrom: from || undefined, doneTo: to || undefined });
              setOpen(false);
            }}
          >
            Show
          </Button>
        </div>
      ) : null}
    </div>
  );
}

/** D-45: untouched open follow-ups get their own group — close it (which asks
 *  what happened) or give it a new date, inline. NEVER auto-closed: a stale row
 *  is a true statement; a false close writes "handled" into an append-only
 *  history when nobody handled it. */
export function StaleSection({
  rows,
  columns = ["person", "due"],
  onComplete,
  onReopen,
  onOpen,
}: {
  rows: BoardRow[];
  columns?: ColumnKey[];
  onComplete: (row: BoardRow) => void;
  onReopen: (row: BoardRow) => void;
  onOpen: (row: BoardRow) => void;
}) {
  if (rows.length === 0) return null;
  return (
    <section className="mb-4">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
        <Clock3 className="h-4 w-4 text-warning" />
        Stale · {rows.length} item{rows.length === 1 ? "" : "s"} nobody has touched in 3 weeks
      </div>
      <p className="mb-2 text-xs text-muted-foreground">
        Close each one (it asks what happened) or give it a new date — they are never closed
        for you.
      </p>
      <TaskTable
        rows={rows}
        groupBy="none"
        columns={columns}
        onComplete={onComplete}
        onReopen={onReopen}
        onOpen={onOpen}
      />
    </section>
  );
}
