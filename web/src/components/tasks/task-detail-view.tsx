"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, CornerUpLeft, Hand, Repeat2, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useCelebration } from "@/components/celebration/celebration-provider";
import { TaskAttachments } from "@/components/tasks/task-attachments";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Sheet } from "@/components/ui/sheet";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";
import { dayLabel, eventTimeLabel, priorityMeta, timeLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

const WEEK = [
  ["mon", "M"], ["tue", "T"], ["wed", "W"], ["thu", "T"],
  ["fri", "F"], ["sat", "S"], ["sun", "S"],
] as const;

const STATUS_META: Record<string, { dot: string; label: string }> = {
  open: { dot: "border-2 border-muted-foreground/40", label: "To do" },
  done: { dot: "bg-success", label: "Done" },
  missed: { dot: "bg-warning", label: "Missed" },
  cancelled: { dot: "bg-muted", label: "Deleted" },
};

export function TaskDetailView({ taskId }: { taskId: string }) {
  const qc = useQueryClient();
  const router = useRouter();
  const { onCompletion } = useCelebration();
  const [pickerOpen, setPickerOpen] = useState(false);
  const [recurOpen, setRecurOpen] = useState(false);
  const [days, setDays] = useState<string[]>(["mon"]);
  const [time, setTime] = useState("");

  const { data: task, isLoading, isError } = useQuery({
    queryKey: ["task", taskId],
    queryFn: () => appApi.task(taskId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["task", taskId] });
    qc.invalidateQueries({ queryKey: ["home"] });
    qc.invalidateQueries({ queryKey: ["my-tasks"] });
    qc.invalidateQueries({ queryKey: ["boards"] });
    if (task) qc.invalidateQueries({ queryKey: ["board-table", task.board_id] });
  };

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => appApi.editTask(taskId, body),
    onSuccess: invalidate,
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not save"),
  });
  const complete = useMutation({
    mutationFn: () => appApi.completeTask(taskId),
    onSuccess: (res) => {
      if (res.already_done) {
        toast(`Already done${res.completed_by_name ? ` by ${res.completed_by_name}` : ""} ✓`);
      } else {
        onCompletion();
        toast.success("Done ✓");
      }
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not complete"),
  });
  const reopen = useMutation({ mutationFn: () => appApi.reopenTask(taskId), onSuccess: invalidate });
  const claim = useMutation({
    mutationFn: () => appApi.claimTask(taskId),
    onSuccess: () => { invalidate(); toast.success("Claimed — it's yours"); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Already taken"),
  });
  const reassign = useMutation({
    mutationFn: (userId: string) => appApi.reassignTask(taskId, userId),
    onSuccess: () => { invalidate(); setPickerOpen(false); toast.success("Passed on"); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not reassign"),
  });
  const del = useMutation({
    mutationFn: () => appApi.cancelTask(taskId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["home"] });
      qc.invalidateQueries({ queryKey: ["my-tasks"] });
      qc.invalidateQueries({ queryKey: ["boards"] });
      toast.success("Task deleted");
      router.back();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not delete"),
  });
  const makeRecurring = useMutation({
    mutationFn: () => appApi.makeRecurring(taskId, days, time || null),
    onSuccess: (tpl) => {
      qc.invalidateQueries({ queryKey: ["boards"] });
      qc.invalidateQueries({ queryKey: ["home"] });
      setRecurOpen(false);
      toast.success("Now repeating");
      router.replace(`/recurring/${tpl.id}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not make recurring"),
  });

  if (isLoading) return <div className="h-60 animate-pulse rounded-lg bg-muted" />;
  if (isError || !task) {
    return (
      <EmptyState
        title="Task not found"
        body="It may have been deleted or you can no longer see its board."
        action={<Button onClick={() => router.push("/home")}>Back to Home</Button>}
      />
    );
  }

  const done = task.status === "done";
  const status = STATUS_META[task.status] ?? STATUS_META.open;
  const creator = task.events.find((e) => e.type === "created")?.actor_name;
  const prio = priorityMeta(task.priority);

  function toggleDay(d: string) {
    setDays((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]));
  }

  return (
    <div className="pb-28">
      <div className="mb-3 flex items-center justify-between">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        <Button variant="outline" size="sm" onClick={() => setRecurOpen(true)}>
          <Repeat2 className="h-4 w-4" /> Make recurring
        </Button>
      </div>

      {/* Editable name */}
      <input
        defaultValue={task.title}
        onBlur={(e) => {
          const v = e.target.value.trim();
          if (v && v !== task.title) save.mutate({ title: v });
          else e.target.value = task.title;
        }}
        onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
        className="w-full rounded-md border border-transparent bg-transparent px-1 py-0.5 text-2xl font-semibold tracking-tight hover:border-border focus:border-border focus:outline-none"
        aria-label="Task name"
      />

      {/* Editable description */}
      <textarea
        defaultValue={task.description ?? ""}
        rows={2}
        onBlur={(e) => {
          const v = e.target.value;
          if (v !== (task.description ?? "")) save.mutate({ description: v || null });
        }}
        placeholder="Add a description…"
        className="mt-1 w-full resize-y rounded-md border border-transparent bg-transparent px-1 py-1 text-sm hover:border-border focus:border-border focus:outline-none"
      />

      {/* Info section */}
      <div className="mt-5">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Details</h2>
        <div className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card text-sm">
          <InfoRow label="Status">
            <span className="flex items-center gap-2">
              <span className={cn("h-3 w-3 rounded-full", status.dot)} />
              {status.label}
            </span>
          </InfoRow>
          <InfoRow label="Assignee">
            <div className="flex items-center justify-between gap-2">
              {task.assignee ? (
                <span className="flex items-center gap-1.5"><Avatar name={task.assignee.name} /> {task.assignee.name}</span>
              ) : (
                <span className="text-muted-foreground">Unassigned</span>
              )}
              {!done ? (
                task.assignee ? (
                  <button onClick={() => setPickerOpen(true)} className="text-xs text-primary hover:underline">Reassign</button>
                ) : (
                  <button onClick={() => claim.mutate()} className="inline-flex items-center gap-1 text-xs text-primary hover:underline"><Hand className="h-3 w-3" /> Claim</button>
                )
              ) : null}
            </div>
          </InfoRow>
          <InfoRow label="Due date">
            {task.due_at
              ? `${dayLabel(task.due_at)}${timeLabel(task.due_at) ? " · " + timeLabel(task.due_at) : ""}`
              : <span className="text-muted-foreground">Anytime</span>}
          </InfoRow>
          <InfoRow label="Priority">
            {task.priority > 0 ? (
              <span className={cn("rounded px-2 py-0.5 text-xs font-medium", prio.cls)}>{prio.label}</span>
            ) : <span className="text-muted-foreground">None</span>}
          </InfoRow>
          <InfoRow label="Category">
            {task.category ? task.category : <span className="text-muted-foreground">—</span>}
          </InfoRow>
          <InfoRow label="Board">{task.board_name}</InfoRow>
          {task.is_critical ? (
            <InfoRow label="Critical"><Badge tone="warning">Alarm reminder</Badge></InfoRow>
          ) : null}
          {task.pass_count > 0 ? (
            <InfoRow label="Passed">
              <span className="inline-flex items-center gap-1 text-warning">
                <CornerUpLeft className="h-3 w-3" /> {task.pass_count}×{task.passed_by ? ` · by ${task.passed_by}` : ""}
              </span>
            </InfoRow>
          ) : null}
          <InfoRow label="Created">
            {dayLabel(task.created_at)}{creator ? ` · by ${creator}` : ""}
          </InfoRow>
        </div>
      </div>

      {/* Notes & comments */}
      <TaskAttachments taskId={taskId} />

      {/* History / audit */}
      <div className="mt-6">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">History</h2>
        <ol className="space-y-2.5 border-l border-border pl-4">
          {task.events.map((e) => (
            <li key={e.id} className="relative text-sm">
              <span className="absolute -left-[1.30rem] top-1.5 h-2 w-2 rounded-full bg-border" />
              <span>{e.text}</span>
              <span className="ml-2 text-xs text-muted-foreground">{eventTimeLabel(e.at)}</span>
            </li>
          ))}
        </ol>
      </div>

      {/* Delete */}
      {task.can_cancel && !done ? (
        <div className="mt-6">
          <Button variant="ghost" className="text-danger" onClick={() => del.mutate()}>
            <Trash2 className="h-4 w-4" /> Delete task
          </Button>
        </div>
      ) : null}

      {/* Primary action (sticky) */}
      <div className="fixed inset-x-0 bottom-16 z-20 border-t border-border bg-card/95 px-4 py-3 backdrop-blur lg:bottom-0 lg:left-60">
        <div className="mx-auto max-w-2xl lg:max-w-4xl">
          {done ? (
            <Button variant="outline" size="lg" className="w-full" onClick={() => reopen.mutate()}>Reopen</Button>
          ) : (
            <Button size="lg" className="w-full" onClick={() => complete.mutate()}>
              <Check className="h-5 w-5" /> Mark done
            </Button>
          )}
        </div>
      </div>

      {/* Reassign picker */}
      <Sheet open={pickerOpen} onOpenChange={setPickerOpen} title="Reassign to">
        <div className="space-y-1.5">
          {task.assignable.map((a) => (
            <button
              key={a.id}
              onClick={() => reassign.mutate(a.id)}
              disabled={a.id === task.assignee?.id}
              className="flex w-full items-center gap-2.5 rounded-md border border-border px-3 py-2.5 text-left text-sm hover:bg-muted disabled:opacity-50"
            >
              <Avatar name={a.name} /> {a.name}
              {a.id === task.assignee?.id ? <span className="ml-auto text-xs text-muted-foreground">current</span> : null}
            </button>
          ))}
        </div>
      </Sheet>

      {/* Make-recurring picker */}
      <Sheet open={recurOpen} onOpenChange={setRecurOpen} title="Make this recurring">
        <div className="space-y-4">
          <div>
            <p className="mb-1.5 text-sm font-medium">Repeat on</p>
            <div className="flex flex-wrap gap-1.5">
              {WEEK.map(([d, label]) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => toggleDay(d)}
                  className={cn(
                    "h-9 w-9 rounded-full border text-xs font-medium",
                    days.includes(d) ? "border-primary bg-primary text-primary-foreground" : "border-border",
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">Time (optional)</label>
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className="mt-1 block w-full rounded-md border border-input bg-card px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </div>
          <p className="text-xs text-muted-foreground">
            This one-time task becomes a daily-style recurring task — a fresh copy appears on each chosen day.
          </p>
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setRecurOpen(false)}>Cancel</Button>
            <Button disabled={days.length === 0 || makeRecurring.isPending} onClick={() => makeRecurring.mutate()}>
              {makeRecurring.isPending ? "Saving…" : "Start repeating"}
            </Button>
          </div>
        </div>
      </Sheet>
    </div>
  );
}

function InfoRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 px-4 py-2.5">
      <dt className="w-24 shrink-0 text-xs text-muted-foreground">{label}</dt>
      <dd className="min-w-0 flex-1">{children}</dd>
    </div>
  );
}
