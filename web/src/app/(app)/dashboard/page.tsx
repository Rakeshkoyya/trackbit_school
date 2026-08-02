"use client";

// The admin dashboard — the overview. Four bands, in the order an admin reads:
//
//   1. THE BRIEFING — the day written as prose (AI when a key is configured,
//      deterministic otherwise). It answers "how did today go?" in one read;
//      every figure behind it folds away under "More" so the page opens calm.
//   2. WHAT'S WAITING — the derived action rail. Not a description of the
//      school but a list of things this person has to go and do, each linking
//      to the screen that clears it. Empty when nothing is waiting.
//   3. THE MODULES — one block each, carrying a sentence, the two or three
//      figures it rests on, and the named rows behind them. Everything deeper —
//      the heatmaps, the drill-downs, the action rails — belongs to the tabs,
//      which is why they are tabs.
//   4. ALERTS + SESSIONS — the feed that becomes tasks, and the day's sessions.
//
// The big chart grid that used to live here is gone: every one of those charts
// is now on the tab that owns it, and a summary that repeats them is not a
// summary. What survives is the shape *inside* a metric — a sparkline behind a
// number, never a second figure.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, CalendarClock, ChevronDown, ChevronUp, RefreshCw, Send, Sparkles, Wand2, Zap,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { MeterBar, STATUS_COLOR } from "@/components/charts";
import { ActionRail, CustomSection, MetricCell, SectionCard } from "@/components/insights/overview";
import { SetupGate } from "@/components/school/setup-gate";
import { WhatsOnCard } from "@/components/school/whats-on";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useYear } from "@/contexts/year-context";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { eventsApi } from "@/lib/events-api";
import { insightsApi } from "@/lib/insights-api";
import type { QuickAction } from "@/lib/insights-types";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";
import type { DashboardAlert, FeeSummary } from "@/lib/school-types";

const longDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "long", day: "numeric", month: "long",
  });

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
    return <div className="h-36 animate-pulse rounded-xl border border-border bg-card" />;
  }
  if (!data) return null;

  const { risks, ambiguities, wins, summary, summary_source } = data.highlights;
  const written = summary?.trim()
    || "Today's figures are in — open the report for the detail.";
  const detailCount = data.sections.length + (ambiguities.length ? 1 : 0) + (wins.length ? 1 : 0);

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="p-5">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5" /> Today’s briefing
          </span>
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

// ── fees ─────────────────────────────────────────────────────────────────────

/** Fees has no tab of its own — it has a whole screen. The block matches the
 *  module blocks so the overview reads as one board, and it renders only when
 *  the payload carries fees at all (teachers never receive them, §2). */
