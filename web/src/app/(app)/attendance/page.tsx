"use client";

// Attendance — every teacher's register book (founder, 2026-08-05, rev 2).
//
// THE PROBLEM THIS CLOSES. The school's rule is that the class teacher takes the
// register at period one, and **if she is away any teacher of the class can**.
// The permission has existed since V2-P2; the door had not. A register only one
// person can open is a register that does not get taken on the days it matters.
//
// THE SHAPE (rev 2, from the founder's walkthrough). A row of class buttons —
// only the classes this teacher is assigned to, the first one open by default —
// with **Take attendance** beside them, and underneath, the month as a register
// book. The book is a VIEW: it is the artifact a school already keeps, and
// reading it is a different act from writing it. Marking happens on its own
// screen, where the whole roll is in front of you.
//
// The rule the class strip must not break: **a class nobody has marked shows the
// roll and a word.** Not 0%, not red. "Nobody has taken it yet" and "nobody came
// in" are opposite facts, and only one of them is news about children.

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ClipboardList, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { RegisterBook } from "@/components/school/register-book";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { PageError } from "@/components/ui/page-error";
import { PageLoading } from "@/components/ui/page-loading";
import { thisMonth, todayKey } from "@/lib/format";
import { schoolApi } from "@/lib/school-api";
import type { MyAttendanceClass, SchoolTone } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const TONE_TEXT: Record<SchoolTone, string> = {
  neutral: "text-muted-foreground",
  green: "text-success",
  amber: "text-warning",
  red: "text-danger",
};

/** Today's state for the picked class, and the one button that changes it. */
function TodayStrip({ klass, day }: { klass: MyAttendanceClass; day: string }) {
  return (
    <section className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
      <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-md",
        klass.marked
          ? "bg-[color:var(--success,#234a37)]/10 text-[color:var(--success,#234a37)]"
          : "bg-muted text-muted-foreground")}>
        {klass.marked ? <CheckCircle2 className="h-4 w-4" /> : <Users className="h-4 w-4" />}
      </span>

      <span className="min-w-0 flex-1">
        <span className={cn("block text-[13px] font-medium leading-snug", TONE_TEXT[klass.tone])}>
          {klass.headline}
        </span>
        <span className="mt-0.5 block font-mono text-[11px] tabular-nums text-muted-foreground">
          {/* The roll is stated whether or not anything is marked; "in" only
              appears once somebody has actually looked. */}
          {klass.roster} on the roll
          {klass.marked ? ` · ${klass.present} in · ${klass.absent} away` : ""}
          {klass.late ? ` · ${klass.late} late` : ""}
        </span>
        {klass.absentee_names.length ? (
          <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
            Away today: {klass.absentee_names.join(", ")}
          </span>
        ) : null}
      </span>

      <span className="flex shrink-0 flex-col items-end gap-1">
        <Link
          href={`/attendance/${klass.class_id}?period=${klass.suggested_period_no}&date=${day}`}
          className={cn(
            "flex h-9 items-center justify-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors",
            klass.marked
              ? "border border-border bg-card hover:bg-muted"
              : "bg-primary text-primary-foreground hover:opacity-90")}>
          <ClipboardList className="h-4 w-4" />
          {klass.marked ? "Edit today's register" : "Take attendance"}
        </Link>
        {/* The one thing worth warning about before the tap. */}
        {!klass.marked && klass.first_of_day ? (
          <span className="text-[10px] leading-snug text-muted-foreground">
            Families of absent children are told
          </span>
        ) : null}
      </span>
    </section>
  );
}

function AttendanceInner() {
  const day = todayKey();
  const [picked, setPicked] = useState<string | null>(null);
  const [month, setMonth] = useState<string>(thisMonth);

  const { data, isLoading, error } = useQuery({
    queryKey: ["attendance", "my-classes", day],
    queryFn: () => schoolApi.myAttendance(day),
    retry: false,
  });

  // The picked class drives the register below, so it is resolved before the
  // second query is described — and it defaults to the first, never to "none".
  const classes = data?.classes ?? [];
  const active = classes.find((c) => c.class_id === picked) ?? classes[0];

  const register = useQuery({
    queryKey: ["class-register-for", active?.class_id, month],
    queryFn: () => schoolApi.classRegisterFor(active!.class_id, month),
    enabled: !!active,
  });

  if (isLoading) return <PageLoading label="Loading your classes…" />;
  // Before the "no classes" empty state, because they are not the same thing.
  // A failed request is not the school declining to assign her anything, and
  // saying so sends her to an admin to fix a problem she does not have.
  if (error) return <PageError error={error} fallback="Could not load your classes." />;
  if (!active) {
    return (
      <EmptyState icon={Users} title="No classes assigned to you"
        body="You take the register for the classes you teach a subject in, and for your own homeroom. Ask your admin to assign you in Staff → People." />
    );
  }

  return (
    <div>
      {/* Class buttons — only what this teacher is assigned to. A class with an
          open register carries a tick, so the strip answers "what is left?" at a
          glance before anything below it is read. */}
      <div className="mb-4 flex flex-wrap gap-1.5">
        {classes.map((c) => (
          <button key={c.class_id} type="button" onClick={() => setPicked(c.class_id)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm",
              c.class_id === active.class_id
                ? "border-primary bg-primary/10 font-medium" : "border-border hover:bg-muted")}>
            {c.class_label}
            {c.is_class_teacher ? (
              <span className="font-mono text-[9px] uppercase tracking-wide text-muted-foreground">
                mine
              </span>
            ) : null}
            {c.marked ? (
              <CheckCircle2 className="h-3.5 w-3.5 text-success" />
            ) : (
              <span className="h-1.5 w-1.5 rounded-full bg-warning" title="not taken yet" />
            )}
          </button>
        ))}
      </div>

      <p className="mb-3 text-[13px] leading-snug">{data?.headline}</p>

      <TodayStrip klass={active} day={day} />

      {register.error ? (
        <PageError error={register.error} fallback="Could not load this register." />
      ) : register.isLoading || !register.data ? (
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
      ) : (
        <RegisterBook data={register.data} month={month} onMonth={setMonth}
          title={active.class_label} />
      )}
    </div>
  );
}

export default function AttendancePage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <PageHeader
        title="Attendance"
        subtitle="Your classes, and the month as it stands. If the class teacher is away, anyone who teaches the class can take the register."
      />
      <AttendanceInner />
    </AuthGuard>
  );
}
