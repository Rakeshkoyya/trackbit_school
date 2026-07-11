"use client";

// Student growth report — staff-only (admin: every student; teacher: students in
// classes they teach). Chapter-level is the default reading; each chapter expands
// to topic level: what was taught, when, and whether THIS student was in the room.

import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowLeft, BookOpen, ChevronDown, ChevronRight, ClipboardCheck,
  Eye, TrendingUp, Users,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { TimelineBlock } from "@/components/students/timeline-block";
import { Badge } from "@/components/ui/badge";
import { schoolApi } from "@/lib/school-api";
import type { GrowthChapter, GrowthSubject } from "@/lib/school-types";

function AttendancePill({ pct }: { pct: number | null }) {
  if (pct == null) return <Badge tone="neutral">no attendance yet</Badge>;
  const tone = pct >= 90 ? "success" : pct >= 75 ? "warning" : "danger";
  return <Badge tone={tone}><Users className="h-3 w-3" /> {pct}% present</Badge>;
}

function ProgressBar({ done, missed, total }: { done: number; missed: number; total: number }) {
  const donePct = total ? (done / total) * 100 : 0;
  const missedPct = total ? (missed / total) * 100 : 0;
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div className="flex h-full">
        <div className="h-full bg-[color:var(--success,#234a37)]" style={{ width: `${donePct - missedPct}%` }} />
        <div className="h-full bg-[color:var(--warning,#8a6d1a)]" style={{ width: `${missedPct}%` }} />
      </div>
    </div>
  );
}

const ATT_LABEL: Record<string, { text: string; cls: string }> = {
  present: { text: "was present", cls: "text-[color:var(--success,#234a37)]" },
  late: { text: "came late", cls: "text-warning" },
  absent: { text: "ABSENT", cls: "text-danger font-semibold" },
};

function ChapterRow({ ch }: { ch: GrowthChapter }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-border bg-background">
      <button type="button" onClick={() => setOpen(!open)} className="w-full px-3 py-2 text-left">
        <div className="mb-1 flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-1 text-sm font-medium">
            {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0" /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" />}
            <span className="truncate">{ch.title}</span>
          </span>
          <span className="flex shrink-0 items-center gap-1.5 text-xs text-muted-foreground">
            {ch.topics_missed > 0 ? <Badge tone="warning">missed {ch.topics_missed}</Badge> : null}
            {ch.topics_taught}/{ch.topics_total} topics
          </span>
        </div>
        <ProgressBar done={ch.topics_taught} missed={ch.topics_missed} total={ch.topics_total} />
      </button>
      {open ? (
        <ul className="space-y-1 border-t border-border px-3 py-2 text-sm">
          {ch.topics.length === 0 ? <li className="text-muted-foreground">No topics in this chapter yet.</li> : null}
          {ch.topics.map((t) => {
            const att = t.student_attendance ? ATT_LABEL[t.student_attendance] : null;
            return (
              <li key={t.topic_id} className="flex items-center gap-2">
                <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${t.status === "done" ? "bg-[color:var(--success,#234a37)]" : t.status === "in_progress" ? "bg-[color:var(--warning,#8a6d1a)]" : "bg-muted-foreground/40"}`} />
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
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold">{s.subject_name}</h2>
          {s.teacher_name ? <p className="text-xs text-muted-foreground">{s.teacher_name}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <AttendancePill pct={s.attendance.pct} />
          {s.checks_flagged > 0 ? <Badge tone="warning"><ClipboardCheck className="h-3 w-3" /> {s.checks_flagged} checks flagged</Badge> : null}
          {s.homework_personal > 0 ? <Badge tone="primary"><BookOpen className="h-3 w-3" /> {s.homework_personal} personal hw</Badge> : null}
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

      {s.scores.length > 0 ? (
        <div className="mt-3 border-t border-border pt-2">
          <p className="mb-1 flex items-center gap-1 text-xs font-semibold text-muted-foreground">
            <TrendingUp className="h-3.5 w-3.5" /> Test scores
          </p>
          <div className="flex flex-wrap gap-1.5">
            {s.scores.map((sc, i) => {
              const pct = sc.max_score ? (sc.score / sc.max_score) * 100 : 0;
              return (
                <Badge key={i} tone={pct >= 60 ? "success" : pct >= 40 ? "warning" : "danger"}>
                  {sc.cycle_name}: {sc.score}/{sc.max_score}
                </Badge>
              );
            })}
          </div>
        </div>
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

  if (isLoading) return <p className="py-12 text-center text-sm text-muted-foreground">Loading report…</p>;
  if (error || !data) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        <p>You can view reports only for students in classes you teach.</p>
        <Link href="/students" className="mt-2 inline-block underline">Back to students</Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/students" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Students
      </Link>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{data.full_name}</h1>
          <p className="text-sm text-muted-foreground">{data.class_label ?? "No class assigned"}</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <AttendancePill pct={data.attendance.pct} />
          {data.band ? <Badge tone="primary">Band {data.band}</Badge> : null}
        </div>
      </div>

      {data.growth_areas.length > 0 ? (
        <section className="mb-4 rounded-xl border border-warning/40 bg-warning/5 p-4">
          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            <AlertTriangle className="h-4 w-4 text-warning" /> Growth areas
          </h2>
          <ul className="space-y-1 text-sm">
            {data.growth_areas.map((g, i) => <li key={i}>• {g}</li>)}
          </ul>
        </section>
      ) : null}

      {data.skills.length > 0 ? (
        <section className="mb-4 rounded-xl border border-border bg-card p-4">
          <h2 className="mb-2 text-sm font-semibold">Skill profile</h2>
          <div className="flex flex-wrap gap-1.5">
            {data.skills.map((sk) => {
              const pct = sk.max_score ? (sk.score / sk.max_score) * 100 : 0;
              return (
                <Badge key={sk.skill_area} tone={pct >= 60 ? "success" : pct >= 40 ? "warning" : "danger"}>
                  {sk.skill_area}: {sk.score}/{sk.max_score}
                </Badge>
              );
            })}
          </div>
        </section>
      ) : null}

      <div className="space-y-3">
        {data.subjects.map((s) => <SubjectCard key={s.class_subject_id} s={s} />)}
        {data.subjects.length === 0 ? (
          <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
            No subjects set up for this class yet.
          </p>
        ) : null}
      </div>

      <div className="mt-4 rounded-xl border border-border bg-card p-4 text-sm">
        <TimelineBlock studentId={data.student_id} />
      </div>

      {data.band_history.length > 1 ? (
        <p className="mt-4 text-xs text-muted-foreground">
          Band history: {data.band_history.map((b) => `${b.tier} (${b.set_on})`).join(" → ")}
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
