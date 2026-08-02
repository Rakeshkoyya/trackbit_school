"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, ClipboardCheck, IndianRupee, Loader2, Moon, NotebookPen, Phone } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { parentApi, type DayStatus, type HomeworkStatus } from "@/lib/parent-api";

import { useParentPortal } from "./parent-context";

/** How each verdict reads to a parent. `not_checked` is deliberately neutral and
 *  worded as the teacher's pending action — never as something the child failed
 *  to do. */
const HW_STATUS: Record<HomeworkStatus, { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  done: { label: "done", tone: "success" },
  // S-99: handed in late IS done. Saying so, and not colouring it as a failure,
  // is the difference between a record and an accusation.
  late: { label: "done, a bit late", tone: "success" },
  not_done: { label: "not done", tone: "danger" },
  partial: { label: "partly done", tone: "warning" },
  // D-35/D-34: their child was ABSENT when this was set. Yellow, never red —
  // a child off sick did not refuse the work, and a parent must never be shown
  // an absence as a miss.
  carried: { label: "was away — still to do", tone: "warning" },
  waived: { label: "not needed", tone: "neutral" },
  not_checked: { label: "not checked yet", tone: "neutral" },
};

function dayLabel(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    { weekday: "short", day: "numeric", month: "short" });
}

const STATUS_COPY: Record<DayStatus, { label: string; tone: "success" | "warning" | "danger" | "neutral"; hint?: string }> = {
  present: { label: "Present today", tone: "success" },
  partial: { label: "Missed some periods", tone: "warning" },
  absent: { label: "Absent today", tone: "danger" },
  // V1-3 (Q-03): the school marks attendance again after lunch, so "went home
  // at midday" is its own plain sentence — never buried inside "partial".
  left_after_lunch: { label: "Went home after lunch", tone: "warning" },
  not_marked: {
    label: "Attendance not marked yet",
    tone: "neutral",
    hint: "Teachers mark attendance during the day — check back later.",
  },
  no_school: { label: "No school periods today", tone: "neutral" },
};

/** V1-3 (S-11): the month strip — the one chart every parent reads instantly.
 *  A DAILY status per square, never per-period detail; a day the school never
 *  marked is neutral, because that is the school's gap, not the child's. */
const STRIP: Record<string, { cls: string; label: string }> = {
  present: { cls: "bg-[color:var(--success,#234a37)]/25", label: "present" },
  partial: { cls: "bg-warning/40", label: "in for part of the day" },
  left_after_lunch: { cls: "bg-warning/60", label: "went home after lunch" },
  absent: { cls: "bg-danger/60", label: "absent" },
  not_marked: { cls: "bg-muted", label: "not marked" },
};

function MonthStrip({ days }: { days: { date: string; status: string }[] }) {
  if (!days.length) return null;
  return (
    <div className="mt-3">
      <div className="flex flex-wrap gap-1">
        {days.map((d) => (
          <span
            key={d.date}
            title={`${new Date(`${d.date}T00:00:00`).toLocaleDateString("en-IN", {
              day: "numeric", month: "short" })} — ${STRIP[d.status]?.label ?? d.status}`}
            className={`h-4 w-4 rounded-[3px] ${STRIP[d.status]?.cls ?? "bg-muted"}`}
          />
        ))}
      </div>
    </div>
  );
}

