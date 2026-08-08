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
  AlertTriangle, CalendarClock, ChevronDown, ChevronUp, RefreshCw, Send, Sparkles,
  UserCheck, Wand2, Zap,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { StaffDayBlock } from "@/components/insights/daybook";
import { BandLegend } from "@/components/insights/band-distribution";
import { ActionRail, CustomSection, MetricCell, SectionCard } from "@/components/insights/overview";
import { PresencePanorama } from "@/components/insights/presence";
import { HomeworkOverviewBlock, OVERVIEW_WINDOW_DAYS } from "@/components/insights/homework";
import { SyllabusPulseBlock } from "@/components/insights/syllabus";
import { CoverSheet } from "@/components/insights/cover-sheet";
import { ReasonSheet, type ReasonTarget } from "@/components/insights/reason-sheet";
import { DayNotice } from "@/components/school/day-notice";
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
import { QuarterRings, YearFeeRing } from "@/components/school/fee-rings";
import type { BandDistribution, CollectionBoard, DashboardAlert } from "@/lib/school-types";

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
 *  module blocks so the overview reads as one board, and it renders only for an
 *  admin (teachers never receive fee figures at all, §2).
 *
 *  It reads `CollectionService.board()`, the same computation `/fees` renders.
 *  It used to read `FeeService.summary()` — four fields, no quarters, and
 *  `opening_dues` excluded — which made this the last surface in the product
 *  still on the old fee arithmetic after V1-12 moved Lucy off it, and directly
 *  contradicted collection.py's own "every fee screen is a rendering of
 *  board()". It also computed `outstanding = total − collected` right here, in
 *  the browser: exactly the pending+overdue blend `Collection` refuses to have
 *  an `outstanding` property in order to prevent (`S-163`). Pending is a
 *  forecast; overdue is a phone call. */
function FeesSection({ board }: { board: CollectionBoard }) {
  const y = board.year;
  const families = new Set(board.defaulters.map((d) => d.student_fee_id)).size;
  const headline = y.billed <= 0
    ? "Nothing has been billed for this year yet."
    : y.due_by_today <= 0
      ? `${money(y.billed)} billed for the year — no instalment has come due yet.`
      : y.shortfall > 0
        ? `${money(y.shortfall)} of what was due by today is not in${
          families ? `, across ${families} ${families === 1 ? "family" : "families"}.` : "."}`
        : `Collection is level with the schedule — ${money(y.collected)} of the ${money(y.due_by_today)} due by today.`;

  return (
    <CustomSection
      sectionKey="fees" label="Fees" href="/fees"
      headline={headline}
      notes={
        <div className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
            By quarter
          </p>
          <QuarterRings quarters={board.quarters} />
          {board.carried ? (
            // D-88: never inside the figures above, and never silently dropped.
            <p className="pt-1 text-[11px] text-muted-foreground">{board.carried.note}</p>
          ) : null}
        </div>
      }>
      <div className="flex-1 px-4 py-3">
        <YearFeeRing year={y} compact />
      </div>
    </CustomSection>
  );
}

/**
 * The support programme's shape (founder 2026-08-04).
 *
 * `S-169` still holds: the headline is the programme's own MOVEMENT sentence,
 * and the distribution explains it underneath. A distribution alone looks
 * identical in a school where nobody has moved for a year, which is exactly why
 * it was kept off the board before — but it answers a question movement cannot:
 * where the support load actually sits, by class and by subject.
 *
 * Client-side off `/bands/distribution`, the same read the ABC bands tab
 * renders in full — the `FeesSection` precedent, and for the same reason: this
 * lives on its own screen and the two must never quote different figures.
 */