function FeesSection({ fees }: { fees: FeeSummary }) {
  const total = Number(fees.total_fee);
  const collected = Number(fees.collected_fee);
  const overdue = Number(fees.overdue_amount);
  const outstanding = Math.max(0, total - collected);
  const pct = total > 0 ? Math.round((collected / total) * 100) : null;

  return (
    <CustomSection
      sectionKey="fees" label="Fees" href="/fees"
      headline={pct == null
        ? "Nothing has been billed for this year yet."
        : `${pct}% of the year’s billed fees are in${overdue > 0 ? `, ${money(fees.overdue_amount)} past due.` : "."}`}
      notes={
        <div className="space-y-1.5">
          <MeterBar parts={[
            { value: collected, color: STATUS_COLOR.green, label: "Collected" },
            { value: outstanding, color: STATUS_COLOR.amber, label: "Outstanding" },
          ]} />
          <p className="text-muted-foreground">
            {money(fees.collected_fee)} collected · {money(outstanding)} still to come
          </p>
        </div>
      }>
      <MetricCell label="Collected" value={money(fees.collected_fee)}
        sub={`of ${money(fees.total_fee)} billed`} href="/fees" />
      <MetricCell label="Overdue" value={money(fees.overdue_amount)}
        sub={overdue > 0 ? "past the due date" : "nothing past due"}
        tone={overdue > 0 ? "amber" : "green"} href="/fees" />
      <MetricCell label="Instalments due" value={String(fees.pending_installments)}
        sub="unpaid instalments across the school" href="/fees" />
    </CustomSection>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────

function DashboardInner() {
  const { yearId } = useYear();
  const [alertFor, setAlertFor] = useState<DashboardAlert | null>(null);
  const [digestOpen, setDigestOpen] = useState(false);

  const { data: board, isLoading: boardLoading } = useQuery({
    queryKey: ["insights", "overview", yearId],
    queryFn: () => insightsApi.overview(yearId ?? undefined),
  });
  const { data } = useQuery({
    queryKey: ["dashboard", yearId],
    queryFn: () => schoolApi.dashboard(yearId ?? undefined),
    enabled: !!yearId,
  });
  // V1-7 (D-51): today's specials + what is coming. Read once for the page —
  // it is the same feed the teacher's My Day strip renders, at more depth.
  const { data: whatsOn } = useQuery({
    queryKey: ["whats-on"],
    queryFn: () => eventsApi.whatsOn(),
  });
  const { data: pendingCaptures = [] } = useQuery({
    queryKey: ["captures", "pending"],
    queryFn: () => schoolApi.captures(),
    select: (rows) => rows.filter((r) => r.status === "uploaded" || r.status === "parsed"),
  });

  // The one action the insights board can't know about: photo score captures
  // sit in a different module, and an unreviewed one means marks that are not
  // saved. It goes first — it is the only item here that can lose data.
  const actions: QuickAction[] = [
    ...(pendingCaptures.length ? [{
      key: "captures", label: "Review photo captures", tone: "amber" as const,
      count: pendingCaptures.length, href: "/students/scores",
      detail: `Test scores stay unsaved until someone confirms ${pendingCaptures.length === 1 ? "it" : "them"}`,
    }] : []),
    ...(board?.actions ?? []),
  ];

  const sections = board?.sections ?? [];
  const modules = sections.filter((s) => s.key !== "exams");
  const exams = sections.find((s) => s.key === "exams");

  // An alert the rail already carries is noise: "2 staff away today" under
  // Alerts, right below "Assign cover — 15 periods", is the same fact told
  // twice and worse the second time. Dropped only when the matching action is
  // actually present, so a staff absence with every period covered still gets
  // said once.
  const railKeys = new Set(actions.map((a) => a.key));
  const alerts = (data?.alerts ?? []).filter((a) => {
    if (a.id === "leave:pending") return !railKeys.has("leave");
    if (a.type === "staff") return !railKeys.has("cover") && !railKeys.has("staff_attendance");
    return true;
  });

  return (
    <div>
      <SetupGate />

      <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
        <div className="[&>header]:mb-0">
          <PageHeader
            title="Dashboard"
            subtitle={board
              ? [longDate(board.date), board.period_label].filter(Boolean).join(" · ")
              : "Is the school teaching well, right now?"}
          />
        </div>
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <Button size="sm" variant="outline" onClick={() => setDigestOpen(true)}>
            <Wand2 className="h-4 w-4" /> Digest
          </Button>
        </div>
      </div>

      <div className="mb-6"><Briefing /></div>

      {/* What's waiting — things to do, not things to know. */}
      <section className="mb-6">
        <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
          <Zap className="h-4 w-4" /> What’s waiting
        </h2>
        {boardLoading ? (
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-16 animate-pulse rounded-xl border border-border bg-card" />
            ))}
          </div>
        ) : (
          <ActionRail actions={actions} />
        )}
      </section>

      {/* The modules. Each block summarises its tab and links to it. */}
      <section className="mb-6">
        <h2 className="mb-2 text-sm font-semibold">The board</h2>
        {boardLoading ? (
          <div className="grid gap-4 lg:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-52 animate-pulse rounded-xl border border-border bg-card" />
            ))}
          </div>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {modules.map((s) => <SectionCard key={s.key} section={s} />)}
            {data?.fees ? <FeesSection fees={data.fees} /> : null}
            {exams ? <SectionCard section={exams} /> : null}
          </div>
        )}
      </section>

      {/* V1-7: the read side of a calendar the school has written for a year.
          It sits below the board because it is context, not a task — and above
          alerts because it is often the explanation for one. */}
      <section className="mb-6">
        <WhatsOnCard data={whatsOn} onOpenCalendar="/plan" />
      </section>

      {/* Alerts feed — each becomes a task, or opens the screen that fixes it. */}
      <section className="mb-6">
        <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
          <AlertTriangle className="h-4 w-4" /> Alerts
        </h2>
        {alerts.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
            {data?.alerts.length
              ? "Everything flagged today is already in the rail above."
              : "Nothing needs attention — nicely done."}
          </p>
        ) : (
          <div className="grid gap-2 lg:grid-cols-2">
            {alerts.map((a) => (
              <div key={a.id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
                <span className={`h-2 w-2 shrink-0 rounded-full ${a.severity === "red" ? "bg-danger" : "bg-warning"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{a.title}</p>
                  <p className="text-xs text-muted-foreground">{a.detail}</p>
                </div>
                {/* A staff alert already has a screen that resolves it — send them
                    there rather than making them file a task about it. */}
                {a.type === "staff" ? (
                  <Link href={a.id === "leave:pending" ? "/staff/leave" : "/staff"}
                    className={buttonVariants({ variant: "outline", size: "sm" })}>
                    Open
                  </Link>
                ) : (
                  <Button size="sm" variant="outline" onClick={() => setAlertFor(a)}>Create task</Button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Today's sessions */}
      <section className="mb-6">
        <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
          <CalendarClock className="h-4 w-4" /> Today’s sessions
        </h2>
        {!data || data.sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No sessions recorded today.</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
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
