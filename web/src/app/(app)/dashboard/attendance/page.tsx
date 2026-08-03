"use client";

// Attendance — the tab rewritten as two halves (V1-14, on top of V1-3's S-08).
//
// **See it, then do something about it.** The old tab led with four tiles and
// hid its charts behind More, which meant an admin could read "91%" and still
// not know whether Tuesday was bad, whether 6-B is struggling, or whether the
// number was even complete. So:
//
//   PART 1 — THE PICTURE
//     · the three rings (students · teachers · admin staff), each with its own
//       denominator, shared with the overview so the two cannot disagree;
//     · a month as a **class × day grid**, because attendance sits at
//       ninety-something percent every day and a line of that is a flat line:
//       a bad day is a vertical stripe, a struggling class a horizontal one,
//       and a day nobody marked is visibly a gap rather than a full house;
//     · staff away per day, in people rather than percent (a six-teacher school
//       makes one absence 17%, which is a true number and a useless one);
//     · what stands out, said as sentences beside the picture.
//
//   PART 2 — THE WORK
//     · students, with the parent's number and the class teacher on the row;
//     · staff, with the periods the absence costs and cover in one tap;
//     · the admin desk, with the one write this screen makes — moving a task.
//
// Everything deeper that V1-3 built — drifting, chronic late, left-after-lunch,
// the day's capture heatmap — is kept, below the work, because each answers a
// question somebody arrives with occasionally rather than every morning.
//
// Colour is a RENDERING of a server-computed status (S-22/D-86). Nothing here
// re-derives "absent", and not-captured is never red.

import { useQuery } from "@tanstack/react-query";
import {
  ChevronDown, Clock, LogOut, TrendingDown, Users,
} from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  ChartCard, ColumnChart, PulseArea, SERIES_COLORS, type ChartRow,
} from "@/components/charts";
import { MonthGrid } from "@/components/insights/month-grid";
import { PeriodHeatmap } from "@/components/insights/period-heatmap";
import { PresenceRingRow } from "@/components/insights/presence";
import {
  AbsenceTable, AdminDeskTable, StaffAwayTable,
} from "@/components/insights/presence-tables";
import { CoverSheet } from "@/components/insights/cover-sheet";
import { ReasonSheet, type ReasonTarget } from "@/components/insights/reason-sheet";
import {
  BoardSkeleton, Empty, RedRow, Section, dayLabel,
} from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { insightsApi } from "@/lib/insights-api";
import type { PresenceAnomaly, StaffAbsentee } from "@/lib/insights-types";
import { cn } from "@/lib/utils";

const MODE_LABEL: Record<string, string> = {
  every_period: "every period",
  first_period: "the first period",
  twice_daily: "twice a day",
};

/** What stands out this month, said as sentences. Each row is a fact already
 *  visible in the grid beside it — nothing here is a score or a prediction. */
