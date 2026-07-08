"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, BookOpen, CalendarClock, FileText, IndianRupee, RefreshCw, Send, Wand2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { appApi } from "@/lib/app-api";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { money } from "@/lib/school-format";
import { schoolApi } from "@/lib/school-api";
import type { DashboardAlert } from "@/lib/school-types";

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={`mt-1 text-2xl font-semibold ${tone ?? ""}`}>{value}</p>
    </div>
  );
}

function AlertToTaskSheet({ alert, onClose }: { alert: DashboardAlert | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [board, setBoard] = useState("");
  const [title, setTitle] = useState("");
  const { data: boards } = useQuery({ queryKey: ["boards"], queryFn: appApi.boards });
  const list = boards ? [...boards.my_boards, ...boards.other_public] : [];

  // seed the form when an alert opens (derived, no effect)
  const effTitle = title || alert?.title || "";
  const effBoard = board || list[0]?.id || "";

  const create = useMutation({
    mutationFn: () => schoolApi.createTaskFromAlert({ board_id: effBoard, title: effTitle, description: alert?.detail }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["boards"] });
      toast.success("Task created");
      setTitle(""); setBoard(""); onClose();
    },
    onError: (e) => showApiError(e, "Could not create task"),
  });

  return (
    <Sheet open={!!alert} onOpenChange={(v) => { if (!v) { setTitle(""); setBoard(""); onClose(); } }} title="Create task from alert">
      {alert ? (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (effBoard && effTitle) create.mutate(); }}>
          <div><Label>Title</Label><Input value={effTitle} onChange={(e) => setTitle(e.target.value)} /></div>
          <p className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">{alert.detail}</p>
          <div>
            <Label>Board</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={effBoard} onChange={(e) => setBoard(e.target.value)}>
              {list.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </select>
          </div>
          <Button type="submit" className="w-full" disabled={create.isPending || !effBoard || !effTitle}>
            <Send className="h-4 w-4" /> Create task
          </Button>
        </form>
      ) : null}
    </Sheet>
  );
}

function DigestSheet({ open, onClose, yearId }: { open: boolean; onClose: () => void; yearId: string | null }) {
  const { data } = useQuery({ queryKey: ["digest", yearId], queryFn: () => schoolApi.digest(yearId ?? undefined), enabled: open && !!yearId });
  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose(); }} title="Monday digest preview">
      <p className="mb-3 text-xs text-muted-foreground">Delivered on WhatsApp when configured (email meanwhile).</p>
      <pre className="whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-4 text-sm">{data?.text ?? "…"}</pre>
    </Sheet>
  );
}

