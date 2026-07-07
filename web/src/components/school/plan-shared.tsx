"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Lock, Plus, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { ClassSubject, SchoolClass } from "@/lib/school-types";

export const RAG: Record<string, "success" | "warning" | "neutral"> = {
  green: "success", amber: "warning", red: "warning", none: "neutral",
};
export const weekLabel = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

/**
 * Shared class → class-subject selection for the Plan area's Syllabus and Week
 * plan tabs. Derives the effective pick (user's choice if still valid, else the
 * first available) with no setState-in-effect.
 */
export function useClassSubjectPick(yearId: string | null) {
  const [pickedClass, setPickedClass] = useState("");
  const [pickedCs, setPickedCs] = useState("");
  const { data: classes = [] } = useQuery({ queryKey: ["classes", yearId], queryFn: () => schoolApi.classes(yearId!), enabled: !!yearId });
  const classId = classes.some((c) => c.id === pickedClass) ? pickedClass : (classes[0]?.id ?? "");
  const { data: subjects = [] } = useQuery({ queryKey: ["class-subjects", classId], queryFn: () => schoolApi.classSubjects(classId), enabled: !!classId });
  const csId = subjects.some((s) => s.id === pickedCs) ? pickedCs : (subjects[0]?.id ?? "");
  return { classes, classId, setClassId: setPickedClass, subjects, csId, setCsId: setPickedCs };
}

export function ClassSelect({ classes, classId, onChange }: {
  classes: SchoolClass[];
  classId: string;
  onChange: (v: string) => void;
}) {
  return (
    <select className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm" value={classId} onChange={(e) => onChange(e.target.value)}>
      {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
    </select>
  );
}

export function SubjectSelect({ subjects, csId, onChange }: {
  subjects: ClassSubject[];
  csId: string;
  onChange: (v: string) => void;
}) {
  return (
    <select className="rounded-md border border-border bg-card px-2 py-1.5 text-sm" value={csId} onChange={(e) => onChange(e.target.value)}>
      {subjects.map((s) => <option key={s.id} value={s.id}>{s.subject_name}</option>)}
    </select>
  );
}

export function SyllabusEditor({ csId, canEdit }: { csId: string; canEdit: boolean }) {
  const qc = useQueryClient();
  const [unitTitle, setUnitTitle] = useState("");
  const [topicFor, setTopicFor] = useState<string | null>(null);
  const [topicTitle, setTopicTitle] = useState("");
  const { data: units = [] } = useQuery({ queryKey: ["syllabus", csId], queryFn: () => schoolApi.syllabus(csId) });
  const inv = () => qc.invalidateQueries({ queryKey: ["syllabus", csId] });

  const addUnit = useMutation({ mutationFn: () => schoolApi.addUnit({ class_subject_id: csId, title: unitTitle.trim() }), onSuccess: () => { inv(); setUnitTitle(""); }, onError: (e) => showApiError(e, "Could not add") });
  const addTopic = useMutation({ mutationFn: (unitId: string) => schoolApi.addTopic({ unit_id: unitId, title: topicTitle.trim(), est_periods: 3 }), onSuccess: () => { inv(); setTopicTitle(""); setTopicFor(null); }, onError: (e) => showApiError(e, "Could not add") });
  const delUnit = useMutation({ mutationFn: (id: string) => schoolApi.deleteUnit(id), onSuccess: inv });
  const delTopic = useMutation({ mutationFn: (id: string) => schoolApi.deleteTopic(id), onSuccess: inv });

  return (
    <div className="space-y-3">
      {units.map((u) => (
        <div key={u.id} className="rounded-lg border border-border bg-card p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-sm font-semibold">{u.title}</p>
            {canEdit ? <button onClick={() => delUnit.mutate(u.id)} className="text-muted-foreground hover:text-danger"><Trash2 className="h-3.5 w-3.5" /></button> : null}
          </div>
          <ul className="space-y-1">
            {u.topics.map((t) => (
              <li key={t.id} className="flex items-center justify-between text-sm">
                <span>{t.title} <span className="text-xs text-muted-foreground">· {t.est_periods}p</span></span>
                {canEdit ? <button onClick={() => delTopic.mutate(t.id)} className="text-muted-foreground hover:text-danger"><Trash2 className="h-3 w-3" /></button> : null}
              </li>
            ))}
          </ul>
          {canEdit ? (
            topicFor === u.id ? (
              <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (topicTitle.trim()) addTopic.mutate(u.id); }}>
                <Input autoFocus className="h-8" placeholder="Topic" value={topicTitle} onChange={(e) => setTopicTitle(e.target.value)} />
                <Button size="sm" type="submit">Add</Button>
              </form>
            ) : (
              <button onClick={() => setTopicFor(u.id)} className="mt-2 text-xs text-primary hover:underline">+ topic</button>
            )
          ) : null}
        </div>
      ))}
      {canEdit ? (
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (unitTitle.trim()) addUnit.mutate(); }}>
          <Input placeholder="New chapter" value={unitTitle} onChange={(e) => setUnitTitle(e.target.value)} />
          <Button size="sm" type="submit"><Plus className="h-4 w-4" /> Chapter</Button>
        </form>
      ) : null}
    </div>
  );
}

export function PlanView({ csId, canEdit, canApprove }: { csId: string; canEdit: boolean; canApprove: boolean }) {
  const qc = useQueryClient();
  const { data: plan } = useQuery({ queryKey: ["plan", csId], queryFn: () => schoolApi.plan(csId) });
  const inv = () => { qc.invalidateQueries({ queryKey: ["plan", csId] }); qc.invalidateQueries({ queryKey: ["forecast"] }); };
  const draft = useMutation({ mutationFn: () => schoolApi.draftPlan(csId), onSuccess: () => { inv(); toast.success("Plan drafted"); }, onError: (e) => showApiError(e, "Could not draft") });
  const approve = useMutation({ mutationFn: () => schoolApi.approvePlan(csId), onSuccess: () => { inv(); toast.success("Baseline locked"); }, onError: (e) => showApiError(e, "Could not approve") });

  const byWeek = new Map<string, string[]>();
  plan?.entries.forEach((e) => { byWeek.set(e.week_start, [...(byWeek.get(e.week_start) ?? []), e.topic_title]); });

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        {plan?.status === "approved" ? (
          <Badge tone="success"><Lock className="h-3 w-3" /> Baseline locked</Badge>
        ) : plan?.status === "draft" ? (
          <Badge tone="warning">Draft</Badge>
        ) : (
          <span className="text-sm text-muted-foreground">No plan yet.</span>
        )}
        {canEdit && plan?.status !== "approved" ? (
          <Button size="sm" variant="outline" onClick={() => draft.mutate()} disabled={draft.isPending}>
            <Sparkles className="h-4 w-4" /> {plan?.status === "draft" ? "Re-draft" : "Draft plan"}
          </Button>
        ) : null}
        {canApprove && plan?.status === "draft" ? (
          <Button size="sm" onClick={() => approve.mutate()} disabled={approve.isPending}><CheckCircle2 className="h-4 w-4" /> Approve</Button>
        ) : null}
      </div>
      {plan && plan.entries.length > 0 ? (
        <div className="space-y-1">
          {[...byWeek.entries()].map(([wk, topics]) => (
            <div key={wk} className="flex gap-3 rounded-md border border-border bg-card px-3 py-2 text-sm">
              <span className="w-20 shrink-0 font-medium text-muted-foreground">{weekLabel(wk)}</span>
              <span>{topics.join(", ")}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
