"use client";

// Staff — presence · leave · load · cover (DASH3 §4.3, revision 2).
//
// This tab is the one that changed most once SF-1 shipped. It is the *analytical
// and decision* surface: who is free right now, who is away and what that breaks,
// what is waiting for approval, and whether the teaching load is balanced. The
// operational screens stay where they are — `/staff` marks attendance,
// `/staff/leave` decides leave, `/staff/today` is the period grid — and this
// links to them rather than re-rendering them.
//
// One rule the copy holds throughout: **"not marked yet" is information, not a
// failure.** An admin who takes staff attendance at 10am must not open a red
// board every morning.

import { useQuery } from "@tanstack/react-query";
import { CalendarCheck2, ExternalLink, UserX } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  ChartCard, ColumnChart, RowBars, SERIES_COLORS, StatTile, STATUS_COLOR, type ChartRow,
} from "@/components/charts";
import {
  DayNav, DaybookGrid, DaybookLegend,
} from "@/components/insights/daybook";
import { CoverSheet } from "@/components/insights/cover-sheet";
import { NowBoard } from "@/components/insights/now-board";
import {
  BoardSkeleton, Empty, RedRow, ScrollX, Section, StateChip, dayLabel,
} from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { insightsApi } from "@/lib/insights-api";
import type { SlackProfile } from "@/lib/insights-types";

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

/** The slack profile (D-21/S-66): teaching · other work · free, per period, for
 *  one weekday. The sentence above it IS the decision; the bars are its evidence
 *  (ux §2). `free` means "free **or** unrecorded" and the hint says so once —
 *  D-23 made an unfilled period free, so there is no third band to draw. */
function SlackProfileCard({ slack }: { slack: SlackProfile }) {
  const days = slack.working_weekdays.length ? slack.working_weekdays : [0, 1, 2, 3, 4, 5];
  const [weekday, setWeekday] = useState(
    () => (slack.best_weekday != null && days.includes(slack.best_weekday)
      ? slack.best_weekday : days[0]));

  const rows: ChartRow[] = slack.slots
    .filter((s) => s.weekday === weekday)
    .sort((a, b) => a.period_no - b.period_no)
    .map((s) => ({
      x: `P${s.period_no}`, teaching: s.teaching, working: s.working, free: s.free,
    }));

  const headline = slack.best_period_no != null
    ? `Period ${slack.best_period_no} on ${DAY_NAMES[slack.best_weekday ?? 0]} is the widest slot — ${slack.best_free} of ${slack.teacher_count} teachers free.`
    : `Every period this week has all ${slack.teacher_count} teachers committed — there is no whole-staff slot.`;

  return (
    <Section
      title="Where the slack is"
      hint="For finding a meeting slot or an invigilation period. “Free” means free or unrecorded — an unfilled period is a free one (D-23). Counted over people who teach at all."
      action={
        <select value={weekday} onChange={(e) => setWeekday(Number(e.target.value))}
          aria-label="Weekday"
          className="rounded-md border border-border bg-card px-2 py-1 text-sm">
          {days.map((d) => <option key={d} value={d}>{DAY_NAMES[d]}</option>)}
        </select>
      }
    >
      <p className="mb-3 text-sm">{headline}</p>
      <ChartCard title={`${DAY_NAMES[weekday]} · ${slack.teacher_count} teachers`}>
        {rows.length ? (
          <ColumnChart rows={rows} stacked height={220} series={[
            { key: "teaching", label: "Teaching", color: STATUS_COLOR.green },
            { key: "working", label: "Other work (recorded)", color: SERIES_COLORS[0] },
            { key: "free", label: "Free or unrecorded", color: STATUS_COLOR.neutral },
          ]} />
        ) : (
          <Empty>No periods on this day.</Empty>
        )}
      </ChartCard>
    </Section>
  );
}

/** Local Y-M-D. Never `toISOString()`: east of UTC that returns the PREVIOUS
 *  day for a local-midnight Date, which is the defect V1-14 had to fix twice. */
