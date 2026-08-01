"use client";

// Attendance — the tab rewritten as the questions an admin arrives with
// (V1-3, S-08; DASH3 §4.1).
//
//   "428 of 470 in today. 6 need a call. 13 periods unmarked in 3 classes."
//   1. Needs a call      — red (nobody explained) first, then amber (explained)
//   2. Drifting          — the slow fade the 3-day rule can't see (S-07)
//   3. Chronic late      — an admin row, never a parent message (S-06)
//   4. Left after lunch  — twice-daily mode's whole reason to exist (Q-03/S-05)
//   5. Is the record even complete? — the capture heatmap
//   6. More              — the charts, which produce no decision on their own
//
// The colours are RENDERINGS of a server-computed status (S-22/D-86): a reason
// on record means somebody dealt with it. Nothing here re-derives "absent".

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2, ChevronDown, Clock, LogOut, MessageSquare, NotebookPen, TrendingDown, UserPlus, Users,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  ChartCard, PulseArea, RowBars, StatTile, toneForPct, type ChartRow,
} from "@/components/charts";
import { PeriodHeatmap } from "@/components/insights/period-heatmap";
import {
  BoardSkeleton, Empty, RailButton, RedRow, Section, dayLabel,
} from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import type { CallRow } from "@/lib/insights-types";
import { schoolApi } from "@/lib/school-api";
import { cn } from "@/lib/utils";

const MODE_LABEL: Record<string, string> = {
  every_period: "every period",
  first_period: "the first period",
  twice_daily: "twice a day",
};

/** D-02 step 3: the reason is added after the fact, by admin or teacher. It is
 *  what turns a red row amber for everyone who looks at it (D-86). */
function ReasonSheet({
  target, onClose,
}: {
  target: CallRow | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [code, setCode] = useState("sick");
  const [note, setNote] = useState("");
  const [days, setDays] = useState(1);

  const save = useMutation({
    mutationFn: async () => {
      const today = new Date().toISOString().slice(0, 10);
      // The reason always lands on today's absence; more than one day ALSO
      // records a planned absence, which pre-explains the days ahead and
      // suppresses their guardian alerts (S-24).
      await schoolApi.setAbsenceReason({
        student_id: target!.student_id, date: today,
        reason_code: code, note: note.trim() || null,
      });
      if (days > 1) {
        const to = new Date();
        to.setDate(to.getDate() + days - 1);
        await schoolApi.addAbsenceNote({
          student_id: target!.student_id, from_date: today,
          to_date: to.toISOString().slice(0, 10),
          reason_code: code, note: note.trim() || null, source: "office",
        });
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["insights", "calls"] });
      qc.invalidateQueries({ queryKey: ["insights", "streaks"] });
      toast.success("Reason recorded");
      setNote(""); setDays(1);
      onClose();
    },
    onError: (e) => showApiError(e, "Could not record the reason"),
  });

  return (
    <Sheet open={!!target} onOpenChange={(v) => { if (!v) onClose(); }}
      title={target ? `Why is ${target.full_name} away?` : ""}>
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Recording this tells everyone the school has dealt with it — the row turns amber
          and stops asking.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {["sick", "family", "travel", "informed", "other"].map((c) => (
            <button key={c} type="button" onClick={() => setCode(c)}
              className={cn("rounded-full border px-3 py-1 text-sm capitalize",
                code === c ? "border-primary bg-primary/10 font-medium" : "border-border")}>
              {c}
            </button>
          ))}
        </div>
        <Input placeholder="What did the family say? (optional)" value={note}
          onChange={(e) => setNote(e.target.value)} />
        <div>
          <label className="text-xs text-muted-foreground" htmlFor="away-days">
            Away for how many days?
          </label>
          <Input id="away-days" type="number" min={1} max={30} value={days}
            onChange={(e) => setDays(Math.max(1, Math.min(30, Number(e.target.value) || 1)))} />
          <p className="mt-1 text-xs text-muted-foreground">
            More than one day records a planned absence: those days are explained ahead of
            time and the family is not messaged again about them.
          </p>
        </div>
        <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Record reason"}
        </Button>
      </div>
    </Sheet>
  );
}

