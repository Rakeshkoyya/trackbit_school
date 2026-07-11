"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Plus, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageLoading } from "@/components/ui/page-loading";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function CreateSessionSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [time, setTime] = useState("16:15");
  const [days, setDays] = useState<number[]>([]);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [q, setQ] = useState("");
  const { data: students = [] } = useQuery({ queryKey: ["students", q], queryFn: () => schoolApi.students({ q: q.trim() || undefined }) });

  const create = useMutation({
    mutationFn: () => schoolApi.createSession({ name: name.trim(), weekdays: days, time, student_ids: [...picked] }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sessions"] });
      toast.success("Session created");
      setName(""); setDays([]); setPicked(new Set()); onOpenChange(false);
    },
    onError: (e) => showApiError(e, "Could not create"),
  });
  const toggleDay = (d: number) => setDays((p) => p.includes(d) ? p.filter((x) => x !== d) : [...p, d]);
  const togglePick = (id: string) => setPicked((p) => {
    const n = new Set(p);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="New session">
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }}>
        <div><Label>Name</Label><Input placeholder="Homework Class 6A" value={name} onChange={(e) => setName(e.target.value)} /></div>
        <div>
          <Label>Days</Label>
          <div className="flex flex-wrap gap-1">
            {DOW.map((d, i) => (
              <button key={d} type="button" onClick={() => toggleDay(i)}
                className={`rounded-md border px-2.5 py-1.5 text-xs ${days.includes(i) ? "border-primary bg-accent" : "border-border"}`}>{d}</button>
            ))}
          </div>
        </div>
        <div><Label>Time</Label><Input type="time" value={time} onChange={(e) => setTime(e.target.value)} /></div>
        <div>
          <Label>Students ({picked.size})</Label>
          <Input className="mb-2" placeholder="Search…" value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="max-h-52 space-y-1 overflow-y-auto rounded-md border border-border p-1">
            {students.map((s) => (
              <label key={s.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-muted/50">
                <input type="checkbox" checked={picked.has(s.id)} onChange={() => togglePick(s.id)} />
                {s.full_name} <span className="text-xs text-muted-foreground">· {s.admission_no}</span>
              </label>
            ))}
          </div>
        </div>
        <Button type="submit" className="w-full" disabled={create.isPending || !name.trim()}>Create session</Button>
      </form>
    </Sheet>
  );
}

function SessionsInner() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const { data: sessions = [], isLoading } = useQuery({ queryKey: ["sessions"], queryFn: schoolApi.sessions });
  const todayDow = (new Date().getDay() + 6) % 7; // JS Sunday=0 → our Monday=0

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Sessions</h1>
        <Button size="sm" onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> New session</Button>
      </div>
      {isLoading ? (
        <PageLoading label="Loading sessions…" />
      ) : sessions.length === 0 ? (
        <EmptyState icon={CalendarClock} title="No sessions yet"
          body="Create a homework class or remedial hour, add its students, then capture attendance in under a minute." />
      ) : (
        <div className="space-y-2">
          {sessions.map((s) => {
            const isToday = s.weekdays.includes(todayDow);
            return (
              <button key={s.id} onClick={() => router.push(`/sessions/${s.id}`)}
                className="flex w-full items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 text-left transition-colors hover:bg-muted/40 active:scale-[0.995]">
                <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-md ${isToday ? "bg-accent text-accent-foreground" : "bg-muted text-muted-foreground"}`}>
                  <CalendarClock className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold">{s.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {s.weekdays.map((d) => DOW[d]).join(" · ") || "no days set"}{s.time ? ` · ${s.time.slice(0, 5)}` : ""}
                  </p>
                </div>
                {isToday ? <Badge tone="primary">today</Badge> : null}
                <Badge tone="neutral"><Users className="h-3 w-3" /> {s.roster_count}</Badge>
              </button>
            );
          })}
        </div>
      )}
      <CreateSessionSheet open={open} onOpenChange={setOpen} />
    </div>
  );
}

export default function SessionsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <SessionsInner />
    </AuthGuard>
  );
}
