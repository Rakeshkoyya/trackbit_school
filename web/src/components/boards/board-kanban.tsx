"use client";

import { CheckCircle2, CornerUpLeft, Repeat2 } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { priorityMeta, relativeDue, timeLabel } from "@/lib/format";
import type { BoardRow } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Kanban view (S4): Open → Done. Dragging an open card onto Done fires the same
 * /complete path, so the celebration layer triggers exactly as from the table.
 * No drag library — native HTML5 DnD keeps the bundle lean. Operates on the
 * unified board rows (recurring tasks are folded to a single card).
 */
export function BoardKanban({
  rows,
  onComplete,
  onClaim,
  onOpen,
}: {
  rows: BoardRow[];
  onComplete: (r: BoardRow) => void;
  onClaim?: (r: BoardRow) => void;
  onOpen: (r: BoardRow) => void;
}) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [over, setOver] = useState(false);

  const open = rows.filter((r) => r.status === "open" || r.status === "missed");
  const done = rows.filter((r) => r.status === "done");

  function dropToDone() {
    if (!dragId) return;
    const r = open.find((x) => `${x.kind}-${x.id}` === dragId);
    setDragId(null);
    setOver(false);
    if (r) onComplete(r);
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {/* Open column */}
      <div className="rounded-xl border border-border bg-muted/20 p-2">
        <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Open ({open.length})
        </h2>
        <div className="space-y-2">
          {open.map((r) => {
            const key = `${r.kind}-${r.id}`;
            return (
              <div
                key={key}
                draggable
                onDragStart={(e) => {
                  setDragId(key);
                  e.dataTransfer.effectAllowed = "move";
                }}
                onDragEnd={() => setDragId(null)}
                onClick={() => onOpen(r)}
                className={cn(
                  "cursor-grab rounded-lg border border-border bg-card p-3 active:cursor-grabbing",
                  dragId === key && "opacity-50",
                )}
              >
                <p className="flex items-center gap-1.5 truncate text-sm font-medium">
                  <span className="truncate">{r.title}</span>
                  {r.kind === "recurring" ? (
                    <Repeat2 className="h-3.5 w-3.5 shrink-0 text-primary" />
                  ) : null}
                  {r.pass_count > 0 ? (
                    <span className="inline-flex shrink-0 items-center text-xs text-warning">
                      <CornerUpLeft className="h-3 w-3" />
                      {r.pass_count > 1 ? r.pass_count : ""}
                    </span>
                  ) : null}
                </p>
                <div className="mt-2 flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      {r.due_at ? (timeLabel(r.due_at) ?? relativeDue(r.due_at)) : "Anytime"}
                    </span>
                    {r.priority > 0 ? (
                      <span className={cn("rounded px-1.5 py-0.5 text-[10px] font-medium", priorityMeta(r.priority).cls)}>
                        {priorityMeta(r.priority).label}
                      </span>
                    ) : null}
                  </span>
                  {r.assignee ? (
                    <Avatar name={r.assignee.name} />
                  ) : onClaim ? (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation();
                        onClaim(r);
                      }}
                    >
                      Claim
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })}
          {open.length === 0 ? (
            <p className="px-1 py-6 text-center text-xs text-muted-foreground">All clear ✓</p>
          ) : null}
        </div>
      </div>

      {/* Done column (drop target) */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={dropToDone}
        className={cn(
          "rounded-xl border border-dashed border-border bg-muted/20 p-2 transition-colors",
          over && "border-success bg-success/5",
        )}
      >
        <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Done ({done.length})
        </h2>
        {dragId ? (
          <div className="mb-2 flex items-center justify-center gap-1.5 rounded-lg border border-dashed border-success/50 py-4 text-xs text-success">
            <CheckCircle2 className="h-4 w-4" /> Drop to complete
          </div>
        ) : null}
        <div className="space-y-2">
          {done.map((r) => (
            <div
              key={`${r.kind}-${r.id}`}
              onClick={() => onOpen(r)}
              className="cursor-pointer rounded-lg border border-border bg-card p-3"
            >
              <p className="flex items-center gap-2 truncate text-sm text-muted-foreground line-through">
                <CheckCircle2 className="h-4 w-4 shrink-0 text-success" />
                {r.title}
              </p>
            </div>
          ))}
          {done.length === 0 ? (
            <p className="px-1 py-6 text-center text-xs text-muted-foreground">
              Drag a card here to finish it.
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