function Section({ icon: Icon, title, children }: {
  icon: React.ElementType; title: string; children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4 text-muted-foreground" />
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function ParentTodayPage() {
  const { child } = useParentPortal();
  const { data, isLoading } = useQuery({
    queryKey: ["parent", "today", child?.student_id],
    queryFn: () => parentApi.today(child!.student_id),
    enabled: !!child,
  });

  if (!child || isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!data) return null;
  const status = STATUS_COPY[data.status];

  return (
    <div className="space-y-4">
      {/* Attendance — one calm daily line, never a per-period feed. */}
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">{child.full_name}</p>
            <p className="mt-0.5 text-base font-semibold">{status.label}</p>
            {data.status === "partial" ? (
              <p className="mt-0.5 text-xs text-muted-foreground">
                Missed {data.absent_periods} of {data.marked_periods} marked periods.
              </p>
            ) : null}
            {data.late_periods > 0 ? (
              <p className="mt-0.5 text-xs text-muted-foreground">
                Arrived late to {data.late_periods} period{data.late_periods > 1 ? "s" : ""}.
              </p>
            ) : null}
            {status.hint ? (
              <p className="mt-0.5 text-xs text-muted-foreground">{status.hint}</p>
            ) : null}
            {/* D-02: the reason the school has on record — so a family that
                already phoned is not asked again. */}
            {data.absence_reason ? (
              <p className="mt-1 text-xs text-muted-foreground">
                The school has recorded: <span className="text-foreground">{data.absence_reason}</span>
              </p>
            ) : null}
          </div>
          <Badge tone={status.tone} className="shrink-0">{data.date}</Badge>
        </div>

        {/* S-11: the pattern, with its denominator stated (ux §4). */}
        {data.marked_days > 0 ? (
          <p className="mt-3 text-xs text-muted-foreground">
            Present {data.present_days} of {data.marked_days} school day
            {data.marked_days === 1 ? "" : "s"} this month.
          </p>
        ) : null}
        <MonthStrip days={data.month ?? []} />

        {/* S-25: the write path is a phone call. Zero parent writes (D-86). */}
        {data.school_phone && (data.status === "absent" || data.status === "left_after_lunch")
          && !data.absence_reason ? (
            <a href={`tel:${data.school_phone}`}
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-muted/40">
              <Phone className="h-4 w-4" /> Tell the school why
            </a>
          ) : null}
      </section>

      <Section icon={BookOpen} title="Taught today">
        {data.taught.length ? (
          <ul className="space-y-2">
            {data.taught.map((t, i) => (
              <li key={i} className="flex items-baseline gap-2 text-sm">
                <span className="w-24 shrink-0 text-xs font-medium text-muted-foreground">
                  {t.subject_name}
                </span>
                <span>{t.topic}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Nothing logged yet today.</p>
        )}
      </Section>

      {/* V1-10 (`D-66`/`S-160`): the fee reminder — **one line**, and only when
          something is actually due. Two questions, "how much" and "by when",
          and both fit on it. Deliberately not a ledger and not a tab: a fee tab
          invites "why was I charged this", which is a counter conversation.
          Neutral tone, never red — it is read by a family that may be having a
          hard year. */}
      {data.fee ? (
        <Section icon={IndianRupee} title="Fees">
          <p className="text-sm">{data.fee.line}</p>
          {data.fee.school_phone ? (
            <a href={`tel:${data.fee.school_phone}`}
              className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-sm">
              <Phone className="h-4 w-4" /> Call the office
            </a>
          ) : null}
        </Section>
      ) : null}

      {/* Yesterday's verdict — the question a parent opens this app to answer. */}
      {data.yesterday ? (
        <Section icon={ClipboardCheck} title={`Last homework · ${dayLabel(data.yesterday.date)}`}>
          <div className="mb-3 flex flex-wrap gap-1.5">
            {data.yesterday.done ? (
              <Badge tone="success">{data.yesterday.done} done</Badge>
            ) : null}
            {data.yesterday.not_done ? (
              <Badge tone="danger">{data.yesterday.not_done} not done</Badge>
            ) : null}
            {data.yesterday.partial ? (
              <Badge tone="warning">{data.yesterday.partial} partly done</Badge>
            ) : null}
            {/* `S-99`: late counts as DONE and is reported beside completion,
                never folded into it and never as a miss. */}
            {data.yesterday.late ? (
              <Badge tone="success">{data.yesterday.late} done late</Badge>
            ) : null}
            {/* `D-35`: absent when it was set — yellow, pending, never red. */}
            {data.yesterday.carried ? (
              <Badge tone="warning">{data.yesterday.carried} to catch up</Badge>
            ) : null}
            {data.yesterday.not_checked ? (
              <Badge tone="neutral">{data.yesterday.not_checked} not checked yet</Badge>
            ) : null}
          </div>
          <ul className="space-y-2">
            {data.yesterday.items.map((hw, i) => (
              <li key={i} className="flex items-baseline gap-2 text-sm">
                <span className="w-24 shrink-0 text-xs font-medium text-muted-foreground">
                  {hw.subject_name}
                </span>
                <span className="min-w-0 flex-1">{hw.text}</span>
                <Badge tone={HW_STATUS[hw.status].tone}>{HW_STATUS[hw.status].label}</Badge>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {/* Still to do — set and not finished, whether or not it was set today. */}
      {data.pending.length ? (
        <Section icon={NotebookPen} title="Still to do">
          <ul className="space-y-2">
            {data.pending.map((hw, i) => (
              <li key={i} className="flex items-baseline gap-2 text-sm">
                <span className="w-24 shrink-0 text-xs font-medium text-muted-foreground">
                  {hw.subject_name}
                </span>
                <span className="min-w-0 flex-1">
                  {hw.text}
                  {hw.personal ? (
                    <span className="ml-1 text-xs text-muted-foreground">(just for them)</span>
                  ) : null}
                </span>
                {hw.due_date ? (
                  <span className="shrink-0 text-xs text-muted-foreground">
                    due {dayLabel(hw.due_date)}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {/* `S-94` — work whose deadline has passed, split OUT of "still to do".
          The two used to be one list, so missed work sat beside upcoming work
          looking as though it could still be handed in. Deliberately carries
          NO red: it is a fact, and the child may well have finished it since. */}
      {data.missed.length ? (
        <Section icon={NotebookPen} title="Missed">
          <ul className="space-y-2">
            {data.missed.map((hw, i) => (
              <li key={i} className="flex items-baseline gap-2 text-sm">
                <span className="w-24 shrink-0 text-xs font-medium text-muted-foreground">
                  {hw.subject_name}
                </span>
                <span className="min-w-0 flex-1">{hw.text}</span>
                {hw.due_date ? (
                  <span className="shrink-0 text-xs text-muted-foreground">
                    was due {dayLabel(hw.due_date)}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs text-muted-foreground">
            Worth a word with them — or with the teacher if it was set while
            they were away.
          </p>
        </Section>
      ) : null}

      <Section icon={NotebookPen} title="Homework set today">
        {data.homework.length ? (
          <ul className="space-y-2">
            {data.homework.map((hw, i) => (
              <li key={i} className="flex items-baseline gap-2 text-sm">
                <span className="w-24 shrink-0 text-xs font-medium text-muted-foreground">
                  {hw.subject_name}
                </span>
                <span className="min-w-0 flex-1">{hw.text}</span>
                {hw.status !== "not_checked" ? (
                  <Badge tone={HW_STATUS[hw.status].tone}>{HW_STATUS[hw.status].label}</Badge>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No homework recorded today.</p>
        )}
      </Section>

      {data.sessions.length ? (
        <Section icon={Moon} title="Evening & activities">
          <ul className="space-y-2.5">
            {data.sessions.map((s, i) => (
              <li key={i} className="text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{s.session_name}</span>
                  <Badge tone={s.status === "absent" ? "danger" : s.status === "late" ? "warning" : "success"}>
                    {s.status}
                  </Badge>
                </div>
                {s.log_note ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">{s.log_note}</p>
                ) : null}
                {s.homework_done != null ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Homework {s.homework_done ? "completed" : "not completed"}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </div>
  );
}
