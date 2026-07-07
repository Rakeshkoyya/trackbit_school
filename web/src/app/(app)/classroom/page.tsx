"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, ClipboardCheck, Send, Users2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { HomeworkPending, MyDayClass } from "@/lib/school-types";

function HomeworkSheet({ cs, onClose }: { cs: MyDayClass | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  const add = useMutation({
    mutationFn: () => schoolApi.addHomework({ class_subject_id: cs!.class_subject_id, text: text.trim(), due_date: due || null }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["my-day"] });
      toast.success(`Homework set · ${res.notified_count} parents notified`);
      setText(""); setDue(""); onClose();
    },
    onError: (e) => showApiError(e, "Could not set homework"),
  });
  return (
    <Sheet open={!!cs} onOpenChange={(v) => { if (!v) onClose(); }} title={cs ? `Homework · ${cs.class_label} ${cs.subject_name}` : ""}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) add.mutate(); }}>
        <Input autoFocus placeholder="e.g. Draw the water cycle" value={text} onChange={(e) => setText(e.target.value)} />
        <div><label className="text-xs text-muted-foreground">Due (optional)</label><Input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></div>
        <Button type="submit" className="w-full" disabled={add.isPending || !text.trim()}>
          <Send className="h-4 w-4" /> {add.isPending ? "Sending…" : "Set homework & notify parents"}
        </Button>
      </form>
    </Sheet>
  );
}

function ClassCard({ c, onHomework }: { c: MyDayClass; onHomework: () => void }) {
  const qc = useQueryClient();
  const log = useMutation({
    mutationFn: (coverage: string) => schoolApi.logLesson({ class_subject_id: c.class_subject_id, topic_id: c.planned_topic_id, coverage }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-day"] }); toast.success("Logged"); },
    onError: (e) => showApiError(e, "Could not log"),
  });
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold">{c.class_label} · {c.subject_name}</p>
          <p className="text-xs text-muted-foreground">
            {c.planned_topic ? `Planned: ${c.planned_topic}` : "No topic planned this week"}
          </p>
        </div>
        {c.logged ? <Badge tone="success"><Check className="h-3 w-3" /> Logged</Badge> : <Badge tone="neutral">Not logged</Badge>}
      </div>
      <div className="flex flex-wrap gap-2">
        {!c.logged ? (
          <>
            <Button size="sm" onClick={() => log.mutate("full")} disabled={log.isPending}>Covered</Button>
            <Button size="sm" variant="outline" onClick={() => log.mutate("partial")} disabled={log.isPending}>Partially</Button>
          </>
        ) : null}
        <Button size="sm" variant={c.homework_set ? "outline" : "ghost"} onClick={onHomework}>
          <BookOpen className="h-4 w-4" /> {c.homework_set ? "Homework set" : "Set homework"}
        </Button>
      </div>
    </div>
  );
}

function HomeworkCheckRow({ hw }: { hw: HomeworkPending }) {
  const qc = useQueryClient();
  const [done, setDone] = useState("");
  const [total, setTotal] = useState("");
  const check = useMutation({
    mutationFn: () => schoolApi.checkHomework(hw.assignment_id, { done_count: Number(done), total_count: Number(total) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-day"] }); toast.success("Recorded"); },
    onError: (e) => showApiError(e, "Could not record"),
  });
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-sm font-medium">{hw.class_label} · {hw.subject_name}</p>
      <p className="mb-2 truncate text-xs text-muted-foreground">{hw.text}</p>
      <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (done && total) check.mutate(); }}>
        <Input className="h-8 w-16" type="number" placeholder="done" value={done} onChange={(e) => setDone(e.target.value)} />
        <span className="text-muted-foreground">/</span>
        <Input className="h-8 w-16" type="number" placeholder="total" value={total} onChange={(e) => setTotal(e.target.value)} />
        <Button size="sm" type="submit" disabled={check.isPending || !done || !total}>Save</Button>
      </form>
    </div>
  );
}

function MyDayInner() {
  const { me } = useAuth();
  const canSeeCompliance = me?.org_role === "admin" || me?.org_role === "coordinator";
  const [hwFor, setHwFor] = useState<MyDayClass | null>(null);
  const { data } = useQuery({ queryKey: ["my-day"], queryFn: schoolApi.myDay });

  return (
    <div>
      <div className="mb-6 flex items-start justify-between">
        <PageHeader title="My Day" subtitle="Log what you taught and set homework — under a minute per class" />
        {canSeeCompliance ? (
          <Link href="/classroom/compliance"><Button size="sm" variant="outline"><Users2 className="h-4 w-4" /> Compliance</Button></Link>
        ) : null}
      </div>

      {data && data.homework_pending.length > 0 ? (
        <section className="mb-6">
          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            <ClipboardCheck className="h-4 w-4" /> Yesterday’s homework — mark completion
          </h2>
          <div className="space-y-2">
            {data.homework_pending.map((hw) => <HomeworkCheckRow key={hw.assignment_id} hw={hw} />)}
          </div>
        </section>
      ) : null}

      <h2 className="mb-2 text-sm font-semibold">Today’s classes</h2>
      {!data || data.classes.length === 0 ? (
        <EmptyState icon={BookOpen} title="No classes assigned to you"
          body="Ask your coordinator to assign your subjects on the Setup → class page." />
      ) : (
        <div className="space-y-3">
          {data.classes.map((c) => <ClassCard key={c.class_subject_id} c={c} onHomework={() => setHwFor(c)} />)}
        </div>
      )}
      <HomeworkSheet cs={hwFor} onClose={() => setHwFor(null)} />
    </div>
  );
}

export default function ClassroomPage() {
  return (
    <AuthGuard allow={["admin", "coordinator", "teacher"]}>
      <MyDayInner />
    </AuthGuard>
  );
}
