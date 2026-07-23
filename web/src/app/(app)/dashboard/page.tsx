"use client";

// The admin dashboard. Two jobs, in this order:
//   1. THE BRIEFING — the day written as prose (AI when a key is configured,
//      deterministic otherwise). It answers "how did today go?" in one read;
//      every figure behind it folds away under "More" so the page opens calm.
//   2. THE SHAPE — the same day as charts: attendance over the fortnight,
//      syllabus pace, homework health, fee collection. A number tells you
//      where you are; the shape tells you where you're heading.
// Everything below that is work: alerts you can turn into tasks, then sessions.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, CalendarClock, Camera, ChevronDown, ChevronUp,
  RefreshCw, Send, Sparkles, Wand2,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  ChartCard, Donut, Gauge, PulseArea, RowBars, StatTile, STATUS_COLOR, toneForPct,
  type ChartRow,
} from "@/components/charts";
import { SetupGate } from "@/components/school/setup-gate";
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
import type { DashboardAlert, DashboardOverview } from "@/lib/school-types";

const dayTick = (iso: string) => {
  const d = new Date(`${iso}T00:00:00`);
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
};

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

// ── the briefing ──────────────────────────────────────────────────────────────

/** The day, written. The summary is the page's opening sentence and the only
 * thing an admin must read; sections, capture gaps and wins live under More. */
