"use client";

// My Class → ABC bands (founder, 2026-08-05).
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
// Two more rules the screen must not break: percentages divide by what was
// ASSESSED, never by the roster; and "not assessed" is not a step on the ramp —
// a child who did not sit the test is not a C.

import { useQuery } from "@tanstack/react-query";
import { Layers } from "lucide-react";
import Link from "next/link";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BAND_COLOR } from "@/components/charts";
import { MyClassShell } from "@/components/school/my-class-shell";
import { EmptyState } from "@/components/ui/empty-state";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";

const TIERS = [
  { key: "a", letter: "A", label: "Working comfortably" },
  { key: "b", letter: "B", label: "Keeping up" },
  { key: "c", letter: "C", label: "Needs support" },
] as const;

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
        is no overall letter, on purpose.
      </p>

      <div className="space-y-3">
        {data.subjects.map((s) => (
          <section key={s.subject_id}
            className="overflow-hidden rounded-xl border border-border bg-card">
            <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border px-4 py-2.5">
              <span className="text-sm font-semibold">{s.subject_name}</span>
              <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                {s.assessed} of {s.assessed + s.not_assessed} assessed
              </span>
            </header>

            <div className="grid gap-3 px-4 py-3 sm:grid-cols-4">
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
              <div>
                <span className="flex items-center gap-1.5">
                  {/* Its own texture, never a tier and never a colour on the ramp. */}
                  <span className="h-2.5 w-2.5 rounded-sm border border-dashed border-muted-foreground/60" />
                  <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                    Not assessed
                  </span>
                </span>
                <span className="mt-1 block font-mono text-[19px] leading-none tabular-nums text-muted-foreground">
                  {s.not_assessed}
                </span>
                <span className="mt-0.5 block text-[10px] leading-snug text-muted-foreground">
                  Has not sat the test — not a band
                </span>
              </div>
            </div>

            {s.assessed ? (
              <div className="flex h-2.5 w-full overflow-hidden">
                {TIERS.map((t) => (s[t.key] ? (
                  <span key={t.key} style={{ flex: s[t.key], background: BAND_COLOR[t.letter] }}
                    title={`${s[t.key]} in band ${t.letter}`} />
                ) : null))}
                {s.not_assessed ? (
                  <span style={{ flex: s.not_assessed }}
                    className="border border-dashed border-muted-foreground/40 bg-muted/30"
                    title={`${s.not_assessed} not assessed`} />
                ) : null}
              </div>
            ) : null}
          </section>
        ))}
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
