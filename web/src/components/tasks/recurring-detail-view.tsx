"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check, Repeat2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useCelebration } from "@/components/celebration/celebration-provider";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";
import { dayLabel, priorityMeta, recurrenceSummary } from "@/lib/format";
import type { RecurringDay, RecurringTemplate } from "@/lib/types";
import { cn } from "@/lib/utils";

const WEEK = [
  ["mon", "M"], ["tue", "T"], ["wed", "W"], ["thu", "T"],
  ["fri", "F"], ["sat", "S"], ["sun", "S"],
] as const;

const STATE: Record<string, { dot: string; label: string }> = {
  done: { dot: "bg-success", label: "Done" },
  missed: { dot: "bg-warning", label: "Missed" },
  open: { dot: "border-2 border-muted-foreground/40", label: "Open" },
  scheduled: { dot: "bg-muted", label: "Scheduled" },
  cancelled: { dot: "bg-muted", label: "Skipped" },
};

function dateLabel(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function RecurringDetailView({ templateId }: { templateId: string }) {
  const qc = useQueryClient();
  const router = useRouter();
  const { onCompletion } = useCelebration();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["recurring-history", templateId],
    queryFn: () => appApi.templateHistory(templateId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["recurring-history", templateId] });
    qc.invalidateQueries({ queryKey: ["home"] });
    qc.invalidateQueries({ queryKey: ["boards"] });
  };

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => appApi.updateTemplate(templateId, body),
    onSuccess: invalidate,
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not save"),
  });
  const complete = useMutation({
    mutationFn: (day: RecurringDay) => appApi.completeTask(day.instance_id!),
    onSuccess: () => { onCompletion(); invalidate(); toast.success("Done ✓"); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not complete"),
  });
  const stop = useMutation({
    mutationFn: () => appApi.deleteTemplate(templateId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["boards"] });
      qc.invalidateQueries({ queryKey: ["home"] });
      toast.success("Stopped repeating");
      router.back();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not stop"),
  });

  if (isLoading) return <div className="h-60 animate-pulse rounded-lg bg-muted" />;
  if (isError || !data) {
    return (
      <EmptyState
        title="Recurring task not found"
        body="It may have been removed."
        action={<Button onClick={() => router.push("/boards")}>Back to boards</Button>}
      />
    );
  }

  const t = data.template;
  const doneCount = data.days.filter((d) => d.status === "done").length;
  const tracked = data.days.filter((d) => d.status !== "scheduled").length;
  const prio = priorityMeta(t.priority);

  return (
    <div className="pb-12">
      <div className="mb-3 flex items-center justify-between">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Back
        </button>
        {/* Recurring toggle (on) — turning it off stops repeating. */}
        <button
          onClick={() => stop.mutate()}
          className="inline-flex items-center gap-2 rounded-md border border-primary bg-accent px-3 py-1.5 text-sm font-medium text-accent-foreground hover:bg-accent/70"
        >
          <Repeat2 className="h-4 w-4" /> Recurring · on
        </button>
      </div>

      {/* Editable name */}
      <input
        defaultValue={t.title}
        onBlur={(e) => {
          const v = e.target.value.trim();
          if (v && v !== t.title) save.mutate({ title: v });
          else e.target.value = t.title;
        }}
        onKeyDown={(e) => { if (e.key === "Enter") e.currentTarget.blur(); }}
        className="w-full rounded-md border border-transparent bg-transparent px-1 py-0.5 text-2xl font-semibold tracking-tight hover:border-border focus:border-border focus:outline-none"
        aria-label="Task name"
      />
      <textarea
        defaultValue={t.description ?? ""}
        rows={2}
        onBlur={(e) => {
          const v = e.target.value;
          if (v !== (t.description ?? "")) save.mutate({ description: v || null });
        }}
        placeholder="Add a description…"
        className="mt-1 w-full resize-y rounded-md border border-transparent bg-transparent px-1 py-1 text-sm hover:border-border focus:border-border focus:outline-none"
      />

      {/* Info */}
      <div className="mt-5">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Details</h2>
        <div className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card text-sm">
          <InfoRow label="Owner">
            {t.default_assignee ? (
              <span className="flex items-center gap-1.5"><Avatar name={t.default_assignee.name} /> {t.default_assignee.name}</span>
            ) : <span className="text-muted-foreground">Unassigned (claimable)</span>}
          </InfoRow>
          <InfoRow label="Priority">
            {t.priority > 0 ? (
              <span className={cn("rounded px-2 py-0.5 text-xs font-medium", prio.cls)}>{prio.label}</span>
            ) : <span className="text-muted-foreground">None</span>}
          </InfoRow>
          <InfoRow label="Category">{t.category ? t.category : <span className="text-muted-foreground">—</span>}</InfoRow>
          <InfoRow label="Board">{t.board_name}</InfoRow>
          <InfoRow label="Track record">{doneCount}/{tracked} done</InfoRow>
          <InfoRow label="Created">{dayLabel(t.created_at)}</InfoRow>
        </div>
      </div>

      {/* Repeat schedule */}
      <div className="mt-6">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Repeats — {recurrenceSummary(t.recurrence)}
        </h2>
        <RepeatEditor template={t} onSaved={invalidate} />
      </div>

      {/* Per-day record */}
      <div className="mt-6">
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Daily record — done vs missed
        </h2>
        {data.days.length === 0 ? (
          <p className="rounded-lg border border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
            No occurrences yet — the first one will appear here.
          </p>
        ) : (
          <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-card">
            {data.days.map((d) => {
              const s = STATE[d.status] ?? STATE.scheduled;
              return (
                <li key={d.date} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <span className={cn("h-3 w-3 shrink-0 rounded-full", s.dot)} />
                  <span className="flex-1">{dateLabel(d.date)}</span>
                  <span className="text-xs text-muted-foreground">
                    {d.status === "done" && d.completed_by_name ? `by ${d.completed_by_name}` : s.label}
                  </span>
                  {d.status === "open" && d.instance_id ? (
                    <Button size="sm" variant="outline" onClick={() => complete.mutate(d)}>
                      <Check className="h-4 w-4" /> Done
                    </Button>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Upcoming */}
      {data.upcoming.length > 0 ? (
        <div className="mt-6">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Upcoming</h2>
          <div className="flex flex-wrap gap-2">
            {data.upcoming.map((u) => (
              <span key={u} className="rounded-full border border-border bg-card px-3 py-1 text-xs">{dateLabel(u)}</span>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function RepeatEditor({ template, onSaved }: { template: RecurringTemplate; onSaved: () => void }) {
  const weekly = template.recurrence.freq === "weekly";
  const [days, setDays] = useState<string[]>(weekly ? template.recurrence.days ?? [] : []);
  const [time, setTime] = useState(template.recurrence.time ?? "");

  const save = useMutation({
    mutationFn: () =>
      appApi.updateTemplate(template.id, {
        recurrence: { freq: "weekly", days, ...(time ? { time } : {}) },
      }),
    onSuccess: () => { onSaved(); toast.success("Schedule updated"); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not update"),
  });

  if (!weekly) {
    return (
      <p className="rounded-lg border border-border bg-card px-4 py-3 text-sm text-muted-foreground">
        {recurrenceSummary(template.recurrence)} — edit weekly schedules here; change others by recreating the task.
      </p>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="mb-1.5 text-xs text-muted-foreground">Repeat on</p>
      <div className="flex flex-wrap gap-1.5">
        {WEEK.map(([d, label]) => (
          <button
            key={d}
            type="button"
            onClick={() => setDays((c) => (c.includes(d) ? c.filter((x) => x !== d) : [...c, d]))}
            className={cn(
              "h-9 w-9 rounded-full border text-xs font-medium",
              days.includes(d) ? "border-primary bg-primary text-primary-foreground" : "border-border",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="mt-3 flex items-end gap-2">
        <div>
          <label className="text-xs text-muted-foreground">Time (optional)</label>
          <input
            type="time"
            value={time}
            onChange={(e) => setTime(e.target.value)}
            className="mt-0.5 block rounded-md border border-input bg-card px-2 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          />
        </div>
        <Button size="sm" disabled={days.length === 0 || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save schedule"}
        </Button>
      </div>
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
