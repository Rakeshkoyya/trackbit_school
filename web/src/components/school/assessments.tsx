"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, TrendingDown } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { BandRow } from "@/lib/school-types";

export const TIER_TONE: Record<string, "success" | "warning" | "neutral"> = { A: "success", B: "neutral", C: "warning" };

/** Class-only picker shared by the Students area's Scores / Bands / Trends tabs. */
export function useClassPick(yearId: string | null) {
  const [picked, setPicked] = useState("");
  const { data: classes = [] } = useQuery({ queryKey: ["classes", yearId], queryFn: () => schoolApi.classes(yearId!), enabled: !!yearId });
  const classId = classes.some((c) => c.id === picked) ? picked : (classes[0]?.id ?? "");
  return { classes, classId, setClassId: setPicked };
}

export function ScoreGrid({ cycleId, classId, canVerify }: { cycleId: string; classId: string; canVerify: boolean }) {
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<string, number>>({});
  const { data: grid } = useQuery({ queryKey: ["grid", cycleId, classId], queryFn: () => schoolApi.scoreGrid(cycleId, classId) });
  const key = (sid: string, cid: string) => `${sid}:${cid}`;
  const cellVal = (sid: string, cid: string) => {
    const k = key(sid, cid);
    if (k in edits) return edits[k];
    return grid?.cells.find((c) => c.student_id === sid && c.column_id === cid)?.score ?? "";
  };
  const save = useMutation({
    mutationFn: () => {
      const rows = Object.entries(edits).map(([k, score]) => {
        const [student_id, column_id] = k.split(":");
        const isSkill = grid!.cycle_type === "diagnostic";
        return { student_id, score, max_score: 100, ...(isSkill ? { skill_area_id: column_id } : { subject_id: column_id }) };
      });
      return schoolApi.saveScores(cycleId, rows);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["grid", cycleId, classId] }); setEdits({}); toast.success("Scores saved"); },
    onError: (e) => showApiError(e, "Could not save"),
  });
  const verify = useMutation({
    mutationFn: () => schoolApi.verifyScores(cycleId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["grid", cycleId, classId] }); toast.success("Verified"); },
    onError: (e) => showApiError(e, "Could not verify"),
  });

  if (!grid) return null;
  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        {grid.verified ? <Badge tone="success"><CheckCircle2 className="h-3 w-3" /> Verified</Badge> : <Badge tone="warning">Unverified</Badge>}
        <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending || !Object.keys(edits).length}>Save</Button>
        {canVerify ? <Button size="sm" variant="outline" onClick={() => verify.mutate()} disabled={verify.isPending}>Verify</Button> : null}
      </div>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
            <tr><th className="px-3 py-2">Student</th>{grid.columns.map((c) => <th key={c.id} className="px-2 py-2">{c.name}</th>)}</tr>
          </thead>
          <tbody>
            {grid.students.map((s) => (
              <tr key={s.student_id} className="border-t border-border">
                <td className="whitespace-nowrap px-3 py-1.5 font-medium">{s.full_name}</td>
                {grid.columns.map((c) => (
                  <td key={c.id} className="px-2 py-1">
                    <input type="number" className="w-14 rounded border border-border bg-card px-1.5 py-1 text-sm"
                      value={cellVal(s.student_id, c.id)}
                      onChange={(e) => setEdits((p) => ({ ...p, [key(s.student_id, c.id)]: Number(e.target.value) }))} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {grid.students.length === 0 ? <p className="mt-2 text-sm text-muted-foreground">No students in this class.</p> : null}
    </div>
  );
}

function InterventionSheet({ row, termId, onClose }: { row: BandRow | null; termId: string | null; onClose: () => void }) {
  const [goal, setGoal] = useState("");
  const [items, setItems] = useState("Daily hard-words drill\n15 min reading practice");
  const [board, setBoard] = useState("");
  const { data: boards } = useQuery({ queryKey: ["boards"], queryFn: appApi.boards });
  const list = boards ? [...boards.my_boards, ...boards.other_public] : [];
  const effBoard = board || list[0]?.id || "";
  const create = useMutation({
    mutationFn: () => schoolApi.createIntervention({
      student_id: row!.student_id, term_id: termId!, goal_text: goal.trim(), target_tier: "B",
      board_id: effBoard, items: items.split("\n").map((i) => i.trim()).filter(Boolean) }),
    onSuccess: () => { toast.success("Intervention created · tasks assigned"); setGoal(""); onClose(); },
    onError: (e) => showApiError(e, "Could not create"),
  });
  return (
    <Sheet open={!!row} onOpenChange={(v) => { if (!v) onClose(); }} title={row ? `Intervention · ${row.full_name}` : ""}>
      {row ? (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (goal.trim() && effBoard && termId) create.mutate(); }}>
          <div><Label>Goal</Label><Input placeholder="Move C→B in reading" value={goal} onChange={(e) => setGoal(e.target.value)} /></div>
          <div><Label>Checklist (one per line → tasks for the class teacher)</Label>
            <textarea className="min-h-24 w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={items} onChange={(e) => setItems(e.target.value)} /></div>
          <div><Label>Task board</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={effBoard} onChange={(e) => setBoard(e.target.value)}>
              {list.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select></div>
          <Button type="submit" className="w-full" disabled={create.isPending || !goal.trim() || !termId}>Create intervention</Button>
        </form>
      ) : null}
    </Sheet>
  );
}

export function BandBoard({ classId, termId, canEdit }: { classId: string; termId: string | null; canEdit: boolean }) {
  const qc = useQueryClient();
  const [ivFor, setIvFor] = useState<BandRow | null>(null);
  const { data: board } = useQuery({ queryKey: ["bands", classId, termId], queryFn: () => schoolApi.bandBoard(classId, termId ?? undefined) });
  const setBand = useMutation({
    mutationFn: (v: { student_id: string; tier: string }) => schoolApi.setBand({ student_id: v.student_id, term_id: termId!, tier: v.tier }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["bands", classId, termId] }); toast.success("Band set"); },
    onError: (e) => showApiError(e, "Could not set band"),
  });
  return (
    <div>
      <p className="mb-2 text-xs text-muted-foreground">Bands are staff-only support tiers — never shared with parents.</p>
      <div className="space-y-2">
        {board?.rows.map((r) => (
          <div key={r.student_id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-2.5 text-sm">
            <div className="min-w-0 flex-1">
              <p className="font-medium">{r.full_name}</p>
              <p className="text-xs text-muted-foreground">{r.latest_pct != null ? `latest ${r.latest_pct}%` : "no scores"}{r.suggested_tier ? ` · suggested ${r.suggested_tier}` : ""}</p>
            </div>
            {r.current_tier ? <Badge tone={TIER_TONE[r.current_tier]}>Band {r.current_tier}</Badge> : null}
            {canEdit && termId ? (
              <select className="rounded-md border border-border bg-card px-1.5 py-1 text-sm" value={r.current_tier ?? ""}
                onChange={(e) => e.target.value && setBand.mutate({ student_id: r.student_id, tier: e.target.value })}>
                <option value="">set…</option>
                {["A", "B", "C"].map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            ) : null}
            {canEdit && r.current_tier === "C" ? (
              <Button size="sm" variant="outline" onClick={() => setIvFor(r)}>Intervention</Button>
            ) : null}
          </div>
        ))}
      </div>
      <InterventionSheet row={ivFor} termId={termId} onClose={() => setIvFor(null)} />
    </div>
  );
}

export function TrendsView({ classId }: { classId: string }) {
  const { data: trends = [] } = useQuery({ queryKey: ["trends", classId], queryFn: () => schoolApi.trends(classId) });
  if (!trends.length) return <p className="text-sm text-muted-foreground">No test cycles yet.</p>;
  return (
    <div className="space-y-2">
      {trends.map((t) => (
        <div key={t.subject_id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-2.5 text-sm">
          <div className="min-w-0 flex-1">
            <p className="font-medium">{t.subject_name}</p>
            <p className="text-xs text-muted-foreground">{t.points.map((p) => `${p.cycle_name} ${p.avg_pct}%`).join(" → ")}</p>
          </div>
          {t.weak ? <Badge tone="warning"><TrendingDown className="h-3 w-3" /> weak</Badge> : null}
        </div>
      ))}
    </div>
  );
}

export function NewCycleSheet({ open, onOpenChange, termId, yearId }: { open: boolean; onOpenChange: (v: boolean) => void; termId: string | null; yearId: string | null }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [type, setType] = useState("diagnostic");
  const [d, setD] = useState("");
  const create = useMutation({
    mutationFn: () => schoolApi.createCycle({ term_id: termId!, type, name: name.trim(), date: d }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cycles", yearId] }); toast.success("Cycle created"); setName(""); setD(""); onOpenChange(false); },
    onError: (e) => showApiError(e, "Could not create"),
  });
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="New assessment cycle">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (name.trim() && d && termId) create.mutate(); }}>
        <div><Label>Name</Label><Input placeholder="Term-start diagnostic" value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div><Label>Type</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={type} onChange={(e) => setType(e.target.value)}>
            <option value="diagnostic">Diagnostic (skill areas)</option>
            <option value="unit_test">Unit test (subjects)</option>
            <option value="term_exam">Term exam (subjects)</option>
          </select></div>
        <div><Label>Date</Label><Input type="date" value={d} onChange={(e) => setD(e.target.value)} /></div>
        <Button type="submit" className="w-full" disabled={create.isPending || !name.trim() || !d || !termId}>Create</Button>
      </form>
    </Sheet>
  );
}
