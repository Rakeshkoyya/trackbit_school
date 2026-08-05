"use client";

/**
 * `Support child` (V1-9, `D-72`/`D-87`/`S-164`/`S-165`).
 *
 * 60 seconds. This is the screen the whole module lives or dies on, because it
 * is the only one that asks a teacher to type about one child, by hand,
 * repeatedly.
 *
 * **`S-164` is the design: the page opens already written.** Everything in *His
 * week* is read from capture five other teachers already did — attendance,
 * lesson observations, daily checks, homework, evening study. She is never asked
 * to record what the product already knows, and she gets value before giving
 * data (P3).
 *
 * `S-167`: the exit criterion is on screen from day one, because a goal decided
 * at the end is a judgement, not a target. `D-76`: **she proposes readiness; a
 * test moves the band** — she is the person who knows he is ready, and also the
 * person with an interest in him being ready.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, CalendarDays, Check, Flag, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SupportAssignments } from "@/components/school/support-assignments";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PageLoading } from "@/components/ui/page-loading";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

const KIND_TONE: Record<string, string> = {
  absent: "text-[color:var(--danger,#7f1d1d)]",
  late: "text-[color:var(--warning,#8a6d1a)]",
};

function ChildInner() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [workedOn, setWorkedOn] = useState("");
  const [changed, setChanged] = useState("");
  const [next, setNext] = useState("");
  const [ready, setReady] = useState(false);
  const [showDescriptors, setShowDescriptors] = useState(false);

  const { data, error } = useQuery({
    queryKey: ["support-child", id], queryFn: () => schoolApi.supportChild(id), retry: false });

  const save = useMutation({
    mutationFn: () => schoolApi.supportCheckIn(id, {
      worked_on: workedOn.trim() || undefined,
      what_changed: changed.trim() || undefined,
      next_step: next.trim() || undefined,
      ready_to_retest: ready }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["support-child", id] });
      qc.invalidateQueries({ queryKey: ["support-list"] });
      setWorkedOn(""); setChanged(""); setNext(""); setReady(false);
      toast.success("Check-in saved");
    },
    onError: (e) => showApiError(e, "Could not save the check-in"),
  });

  const close = useMutation({
    mutationFn: (status: string) => schoolApi.closeSupportPlan(id, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["support-child", id] });
      qc.invalidateQueries({ queryKey: ["support-list"] });
      toast.success("Closed — the daily check for this goal stops now");
    },
    onError: (e) => showApiError(e, "Could not close it"),
  });

  if (error) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        <p>This child is another teacher&apos;s to support.</p>
        <Link href="/bands/my-students" className="mt-2 inline-block underline">Back to my students</Link>
      </div>
    );
  }
  if (!data) return <PageLoading />;

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link href="/bands/my-students" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> My support students
      </Link>

      {/* the headline — the band, since when, and what "done" means */}
      <header className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold tracking-tight">{data.full_name}</h1>
          {data.class_label ? <Badge tone="neutral">{data.class_label}</Badge> : null}
          {data.subject_name ? <Badge tone="neutral">{data.subject_name}</Badge> : null}
          {data.status !== "active" ? <Badge tone="success">{data.status}</Badge> : null}
        </div>
        <p className="mt-2 text-sm leading-relaxed">{data.headline}</p>
        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          {data.owner_name ? <span>Owner: {data.owner_name}</span> : null}
          {data.latest_pct != null
            ? <span>Last test: {data.latest_pct}% ({data.latest_test})</span> : null}
          <button type="button" className="inline-flex items-center gap-1 underline"
            onClick={() => setShowDescriptors(!showDescriptors)}>
            <BookOpen className="h-3 w-3" /> what the bands mean
          </button>
        </div>
        {showDescriptors ? (
          <ul className="mt-3 space-y-1.5 border-t border-border pt-3">
            {data.descriptors.map((d) => (
              <li key={d.tier} className="flex gap-2 text-xs">
                <span className="font-semibold">Band {d.tier}</span>
                <span className="text-muted-foreground">{d.text}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </header>

      {/* The written summary — a READ over the facts below it, never a new
          record. `source` says whether a model wrote it or the deterministic
          builder did, because a reader is entitled to know which. It is
          deliberately above the week and below the goal: it summarises, so it
          must not be the only thing on screen. */}
      <SummaryBlock interventionId={id} />

      {/* his week, already recorded — nothing here was typed twice */}
      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <CalendarDays className="h-4 w-4" /> His week, already recorded
        </h2>
        {data.week.length ? (
          <ul className="mt-2 space-y-1">
            {data.week.map((row, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="w-20 shrink-0 text-xs text-muted-foreground">{row.date}</span>
                <span className={KIND_TONE[row.kind] ?? ""}>{row.text}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-muted-foreground">
            Nothing was flagged this week — no absences, no missed homework, no notes.
          </p>
        )}
        <p className="mt-2 text-xs text-muted-foreground">
          Read from what his other teachers already recorded. You are never asked to type it again.
        </p>
      </section>

      {/* Assignments — per-student homework, given and checked here. Not a
          support-specific store: the child's homework history and this block
          are the same rows. */}
      <SupportAssignments studentId={data.student_id} classSubjectId={data.class_subject_id} />

      {/* four fields, once a week */}
      {data.status === "active" ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="text-sm font-semibold">This week&apos;s check-in</h2>
          <div className="mt-3 space-y-3">
            <div>
              <Label htmlFor="w1">What we worked on</Label>
              <input id="w1" value={workedOn} onChange={(e) => setWorkedOn(e.target.value)}
                placeholder="flashcards, 10 min daily"
                className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm" />
            </div>
            <div>
              <Label htmlFor="w2">What changed</Label>
              <input id="w2" value={changed} onChange={(e) => setChanged(e.target.value)}
                placeholder="read a full paragraph unaided"
                className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm" />
            </div>
            <div>
              <Label htmlFor="w3">What&apos;s next</Label>
              <input id="w3" value={next} onChange={(e) => setNext(e.target.value)}
                placeholder="move to the Ch 5 passage"
                className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm" />
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={ready} onChange={(e) => setReady(e.target.checked)} />
              <Flag className="h-3.5 w-3.5" /> Ready to re-test
            </label>
            <p className="text-xs text-muted-foreground">
              Flagging readiness tells the school he is ready — the band itself moves on a
              test, from the exam screen. Blank fields are fine: a week where nothing
              happened is a true answer.
            </p>
            <Button disabled={save.isPending} onClick={() => save.mutate()}>
              <Check className="h-4 w-4" /> Save check-in
            </Button>
          </div>
        </section>
      ) : null}

      {/* the thread — movement is only visible as a sequence */}
      {data.checkpoints.length ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="text-sm font-semibold">Before this</h2>
          <ul className="mt-2 space-y-2">
            {data.checkpoints.map((c) => (
              <li key={c.id} className="border-l-2 border-border pl-3 text-sm">
                <p className="text-xs text-muted-foreground">
                  week of {c.week_start}{c.author_name ? ` · ${c.author_name}` : ""}
                  {c.ready_to_retest ? " · flagged ready" : ""}
                </p>
                {c.worked_on ? <p>{c.worked_on}</p> : null}
                {c.what_changed ? (
                  <p className="text-muted-foreground">→ {c.what_changed}</p>
                ) : null}
                {c.next_step ? (
                  <p className="text-xs text-muted-foreground">next: {c.next_step}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {data.status === "active" ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" disabled={close.isPending}
            onClick={() => close.mutate("achieved")}>
            He&apos;s there — close this plan
          </Button>
          <Button variant="outline" size="sm" disabled={close.isPending}
            onClick={() => close.mutate("dropped")}>
            Stop supporting for now
          </Button>
          <p className="text-xs text-muted-foreground">
            Closing stops the daily targeted check for this goal.
          </p>
        </div>
      ) : null}
    </div>
  );
}

/**
 * The summary and key insights (founder 2026-08-04).
 *
 * Nothing here is a diagnosis and nothing here reaches a parent (P4). The
 * server refuses to write about the child's ability — see `ai/band_summary.py`
 * — and with no AI key it is the deterministic sentences, which is the normal
 * case in dev and in any school without a key. Never blank.
 */
function SummaryBlock({ interventionId }: { interventionId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["support-summary", interventionId],
    queryFn: () => schoolApi.supportSummary(interventionId),
  });
  if (isLoading || !data?.summary) return null;
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold">
        <Sparkles className="h-4 w-4" /> Summary
        <span className="font-normal text-xs text-muted-foreground">
          {data.source === "ai" ? "· written from the record below" : "· computed"}
        </span>
      </h2>
      <p className="mt-2 text-sm leading-relaxed">{data.summary}</p>
      {data.insights.length ? (
        <ul className="mt-3 space-y-1.5 border-t border-border pt-3">
          {data.insights.map((i, n) => (
            <li key={n} className="flex gap-2 text-sm">
              <span className="text-muted-foreground">&middot;</span>
              <span>{i}</span>
            </li>
          ))}
        </ul>
      ) : null}
      {data.based_on.length ? (
        <p className="mt-3 text-xs text-muted-foreground">
          From {data.based_on.join(" · ")}.
        </p>
      ) : null}
    </section>
  );
}

export default function SupportChildPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ChildInner />
    </AuthGuard>
  );
}