function NeedsCall({ rows, onReason }: { rows: CallRow[]; onReason: (r: CallRow) => void }) {
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: ({ kind, row }: { kind: "guardian_reminded" | "followup_assigned"; row: CallRow }) =>
      insightsApi.action(kind, {
        student_id: row.student_id,
        title: kind === "followup_assigned"
          ? `Call ${row.full_name}'s parent — absent ${row.streak} days`
          : undefined,
      }),
    onSuccess: (res) => {
      // `already_done` is the rail refusing to fire twice today, not a failure.
      if (res.already_done) toast.info(res.message);
      else toast.success(res.message);
      qc.invalidateQueries({ queryKey: ["insights", "calls"] });
    },
    onError: (e) => showApiError(e, "Could not complete that"),
  });

  if (!rows.length) {
    return (
      <Empty>
        Nobody is currently absent without being back — this list fills the moment a student
        misses every marked period of a school day.
      </Empty>
    );
  }

  return (
    <div className="space-y-2">
      {rows.map((r) => (
        <RedRow
          key={r.student_id}
          href={`/students/${r.student_id}`}
          tone={r.status === "explained" ? "amber" : "red"}
          title={<>{r.full_name} <span className="font-normal text-muted-foreground">· {r.class_label ?? "—"}</span></>}
          subtitle={
            <>
              {r.streak} school day{r.streak === 1 ? "" : "s"} absent
              {r.last_present ? ` · last seen ${dayLabel(r.last_present)}` : ""}
              {r.class_teacher_name ? ` · class teacher ${r.class_teacher_name}` : ""}
              {r.guardian_count === 0 ? " · no guardian on file" : ""}
              {r.status === "explained"
                ? ` · ${r.reason_note || r.reason_code || "reason recorded"}`
                : " · nobody has explained this"}
            </>
          }
          meta={<Badge tone={r.status === "explained" ? "warning" : "danger"}>{r.streak}d</Badge>}
          actions={
            <>
              {r.status === "unexplained" ? (
                <Button size="sm" variant="outline" onClick={() => onReason(r)}>
                  <NotebookPen className="h-3.5 w-3.5" /> Record a reason
                </Button>
              ) : null}
              <RailButton
                label="Remind guardian" doneLabel="Reminded"
                done={r.reminded_today} pending={run.isPending}
                icon={r.reminded_today
                  ? <CheckCircle2 className="h-3.5 w-3.5" />
                  : <MessageSquare className="h-3.5 w-3.5" />}
                onClick={() => run.mutate({ kind: "guardian_reminded", row: r })}
              />
              <RailButton
                label="Assign follow-up" doneLabel="Assigned"
                done={r.followup_assigned_today} pending={run.isPending}
                icon={r.followup_assigned_today
                  ? <CheckCircle2 className="h-3.5 w-3.5" />
                  : <UserPlus className="h-3.5 w-3.5" />}
                onClick={() => run.mutate({ kind: "followup_assigned", row: r })}
              />
            </>
          }
        />
      ))}
    </div>
  );
}

