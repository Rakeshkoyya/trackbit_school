"use client";

import { useRouter } from "next/navigation";
import { CornerUpLeft } from "lucide-react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { TaskCheckbox } from "@/components/tasks/task-checkbox";
import { relativeDue, timeLabel } from "@/lib/format";
import type { Task } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * A single task line used on Home and Board views. Shows board name, due,
 * "passed by X", and the ↩n badge — the open model surfaced casually.
 */
export function TaskRow({
  task,
  onComplete,
  onClaim,
  showBoard = true,
  removing = false,
  variant = "default",
}: {
  task: Task;
  onComplete?: (task: Task) => void;
  onClaim?: (task: Task) => void;
  showBoard?: boolean;
  removing?: boolean;
  variant?: "default" | "overdue";
}) {
  const router = useRouter();
  const done = task.status === "done";

  return (
    <div
      onClick={() => router.push(`/task/${task.id}`)}
      className={cn(
        "flex cursor-pointer items-center gap-3 rounded-lg border border-border bg-card px-3 py-3 transition-colors hover:bg-muted/40",
        variant === "overdue" && "border-warning/30 bg-warning-soft/40",
        removing && "tb-row-out",
      )}
    >
      {onComplete ? (
        <TaskCheckbox checked={done} onComplete={() => onComplete(task)} />
      ) : (
        <span className="h-6 w-6 shrink-0 rounded-full border-2 border-muted-foreground/30" />
      )}

      <div className="min-w-0 flex-1">
        <p className={cn("truncate text-sm font-medium", done && "text-muted-foreground line-through")}>
          {task.title}
          {task.pass_count > 0 ? (
            <span className="ml-1.5 inline-flex items-center text-xs text-warning">
              <CornerUpLeft className="h-3 w-3" />
              {task.pass_count > 1 ? task.pass_count : ""}
            </span>
          ) : null}
        </p>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {showBoard ? task.board_name : null}
          {task.passed_by ? <span> · passed by {task.passed_by}</span> : null}
        </p>
      </div>

      <div className="flex shrink-0 items-center gap-2">
        {task.due_at ? (
          <span className="text-xs text-muted-foreground">{timeLabel(task.due_at) ?? relativeDue(task.due_at)}</span>
        ) : null}
        {task.assignee ? (
          <Avatar name={task.assignee.name} />
        ) : onClaim ? (
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              onClaim(task);
            }}
          >
            Claim
          </Button>
        ) : null}
      </div>
    </div>
  );
}
