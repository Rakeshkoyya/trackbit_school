"use client";

// My Class → ABC bands (founder, 2026-08-05; expanded same day).
//
// Which of her children is at what level, **per subject**. `D-75`: there is no
// overall letter, and that is the point — one letter for a child who reads two
// years below grade and is fine at arithmetic described neither, and the daily
// check generator then handed him easier maths.
//
// So the unit here is the PLACEMENT, not the child: a boy who is A in Maths and
// C in Hindi is counted in both columns. Only a subject row collapses back to
// children, and the caption says so on every mounting — the obvious "fix" is to
// collapse him to one row, and that quietly reinstates the letter the module
// deleted.
//
// Founder 2026-08-05, two changes:
//
//   · **"Not assessed" is no longer a tile.** Beside A, B and C it read as a
//     fourth tier, which is the one thing it must never be. It survives as the
//     denominator on the header ("11 of 15 assessed") — every figure in this
//     product carries its denominator (ux §4) — and as the empty part of the
//     bar, drawn in the dashed no-record texture rather than as a step on the
//     ramp.
//   · **A subject expands to its children**, with how each is doing in THAT
//     subject. The percentage carries the scale it came from: `core/exams.py`
//     refuses to pool a slip test with a term paper, so a bare number here
//     would be exactly what the exam module exists to prevent. Nothing recorded
//     shows as "no marks yet", never 0%.
//
// And the list inside a tier is ordered A → B → C then by NAME, never by the
// percentage — a band is a teaching group, and sorting children by their marks
// turns it into a ranking (`S-170`).

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, Layers } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BAND_COLOR } from "@/components/charts";
import { MyClassShell } from "@/components/school/my-class-shell";
import { EmptyState } from "@/components/ui/empty-state";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import type { MyClassBandStudent, MyClassBandSubject } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const TIERS = [
  { key: "a", letter: "A", label: "Working comfortably" },
  { key: "b", letter: "B", label: "Keeping up" },
  { key: "c", letter: "C", label: "Needs support" },
] as const;

/** One child's row inside a tier. Two figures, each with its denominator, and
 *  neither of them a rank. */
function StudentRow({ s }: { s: MyClassBandStudent }) {
  return (
    <Link href={`/students/${s.student_id}`}
      className="grid grid-cols-[1.5rem_1fr_auto_auto] items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-muted/50">
      <span className="h-4 w-1 rounded-full justify-self-center"
        style={{ background: BAND_COLOR[s.tier] }} />
      <span className="min-w-0">
        <span className="block truncate text-[13px]">{s.full_name}</span>
        {s.roll_no ? (
          <span className="font-mono text-[10px] text-muted-foreground">
            roll {s.roll_no}
          </span>
        ) : null}
      </span>
      <span className="text-right font-mono text-[11px] tabular-nums">
        {s.pct != null ? (
          <>
            <span className="text-[13px]">{s.pct}%</span>
            {/* Which bucket the figure came from — never a blended number. */}
            <span className="ml-1 text-[10px] text-muted-foreground">
              {s.tests_taken} of {s.tests_held} {s.scale === "major" ? "major" : "tests"}
            </span>
          </>
        ) : (
          <span className="text-[10px] text-muted-foreground">no marks yet</span>
        )}
      </span>
      <span className="w-16 text-right font-mono text-[10px] tabular-nums text-muted-foreground">
        {s.attendance_pct != null ? `${s.attendance_pct}% present` : "—"}
      </span>
    </Link>
  );
}

