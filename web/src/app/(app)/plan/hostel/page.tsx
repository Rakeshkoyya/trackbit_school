"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Moon, Plus, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { SessionKind, SessionSummary } from "@/lib/school-types";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const KINDS: { value: SessionKind; label: string }[] = [
  { value: "study", label: "Study" },
  { value: "homework", label: "Homework" },
  { value: "activity", label: "Activity" },
];
const KIND_TONE: Record<SessionKind, "primary" | "warning" | "success"> = {
  study: "primary", homework: "warning", activity: "success",
};

function BlockSheet({ open, onOpenChange, editing }: {
  open: boolean; onOpenChange: (v: boolean) => void; editing: SessionSummary | null;
}) {
  const qc = useQueryClient();
  const { me } = useAuth();
  const { yearId } = useYear();
  const isAdmin = me?.org_role === "admin";
  const [name, setName] = useState(editing?.name ?? "");
  const [kind, setKind] = useState<SessionKind>(editing?.kind ?? "study");
  const [days, setDays] = useState<number[]>(editing?.weekdays ?? []);
  const [time, setTime] = useState(editing?.time ?? "18:00");
  const [endTime, setEndTime] = useState(editing?.end_time ?? "19:00");
  const [owner, setOwner] = useState<string>(editing?.owner_member_id ?? "");
  const [classIds, setClassIds] = useState<Set<string>>(new Set());
  const [hostellersOnly, setHostellersOnly] = useState(editing?.hostellers_only ?? true);
  const [loadedDetail, setLoadedDetail] = useState(false);

  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId], queryFn: () => schoolApi.classes(yearId || undefined), enabled: open });
  const { data: membersRes } = useQuery({
    queryKey: ["members"], queryFn: appApi.members, enabled: open && isAdmin });
  // For an existing block, pull class links once the sheet opens.
  useQuery({
    queryKey: ["session", editing?.id],
    queryFn: async () => {
      const d = await schoolApi.session(editing!.id);
      if (!loadedDetail) { setClassIds(new Set(d.class_ids)); setLoadedDetail(true); }
      return d;
    },
    enabled: open && !!editing,
  });

  const body = () => ({
    name: name.trim(), kind, weekdays: days, time, end_time: endTime,
    class_ids: [...classIds], hostellers_only: hostellersOnly,
    owner_member_id: owner || null,
  });
  const done = (msg: string) => {
    qc.invalidateQueries({ queryKey: ["sessions"] });
    toast.success(msg);
    onOpenChange(false);
  };
  const create = useMutation({
    mutationFn: () => schoolApi.createSession(body()),
    onSuccess: () => done("Block added"),
    onError: (e) => showApiError(e, "Could not add"),
  });
  const update = useMutation({
    mutationFn: () => schoolApi.updateSession(editing!.id, body()),
    onSuccess: () => done("Block updated"),
    onError: (e) => showApiError(e, "Could not update"),
  });
  const remove = useMutation({
    mutationFn: () => schoolApi.deleteSession(editing!.id),
    onSuccess: () => done("Block removed"),
    onError: (e) => showApiError(e, "Could not remove"),
  });

  const toggleDay = (d: number) => setDays((p) => p.includes(d) ? p.filter((x) => x !== d) : [...p, d]);
  const toggleClass = (id: string) => setClassIds((p) => {
    const n = new Set(p);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const teachers = (membersRes?.members ?? []).filter((m) => m.status === "active" && m.member_id);

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title={editing ? "Edit block" : "New hostel block"}>
      <form className="space-y-4" onSubmit={(e) => {
        e.preventDefault();
        if (!name.trim()) return;
        if (editing) update.mutate(); else create.mutate();
      }}>
        <div><Label>Name</Label><Input placeholder="Evening prep" value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div>
          <Label>Type</Label>
          <div className="flex gap-1">
            {KINDS.map((k) => (
              <button key={k.value} type="button" onClick={() => setKind(k.value)}
                className={`rounded-md border px-3 py-1.5 text-xs ${kind === k.value ? "border-primary bg-accent" : "border-border"}`}>
                {k.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <Label>Days</Label>
          <div className="flex flex-wrap gap-1">
            {DOW.map((d, i) => (
              <button key={d} type="button" onClick={() => toggleDay(i)}
                className={`rounded-md border px-2.5 py-1.5 text-xs ${days.includes(i) ? "border-primary bg-accent" : "border-border"}`}>{d}</button>
            ))}
          </div>
        </div>
        <div className="flex gap-3">
          <div className="flex-1"><Label>Starts</Label><Input type="time" value={time} onChange={(e) => setTime(e.target.value)} /></div>
          <div className="flex-1"><Label>Ends</Label><Input type="time" value={endTime} onChange={(e) => setEndTime(e.target.value)} /></div>
        </div>
        {isAdmin ? (
          <div>
            <Label>Teacher</Label>
            <select value={owner} onChange={(e) => setOwner(e.target.value)}
              className="h-9 w-full rounded-md border border-border bg-card px-2 text-sm">
              <option value="">Me</option>
              {teachers.map((t) => <option key={t.member_id} value={t.member_id!}>{t.name}</option>)}
            </select>
          </div>
        ) : null}
        <div>
          <Label>Classes</Label>
          <div className="flex flex-wrap gap-1">
            {classes.map((c) => (
              <button key={c.id} type="button" onClick={() => toggleClass(c.id)}
                className={`rounded-md border px-2.5 py-1.5 text-xs ${classIds.has(c.id) ? "border-primary bg-accent" : "border-border"}`}>
                {c.name}{c.section ?? ""}
              </button>
            ))}
          </div>
          <label className="mt-2 flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={hostellersOnly} onChange={(e) => setHostellersOnly(e.target.checked)} />
            Hostellers only
          </label>
          <p className="mt-1 text-xs text-muted-foreground">
            The roster follows the class list — new admissions join automatically.
          </p>
        </div>
        <div className="flex gap-2">
          <Button type="submit" className="flex-1" disabled={create.isPending || update.isPending || !name.trim()}>
            {editing ? "Save block" : "Add block"}
          </Button>
          {editing ? (
            <Button type="button" variant="outline" onClick={() => remove.mutate()} disabled={remove.isPending}>
              Remove
            </Button>
          ) : null}
        </div>
      </form>
    </Sheet>
  );
}

function HostelInner() {
  const router = useRouter();
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";
  const [sheet, setSheet] = useState<{ open: boolean; editing: SessionSummary | null }>({ open: false, editing: null });
  const { data: sessions = [], isLoading } = useQuery({ queryKey: ["sessions"], queryFn: schoolApi.sessions });
  const active = sessions.filter((s) => s.active);

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Hostel timetable</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {isAdmin ? "Plan the evenings: study, homework and activity blocks." : "Your after-school blocks. Tap one to run it."}
          </p>
        </div>
        {isAdmin ? (
          <Button size="sm" onClick={() => setSheet({ open: true, editing: null })}>
            <Plus className="h-4 w-4" /> Add block
          </Button>
        ) : null}
      </div>
      {!isLoading && active.length === 0 ? (
        <EmptyState icon={Moon} title="No hostel blocks yet"
          body="Add the evening blocks — study hall, homework hour, yoga — and assign a teacher to each. Rosters follow the class lists." />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-7">
          {DOW.map((d, i) => {
            const blocks = active
              .filter((s) => s.weekdays.includes(i))
              .sort((a, b) => (a.time ?? "").localeCompare(b.time ?? ""));
            return (
              <div key={d} className="rounded-lg border border-border bg-card p-2">
                <p className="mb-2 px-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">{d}</p>
                <div className="space-y-1.5">
                  {blocks.length === 0 ? (
                    <p className="px-1 pb-1 text-xs text-muted-foreground/60">—</p>
                  ) : blocks.map((s) => (
                    <button key={s.id}
                      onClick={() => isAdmin ? setSheet({ open: true, editing: s }) : router.push(`/sessions/${s.id}`)}
                      className="w-full rounded-md border border-border bg-background px-2 py-1.5 text-left hover:bg-muted/40">
                      <p className="text-xs font-medium">{s.time}{s.end_time ? `–${s.end_time}` : ""}</p>
                      <p className="truncate text-sm">{s.name}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-1">
                        <Badge tone={KIND_TONE[s.kind]}>{s.kind}</Badge>
                        {s.class_labels.length > 0 ? (
                          <span className="text-[11px] text-muted-foreground">{s.class_labels.join(" · ")}</span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 flex items-center gap-1 text-[11px] text-muted-foreground">
                        {s.teacher_name ? <span>{s.teacher_name}</span> : null}
                        <Users className="h-3 w-3" /> {s.roster_count}
                      </p>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      {sheet.open ? (
        <BlockSheet key={sheet.editing?.id ?? "new"} open={sheet.open}
          onOpenChange={(v) => setSheet((p) => ({ ...p, open: v }))} editing={sheet.editing} />
      ) : null}
    </div>
  );
}

export default function HostelPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <HostelInner />
    </AuthGuard>
  );
}