function BandsSection({ data }: { data: BandDistribution }) {
  const s = data.school;
  return (
    <CustomSection
      sectionKey="bands" label="ABC bands" href="/bands"
      headline={data.headline}
      notes={
        <div className="space-y-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
            {data.caption}
          </p>
          <BandLegend />
        </div>
      }>
      <div className="flex-1 px-4 py-3">
        <MetricCell label="In Band C" value={s.assessed ? `${s.c_pct}%` : "—"}
          sub={s.assessed ? `${s.c} of ${s.assessed} placements` : "nobody assessed yet"}
          href="/bands" />
      </div>
      <div className="flex-1 px-4 py-3">
        <MetricCell label="Moved up" value={String(data.moved_up)}
          sub={`${data.slipped} slipped this term`} href="/bands/reports" />
      </div>
      <div className="flex-1 px-4 py-3">
        {/* Not assessed is its own number and never red — a class nobody has
            banded is a gap in the record, not a result (ux §5). */}
        <MetricCell label="Not assessed" value={String(s.not_assessed)}
          sub={s.not_assessed ? "placements with no band yet" : "every placement has a band"}
          href="/bands/manage" />
      </div>
    </CustomSection>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────

function DashboardInner() {
  const { yearId } = useYear();
  const [alertFor, setAlertFor] = useState<DashboardAlert | null>(null);
  const [digestOpen, setDigestOpen] = useState(false);
  const [coverFor, setCoverFor] = useState<{ id: string; name: string } | null>(null);
  const [reasonFor, setReasonFor] = useState<ReasonTarget | null>(null);
  // V1-15: the syllabus block is narrowable to a term. Its own state and its own
  // read, so pressing the switcher re-fetches one module rather than all seven.
  const [syllabusTerm, setSyllabusTerm] = useState("");

  const { data: board, isLoading: boardLoading } = useQuery({
    queryKey: ["insights", "overview", yearId],
    queryFn: () => insightsApi.overview(yearId ?? undefined),
  });
  // V1-14: presence is its own read, and it leads the page. Three rings and
  // three named blocks answer "who is in, who is missing, and what do I do
  // about it" — which the single attendance card could state but never resolve.
  const { data: presence, isLoading: presenceLoading } = useQuery({
    queryKey: ["insights", "presence", yearId],
    queryFn: () => insightsApi.presence(yearId ?? undefined),
  });
  // V1-16: the staff day. Its own read for the same reason presence has one —
  // it moves with the bell and the timesheet all morning, while the module
  // blocks below do not, so refetching one must not refetch seven.
  const { data: daybook, isLoading: daybookLoading } = useQuery({
    queryKey: ["insights", "daybook", "glimpse"],
    queryFn: () => insightsApi.daybookGlimpse({ limit: 8 }),
    refetchInterval: 300_000,
  });
  // The SAME window the server composes the block's sentence over — a mismatch
  // here put "430 given" in the headline above stage bars reading 205, which is
  // the one thing this block exists not to do. Its own request like the
  // syllabus pulse, so the funnel and the shape arrive with the figures they
  // are drawn from rather than being reconstructed here.
  // The SAME computation `/fees` renders (`S-152`). This page is admin-only
  // (`AuthGuard allow={["admin"]}` at the foot), which is what makes calling an
  // admin-only fee route from here safe — teachers never reach this component,
  // let alone the request.
  const { data: feeBoard } = useQuery({
    queryKey: ["collection", yearId, null],
    queryFn: () => schoolApi.collectionBoard({ yearId: yearId ?? undefined }),
  });
  const { data: homework, isLoading: homeworkLoading } = useQuery({
    queryKey: ["insights", "homework", OVERVIEW_WINDOW_DAYS],
    queryFn: () => insightsApi.homework(OVERVIEW_WINDOW_DAYS),
  });
  const { data: syllabus, isLoading: syllabusLoading } = useQuery({
    queryKey: ["insights", "syllabus-pulse", yearId, syllabusTerm],
    queryFn: () => insightsApi.syllabusPulse({
      yearId: yearId ?? undefined, termId: syllabusTerm || undefined,
    }),
    // The term switch is a filter, not a navigation: keeping the previous board
    // on screen while the next one loads stops the whole block collapsing to a
    // skeleton and back every time somebody compares two terms.
    placeholderData: (prev) => prev,
  });
  const { data } = useQuery({
    queryKey: ["dashboard", yearId],
    queryFn: () => schoolApi.dashboard(yearId ?? undefined),
    enabled: !!yearId,
  });
  // V1-7 (D-51): today's specials and the week ahead, in one dismissible line.
  // Seven days, deliberately: the founder's rule is that a date shows up a week
  // before, which is what removed the "Coming up" list under this — a 21-day
  // horizon needed a second section to hold it, and nobody acts three weeks out.
  const { data: whatsOn } = useQuery({
    queryKey: ["whats-on", "week"],
    queryFn: () => eventsApi.whatsOn({ horizon: 7 }),
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
      count: pendingCaptures.length, href: "/students/academics/exams",
      detail: `Test scores stay unsaved until someone confirms ${pendingCaptures.length === 1 ? "it" : "them"}`,
    }] : []),
    ...(board?.actions ?? []),
  ];

  // The support programme's shape — its own read, like fees, so the block and
  // the ABC bands tab can never disagree.
  const { data: bandDist } = useQuery({
    queryKey: ["band-distribution", "overview"],
    queryFn: () => schoolApi.bandDistribution(),
  });

  const sections = board?.sections ?? [];
  // Attendance and staff have graduated out of the one-card-per-module grid into
  // the panorama above it — keeping their old cards here would state the same
  // two facts twice, and worse the second time. V1-15 does the same for
  // syllabus: the pulse block below says everything the card said, plus which
  // class, which subject, and whether the figure is good for the date.
  // V1-17 does the same for homework: the generic three-metric card could not
  // show that its three figures NEST, because two of them counted sets and one
  // counted students. The block below draws the funnel instead.
  const modules = sections.filter(
    (s) => s.key !== "exams" && s.key !== "attendance" && s.key !== "staff"
      && s.key !== "syllabus" && s.key !== "homework");
  const exams = sections.find((s) => s.key === "exams");
  const homeworkSection = sections.find((s) => s.key === "homework");

  // An alert the rail already carries is noise: "2 staff away today" under
  // Alerts, right below "Assign cover — 15 periods", is the same fact told
  // twice and worse the second time. Dropped only when the matching action is
  // actually present, so a staff absence with every period covered still gets
  // said once.
  const railKeys = new Set(actions.map((a) => a.key));
  const alerts = (data?.alerts ?? []).filter((a) => {
    if (a.id === "leave:pending") return !railKeys.has("leave");
    if (a.type === "staff") return !railKeys.has("cover") && !railKeys.has("staff_attendance");
    // "N homework past due with no check recorded" is the rail's "Chase
    // homework checks" verbatim, and it has been rendering twice on this page
    // since DASH3 — once as something to go and do, once as something to file a
    // task about. The rail wins: it links to the screen that clears it.
    if (a.id === "homework:unchecked") return !railKeys.has("unchecked");
    return true;
  });

  return (
    <div>
      {/* V1-7, re-sited by the founder (2026-08-05): the day's notice leads the
          screen and is dismissible, because it is the one block here nobody has
          to act on. It was a section below the board with a "Coming up" list of
          its own; the horizon is now a week and there is no second list — a date
          joins the notice seven days out, which is the only warning a school
          actually uses. */}
      <div className="mb-4"><DayNotice data={whatsOn} scope="school" calendarHref="/plan" /></div>

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

      {/* V1-14 — who is in. Three rings (students · teachers · admin staff) and,
          beside them, the people missing from each with the button that deals
          with them. Named at three or fewer, counted above that; the server
          decides which, so the tab below can never disagree with this. */}
      <section className="mb-6">
        <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
          <UserCheck className="h-4 w-4" /> Who is in
        </h2>
        {presenceLoading || !presence ? (
          <div className="grid gap-4 lg:grid-cols-[minmax(240px,300px)_1fr]">
            <div className="h-52 animate-pulse rounded-xl border border-border bg-card" />
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="h-40 animate-pulse rounded-xl border border-border bg-card" />
              ))}
            </div>
          </div>
        ) : (
          <PresencePanorama
            board={presence}
            onCover={(row) => setCoverFor({ id: row.id, name: row.name })}
            onReason={(row) => setReasonFor({ student_id: row.id, full_name: row.name })}
          />
        )}
      </section>

      {/* V1-16 — what the staff's day actually looked like. It sits directly
          under "who is in" because the two are one question asked twice: the
          rings say who turned up, this says what their day was spent on. The
          timesheet has existed since SF-1 and until now the admin could only
          read it one person at a time. */}
      <section className="mb-6">
        <StaffDayBlock book={daybook} loading={daybookLoading} />
      </section>

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
            {/* Full width, and first: it is the only block that carries a
                filter, and the ring plus two breakdowns need the room. */}
            <div className="lg:col-span-2">
              <SyllabusPulseBlock pulse={syllabus} termId={syllabusTerm}
                onTerm={setSyllabusTerm} loading={syllabusLoading && !syllabus} />
            </div>
            {/* Also full width: three stacked stage bars beside a week of
                columns need the room, and squeezing them into half a grid
                column is how the funnel stops being readable as a funnel. */}
            <div className="lg:col-span-2">
              <HomeworkOverviewBlock section={homeworkSection} board={homework}
                loading={homeworkLoading && !homework} />
            </div>
            {modules.map((s) => <SectionCard key={s.key} section={s} />)}
            {/* Full width, like syllabus and homework: a ring beside its ledger
                and then a row of quarter rings does not fit half a grid column
                without the quarters collapsing to something unreadable. */}
            {feeBoard && feeBoard.academic_year_id ? (
              <div className="lg:col-span-2"><FeesSection board={feeBoard} /></div>
            ) : null}
            {bandDist && bandDist.subjects.length ? (
              <div className="lg:col-span-2"><BandsSection data={bandDist} /></div>
            ) : null}
            {exams ? <SectionCard section={exams} /> : null}
          </div>
        )}
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

      {/* The same cover sheet the staff tab uses — an absence on the overview
          is resolvable where it is read, not two screens away. */}
      <CoverSheet memberId={coverFor?.id ?? null} memberName={coverFor?.name}
        onDate={presence?.date} onClose={() => setCoverFor(null)} />
      <ReasonSheet target={reasonFor} onClose={() => setReasonFor(null)} />
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
