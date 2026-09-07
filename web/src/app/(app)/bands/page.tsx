"use client";

/**
 * ABC bands → Overview.
 *
 * The programme in one screen: the movement sentence, the three distributions,
 * then the two lists that carry an action — children still in C, and the
 * class-subjects nobody has assessed.
 *
 * The distribution block is `BandDistributionView`, the same component the
 * dashboard mounts in compact form off the same endpoint, so this tab and the
 * dashboard card can never disagree (`S-51`).
 *
 * `S-170` holds: there is no ranking of teachers by children moved anywhere on
 * this page. The children handed to the best teacher are by construction the
 * hardest ones.
 */

import { useQuery } from "@tanstack/react-query";
import { ChevronRight, UserPlus } from "lucide-react";
import Link from "next/link";

import { BandDistributionView } from "@/components/insights/band-distribution";
import { Empty, Section } from "@/components/insights/shared";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

export default function BandsOverviewPage() {
  const { yearId } = useYear();
  const { data: scope } = useQuery({ queryKey: ["band-scope"], queryFn: schoolApi.bandScope });
  const { data, isLoading } = useQuery({
    queryKey: ["band-distribution", yearId],
    queryFn: () => schoolApi.bandDistribution(),
  });
  // Only an admin may read the programme board; a teacher's overview is her own
  // distribution plus her own children, which the tabs beside this one carry.
  const isAdmin = scope?.is_admin ?? false;
  const { data: programme } = useQuery({
    queryKey: ["band-programme", yearId],
    queryFn: () => schoolApi.bandProgramme(),
    enabled: isAdmin,
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader
          title="ABC bands"
          subtitle={
            data?.subjects.length
              // FB-1i: "Term-2 · English, Hindi, Maths" reads as a LIMIT, and a
              // teacher wrote in asking us to "add other subjects under the ABC
              // category". Nothing needed adding — the monitored set is
              // configuration and an admin can change it in Settings — but
              // nothing on this screen said so unless the set was empty. Name
              // the list for what it is, and say who can change it.
              ? `${data.term_name ?? "This term"} · monitoring ${data.subjects.join(", ")}`
              : "Staff-only support tiers — never shared with parents"
          }
        />
        <YearSwitcher />
      </div>

      {data?.subjects.length ? (
        <p className="-mt-2 mb-4 text-xs text-muted-foreground">
          {isAdmin ? (
            <>
              Any subject can be monitored —{" "}
              <Link href="/setup/settings"
                className="underline underline-offset-4 hover:text-foreground">
                choose them in Settings → Support programme
              </Link>
              .
            </>
          ) : (
            "Any subject can be monitored — ask your admin to add one in Settings → Support programme."
          )}
        </p>
      ) : null}

      {isLoading || !data ? (
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
      ) : (
        <div className="space-y-6">
          <BandDistributionView data={data} />

          {isAdmin && programme ? (
            <>
              <Section
                title="Still in Band C"
                hint="Named with the subject — one owner per subject, so a child can appear twice."
              >
                {programme.stuck.length ? (
                  <div className="space-y-2">
                    {programme.stuck.map((r) => (
                      <div
                        key={`${r.student_id}-${r.subject_id}`}
                        className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium">
                            <Link href={`/students/${r.student_id}`} className="hover:underline">
                              {r.full_name}
                            </Link>
                            <span className="ml-2 text-xs text-muted-foreground">
                              {r.class_label} · {r.subject_name}
                            </span>
                          </p>
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            {r.since ? `C since ${r.since}` : "Band C"}
                            {r.owner_name ? ` · owner ${r.owner_name}` : " · no owner yet"}
                            {r.last_checkin
                              ? ` · last check-in ${r.last_checkin}`
                              : r.owner_name
                                ? " · never checked in"
                                : ""}
                          </p>
                        </div>
                        {r.owner_name ? (
                          <Badge tone="neutral">assigned</Badge>
                        ) : (
                          <Link
                            href="/bands/allocation"
                            className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90"
                          >
                            <UserPlus className="h-4 w-4" />
                            Assign
                          </Link>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <Empty>No child is in Band C without movement this term.</Empty>
                )}
              </Section>

              {/* A gap in the record — a word, never a zero and never red. */}
              {programme.not_assessed.length ? (
                <section className="rounded-xl border border-dashed border-border p-4">
                  <h2 className="text-sm font-semibold">Not assessed yet</h2>
                  <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                    {programme.not_assessed.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                  <Link
                    href="/bands/manage"
                    className="mt-3 inline-flex items-center gap-1 text-xs font-medium underline underline-offset-2"
                  >
                    Assess a class <ChevronRight className="h-3 w-3" />
                  </Link>
                </section>
              ) : null}
            </>
          ) : null}
        </div>
      )}
    </div>
  );
}
