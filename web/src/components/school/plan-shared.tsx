"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Lock, LockOpen, Plus, Sparkles, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { ClassSubject, PlanTerm, SchoolClass, Term } from "@/lib/school-types";

export const RAG: Record<string, "success" | "warning" | "neutral"> = {
  green: "success", amber: "warning", red: "warning", none: "neutral",
  // Not a RAG colour: no finish date can be computed while chapters are unsized.
  unplanned: "warning",
};
/** What the pace row should say when there is no forecast to show. */
export const forecastLabel = (status: string, unestimated: number) =>
  status === "none" ? "no plan"
    : status === "unplanned" ? `${unestimated} chapter${unestimated === 1 ? "" : "s"} unsized`
      : status;
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

/** A topic's period estimate: a number, or "—" with an inline box to set it.
 * Sizing a chapter when its term begins is the whole term-wise planning flow, so
 * it lives on the topic row rather than behind a dialog. */
function TopicEstimate({ topicId, est, canEdit, onSaved }: {
  topicId: string; est: number | null; canEdit: boolean; onSaved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(est?.toString() ?? "");
  const save = useMutation({
    mutationFn: () => schoolApi.setTopicEstimate(topicId, value.trim() ? Number(value) : null),
    onSuccess: () => { setEditing(false); onSaved(); },
    onError: (e) => showApiError(e, "Could not set periods"),
  });

  if (!canEdit) {
    return est === null
      ? <span className="text-xs text-warning">· not sized</span>
      : <span className="text-xs text-muted-foreground">· {est}p</span>;
  }
  if (editing) {
    return (
      <form className="inline-flex items-center gap-1" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
        <Input autoFocus type="number" min={1} max={40} className="h-6 w-16 text-xs" value={value}
          onChange={(e) => setValue(e.target.value)} onBlur={() => save.mutate()} />
        <span className="text-xs text-muted-foreground">p</span>
      </form>
    );
  }
  return (
    <button onClick={() => { setValue(est?.toString() ?? ""); setEditing(true); }}
      className={est === null ? "text-xs text-warning hover:underline" : "text-xs text-muted-foreground hover:underline"}>
      · {est === null ? "set periods" : `${est}p`}
    </button>
  );
}

export function SyllabusEditor({ csId, canEdit, terms = [] }: {
  csId: string; canEdit: boolean; terms?: Term[];
}) {
  const qc = useQueryClient();
  const [unitTitle, setUnitTitle] = useState("");
  const [unitTerm, setUnitTerm] = useState("");
  const [topicFor, setTopicFor] = useState<string | null>(null);
  const [topicTitle, setTopicTitle] = useState("");
  const { data: units = [] } = useQuery({ queryKey: ["syllabus", csId], queryFn: () => schoolApi.syllabus(csId) });
  const inv = () => {
    qc.invalidateQueries({ queryKey: ["syllabus", csId] });
    qc.invalidateQueries({ queryKey: ["plan", csId] });
    qc.invalidateQueries({ queryKey: ["forecast"] });
  };

  const addUnit = useMutation({ mutationFn: () => schoolApi.addUnit({ class_subject_id: csId, title: unitTitle.trim(), term_id: unitTerm || null }), onSuccess: () => { inv(); setUnitTitle(""); }, onError: (e) => showApiError(e, "Could not add") });
  // A new chapter's topics start UNSIZED. Recording the portion and estimating it
  // are different acts, months apart — defaulting to 3 would fake the estimate.
  const addTopic = useMutation({ mutationFn: (unitId: string) => schoolApi.addTopic({ unit_id: unitId, title: topicTitle.trim() }), onSuccess: () => { inv(); setTopicTitle(""); setTopicFor(null); }, onError: (e) => showApiError(e, "Could not add") });
  const delUnit = useMutation({ mutationFn: (id: string) => schoolApi.deleteUnit(id), onSuccess: inv });
  const delTopic = useMutation({ mutationFn: (id: string) => schoolApi.deleteTopic(id), onSuccess: inv });

  const termName = (id: string | null) => (id ? terms.find((t) => t.id === id)?.name : undefined);

  return (
    <div className="space-y-3">
      {units.map((u) => {
        const label = termName(u.term_id);
        const unsized = u.topics.filter((t) => t.est_periods === null).length;
        return (
          <div key={u.id} className="rounded-lg border border-border bg-card p-3">
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold">{u.title}</p>
                {label ? <Badge tone="neutral">{label}</Badge> : null}
                {unsized > 0 ? <Badge tone="warning">{unsized} unsized</Badge> : null}
              </div>
              {canEdit ? <button onClick={() => delUnit.mutate(u.id)} className="text-muted-foreground hover:text-danger"><Trash2 className="h-3.5 w-3.5" /></button> : null}
            </div>
            <ul className="space-y-1">
              {u.topics.map((t) => (
                <li key={t.id} className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-1">
                    {t.title} <TopicEstimate topicId={t.id} est={t.est_periods} canEdit={canEdit} onSaved={inv} />
                  </span>
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
        );
      })}
      {canEdit ? (
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (unitTitle.trim()) addUnit.mutate(); }}>
          <Input placeholder="New chapter" value={unitTitle} onChange={(e) => setUnitTitle(e.target.value)} />
          {terms.length ? (
            <select className="rounded-md border border-border bg-card px-2 py-1.5 text-sm" value={unitTerm} onChange={(e) => setUnitTerm(e.target.value)}>
              <option value="">No term</option>
              {terms.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          ) : null}
          <Button size="sm" type="submit"><Plus className="h-4 w-4" /> Chapter</Button>
        </form>
      ) : null}
    </div>
  );
}

export function PlanView({ csId, canEdit, canApprove }: { csId: string; canEdit: boolean; canApprove: boolean }) {
  const qc = useQueryClient();
  const [pickedTerm, setPickedTerm] = useState<string | null>(null);
  const { data: plan } = useQuery({ queryKey: ["plan", csId], queryFn: () => schoolApi.plan(csId) });
  const inv = () => { qc.invalidateQueries({ queryKey: ["plan", csId] }); qc.invalidateQueries({ queryKey: ["forecast"] }); };

  const terms = plan?.terms ?? [];
  const termed = terms.filter((t) => t.term_id);
  // The selected window: the user's pick if still valid, else the first term that
  // is not yet locked (the one they came here to plan), else the first.
  const active: PlanTerm | undefined = termed.length
    ? (termed.find((t) => t.term_id === pickedTerm) ?? termed.find((t) => !t.approved) ?? termed[0])
    : undefined;
  const termId = active?.term_id ?? null;

  const draft = useMutation({ mutationFn: () => schoolApi.draftPlan(csId, termId), onSuccess: () => { inv(); toast.success("Plan drafted"); }, onError: (e) => showApiError(e, "Could not draft") });
  const approve = useMutation({ mutationFn: () => schoolApi.approvePlan(csId, termId), onSuccess: () => { inv(); toast.success("Baseline locked"); }, onError: (e) => showApiError(e, "Could not approve") });
  const unapprove = useMutation({ mutationFn: () => schoolApi.unapprovePlan(csId, termId), onSuccess: () => { inv(); toast.success("Baseline unlocked"); }, onError: (e) => showApiError(e, "Could not un-approve") });

  // With terms, "locked" and "unsized" are per-window; without, they are the plan's.
  const locked = active ? active.approved : plan?.status === "approved";
  const unsized = active ? active.unestimated_topics : (plan?.unestimated_topics ?? 0);
  const hasPlan = plan && plan.status !== "none";

  const byWeek = new Map<string, string[]>();
  plan?.entries.forEach((e) => { byWeek.set(e.week_start, [...(byWeek.get(e.week_start) ?? []), e.topic_title]); });

  return (
    <div>
      {termed.length > 1 ? (
        <div className="mb-3 flex items-center gap-1">
          {termed.map((t) => (
            <button key={t.term_id} onClick={() => setPickedTerm(t.term_id)}
              className={`rounded-md border px-2.5 py-1 text-xs ${t.term_id === termId ? "border-primary bg-primary/10 font-medium" : "border-border text-muted-foreground hover:bg-muted"}`}>
              {t.name}
              {t.approved ? <Lock className="ml-1 inline h-3 w-3" /> : t.unestimated_topics > 0 ? <span className="ml-1 text-warning">·{t.unestimated_topics}</span> : null}
            </button>
          ))}
        </div>
      ) : null}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        {locked ? (
          <Badge tone="success"><Lock className="h-3 w-3" /> Baseline locked</Badge>
        ) : hasPlan ? (
          <Badge tone="warning">Draft</Badge>
        ) : (
          <span className="text-sm text-muted-foreground">No plan yet.</span>
        )}
        {unsized > 0 ? (
          <Badge tone="warning">{unsized} chapter{unsized === 1 ? "" : "s"} not sized</Badge>
        ) : null}

        {canEdit && !locked ? (
          <Button size="sm" variant="outline" onClick={() => draft.mutate()} disabled={draft.isPending}>
            <Sparkles className="h-4 w-4" /> {hasPlan ? "Re-draft" : "Draft plan"}{active ? ` ${active.name}` : ""}
          </Button>
        ) : null}
        {/* Approving a window with unsized chapters would lock a plan that silently
            omits them, so the button is not offered — the server refuses it too. */}
        {canApprove && !locked && hasPlan && unsized === 0 ? (
          <Button size="sm" onClick={() => approve.mutate()} disabled={approve.isPending}><CheckCircle2 className="h-4 w-4" /> Approve{active ? ` ${active.name}` : ""}</Button>
        ) : null}
        {canApprove && locked ? (
          <Button size="sm" variant="outline" onClick={() => unapprove.mutate()} disabled={unapprove.isPending}>
            <LockOpen className="h-4 w-4" /> Un-approve{active ? ` ${active.name}` : ""}
          </Button>
        ) : null}
      </div>

      {unsized > 0 ? (
        <p className="mb-3 text-xs text-muted-foreground">
          Unsized chapters are recorded but not scheduled. Set their periods on the Syllabus tab
          {active ? ` when ${active.name} begins` : ""} — until then there is no finish date to forecast.
        </p>
      ) : null}

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