function Anomalies({ rows }: { rows: PresenceAnomaly[] }) {
  const dot = {
    neutral: "bg-muted-foreground/40", green: "bg-success",
    amber: "bg-warning", red: "bg-danger",
  };
  return (
    <section className="h-fit overflow-hidden rounded-xl border border-border bg-card">
      <header className="border-b border-border px-4 py-2.5">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          What stands out
        </span>
      </header>
      <ul>
        {rows.map((a) => (
          <li key={a.key} className="flex gap-2.5 border-t border-border/60 px-4 py-3 first:border-t-0">
            <span className={cn("mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full", dot[a.tone])} />
            <span className="min-w-0">
              <span className="block text-[13px] font-medium">
                {a.href ? (
                  <a href={a.href} className="hover:underline">{a.title}</a>
                ) : a.title}
              </span>
              <span className="mt-1 block text-[11px] leading-relaxed text-muted-foreground">
                {a.detail}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function AttendanceInner() {
  const { yearId } = useYear();
  const [showMore, setShowMore] = useState(false);
  const [reasonFor, setReasonFor] = useState<ReasonTarget | null>(null);
  const [coverFor, setCoverFor] = useState<StaffAbsentee | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["insights", "attendance", yearId],
    queryFn: () => insightsApi.attendance(yearId ?? undefined),
  });
  const presence = useQuery({
    queryKey: ["insights", "presence", yearId],
    queryFn: () => insightsApi.presence(yearId ?? undefined),
  });
  const month = useQuery({
    queryKey: ["insights", "presence-month", yearId],
    queryFn: () => insightsApi.presenceMonth({ yearId: yearId ?? undefined }),
  });
  const calls = useQuery({
    queryKey: ["insights", "calls", yearId],
    queryFn: () => insightsApi.attendanceCalls(yearId ?? undefined),
  });
  // `S-62` — the honest half of removing WhatsApp: which of today's own alerts
  // never landed on a phone. Not year-scoped; it is a today question.
  const reach = useQuery({
    queryKey: ["insights", "reach"],
    queryFn: () => insightsApi.attendanceReach(),
  });

  if (isLoading || !data) {
    return <><PageHeader title="Attendance" subtitle="Who is here, and was it even taken?" /><BoardSkeleton /></>;
  }

  const board = calls.data;
  const m = month.data;
  const unmarked = data.capture.expected - data.capture.marked;
  const unmarkedClasses = data.capture.rows.filter((r) => r.marked < r.expected).length;
  const needCall = board?.needs_call.length ?? 0;

  // ux §2: lead with a sentence, and every figure carries its denominator.
  const headline = [
    board && board.roster_considered
      ? `${board.present_today} of ${board.roster_considered} in today.`
      : "Nothing marked yet today.",
    needCall ? `${needCall} need${needCall === 1 ? "s" : ""} a call.` : "Nobody needs a call.",
    unmarked > 0
      ? `${unmarked} period${unmarked === 1 ? "" : "s"} unmarked in ${unmarkedClasses} class${unmarkedClasses === 1 ? "" : "es"}.`
      : "Every expected period is marked.",
  ].join(" ");

  // The month, as three pictures. Days nobody marked are dropped from the line
  // rather than plotted at zero — a gap in the record is not a bad day, and the
  // grid below is where the gap is actually shown.
  const pulseRows: ChartRow[] = (m?.students ?? [])
    .filter((d) => d.marked)
    .map((d) => ({ x: dayLabel(d.date), pct: d.pct }));
  // Staff in PEOPLE, not percent: on a six-teacher roster one absence is 17%,
  // which is true and tells nobody anything. Two series, so a legend is present.
  //
  // Days nobody marked are DROPPED, not plotted as empty slots — the same rule
  // the student line follows. A school that started taking staff attendance a
  // fortnight ago was otherwise given a chart that was two-thirds blank canvas,
  // which reads as a broken chart rather than as a young record.
  const staffRows: ChartRow[] = (m?.dates ?? [])
    .map((d, i) => ({ d, t: m?.teachers[i], a: m?.admins[i] }))
    .filter((r) => r.t?.marked || r.a?.marked)
    .map((r) => ({
      x: dayLabel(r.d),
      teachers: r.t?.marked ? r.t.absent : null,
      admins: r.a?.marked ? r.a.absent : null,
    }));
  const anyStaffMarked = staffRows.length > 0;
  const staffMarkedDays = staffRows.length;

  return (
    <div>
      <PageHeader title="Attendance" subtitle="Who is here, and was it even taken?" />

      <p className="mb-5 text-base">{headline}</p>

      {/* ── PART 1: the picture ─────────────────────────────────────────── */}
      {/* Three SEPARATE rings here, not the overview's medallion: this tab is the
          workspace for exactly these three groups, so each wants its own ring,
          figure and denominator laid side by side. The named blocks that sat
          beside them on the overview are gone — the tables below are the fuller
          version of the same three lists, and saying it twice on one screen only
          raises the question of which one is authoritative. */}
      <Section title="Who is in"
        hint={presence.data && !presence.data.is_today
          ? `Showing ${new Date(`${presence.data.date}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })} — the last day attendance was captured.`
          : "The same figures the dashboard leads with — one computation, two renderings, so they can never disagree."}>
        {presence.isLoading || !presence.data ? (
          <div className="h-28 animate-pulse rounded-xl border border-border bg-card" />
        ) : (
          <PresenceRingRow rings={presence.data.rings} />
        )}
      </Section>

      <Section
        title={`The last ${m?.window_days ?? 30} days`}
        hint={m?.headline ?? "Loading the month…"}
      >
        {month.isLoading || !m ? (
          <div className="h-72 animate-pulse rounded-xl border border-border bg-card" />
        ) : (
          /* The register gets the full width — it is the widest thing on the
             page and squeezing it into a 1fr column pushed its own Month total
             off the right edge. The chart and the notes then share a row under
             it, which also gives the chart a stable width to measure. */
          <div className="space-y-4">
            <ChartCard
              title="Every class, every day"
              hint="Darker means more of the class was away that day. A dashed cell is a day nobody marked — a gap in the record, never a full house."
            >
              <MonthGrid rows={m.classes} dates={m.dates} />
            </ChartCard>

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(260px,340px)]">
              <ChartCard title="Staff away, by day"
                hint={`Counted in people, not percent — on a small roster one absence is a big share and a meaningless one. ${staffMarkedDays} day${staffMarkedDays === 1 ? "" : "s"} in this window had staff attendance taken; the rest are not shown.`}>
                {anyStaffMarked ? (
                  <ColumnChart rows={staffRows} stacked height={200}
                    xInterval={Math.max(0, Math.floor(staffRows.length / 7))}
                    series={[
                      { key: "teachers", label: "Teachers", color: SERIES_COLORS[0] },
                      { key: "admins", label: "Admin staff", color: SERIES_COLORS[3] },
                    ]} />
                ) : (
                  <Empty>
                    Staff attendance has not been taken on any day in this window —
                    that is a gap in the record, not a month with nobody away.
                  </Empty>
                )}
              </ChartCard>

              <Anomalies rows={m.anomalies} />
            </div>
          </div>
        )}
      </Section>

      {/* ── PART 2: the work ────────────────────────────────────────────── */}
      <h2 className="mb-1 mt-8 text-base font-semibold">Who needs dealing with</h2>
      <p className="mb-4 max-w-[70ch] text-sm text-muted-foreground">
        One table per group of people. Every row carries what somebody needs before
        they act — the number to ring, the periods an absence costs, the task to
        move — so nothing here sends you to another screen to find out who or what.
      </p>

      <Section
        title="Students away"
        hint="Everyone with a full day's absence this month, with the number to ring and the teacher who knows them. Red is a run of three or more school days nobody has explained."
      >
        {month.isLoading || !m ? (
          <div className="h-56 animate-pulse rounded-xl border border-border bg-card" />
        ) : (
          <AbsenceTable
            rows={m.profiles}
            onReason={(r) => setReasonFor({ student_id: r.student_id, full_name: r.full_name })}
          />
        )}
      </Section>

      {reach.data?.rows.length ? (
        <Section
          title="Not reached"
          hint="Alerts are delivered in the app and by notification. These families got neither — a phone call is the fallback the school controls."
        >
          <div className="space-y-2">
            {reach.data.rows.map((r) => (
              <RedRow
                key={`${r.student_id}-${r.kind}`}
                tone="amber"
                href={`/students/${r.student_id}`}
                title={
                  <>
                    {r.student_name}{" "}
                    <span className="font-normal text-muted-foreground">
                      · {r.guardian_name}
                    </span>
                  </>
                }
                subtitle={`${r.title} — ${r.reason}`}
                meta={
                  r.phone ? (
                    <a
                      href={`tel:${r.phone}`}
                      onClick={(e) => e.stopPropagation()}
                      className="whitespace-nowrap text-xs font-medium text-primary"
                    >
                      {r.phone}
                    </a>
                  ) : null
                }
              />
            ))}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {reach.data.summary}
            {/* Opted-out families are counted, never listed for chasing. */}
            {reach.data.opted_out
              ? ` ${reach.data.opted_out} ${reach.data.opted_out === 1 ? "family has" : "families have"} asked not to be messaged.`
              : ""}
          </p>
        </Section>
      ) : null}

      <Section
        title="Staff away"
        hint="How many periods each absence costs, and who is genuinely free to take them. Cover opens here rather than two screens away."
      >
        {month.isLoading || !m ? (
          <div className="h-32 animate-pulse rounded-xl border border-border bg-card" />
        ) : (
          <StaffAwayTable rows={m.staff_absent} onCover={setCoverFor} />
        )}
      </Section>

      {/* Only when somebody is actually away. On a normal day the admin desk is
          a list of work that already has a home on the Tasks tab, and a section
          that is always on screen stops being read at all. */}
      {m && m.admin_work.some((w) => !w.present) ? (
        <Section
          title="The admin desk"
          hint="Work sitting with an admin who is away. Moving a task is a decision, not a rule — leaving it for them to pick up on Monday is very often the right answer."
        >
          <AdminDeskTable
            rows={m.admin_work.filter((w) => !w.present)}
            options={m.admin_options}
          />
        </Section>
      ) : null}

      <Section
        title="Is the record complete?"
        hint={data.capture.expected
          ? `Attendance is taken ${MODE_LABEL[data.capture.mode] ?? data.capture.mode}. A grey cell in an expected period is a gap in the record, not a class with nobody in it.`
          : "No timetable runs today, so no period is expected — this fills on the next school day."}
      >
        {/* `overflow-hidden` so the card clips its own content: the heatmap's
            sticky first column contributes to an ancestor's scroll width even
            though the table scrolls inside `ScrollX`, and at 390px that pushed
            the whole page sideways. The table still scrolls; only the page
            stops moving with it. */}
        <div className="overflow-hidden rounded-xl border border-border bg-card p-4">
          <PeriodHeatmap grid={data.capture} />
        </div>
      </Section>

      {/* §7: the patterns somebody arrives with occasionally, rather than every
          morning — kept in full, one fold away. */}
      <button
        onClick={() => setShowMore((v) => !v)}
        className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
      >
        <ChevronDown className={cn("h-4 w-4 transition-transform", showMore && "rotate-180")} />
        {showMore ? "Hide the slower patterns" : "More — drifting, chronic late and the trend"}
      </button>

      {showMore ? (
        <>
          <ChartCard
            title={`Present, the days that were marked`}
            hint="Share of students present on each day something was captured. Unmarked days are absent from this line entirely — the grid above is where they are shown."
            className="mb-4"
          >
            {pulseRows.length > 1 ? (
              <PulseArea rows={pulseRows} dataKey="pct" label="Present" yUnit="%"
                yDomain={[0, 100]} height={170} />
            ) : (
              <Empty>Not enough marked days yet — the line starts once two days are captured.</Empty>
            )}
          </ChartCard>

          {board?.drifting.length ? (
            <Section
              title="Drifting"
              hint={`Below ${board.min_attendance_pct}% over the last month — the slow fade the 3-day rule cannot see. Denominated on the days each class actually marked.`}
            >
              <div className="space-y-2">
                {board.drifting.slice(0, 10).map((r) => (
                  <RedRow key={r.student_id} tone="amber" href={`/students/${r.student_id}`}
                    title={<>{r.full_name} <span className="font-normal text-muted-foreground">· {r.class_label ?? "—"}</span></>}
                    subtitle={`in ${r.present_days} of ${r.marked_days} marked school days`}
                    meta={<Badge tone="warning"><TrendingDown className="h-3 w-3" /> {r.pct}%</Badge>} />
                ))}
              </div>
            </Section>
          ) : null}

          {board?.chronic_late.length ? (
            <Section title="Chronic late" hint="An admin conversation, never a message to the family.">
              <div className="space-y-2">
                {board.chronic_late.slice(0, 10).map((r) => (
                  <RedRow key={r.student_id} tone="amber" href={`/students/${r.student_id}`}
                    title={<>{r.full_name} <span className="font-normal text-muted-foreground">· {r.class_label ?? "—"}</span></>}
                    subtitle={`late on ${r.late_days} of the last ${r.window_days} days`}
                    meta={<Badge tone="warning"><Clock className="h-3 w-3" /> {r.late_days}</Badge>} />
                ))}
              </div>
            </Section>
          ) : null}

          {board?.left_after_lunch.length ? (
            <Section
              title="Left after lunch"
              hint="Present this morning, absent this afternoon — the one fact twice-daily marking exists to catch."
            >
              <div className="space-y-2">
                {board.left_after_lunch.map((r) => (
                  <RedRow key={r.student_id} tone="amber" href={`/students/${r.student_id}`}
                    title={<>{r.full_name} <span className="font-normal text-muted-foreground">· {r.class_label ?? "—"}</span></>}
                    subtitle="In this morning, gone after lunch"
                    meta={<LogOut className="h-4 w-4" />} />
                ))}
              </div>
            </Section>
          ) : null}

          {!board?.drifting.length && !board?.chronic_late.length
            && !board?.left_after_lunch.length ? (
              <Empty>
                <Users className="mr-1 inline h-4 w-4" />
                Nobody is drifting below the threshold, chronically late, or leaving
                after lunch.
              </Empty>
            ) : null}
        </>
      ) : null}

      <ReasonSheet target={reasonFor} onClose={() => setReasonFor(null)} />
      <CoverSheet
        memberId={coverFor?.member_id ?? null}
        memberName={coverFor?.name}
        onDate={coverFor?.date ?? undefined}
        leaveStart={coverFor?.leave_start ?? undefined}
        leaveEnd={coverFor?.leave_end ?? undefined}
        onClose={() => setCoverFor(null)} />
    </div>
  );
}

export default function DashboardAttendancePage() {
  return (
    <AuthGuard allow={["admin"]}>
      <AttendanceInner />
    </AuthGuard>
  );
}