function Briefing() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: ["daily-report"], queryFn: () => schoolApi.dailyReport() });
  const regen = useMutation({
    mutationFn: () => schoolApi.regenerateReport(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["daily-report"] }); toast.success("Report rewritten"); },
    onError: (e) => showApiError(e, "Could not refresh"),
  });

  if (isLoading) {
    return <div className="mb-6 h-36 animate-pulse rounded-xl border border-border bg-card" />;
  }
  if (!data) return null;

  const { risks, ambiguities, wins, summary, summary_source } = data.highlights;
  const written = summary?.trim()
    || "Today's figures are in — open the report for the detail.";
  const detailCount = data.sections.length + (ambiguities.length ? 1 : 0) + (wins.length ? 1 : 0);

  return (
    <section className="mb-6 overflow-hidden rounded-xl border border-border bg-card">
      <div className="p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5" /> Today’s briefing
          </span>
          <span className="text-xs text-muted-foreground">· {data.for_date}</span>
          <Badge tone={risks.length ? "warning" : "success"}>
            {risks.length ? `${risks.length} need${risks.length === 1 ? "s" : ""} attention` : "all calm"}
          </Badge>
          <div className="ml-auto flex items-center gap-1">
            <Button size="sm" variant="ghost" title="Rewrite from today’s figures"
              onClick={() => regen.mutate()} disabled={regen.isPending}>
              <RefreshCw className={`h-3.5 w-3.5 ${regen.isPending ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* The one thing to read. Wide leading, short measure — this is prose. */}
        <p className="max-w-[62ch] text-[15px] leading-relaxed text-foreground">{written}</p>

        {risks.length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {risks.slice(0, 4).map((r, i) => (
              <li key={i} className="inline-flex items-center gap-1.5 rounded-full border border-danger/25 bg-danger/8 px-2.5 py-1 text-xs">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-danger" />
                {r}
              </li>
            ))}
            {risks.length > 4 ? (
              <li className="inline-flex items-center rounded-full px-2 py-1 text-xs text-muted-foreground">
                +{risks.length - 4} more
              </li>
            ) : null}
          </ul>
        ) : null}
      </div>

      <div className="flex items-center gap-3 border-t border-border bg-muted/25 px-5 py-2.5">
        <button type="button" onClick={() => setOpen((v) => !v)}
          className="inline-flex items-center gap-1 text-xs font-medium text-foreground hover:underline">
          {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {open ? "Hide the detail" : `More — ${detailCount} section${detailCount === 1 ? "" : "s"}`}
        </button>
        <span className="ml-auto text-xs text-muted-foreground">
          {summary_source === "ai" ? "Written by TrackBit AI from today’s captures" : "Assembled from today’s captures"}
        </span>
      </div>

      {open ? (
        <div className="grid gap-x-8 gap-y-4 border-t border-border p-5 sm:grid-cols-2">
          {data.sections.map((s) => (
            <div key={s.heading}>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{s.heading}</p>
              <ul className="mt-1 space-y-0.5">
                {s.lines.map((l, i) => <li key={i} className="text-sm">{l}</li>)}
              </ul>
            </div>
          ))}
          {ambiguities.length > 0 ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-warning">Worth a look</p>
              <ul className="mt-1 space-y-0.5">
                {ambiguities.map((a, i) => <li key={i} className="text-sm">{a}</li>)}
              </ul>
            </div>
          ) : null}
          {wins.length > 0 ? (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-success">Wins</p>
              <ul className="mt-1 space-y-0.5">
                {wins.map((w, i) => <li key={i} className="text-sm">{w}</li>)}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

// ── the shape ────────────────────────────────────────────────────────────────

function PulseRow({ data }: { data: DashboardOverview | undefined }) {
  const att = data?.attendance;
  const today = att?.today ?? null;
  const trend = (att?.days ?? []).map((d) => d.present_pct);
  const capturedToday = (att?.classes_today ?? []).reduce((s, c) => s + c.periods_marked, 0);
  const expectedToday = (att?.classes_today ?? []).reduce((s, c) => s + c.periods_expected, 0);
  const hw = data?.homework.overall_completion;
  const totalRag = (data?.rag_green ?? 0) + (data?.rag_amber ?? 0) + (data?.rag_red ?? 0);
  const onTrackPct = totalRag ? Math.round(((data?.rag_green ?? 0) / totalRag) * 100) : null;

  return (
    <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile
        label="Attendance today"
        value={today?.present_pct != null ? `${today.present_pct}%` : "—"}
        sub={today ? `${today.absent} absent · ${today.late} late` : "nothing marked yet"}
        tone={today?.present_pct == null ? "neutral" : today.present_pct >= 90 ? "green" : today.present_pct >= 80 ? "amber" : "red"}
        trend={trend}
      />
      <StatTile
        label="Periods captured today"
        value={expectedToday ? `${capturedToday}/${expectedToday}` : String(capturedToday)}
        sub={expectedToday ? `${Math.round((capturedToday / expectedToday) * 100)}% of the timetable` : "no timetable for today"}
        tone={!expectedToday ? "neutral" : capturedToday >= expectedToday ? "green" : capturedToday >= expectedToday / 2 ? "amber" : "red"}
      />
      <StatTile
        label="Syllabus on track"
        value={onTrackPct != null ? `${onTrackPct}%` : "—"}
        sub={totalRag ? `${data?.rag_green ?? 0} of ${totalRag} class-subjects` : "no plans yet"}
        tone={onTrackPct == null ? "neutral" : onTrackPct >= 80 ? "green" : onTrackPct >= 60 ? "amber" : "red"}
        href="/plan/week"
      />
      {data?.fees ? (
        <StatTile
          label="Fees collected"
          value={money(data.fees.collected_fee)}
          sub={`${money(data.fees.overdue_amount)} overdue`}
          href="/fees"
        />
      ) : (
        <StatTile
          label={`Homework done (${data?.homework.window_days ?? 14}d)`}
          value={hw != null ? `${Math.round(hw * 100)}%` : "—"}
          sub={hw != null ? "across every class" : "no checks recorded"}
          tone={hw == null ? "neutral" : hw >= 0.75 ? "green" : hw >= 0.6 ? "amber" : "red"}
        />
      )}
    </div>
  );
}

function ShapeGrid({ data }: { data: DashboardOverview }) {
  const att = data.attendance;
  const attRows: ChartRow[] = att.days.map((d) => ({ x: dayTick(d.date), pct: d.present_pct }));
  const ragSlices = [
    { label: "On track", value: data.rag_green, color: STATUS_COLOR.green },
    { label: "Slipping", value: data.rag_amber, color: STATUS_COLOR.amber },
    { label: "Behind", value: data.rag_red, color: STATUS_COLOR.red },
  ].filter((s) => s.value > 0);
  const ragTotal = data.rag_green + data.rag_amber + data.rag_red;

  const hwRows: ChartRow[] = data.homework.classes
    .filter((c) => c.completion != null)
    .map((c) => ({ x: c.class_label, pct: Math.round((c.completion ?? 0) * 100) }));
  const classRows: ChartRow[] = att.classes_today
    .filter((c) => c.present_pct != null)
    .map((c) => ({ x: c.class_label, pct: c.present_pct }));

  const feePct = data.fees && Number(data.fees.total_fee) > 0
    ? (Number(data.fees.collected_fee) / Number(data.fees.total_fee)) * 100
    : null;

  return (
    <div className="mb-6 grid gap-4 lg:grid-cols-2">
      <ChartCard
        title={`Attendance, last ${att.window_days} days`}
        hint="Share of student-periods present. Only days with marked periods appear."
        className="lg:col-span-2">
        {attRows.length > 1 ? (
          <PulseArea rows={attRows} dataKey="pct" label="Present" yUnit="%" yDomain={[0, 100]} height={170} />
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Not enough marked days yet — the line starts once two days are captured.
          </p>
        )}
      </ChartCard>

      <ChartCard title="Syllabus pace" hint="Every class-subject, rated against its approved plan.">
        {ragTotal ? (
          <Donut slices={ragSlices} centerValue={String(ragTotal)} centerLabel="class-subjects" />
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">No plans approved yet.</p>
        )}
      </ChartCard>

      <ChartCard title="Attendance by class, today" hint="Present share per class from today’s marked periods.">
        {classRows.length ? (
          <RowBars rows={classRows} dataKey="pct" unit="%" max={100}
            height={Math.max(140, classRows.length * 30)}
            colorFor={(r) => toneForPct(r.pct as number, { good: 90, fair: 80 })} />
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">No attendance marked today yet.</p>
        )}
      </ChartCard>

      <ChartCard title={`Homework completion (${data.homework.window_days}d)`}
        hint="Done vs set, per class. Under 60% raises an alert.">
        {hwRows.length ? (
          <RowBars rows={hwRows} dataKey="pct" unit="%" max={100}
            height={Math.max(140, hwRows.length * 30)}
            colorFor={(r) => toneForPct(r.pct as number, { good: 75, fair: 60 })} />
        ) : (
          <p className="py-8 text-center text-sm text-muted-foreground">No homework checks recorded yet.</p>
        )}
      </ChartCard>

      {data.fees ? (
        <ChartCard title="Fee collection" hint="Collected against the year’s billed total.">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <Gauge value={feePct} label={money(data.fees.collected_fee)}
              sub={`of ${money(data.fees.total_fee)} billed`}
              color={feePct != null && feePct >= 75 ? STATUS_COLOR.green : STATUS_COLOR.amber} />
            <div className="text-right text-sm">
              <p className="text-muted-foreground">Overdue</p>
              <p className="text-lg font-semibold tabular-nums text-warning">{money(data.fees.overdue_amount)}</p>
              <Link href="/fees" className="text-xs text-muted-foreground underline">Open fees</Link>
            </div>
          </div>
        </ChartCard>
      ) : null}
    </div>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────

function DashboardInner() {
  const { yearId } = useYear();
  const [alertFor, setAlertFor] = useState<DashboardAlert | null>(null);
  const [digestOpen, setDigestOpen] = useState(false);
  const { data } = useQuery({ queryKey: ["dashboard", yearId], queryFn: () => schoolApi.dashboard(yearId ?? undefined), enabled: !!yearId });
  const { data: pendingCaptures = [] } = useQuery({
    queryKey: ["captures", "pending"],
    queryFn: () => schoolApi.captures(),
    select: (rows) => rows.filter((r) => r.status === "uploaded" || r.status === "parsed"),
  });

  return (
    <div>
      <SetupGate />
      <div className="mb-6 flex items-center justify-between">
        <PageHeader title="Dashboard" subtitle="Is the school teaching well, right now?" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <Button size="sm" variant="outline" onClick={() => setDigestOpen(true)}><Wand2 className="h-4 w-4" /> Digest</Button>
        </div>
      </div>

      <Briefing />

      {/* Photo score captures waiting on a human (SC-4) — a pending review is actionable. */}
      {pendingCaptures.length > 0 ? (
        <Link href="/students/scores"
          className="mb-6 flex items-center gap-3 rounded-lg border border-[color:var(--warning,#8a6d1a)]/40 bg-[color:var(--warning,#8a6d1a)]/5 px-4 py-3 text-sm hover:bg-[color:var(--warning,#8a6d1a)]/10">
          <Camera className="h-4 w-4 shrink-0" />
          <span className="min-w-0 flex-1">
            <span className="font-medium">{pendingCaptures.length} photo capture{pendingCaptures.length === 1 ? "" : "s"} waiting for review</span>
            <span className="ml-1 text-muted-foreground">— test scores aren’t saved until someone confirms them.</span>
          </span>
        </Link>
      ) : null}

      <PulseRow data={data} />
      {data ? <ShapeGrid data={data} /> : null}

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

      {/* Today's sessions */}
      <section className="mb-6">
        <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><CalendarClock className="h-4 w-4" /> Today’s sessions</h2>
        {!data || data.sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sessions recorded today.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
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

      <AlertToTaskSheet alert={alertFor} onClose={() => setAlertFor(null)} />
      <DigestSheet open={digestOpen} onClose={() => setDigestOpen(false)} yearId={yearId} />
    </div>
  );
}

export default function DashboardPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <DashboardInner />
    </AuthGuard>
  );
}
