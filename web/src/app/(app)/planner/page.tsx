"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, ListChecks, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { CalendarEventType } from "@/lib/school-types";

const TYPE_META: Record<CalendarEventType, { label: string; tone: "warning" | "neutral" | "primary" | "success" }> = {
  holiday: { label: "Holiday", tone: "warning" },
  exam_block: { label: "Exam block", tone: "neutral" },
  event: { label: "Event", tone: "primary" },
  celebration: { label: "Celebration", tone: "success" },
};

const fmt = (d: string) => new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

function AddEventForm({ yearId }: { yearId: string }) {
  const qc = useQueryClient();
  const [type, setType] = useState<CalendarEventType>("holiday");
  const [title, setTitle] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  const create = useMutation({
    mutationFn: () => schoolApi.createEvent({
      academic_year_id: yearId, type, title: title.trim(),
      start_date: start, end_date: end || start,
      affects_teaching: type !== "event" ? true : false,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["calendar", yearId] });
      toast.success("Added to calendar");
      setTitle(""); setStart(""); setEnd("");
    },
    onError: (e) => showApiError(e, "Could not add event"),
  });

  return (
    <form className="flex flex-wrap items-end gap-2 rounded-xl border border-border bg-card p-4"
          onSubmit={(e) => { e.preventDefault(); if (title && start) create.mutate(); }}>
      <div>
        <Label>Type</Label>
        <select className="rounded-md border border-border bg-card px-2 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value as CalendarEventType)}>
          {Object.entries(TYPE_META).map(([v, m]) => <option key={v} value={v}>{m.label}</option>)}
        </select>
      </div>
      <div className="min-w-40 flex-1"><Label>Title</Label><Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Diwali Break" /></div>
      <div><Label>From</Label><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></div>
      <div><Label>To</Label><Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} /></div>
      <Button size="sm" type="submit" disabled={create.isPending || !title || !start}><Plus className="h-4 w-4" /> Add</Button>
    </form>
  );
}

function PlannerInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin" || me?.org_role === "coordinator";
  const { yearId } = useYear();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["calendar", yearId],
    queryFn: () => schoolApi.calendarSummary(yearId!),
    enabled: !!yearId,
  });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteEvent(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["calendar", yearId] }); toast.success("Removed"); },
    onError: (e) => showApiError(e, "Could not remove"),
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <PageHeader title="Planner" subtitle="School calendar & effective teaching days" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <Link href="/planner/plan"><Button size="sm" variant="outline"><ListChecks className="h-4 w-4" /> Syllabus & Plan</Button></Link>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Effective teaching days</p>
          <p className="mt-1 text-3xl font-semibold text-primary">{data?.teaching_days ?? "—"}</p>
          <p className="mt-1 text-xs text-muted-foreground">across the whole year</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Calendar entries</p>
          <p className="mt-1 text-3xl font-semibold">{data?.events.length ?? 0}</p>
          <p className="mt-1 text-xs text-muted-foreground">holidays · exams · events</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground">Working week</p>
          <p className="mt-1 text-3xl font-semibold">{data ? data.working_weekdays.length : "—"}<span className="text-base font-normal text-muted-foreground"> days</span></p>
          <p className="mt-1 text-xs text-muted-foreground">Mon–Sat by default</p>
        </div>
      </div>

      {canEdit && yearId ? <div className="mb-6"><AddEventForm yearId={yearId} /></div> : null}

      <h2 className="mb-2 text-sm font-semibold">Calendar</h2>
      {!data || data.events.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No calendar entries yet.
        </p>
      ) : (
        <div className="space-y-2">
          {data.events.map((e) => (
            <div key={e.id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
              <CalendarDays className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{e.title}</p>
                <p className="text-xs text-muted-foreground">
                  {fmt(e.start_date)}{e.end_date !== e.start_date ? ` – ${fmt(e.end_date)}` : ""}
                  {e.affects_teaching ? " · reduces teaching days" : ""}
                </p>
              </div>
              <Badge tone={TYPE_META[e.type].tone}>{TYPE_META[e.type].label}</Badge>
              {canEdit ? (
                <button onClick={() => remove.mutate(e.id)} aria-label="Remove" className="text-muted-foreground hover:text-danger">
                  <Trash2 className="h-4 w-4" />
                </button>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PlannerPage() {
  return (
    <AuthGuard allow={["admin", "coordinator", "teacher"]}>
      <PlannerInner />
    </AuthGuard>
  );
}