function SubjectCard({ s }: { s: MyClassBandSubject }) {
  const [open, setOpen] = useState(false);
  const total = s.assessed + s.not_assessed;

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <button type="button" onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full flex-wrap items-baseline justify-between gap-2 border-b border-border px-4 py-2.5 text-left transition-colors hover:bg-muted/40">
        <span className="flex items-center gap-1.5">
          <ChevronRight className={cn("h-3.5 w-3.5 text-muted-foreground transition-transform",
            open && "rotate-90")} />
          <span className="text-sm font-semibold">{s.subject_name}</span>
        </span>
        {/* The denominator, which is the only form "not assessed" takes now. */}
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          {s.assessed} of {total} assessed
        </span>
      </button>

      <div className="grid gap-3 px-4 py-3 sm:grid-cols-3">
        {TIERS.map((t) => (
          <div key={t.key}>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-sm"
                style={{ background: BAND_COLOR[t.letter] }} />
              <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                Band {t.letter}
              </span>
            </span>
            <span className="mt-1 block font-mono text-[19px] leading-none tabular-nums">
              {s[t.key]}
              {/* Divided by what was ASSESSED — never by the roster. */}
              {s.assessed ? (
                <span className="ml-1.5 text-[11px] text-muted-foreground">
                  {Math.round((s[t.key] / s.assessed) * 100)}%
                </span>
              ) : null}
            </span>
            <span className="mt-0.5 block text-[10px] leading-snug text-muted-foreground">
              {t.label}
            </span>
          </div>
        ))}
      </div>

      {s.assessed ? (
        <div className="flex h-2.5 w-full overflow-hidden">
          {TIERS.map((t) => (s[t.key] ? (
            <span key={t.key} style={{ flex: s[t.key], background: BAND_COLOR[t.letter] }}
              title={`${s[t.key]} in band ${t.letter}`} />
          ) : null))}
          {s.not_assessed ? (
            // Not a step on the ramp: the absence of a record, drawn as one.
            <span style={{ flex: s.not_assessed }}
              className="border border-dashed border-muted-foreground/40 bg-muted/30"
              title={`${s.not_assessed} not assessed — not a band`} />
          ) : null}
        </div>
      ) : null}

      {open ? (
        <div className="border-t border-border bg-muted/15 px-2 py-2">
          {s.students.length ? (
            <>
              <div className="grid grid-cols-[1.5rem_1fr_auto_auto] gap-3 px-2 pb-1.5">
                <span />
                <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                  Child
                </span>
                <span className="text-right font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                  In {s.subject_name}
                </span>
                <span className="w-16 text-right font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                  Attendance
                </span>
              </div>
              <div className="space-y-0.5">
                {s.students.map((st) => (
                  <StudentRow key={st.student_id} s={st} />
                ))}
              </div>
              {s.not_assessed ? (
                <p className="px-2 pt-2 text-[10px] leading-snug text-muted-foreground">
                  {s.not_assessed} {s.not_assessed === 1 ? "child has" : "children have"}{" "}
                  not been assessed in {s.subject_name}. Not sitting the test is
                  not a band — they are simply not on the list.
                </p>
              ) : null}
            </>
          ) : (
            <p className="px-2 py-3 text-[12px] text-muted-foreground">
              Nobody in this class has been assessed in {s.subject_name} yet.
            </p>
          )}
        </div>
      ) : null}
    </section>
  );
}

function BandsInner({ classId }: { classId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["my-class", "bands", classId],
    queryFn: () => schoolApi.myClassBands(classId),
  });

  if (isLoading) return <PageLoading label="Loading bands…" />;
  if (!data) return null;

  if (!data.monitored) {
    return (
      <EmptyState icon={Layers} title="No subject is on the support programme yet"
        body="An admin chooses which subjects the school monitors in Setup → Settings → Support programme. Until then there are no bands to show — which is not the same as everybody being fine." />
    );
  }

  return (
    <div>
      <p className="mb-1 text-[15px] font-medium leading-snug">{data.headline}</p>
      <p className="mb-4 text-[11px] leading-snug text-muted-foreground">
        Counted in <span className="font-medium">placements, not children</span> — a
        child who is A in one subject and C in another appears in both rows. There
        is no overall letter, on purpose. Open a subject to see who is where.
      </p>

      <div className="space-y-3">
        {data.subjects.map((s) => <SubjectCard key={s.subject_id} s={s} />)}
      </div>

      <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
        A band is a teaching group, never a label on a child, and it never reaches
        a parent (P4). To move one, record a test —{" "}
        <Link href="/bands" className="text-primary hover:underline">the programme</Link>{" "}
        is where the assessment and the weekly check-ins live.
      </p>
    </div>
  );
}

export default function MyClassBandsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyClassShell
        title={(k) => `${k.class_label} · ABC bands`}
        subtitle={() => "Who is at what level, in each monitored subject"}>
        {(k) => <BandsInner classId={k.class_id} />}
      </MyClassShell>
    </AuthGuard>
  );
}
