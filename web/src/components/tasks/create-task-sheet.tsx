"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { PRIORITY } from "@/lib/format";
import type { RecurrenceRule } from "@/lib/types";
import { cn } from "@/lib/utils";

const UNASSIGNED = "__unassigned__";
const WEEK = [
  ["mon", "Mo"], ["tue", "Tu"], ["wed", "We"], ["thu", "Th"],
  ["fri", "Fr"], ["sat", "Sa"], ["sun", "Su"],
] as const;
type Freq = "daily" | "weekdays" | "weekly" | "monthly";

export function CreateTaskSheet({
  open,
  onOpenChange,
  defaultBoardId,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  defaultBoardId?: string;
}) {
  const qc = useQueryClient();
  const { me } = useAuth();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState("");
  const [priority, setPriority] = useState(0);
  const [boardId, setBoardId] = useState(defaultBoardId ?? "");
  const [assignee, setAssignee] = useState(UNASSIGNED);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  // Recurrence
  const [repeats, setRepeats] = useState(false);
  const [freq, setFreq] = useState<Freq>("daily");
  const [weeklyDays, setWeeklyDays] = useState<string[]>(["mon"]);
  const [monthlyDay, setMonthlyDay] = useState(1);
  const [isCritical, setIsCritical] = useState(false);

  const boards = useQuery({ queryKey: ["boards"], queryFn: appApi.boards, enabled: open });
  const members = useQuery({ queryKey: ["members"], queryFn: appApi.members, enabled: open });

  const allBoards = boards.data ? [...boards.data.my_boards, ...boards.data.other_public] : [];
  const effectiveBoard = boardId || defaultBoardId || allBoards[0]?.id || "";
  const selectedBoard = allBoards.find((b) => b.id === effectiveBoard);
  // On a privacy board, a regular member can only put a task on themselves.
  const selfAssignOnly =
    !!selectedBoard &&
    selectedBoard.task_scope === "assigned" &&
    !selectedBoard.is_owner &&
    me?.org_role !== "admin";

  const categories = useQuery({
    queryKey: ["board-categories", effectiveBoard],
    queryFn: () => appApi.boardCategories(effectiveBoard),
    enabled: open && !!effectiveBoard,
  });

  function buildRule(): RecurrenceRule {
    const rule: RecurrenceRule = { freq };
    if (time) rule.time = time;
    if (freq === "weekly") rule.days = weeklyDays;
    if (freq === "monthly") rule.day = monthlyDay;
    return rule;
  }

  const create = useMutation({
    mutationFn: (): Promise<unknown> => {
      // selfAssignOnly: let the backend auto-assign to the creator (send null).
      const assignee_id = selfAssignOnly ? null : assignee === UNASSIGNED ? null : assignee;
      const cat = category.trim() || null;
      if (repeats) {
        return appApi.createTemplate({
          board_id: effectiveBoard,
          title: title.trim(),
          description: description.trim() || null,
          category: cat,
          priority,
          recurrence: buildRule(),
          default_assignee_id: assignee_id,
          is_critical: isCritical,
        });
      }
      let due_at: string | null = null;
      if (date) due_at = new Date(`${date}T${time || "09:00"}`).toISOString();
      return appApi.createTask({
        board_id: effectiveBoard,
        title: title.trim(),
        description: description.trim() || null,
        category: cat,
        priority,
        assignee_id,
        due_at,
        all_day: !time && !!date,
        is_critical: isCritical,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["home"] });
      qc.invalidateQueries({ queryKey: ["boards"] });
      qc.invalidateQueries({ queryKey: ["board-table", effectiveBoard] });
      qc.invalidateQueries({ queryKey: ["board-tasks", effectiveBoard] });
      qc.invalidateQueries({ queryKey: ["board-categories", effectiveBoard] });
      qc.invalidateQueries({ queryKey: ["templates", effectiveBoard] });
      toast.success(repeats ? "Recurring task created" : "Task created");
      reset();
      onOpenChange(false);
    },
    onError: (e) => showApiError(e, "Could not create task"),
  });

  function reset() {
    setTitle("");
    setDescription("");
    setCategory("");
    setPriority(0);
    setAssignee(UNASSIGNED);
    setDate("");
    setTime("");
    setRepeats(false);
    setFreq("daily");
    setWeeklyDays(["mon"]);
    setMonthlyDay(1);
    setIsCritical(false);
  }

  function toggleDay(d: string) {
    setWeeklyDays((cur) => (cur.includes(d) ? cur.filter((x) => x !== d) : [...cur, d]));
  }

  const canSubmit =
    !!title.trim() && !!effectiveBoard && (!repeats || freq !== "weekly" || weeklyDays.length > 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="New task">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) create.mutate();
        }}
      >
        <div>
          <Label htmlFor="t-title">Title</Label>
          <Input id="t-title" autoFocus required value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="t-desc">Details</Label>
          <textarea
            id="t-desc"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="flex w-full rounded-md border border-input bg-card px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <div>
          <Label htmlFor="t-category">Category</Label>
          <Input
            id="t-category"
            list="t-category-list"
            placeholder="Optional tag"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
          <datalist id="t-category-list">
            {(categories.data ?? []).map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </div>
        <div>
          <Label>Priority</Label>
          <div className="flex gap-2">
            {PRIORITY.map((p) => (
              <button
                key={p.v}
                type="button"
                onClick={() => setPriority(p.v)}
                className={cn(
                  "flex-1 rounded-md border px-3 py-2 text-sm",
                  priority === p.v ? "border-primary bg-accent" : "border-border",
                )}
              >
                {p.v === 0 ? "None" : p.label}
              </button>
            ))}
          </div>
        </div>
        <button
          type="button"
          onClick={() => setIsCritical((v) => !v)}
          className={cn(
            "flex w-full items-center justify-between rounded-md border px-3 py-2.5 text-sm",
            isCritical ? "border-warning bg-warning-soft/40" : "border-border",
          )}
        >
          <span className="flex items-center gap-2">
            ⏰ <span className="font-medium">Critical</span>
            <span className="text-xs text-muted-foreground">alarm-style reminder (Pro)</span>
          </span>
          <span
            className={cn(
              "relative h-5 w-9 rounded-full transition-colors",
              isCritical ? "bg-warning" : "bg-muted",
            )}
          >
            <span
              className={cn(
                "absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all",
                isCritical ? "left-4" : "left-0.5",
              )}
            />
          </span>
        </button>
        <div>
          <Label htmlFor="t-board">Board</Label>
          <select
            id="t-board"
            value={effectiveBoard}
            onChange={(e) => setBoardId(e.target.value)}
            className="h-11 w-full rounded-md border border-input bg-card px-3 text-sm"
          >
            {allBoards.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label htmlFor="t-assignee">Assign</Label>
          {selfAssignOnly ? (
            <p className="rounded-md border border-border bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground">
              Assigned to you — this board only shows you your own tasks.
            </p>
          ) : (
            <select
              id="t-assignee"
              value={assignee}
              onChange={(e) => setAssignee(e.target.value)}
              className="h-11 w-full rounded-md border border-input bg-card px-3 text-sm"
            >
              <option value={UNASSIGNED}>Leave unassigned (anyone claims)</option>
              {members.data?.members.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.name}
                </option>
              ))}
            </select>
          )}
        </div>

        {!repeats ? (
          <div className="flex gap-3">
            <div className="flex-1">
              <Label htmlFor="t-date">Due date</Label>
              <Input id="t-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div className="flex-1">
              <Label htmlFor="t-time">Time</Label>
              <Input id="t-time" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
            </div>
          </div>
        ) : null}

        {/* Repeats */}
        <div className="rounded-md border border-border p-3">
          <label className="flex items-center justify-between">
            <span className="text-sm font-medium">Repeats?</span>
            <input
              type="checkbox"
              checked={repeats}
              onChange={(e) => setRepeats(e.target.checked)}
              className="h-4 w-8 appearance-none rounded-full bg-muted transition-colors checked:bg-primary"
            />
          </label>

          {repeats ? (
            <div className="mt-3 space-y-3">
              <div className="grid grid-cols-2 gap-2">
                {(
                  [
                    ["daily", "Daily"],
                    ["weekdays", "Weekdays"],
                    ["weekly", "Weekly"],
                    ["monthly", "Monthly"],
                  ] as const
                ).map(([f, label]) => (
                  <button
                    key={f}
                    type="button"
                    onClick={() => setFreq(f)}
                    className={cn(
                      "rounded-md border px-3 py-2 text-sm",
                      freq === f ? "border-primary bg-accent" : "border-border",
                    )}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {freq === "weekly" ? (
                <div className="flex flex-wrap gap-1.5">
                  {WEEK.map(([d, label]) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => toggleDay(d)}
                      className={cn(
                        "h-9 w-9 rounded-full border text-xs font-medium",
                        weeklyDays.includes(d) ? "border-primary bg-primary text-primary-foreground" : "border-border",
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              ) : null}

              {freq === "monthly" ? (
                <div>
                  <Label htmlFor="t-monthday">Day of month</Label>
                  <Input
                    id="t-monthday"
                    type="number"
                    min={1}
                    max={31}
                    value={monthlyDay}
                    onChange={(e) => setMonthlyDay(Math.min(31, Math.max(1, Number(e.target.value))))}
                  />
                </div>
              ) : null}

              <div>
                <Label htmlFor="t-rtime">Time (optional)</Label>
                <Input id="t-rtime" type="time" value={time} onChange={(e) => setTime(e.target.value)} />
              </div>
            </div>
          ) : null}
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" disabled={create.isPending || !canSubmit}>
            {create.isPending ? "Saving…" : "Save"}
          </Button>
        </div>
      </form>
    </Sheet>
  );
}
