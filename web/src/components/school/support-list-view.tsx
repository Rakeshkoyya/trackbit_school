"use client";

/**
 * `My support students` — the owner's list (V1-9, `D-71`/`D-77`/`D-87`).
 *
 * Friday afternoon, phone, bag packed. **Six children, five minutes, total.** If
 * this screen takes longer than that it will be opened twice and never again.
 *
 * Her children are grouped by **subject**, because ownership is per subject: a
 * child who is C in Hindi and C in Maths sits on two teachers' lists, and
 * neither is guessing whose he is.
 *
 * Extracted from `/support` when ABC bands got its own area (founder
 * 2026-08-04), so the same list renders in both places rather than being written
 * twice and drifting.
 *
 * Deliberately not here: other owners' children · the whole class's bands (that
 * is the admin's screen) · **any comparison of her against other owners**
 * (`S-170`) · a completion percentage for her check-ins. A finished week must
 * read as finished, and an unfinished one must not read as a failing grade.
 */

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronRight, HeartHandshake } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import type { SupportStudentRow } from "@/lib/school-types";

function Row({ r }: { r: SupportStudentRow }) {
  const overdue = (r.weeks_since_checkin ?? 99) >= 3;
  return (
    <Link
      href={`/support/${r.intervention_id}`}
      className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 transition-colors hover:bg-muted/40"
    >
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">
          {r.full_name}
          {r.class_label ? (
            <span className="ml-2 text-xs text-muted-foreground">{r.class_label}</span>
          ) : null}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {r.since ? `in since ${r.since}` : "new"}
          {r.checkins
            ? ` · ${r.checkins} check-in${r.checkins === 1 ? "" : "s"}`
            : " · no check-in yet"}
          {overdue && r.weeks_since_checkin != null
            ? ` · nothing for ${r.weeks_since_checkin} weeks`
            : ""}
        </p>
      </div>
      {r.ready_to_retest ? <Badge tone="success">ready to re-test</Badge> : null}
      {r.checked_in_this_week ? (
        <CheckCircle2 className="h-4 w-4 text-[color:var(--success,#234a37)]" />
      ) : (
        <span className="text-xs font-medium text-primary">check in</span>
      )}
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
    </Link>
  );
}

export function SupportListView() {
  const { data } = useQuery({ queryKey: ["support-list"], queryFn: () => schoolApi.supportList() });
  if (!data) return <PageLoading label="Loading your students…" />;

  return (
    <>
      <p className="rounded-xl border border-border bg-card p-4 text-sm leading-relaxed">
        {data.headline}
      </p>

      {data.groups.map((g) => (
        <section key={g.subject_name} className="mt-5">
          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            <HeartHandshake className="h-4 w-4" /> {g.subject_name}
            <span className="font-normal text-muted-foreground">
              · {g.rows.length} child{g.rows.length === 1 ? "" : "ren"}
            </span>
          </h2>
          <div className="space-y-2">
            {g.rows.map((r) => (
              <Row key={r.intervention_id} r={r} />
            ))}
          </div>
        </section>
      ))}

      {/* The only place the work pays off — a list that only ever grows is a
          list nobody opens. */}
      {data.moved_on.length ? (
        <section className="mt-6">
          <h2 className="mb-2 text-sm font-semibold">Moved on</h2>
          <div className="space-y-2">
            {data.moved_on.map((r) => (
              <div
                key={r.intervention_id}
                className="flex items-center gap-3 rounded-lg border border-border px-4 py-2.5 text-sm"
              >
                <span className="min-w-0 flex-1">
                  {r.full_name}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {r.subject_name} · {r.status === "achieved" ? "moved up" : "closed"}
                  </span>
                </span>
                <Badge tone="success">done</Badge>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}
