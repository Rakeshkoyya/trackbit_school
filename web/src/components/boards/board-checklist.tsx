"use client";

import { TaskRow } from "@/components/tasks/task-row";
import { dayLabel } from "@/lib/format";
import type { Task } from "@/lib/types";

/**
 * Checklist-category layout (plan P4-FE-03): day-grouped, completion-first.
 * Open items lead each day so the checkbox is the obvious next action; finished
 * ones settle below. Dateless items live under "Anytime".
 */
export function BoardChecklist({
  tasks,
  onComplete,
  onClaim,
  removing,
}: {
  tasks: Task[];
  onComplete: (t: Task) => void;
  onClaim?: (t: Task) => void;
  removing?: Set<string>;
}) {
  const groups = new Map<string, { label: string; sort: string; items: Task[] }>();
  for (const t of tasks) {
    const key = t.due_at ? t.due_at.slice(0, 10) : "anytime";
    const label = t.due_at ? (dayLabel(t.due_at) ?? "Anytime") : "Anytime";
    const sort = t.due_at ? t.due_at.slice(0, 10) : "9999"; // Anytime last
    if (!groups.has(key)) groups.set(key, { label, sort, items: [] });
    groups.get(key)!.items.push(t);
  }
  const ordered = [...groups.values()].sort((a, b) => a.sort.localeCompare(b.sort));

  return (
    <div className="space-y-6">
      {ordered.map((g) => {
        // completion-first: open tasks lead, done settle below.
        const items = [...g.items].sort(
          (a, b) => Number(a.status === "done") - Number(b.status === "done"),
        );
        return (
          <div key={g.label}>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {g.label}
            </h2>
            <div className="space-y-2">
              {items.map((t) => (
                <TaskRow
                  key={t.id}
                  task={t}
                  showBoard={false}
                  onComplete={t.status !== "done" ? onComplete : undefined}
                  onClaim={!t.assignee && onClaim ? onClaim : undefined}
                  removing={removing?.has(t.id)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
