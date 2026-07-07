"use client";

import { Check, ChevronRight, CornerUpLeft, Repeat2, Tag } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { dayLabel, priorityMeta, recurrenceSummary, timeLabel } from "@/lib/format";
import type { BoardRow } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Mobile board view (plan: phones get a simple checkable list). Each item shows
 * the title + a done check; tapping it expands the full detail inline, with a
 * link to the dedicated page.
 */
export function BoardMobile({
  rows,
  onComplete,
  onClaim,
  onOpen,
}: {
  rows: BoardRow[];
  onComplete: (row: BoardRow) => void;
  onClaim: (row: BoardRow) => void;
  onOpen: (row: BoardRow) => void;
}) {
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <div className="space-y-2">
      {rows.map((row) => {
        const key = `${row.kind}-${row.id}`;
        const done = row.status === "done";
        const scheduled = row.status === "scheduled";
        const expanded = openId === key;
        const overdue = row.due_at != null && !done && new Date(row.due_at) < new Date();
        const checkDisabled = scheduled || (row.kind === "recurring" && !row.today_instance_id);

        return (
          <div
            key={key}
            className={cn(
              "rounded-lg border border-border bg-card",
              overdue && "border-warning/30 bg-warning-soft/30",
            )}
          >
            <div className="flex items-center gap-3 px-3 py-3">
              {done ? (
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-success text-success-foreground">
                  <Check className="h-4 w-4" />
                </span>
              ) : (
                <button
                  disabled={checkDisabled}
                  onClick={() => onComplete(row)}
                  aria-label="Mark done"
                  className={cn(
                    "h-7 w-7 shrink-0 rounded-full border-2 transition-colors",
                    row.status === "missed" ? "border-warning" : "border-muted-foreground/30",
                    checkDisabled ? "opacity-40" : "active:scale-90",
                  )}
                />
              )}

              <button
                onClick={() => setOpenId(expanded ? null : key)}
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
              >
                <span className="min-w-0 flex-1">
                  <span
                    className={cn(
                      "flex items-center gap-1.5 truncate text-sm font-medium",
                      done && "text-muted-foreground line-through",
                    )}
                  >
                    {row.title}
                    {row.kind === "recurring" ? (
                      <Repeat2 className="h-3.5 w-3.5 shrink-0 text-primary" />
                    ) : null}
                  </span>
                  <span className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                    {row.category ? (
                      <span className="inline-flex items-center gap-0.5">
                        <Tag className="h-3 w-3" />
                        {row.category}
                      </span>
                    ) : null}
                    {row.due_at ? <span>{timeLabel(row.due_at) ?? dayLabel(row.due_at)}</span> : null}
                    {row.priority > 0 ? (
                      <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", priorityMeta(row.priority).cls)}>
                        {priorityMeta(row.priority).label}
                      </span>
                    ) : null}
                  </span>
                </span>
                <ChevronRight
                  className={cn(
                    "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                    expanded && "rotate-90",
                  )}
                />
              </button>
            </div>

            {expanded ? (
              <div className="space-y-3 border-t border-border px-3 py-3 text-sm">
                {row.description ? (
                  <p className="whitespace-pre-wrap text-sm">{row.description}</p>
                ) : null}
                <dl className="space-y-1.5 text-xs">
                  <Detail label="Owner">
                    {row.assignee ? (
                      <span className="flex items-center gap-1.5">
                        <Avatar name={row.assignee.name} /> {row.assignee.name}
                      </span>
                    ) : (
                      "Unassigned"
                    )}
                  </Detail>
                  <Detail label="Due">
                    {row.due_at
                      ? `${dayLabel(row.due_at)}${timeLabel(row.due_at) ? " · " + timeLabel(row.due_at) : ""}`
                      : "Anytime"}
                  </Detail>
                  {row.priority > 0 ? (
                    <Detail label="Priority">{priorityMeta(row.priority).label}</Detail>
                  ) : null}
                  {row.kind === "recurring" && row.recurrence ? (
                    <Detail label="Repeats">{recurrenceSummary(row.recurrence)}</Detail>
                  ) : null}
                  {row.pass_count > 0 ? (
                    <Detail label="Passed">
                      <span className="inline-flex items-center text-warning">
                        <CornerUpLeft className="mr-0.5 h-3 w-3" />
                        {row.pass_count}×{row.passed_by ? ` · by ${row.passed_by}` : ""}
                      </span>
                    </Detail>
                  ) : null}
                </dl>
                <div className="flex flex-wrap gap-2 pt-1">
                  {!row.assignee && !done && !scheduled ? (
                    <Button size="sm" variant="outline" onClick={() => onClaim(row)}>
                      Claim
                    </Button>
                  ) : null}
                  <Button size="sm" variant="ghost" onClick={() => onOpen(row)}>
                    Open full <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <dt className="w-16 shrink-0 text-muted-foreground">{label}</dt>
      <dd className="flex items-center">{children}</dd>
    </div>
  );
}