function AttendanceInner() {
  const { yearId } = useYear();
  const [showCharts, setShowCharts] = useState(false);
  const [reasonFor, setReasonFor] = useState<CallRow | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["insights", "attendance", yearId],
    queryFn: () => insightsApi.attendance(yearId ?? undefined),
  });
  const calls = useQuery({
    queryKey: ["insights", "calls", yearId],
    queryFn: () => insightsApi.attendanceCalls(yearId ?? undefined),
  });

  if (isLoading || !data) {
    return <><PageHeader title="Attendance" subtitle="Who is here, and was it even taken?" /><BoardSkeleton /></>;
  }

  const today = data.students.today;
  const trend = data.students.days.map((d) => d.present_pct);
  const pulseRows: ChartRow[] = data.students.days.map((d) => ({ x: dayLabel(d.date), pct: d.present_pct }));
  const classRows: ChartRow[] = data.students.classes_today
    .filter((c) => c.present_pct != null)
    .map((c) => ({ x: c.class_label, pct: c.present_pct }));
  const capturePct = data.capture.expected
    ? Math.round((data.capture.marked / data.capture.expected) * 100)
    : null;
  const staff = data.staff;
  const board = calls.data;
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

  return (
    <div>
      <PageHeader title="Attendance" subtitle="Who is here, and was it even taken?" />

      <p className="mb-5 text-base">{headline}</p>

      <Section
        title="Needs a call"
        hint="Red means nobody has explained the absence; amber means somebody has. Longest run first."
      >
        {calls.isLoading ? (
          <div className="h-32 animate-pulse rounded-xl border border-border bg-card" />
        ) : (
          <NeedsCall rows={board?.needs_call ?? []} onReason={setReasonFor} />
        )}
      </Section>

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

      <Section
        title="Is the record complete?"
        hint={`Attendance is taken ${MODE_LABEL[data.capture.mode] ?? data.capture.mode}. A grey cell in an expected period is a gap in the record, not a class with nobody in it.`}
      >
        <div className="rounded-xl border border-border bg-card p-4">
          <PeriodHeatmap grid={data.capture} />
        </div>
      </Section>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile
          label="Present today"
          value={today?.present_pct != null ? `${today.present_pct}%` : "—"}
          sub={today ? `${today.absent} absent · ${today.late} late` : "nothing marked yet"}
          tone={today?.present_pct == null ? "neutral"
            : today.present_pct >= 90 ? "green" : today.present_pct >= 80 ? "amber" : "red"}
          trend={trend}
        />
        <StatTile
          label="Periods captured"
          value={data.capture.expected ? `${data.capture.marked}/${data.capture.expected}` : "—"}
          sub={capturePct != null
            ? `${capturePct}% of the periods this mode marks`
            : "no timetable for today"}
          tone={capturePct == null ? "neutral" : capturePct >= 90 ? "green" : capturePct >= 50 ? "amber" : "red"}
        />
        <StatTile
          label="Absent 3+ days"
          value={String(data.streak_count)}
          sub={data.streak_count ? "each needs a phone call" : "nobody on the red list"}
          tone={data.streak_count ? "red" : "green"}
        />
        {/* "Not marked" is information, never a failure — an admin who marks
            staff at 10am must not see a red tile every morning. */}
        <StatTile
          label="Staff in today"
          value={staff.marked ? `${staff.present}/${staff.total}` : "not marked"}
          sub={staff.marked
            ? `${staff.absent} away${staff.on_leave ? ` · ${staff.on_leave} on leave` : ""}`
            : "nobody has taken staff attendance"}
          tone={!staff.marked ? "neutral" : staff.absent > 2 ? "red" : staff.absent ? "amber" : "green"}
          href="/dashboard/staff"
        />
      </div>

      {/* §7: a chart that produces no decision on its own goes behind More. */}
      <button
        onClick={() => setShowCharts((v) => !v)}
        className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
      >
        <ChevronDown className={cn("h-4 w-4 transition-transform", showCharts && "rotate-180")} />
        {showCharts ? "Hide the trends" : "More — trends and by-class"}
      </button>

      {showCharts ? (
        <div className="mb-6 grid gap-4 lg:grid-cols-2">
          <ChartCard
            title={`Present, last ${data.students.window_days} days`}
            hint="Share of student-periods present. Only days with marked periods appear."
            className="lg:col-span-2"
          >
            {pulseRows.length > 1 ? (
              <PulseArea rows={pulseRows} dataKey="pct" label="Present" yUnit="%" yDomain={[0, 100]} height={170} />
            ) : (
              <Empty>Not enough marked days yet — the line starts once two days are captured.</Empty>
            )}
          </ChartCard>

          <ChartCard title="By class, today" hint="Present share from today's marked periods.">
            {classRows.length ? (
              <RowBars rows={classRows} dataKey="pct" unit="%" max={100}
                height={Math.max(140, classRows.length * 30)}
                colorFor={(r) => toneForPct(r.pct as number, { good: 90, fair: 80 })} />
            ) : (
              <Empty>No attendance marked today yet.</Empty>
            )}
          </ChartCard>

          <ChartCard title="Staff today" hint="Marked by the admin on the Staff screen.">
            {staff.marked ? (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-4 text-sm">
                  <span><span className="text-lg font-semibold tabular-nums">{staff.present}</span> <span className="text-muted-foreground">in</span></span>
                  <span><span className="text-lg font-semibold tabular-nums text-danger">{staff.absent}</span> <span className="text-muted-foreground">away</span></span>
                  <span><span className="text-lg font-semibold tabular-nums text-warning">{staff.on_leave}</span> <span className="text-muted-foreground">on leave</span></span>
                </div>
                {staff.absentees.length ? (
                  <ul className="space-y-1 text-sm">
                    {staff.absentees.slice(0, 5).map((a) => (
                      <li key={a.member_id} className="flex items-center justify-between gap-2">
                        <span className="truncate">{a.name}</span>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {a.periods_due
                            ? `${a.periods_due - a.periods_covered} of ${a.periods_due} periods uncovered`
                            : a.reason ?? "no periods today"}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}
                <Link href="/dashboard/staff" className="inline-flex items-center gap-1 text-xs text-muted-foreground underline">
                  <Users className="h-3.5 w-3.5" /> Open the staff board
                </Link>
              </div>
            ) : (
              <Empty>Staff attendance has not been taken today — that is a gap in the record, not a full house.</Empty>
            )}
          </ChartCard>
        </div>
      ) : null}

      <ReasonSheet target={reasonFor} onClose={() => setReasonFor(null)} />
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
