"use client";

// A student's report card — staff-only (admin: every student; teacher: students
// in classes they teach). It reads top-down as a document: who this is and how
// present they are, the shape of their ability, what they are good at and what
// needs work, how they have moved, then subject by subject with the chapter
// drill-down (what was taught, when, and whether THIS student was in the room).
//
// Support tiers (A/B/C) stay on this screen and this screen only (P4) — nothing
// here is parent-facing.

import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft, BookOpen, ChevronDown, ChevronRight, ClipboardCheck, Eye, Users,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Gauge, MeterBar, STATUS_COLOR } from "@/components/charts";
import {
  AttendanceBySubject, GrowthProfiles, GrowthTiles, ScoreHistory, StrengthsAndGrowth,
} from "@/components/students/growth-analytics";
import { TimelineBlock } from "@/components/students/timeline-block";
import { Badge } from "@/components/ui/badge";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import type { GrowthChapter, GrowthSubject } from "@/lib/school-types";

const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");

const ATT_LABEL: Record<string, { text: string; cls: string }> = {
  present: { text: "was present", cls: "text-success" },
  late: { text: "came late", cls: "text-warning" },
  absent: { text: "ABSENT", cls: "text-danger font-semibold" },
};

function ChapterRow({ ch }: { ch: GrowthChapter }) {
  const [open, setOpen] = useState(false);
  const taught = Math.max(0, ch.topics_taught - ch.topics_missed);
  return (
    <div className="rounded-lg border border-border bg-background">
      <button type="button" onClick={() => setOpen(!open)} className="w-full px-3 py-2 text-left">
        <div className="mb-1.5 flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-1 text-sm font-medium">
            {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
            <span className="truncate">{ch.title}</span>
          </span>
          <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
            {ch.topics_missed > 0 ? <Badge tone="warning">missed {ch.topics_missed}</Badge> : null}
            {ch.topics_taught}/{ch.topics_total} topics
          </span>
        </div>
        <MeterBar parts={[
          { value: taught, color: STATUS_COLOR.green, label: "taught, present" },
          { value: ch.topics_missed, color: STATUS_COLOR.amber, label: "taught while absent" },
          { value: Math.max(0, ch.topics_total - ch.topics_taught), color: "var(--color-muted)", label: "not taught yet" },
        ]} />
      </button>
      {open ? (
        <ul className="space-y-1 border-t border-border px-3 py-2 text-sm">
          {ch.topics.length === 0 ? <li className="text-muted-foreground">No topics in this chapter yet.</li> : null}
          {ch.topics.map((t) => {
            const att = t.student_attendance ? ATT_LABEL[t.student_attendance] : null;
            return (
              <li key={t.topic_id} className="flex items-center gap-2">
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${t.status === "done" ? "bg-success" : t.status === "in_progress" ? "bg-warning" : "bg-muted-foreground/40"}`} />
                <span className="min-w-0 flex-1 truncate">{t.title}</span>
                {t.status === "pending" ? (
                  <span className="shrink-0 text-xs text-muted-foreground">not taught yet</span>
                ) : (
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {t.taught_on ?? ""}{att ? <> · <span className={att.cls}>{att.text}</span></> : null}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}

function SubjectCard({ s }: { s: GrowthSubject }) {
  const latest = s.scores[s.scores.length - 1];
  const latestPct = latest && latest.max_score ? Math.round((latest.score / latest.max_score) * 100) : null;
  const taught = s.chapters.reduce((n, c) => n + c.topics_taught, 0);
  const total = s.chapters.reduce((n, c) => n + c.topics_total, 0);
  const missed = s.chapters.reduce((n, c) => n + c.topics_missed, 0);

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{s.subject_name}</h3>
          <p className="text-xs text-muted-foreground">
            {s.teacher_name ?? "No teacher assigned"}
            {total ? ` · ${taught} of ${total} topics covered` : ""}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {latestPct != null ? (
            <Badge tone={latestPct >= 60 ? "success" : latestPct >= 40 ? "warning" : "danger"}>
              {latest.cycle_name}: {latest.score}/{latest.max_score}
            </Badge>
          ) : null}
          {s.attendance.pct != null ? (
            <Badge tone={s.attendance.pct >= 90 ? "success" : s.attendance.pct >= 75 ? "warning" : "danger"}>
              <Users className="h-3 w-3" /> {s.attendance.pct}%
            </Badge>
          ) : <Badge tone="neutral">no attendance yet</Badge>}
          {missed > 0 ? <Badge tone="warning">{missed} missed while absent</Badge> : null}
          {s.checks_flagged > 0 ? <Badge tone="warning"><ClipboardCheck className="h-3 w-3" /> {s.checks_flagged}</Badge> : null}
          {s.homework_personal > 0 ? <Badge tone="primary"><BookOpen className="h-3 w-3" /> {s.homework_personal} personal</Badge> : null}
        </div>
      </div>

      {s.chapters.length === 0 ? (
        <p className="text-sm text-muted-foreground">No syllabus loaded for this subject yet.</p>
      ) : (
        <div className="space-y-2">
          {s.chapters.map((ch) => <ChapterRow key={ch.unit_id} ch={ch} />)}
        </div>
      )}

      {s.observations.length > 0 ? (
        <div className="mt-3 border-t border-border pt-2">
          <p className="mb-1 flex items-center gap-1 text-xs font-semibold text-muted-foreground">
            <Eye className="h-3.5 w-3.5" /> Classroom observations
          </p>
          <ul className="space-y-0.5 text-sm">
            {s.observations.map((o, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate">
                  {o.section}{o.concept ? ` · ${o.concept}` : ""}{o.note ? ` — ${o.note}` : ""}
                </span>
                <Badge tone={o.rating === "needs_work" ? "warning" : "success"}>
                  {o.rating === "needs_work" ? "needs work" : "excellent"}
                </Badge>
                <span className="shrink-0 text-xs text-muted-foreground">{o.date}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {s.scores.length > 1 ? (
        <p className="mt-3 border-t border-border pt-2 text-xs text-muted-foreground">
          {s.scores.map((sc) => `${sc.cycle_name} ${sc.score}/${sc.max_score}`).join(" → ")}
        </p>
      ) : null}
    </section>
  );
}

function GrowthInner() {
  const params = useParams<{ id: string }>();
  const { data, error, isLoading } = useQuery({
    queryKey: ["growth", params.id],
    queryFn: () => schoolApi.studentGrowth(params.id),
    retry: false,
  });

  if (isLoading) return <PageLoading label="Loading report…" />;
  if (error || !data) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        <p>You can view reports only for students in classes you teach.</p>
        <Link href="/students" className="mt-2 inline-block underline">Back to students</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-4">
      <Link href="/students" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Students
      </Link>

      {/* Identity band — who this is, and how present they have been. */}
      <header className="flex flex-wrap items-center gap-4 rounded-xl border border-border bg-card p-5">
        <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-accent text-lg font-semibold text-accent-foreground">
          {initials(data.full_name)}
        </span>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold tracking-tight">{data.full_name}</h1>
          <p className="text-sm text-muted-foreground">
            {data.class_label ?? "No class assigned"}
            {data.subjects.length ? ` · ${data.subjects.length} subjects` : ""}
          </p>
          {data.band ? (
            <p className="mt-1.5">
              <Badge tone="primary">Support tier {data.band}</Badge>
              <span className="ml-2 text-xs text-muted-foreground">staff-only — never shown to parents</span>
            </p>
          ) : null}
        </div>
        <Gauge value={data.attendance.pct} label="Attendance"
          sub={`${data.attendance.present}/${data.attendance.marked_periods} periods present`}
          color={data.attendance.pct == null ? STATUS_COLOR.neutral
            : data.attendance.pct >= 90 ? STATUS_COLOR.green
              : data.attendance.pct >= 75 ? STATUS_COLOR.amber : STATUS_COLOR.red} />
      </header>

      <GrowthTiles data={data} />
      <GrowthProfiles data={data} />
      <StrengthsAndGrowth data={data} />
      <ScoreHistory data={data} />
      <AttendanceBySubject data={data} />

      <div>
        <h2 className="mb-2 text-sm font-semibold">Subject by subject</h2>
        <div className="space-y-3">
          {data.subjects.map((s) => <SubjectCard key={s.class_subject_id} s={s} />)}
          {data.subjects.length === 0 ? (
            <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
              No subjects set up for this class yet.
            </p>
          ) : null}
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card p-4 text-sm">
        <TimelineBlock studentId={data.student_id} />
      </div>

      {data.band_history.length > 1 ? (
        <p className="text-xs text-muted-foreground">
          Support tier history: {data.band_history.map((b) => `${b.tier} (${b.set_on})`).join(" → ")}
        </p>
      ) : null}
    </div>
  );
}

export default function StudentGrowthPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <GrowthInner />
    </AuthGuard>
  );
}