function localIso(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

/**
 * The day-book (V1-16) — the school's whole day, people down and periods across.
 *
 * It leads the tab because it is the only view here that answers the question an
 * admin actually walks in with: *what is everybody doing today?* Everything
 * below it is a consequence — who is missing, what that breaks, who is carrying
 * more than their share.
 *
 * The date is navigable, and the board says what a past date WAS: a Sunday reads
 * "not a school day" rather than showing an empty grid, which would read as a
 * school where nobody worked.
 */
function DaybookSection() {
  const today = localIso();
  const [on, setOn] = useState(today);
  const { data, isLoading } = useQuery({
    queryKey: ["insights", "daybook", on],
    queryFn: () => insightsApi.daybook(on),
    // Navigating a day should not collapse the grid to a skeleton and back —
    // the previous day stays on screen while the next one loads.
    placeholderData: (prev) => prev,
  });

  return (
    <Section
      title="The day, period by period"
      hint="From the timetable, the timesheet, the cover board and staff attendance — one page. Tap a name for that person’s record."
      action={<DayNav date={on} onChange={setOn} today={today} />}
    >
      {isLoading && !data ? (
        <div className="h-72 animate-pulse rounded-xl border border-border bg-card" />
      ) : !data ? null : (
        <div className="space-y-3">
          <p className="text-sm">{data.headline}</p>
          <DaybookGrid book={data} hrefFor={(r) => `/staff/member/${r.member_id}`} />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <DaybookLegend book={data} />
            {data.slots_total ? (
              <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                {data.slots_teaching} teaching · {data.slots_work} recorded ·{" "}
                {data.slots_free} free
                {data.slots_away ? ` · ${data.slots_away} away` : ""}
              </span>
            ) : null}
          </div>
        </div>
      )}
    </Section>
  );
}

function StaffInner() {
  const [coverFor, setCoverFor] =
    useState<{ id: string; name: string; date?: string } | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["insights", "staff"],
    queryFn: () => insightsApi.staff(),
    // The live board moves with the bell; a stale "period 4" is worse than a
    // spinner, so this refetches while the tab is open.
    refetchInterval: 120_000,
  });

  if (isLoading || !data) {
    return <><PageHeader title="Staff" subtitle="Who is in, who is free, and what an absence breaks." /><BoardSkeleton /></>;
  }

  const { presence, leave, week } = data;
  const loadRows: ChartRow[] = week.teachers
    .filter((t) => t.teaching_periods > 0)
    .slice(0, 14)
    .map((t) => ({ x: t.name, periods: t.teaching_periods }));
  const bucketRows: ChartRow[] = week.buckets.map((b) => ({ x: b.label, periods: b.periods }));

  return (
    <div>
      <PageHeader title="Staff" subtitle="Who is in, who is free, and what an absence breaks." />

      <DaybookSection />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="In today"
          value={presence.marked ? `${presence.present}/${presence.total}` : "not marked"}
          sub={presence.marked
            ? `${presence.absent} away${presence.on_leave ? ` · ${presence.on_leave} on leave` : ""}`
            : "nobody has taken staff attendance"}
          tone={!presence.marked ? "neutral" : presence.absent > 2 ? "red" : presence.absent ? "amber" : "green"}
          href="/staff"
        />
        <StatTile
          label="Periods uncovered"
          value={String(data.uncovered_periods)}
          sub={data.uncovered_periods ? "an absent teacher's classes" : "every absence is covered"}
          tone={data.uncovered_periods ? "red" : "green"}
        />
        <StatTile
          label="Leave waiting"
          value={String(leave.pending)}
          sub={leave.pending ? "needs a decision" : `${leave.on_leave_today} on leave today`}
          tone={leave.pending ? "amber" : "green"}
          href="/staff/leave"
        />
        {/* StatTile truncates its sub to one line — keep it short enough to read.
            S-76 deleted the "free periods unlogged" tile that stood here: under
            D-23 an unfilled period IS free, so it counted nothing the school
            had agreed was a problem, and it was at its reddest at 8:30am. */}
        <StatTile
          label="Cover ahead"
          value={String(leave.upcoming.length)}
          sub={leave.upcoming.length
            ? `${dayLabel(leave.upcoming[0].date)}: ${leave.upcoming[0].member_name}`
            : "no approved absences to arrange"}
          tone={leave.upcoming.length ? "amber" : "green"}
          href="/staff/leave"
        />
      </div>

      <Section title="Right now"
        hint="The timetable says who is teaching; the timesheet says what the rest are doing.">
        <NowBoard board={data.now} />
      </Section>

      {presence.absentees.length ? (
        <Section title="Away today"
          hint="Open one to see the periods it breaks and who is genuinely free to cover them.">
          <div className="space-y-2">
            {presence.absentees.map((a) => {
              const uncovered = Math.max(0, a.periods_due - a.periods_covered);
              return (
                <RedRow
                  key={a.member_id}
                  tone={uncovered ? "red" : "amber"}
                  title={<>{a.name} <span className="font-normal text-muted-foreground">· {a.role}</span></>}
                  subtitle={
                    <>
                      {a.on_leave ? "On approved leave" : "Marked away"}
                      {a.reason ? ` · ${a.reason}` : ""}
                      {a.periods_due
                        ? ` · ${a.periods_due} period${a.periods_due === 1 ? "" : "s"} today`
                        : " · no lessons today"}
                    </>
                  }
                  meta={a.periods_due
                    ? <Badge tone={uncovered ? "danger" : "success"}>
                        {uncovered ? `${uncovered} uncovered` : "all covered"}
                      </Badge>
                    : null}
                  actions={
                    <Button size="sm" variant="outline"
                      onClick={() => setCoverFor({ id: a.member_id, name: a.name })}>
                      <UserX className="h-3.5 w-3.5" /> Arrange cover
                    </Button>
                  }
                />
              );
            })}
          </div>
        </Section>
      ) : null}

      {/* S-81 — the moment leave is approved the uncovered periods are known.
          Saying so now beats remembering on the morning it starts. */}
      {leave.upcoming.length ? (
        <Section title="Cover to arrange"
          hint="Approved absences in the next two weeks whose periods nobody has taken yet.">
          <div className="space-y-2">
            {leave.upcoming.slice(0, 8).map((u) => {
              const open = Math.max(0, u.periods_due - u.periods_covered);
              return (
                <RedRow
                  key={`${u.member_id}-${u.date}`}
                  tone="amber"
                  title={<>{dayLabel(u.date)} <span className="font-normal text-muted-foreground">· {u.member_name} away</span></>}
                  subtitle={`${open} of ${u.periods_due} period${u.periods_due === 1 ? "" : "s"} still to cover`}
                  actions={
                    <Button size="sm" variant="outline"
                      onClick={() => setCoverFor({ id: u.member_id, name: u.member_name, date: u.date })}>
                      <UserX className="h-3.5 w-3.5" /> Arrange cover
                    </Button>
                  }
                />
              );
            })}
          </div>
        </Section>
      ) : null}

      <Section
        title="Leave"
        hint={`School allowance: ${leave.allowed_per_year} days a year, ${leave.allowed_per_month} a month. Over-policy applications are flagged, never blocked.`}
        action={
          <Link href="/staff/leave" className={buttonVariants({ variant: "outline", size: "sm" })}>
            <ExternalLink className="h-3.5 w-3.5" /> Decide on /staff/leave
          </Link>
        }
      >
        {leave.queue.length ? (
          <div className="space-y-2">
            {leave.queue.map((r) => (
              <RedRow
                key={r.request_id}
                tone={r.warnings.length ? "amber" : "neutral"}
                href="/staff/leave"
                title={<>{r.member_name} <span className="font-normal text-muted-foreground">· {r.days} day{r.days === 1 ? "" : "s"}</span></>}
                subtitle={
                  <>
                    {dayLabel(r.start_date)}
                    {r.start_date !== r.end_date ? ` – ${dayLabel(r.end_date)}` : ""} · {r.reason}
                  </>
                }
                meta={r.warnings.length
                  ? <span className="text-warning">{r.warnings[0]}</span>
                  : <CalendarCheck2 className="h-4 w-4 text-muted-foreground" />}
              />
            ))}
          </div>
        ) : (
          <Empty>
            Nothing waiting. {leave.on_leave_today} on leave today · {leave.approved_days_this_month} day
            {leave.approved_days_this_month === 1 ? "" : "s"} approved this month.
          </Empty>
        )}
      </Section>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Teaching periods this week"
          hint={`Against an org mean of ${week.mean_teaching}, computed over people who teach at all.`}
        >
          {loadRows.length ? (
            <RowBars rows={loadRows} dataKey="periods" max={undefined}
              height={Math.max(140, loadRows.length * 26)}
              colorFor={(r) => {
                const t = week.teachers.find((x) => x.name === r.x);
                return t?.load_flag === "over" ? STATUS_COLOR.red
                  : t?.load_flag === "under" ? STATUS_COLOR.amber : STATUS_COLOR.green;
              }} />
          ) : (
            <Empty>No timetable slots this week — the grid has not been set.</Empty>
          )}
        </ChartCard>

        <ChartCard title="What non-teaching periods went on"
          hint="From the timesheet, this week. A school with nothing here has not adopted it yet.">
          {bucketRows.length ? (
            <RowBars rows={bucketRows} dataKey="periods"
              height={Math.max(140, bucketRows.length * 26)} />
          ) : (
            <Empty>No timesheet entries this week.</Empty>
          )}
        </ChartCard>
      </div>

      {/* D-21 / S-66 — the one genuinely new chart. Its job is finding slack:
          when the whole staff could meet, which period invigilation should come
          out of. Not a scoreboard, and framed so it cannot become one (S-67). */}
      {week.slack ? <SlackProfileCard slack={week.slack} /> : null}

      {/* V1-16 dropped this table's "Today" column: the day-book at the top of
          the tab is the same fact at full size, and two renderings of one day on
          one screen only raise the question of which is authoritative. What
          survives is the WEEK, which the day-book does not carry. */}
      <Section title="The week, teacher by teacher"
        hint="Teaching and recorded work across the whole week, against the staff mean.">
        <ScrollX>
          <table className="w-full min-w-[480px] text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted-foreground">
                <th className="py-2 pr-3 font-medium">Teacher</th>
                <th className="py-2 pr-3 text-right font-medium">Teaching</th>
                <th className="py-2 pr-3 text-right font-medium">Other work</th>
                <th className="py-2 text-right font-medium">Load</th>
              </tr>
            </thead>
            <tbody>
              {week.teachers.map((t) => (
                <tr key={t.member_id} className="border-b border-border/60">
                  <td className="py-2 pr-3">
                    <Link href={`/staff/member/${t.member_id}`} className="hover:underline">
                      <span className="block truncate">{t.name}</span>
                    </Link>
                    <span className="block text-xs text-muted-foreground">{t.role}</span>
                  </td>
                  <td className="py-2 pr-3 text-right tabular-nums">{t.teaching_periods}</td>
                  <td className="py-2 pr-3 text-right tabular-nums">{t.work_periods}</td>
                  <td className="py-2 text-right">
                    {t.teaching_periods === 0 ? (
                      <StateChip>no classes</StateChip>
                    ) : t.load_flag === "over" ? (
                      <Badge tone="danger">+{t.delta_vs_mean}</Badge>
                    ) : t.load_flag === "under" ? (
                      <Badge tone="warning">{t.delta_vs_mean}</Badge>
                    ) : (
                      <Badge tone="success">balanced</Badge>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollX>
      </Section>

      <CoverSheet memberId={coverFor?.id ?? null} memberName={coverFor?.name}
        onDate={coverFor?.date} onClose={() => setCoverFor(null)} />
    </div>
  );
}

export default function DashboardStaffPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <StaffInner />
    </AuthGuard>
  );
}