// The 8 AM report — the day, written by the system (V2-P4 §5.6). Leads the board.
function ReportView() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const { data } = useQuery({ queryKey: ["daily-report"], queryFn: () => schoolApi.dailyReport() });
  const regen = useMutation({
    mutationFn: () => schoolApi.regenerateReport(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["daily-report"] }); toast.success("Report refreshed"); },
    onError: (e) => showApiError(e, "Could not refresh"),
  });
  if (!data) return null;
  const { risks, ambiguities, wins } = data.highlights;
  return (
    <section className="mb-6 rounded-xl border border-border bg-card p-4">
      <div className="mb-2 flex items-center gap-2">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <h2 className="text-sm font-semibold">Daily report · {data.for_date}</h2>
        <Badge tone={risks.length ? "warning" : "success"}>
          {risks.length ? `${risks.length} need attention` : "all calm"}
        </Badge>
        <div className="ml-auto flex items-center gap-1">
          <Button size="sm" variant="ghost" onClick={() => regen.mutate()} disabled={regen.isPending}>
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" variant="outline" onClick={() => setOpen((v) => !v)}>{open ? "Hide" : "Read"}</Button>
        </div>
      </div>

      {risks.length > 0 ? (
        <ul className="mb-1 space-y-0.5">
          {risks.map((r, i) => <li key={i} className="flex gap-2 text-sm"><span className="text-danger">•</span>{r}</li>)}
        </ul>
      ) : null}
      {ambiguities.length > 0 ? (
        <p className="text-xs text-muted-foreground">{ambiguities.length} thing(s) worth a look — open the report.</p>
      ) : null}

      {open ? (
        <div className="mt-3 space-y-3 border-t border-border pt-3">
          {data.sections.map((s) => (
            <div key={s.heading}>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{s.heading}</p>
              <ul className="mt-0.5 space-y-0.5">
                {s.lines.map((l, i) => <li key={i} className="text-sm">{l}</li>)}
              </ul>
            </div>
          ))}
          {ambiguities.length > 0 ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-warning">Worth a look</p>
              <ul className="mt-0.5 space-y-0.5">
                {ambiguities.map((a, i) => <li key={i} className="text-sm">{a}</li>)}
              </ul>
            </div>
          ) : null}
          {wins.length > 0 ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-[#234a37]">Wins</p>
              <ul className="mt-0.5 space-y-0.5">
                {wins.map((w, i) => <li key={i} className="text-sm">{w}</li>)}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

function InsightsInner() {
  const { yearId } = useYear();
  const [alertFor, setAlertFor] = useState<DashboardAlert | null>(null);
  const [digestOpen, setDigestOpen] = useState(false);
  const { data } = useQuery({ queryKey: ["dashboard", yearId], queryFn: () => schoolApi.dashboard(yearId ?? undefined), enabled: !!yearId });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <PageHeader title="Dashboard" subtitle="Is the school teaching well, right now?" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <Button size="sm" variant="outline" onClick={() => setDigestOpen(true)}><Wand2 className="h-4 w-4" /> Digest</Button>
        </div>
      </div>

      <ReportView />

      {/* RAG + fees + homework summary */}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="On track" value={String(data?.rag_green ?? 0)} tone="text-[#234a37]" />
        <Stat label="Behind (amber)" value={String(data?.rag_amber ?? 0)} tone="text-warning" />
        <Stat label="Behind (red)" value={String(data?.rag_red ?? 0)} tone="text-danger" />
        {data?.fees ? (
          <Stat label="Fees collected" value={money(data.fees.collected_fee)} />
        ) : (
          <Stat label="Homework done" value={data?.homework.overall_completion != null ? `${Math.round(data.homework.overall_completion * 100)}%` : "—"} />
        )}
      </div>

      {/* Alerts feed — each with Create task */}
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><AlertTriangle className="h-4 w-4" /> Alerts</h2>
      {!data || data.alerts.length === 0 ? (
        <p className="mb-6 rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">Nothing needs attention — nicely done.</p>
      ) : (
        <div className="mb-6 space-y-2">
          {data.alerts.map((a) => (
            <div key={a.id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
              <span className={`h-2 w-2 shrink-0 rounded-full ${a.severity === "red" ? "bg-danger" : "bg-warning"}`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">{a.title}</p>
                <p className="text-xs text-muted-foreground">{a.detail}</p>
              </div>
              <Button size="sm" variant="outline" onClick={() => setAlertFor(a)}>Create task</Button>
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Today's sessions */}
        <section>
          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><CalendarClock className="h-4 w-4" /> Today’s sessions</h2>
          {!data || data.sessions.length === 0 ? (
            <p className="text-sm text-muted-foreground">No sessions recorded today.</p>
          ) : (
            <div className="space-y-2">
              {data.sessions.map((s) => (
                <div key={s.meeting_id} className="rounded-lg border border-border bg-card px-4 py-3 text-sm">
                  <p className="font-medium">{s.session_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {s.present + s.late}/{s.total} attended · {s.late} late · {s.homework_done} did homework
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Homework health */}
        <section>
          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><BookOpen className="h-4 w-4" /> Homework health (14d)</h2>
          <div className="space-y-2">
            {data?.homework.classes.map((c) => (
              <div key={c.class_label} className="flex items-center justify-between rounded-lg border border-border bg-card px-4 py-2.5 text-sm">
                <span>{c.class_label} <span className="text-xs text-muted-foreground">· {c.assignments} set</span></span>
                <Badge tone={c.completion == null ? "neutral" : c.completion < 0.6 ? "warning" : "success"}>
                  {c.completion == null ? "no data" : `${Math.round(c.completion * 100)}%`}
                </Badge>
              </div>
            ))}
          </div>
        </section>
      </div>

      {data?.fees ? (
        <div className="mt-6 flex items-center gap-3 rounded-xl border border-border bg-card p-4">
          <IndianRupee className="h-5 w-5 text-muted-foreground" />
          <div className="flex-1 text-sm">
            <p className="font-medium">Fee collection</p>
            <p className="text-xs text-muted-foreground">{money(data.fees.collected_fee)} of {money(data.fees.total_fee)} · {money(data.fees.overdue_amount)} overdue</p>
          </div>
        </div>
      ) : null}

      <AlertToTaskSheet alert={alertFor} onClose={() => setAlertFor(null)} />
      <DigestSheet open={digestOpen} onClose={() => setDigestOpen(false)} yearId={yearId} />
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <InsightsInner />
    </AuthGuard>
  );
}
