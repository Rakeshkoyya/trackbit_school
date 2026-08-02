"use client";

/**
 * The support programme board (V1-9, `D-67`/`D-73`/`S-169`).
 *
 * It used to be three columns of names and a count. It could answer *how many
 * are in C* and nothing else — not who moved, not who owns them, not who has
 * been C since April, which are all four of the questions the programme is
 * actually about.
 *
 * So: **movement is the headline**, the children still in C are named *with
 * their subject* (`S-188` — a child can have two owners, and "Kabir Shah — owner
 * Priya" lets each of them assume the other is on it), and the distribution is
 * not on this screen at all: it is a photograph of a decision already made, and
 * it looks identical in a school where nobody has moved for a year.
 *
 * Deliberately absent: **any ranking of teachers by children moved** (`S-170`).
 * The children handed to the best teacher are, by construction, the hardest.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, ChevronRight, UserPlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useYear } from "@/contexts/year-context";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { ProgrammeRow } from "@/lib/school-types";

function OwnerSheet({ row, onClose }: { row: ProgrammeRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [member, setMember] = useState("");
  const [criterion, setCriterion] = useState("");
  const { data: members } = useQuery({ queryKey: ["members"], queryFn: appApi.members });
  const teachers = (members?.members ?? []).filter((x) => x.member_id);

  const save = useMutation({
    mutationFn: () => schoolApi.assignBandOwner({
      student_id: row!.student_id, subject_id: row!.subject_id,
      member_id: member || null, exit_criterion: criterion.trim() || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["band-programme"] });
      toast.success("Owner assigned — the child is on their list today");
      setMember(""); setCriterion(""); onClose();
    },
    onError: (e) => showApiError(e, "Could not assign"),
  });

  return (
    <Sheet open={!!row} onOpenChange={(v) => { if (!v) onClose(); }}
      title={row ? `${row.full_name} · ${row.subject_name}` : ""}>
      {row ? (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            One owner per subject. A child who is C in two subjects has two owners,
            and each knows exactly what hers is.
          </p>
          <div>
            <Label htmlFor="owner">Owner</Label>
            <select id="owner" className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={member} onChange={(e) => setMember(e.target.value)}>
              <option value="">the subject teacher (default)</option>
              {teachers.map((t) => (
                <option key={t.member_id!} value={t.member_id!}>{t.name}</option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="crit">Moves to B when… (optional)</Label>
            <textarea id="crit" rows={2} value={criterion} onChange={(e) => setCriterion(e.target.value)}
              placeholder="reads a grade-level passage at 60 wpm with ≤3 errors, twice running"
              className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm" />
            <p className="mt-1 text-xs text-muted-foreground">
              Written now, not judged at the end of term — otherwise the owner is
              scored on a judgement she also makes.
            </p>
          </div>
          <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
            Assign
          </Button>
        </div>
      ) : null}
    </Sheet>
  );
}

function BandsInner() {
  const { yearId } = useYear();
  const [ownerFor, setOwnerFor] = useState<ProgrammeRow | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["band-programme", yearId],
    queryFn: () => schoolApi.bandProgramme(),
  });
  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId], queryFn: () => schoolApi.classes(yearId!), enabled: !!yearId });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Support programme"
          subtitle={data?.subjects.length
            ? `${data.term_name ?? "This term"} · ${data.subjects.join(", ")}`
            : "Staff-only support tiers — never shared with parents"} />
        <YearSwitcher />
      </div>

      {isLoading || !data ? <div className="h-40 animate-pulse rounded-xl bg-muted" /> : (
        <div className="space-y-5">
          {/* movement, as a sentence */}
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm leading-relaxed">{data.headline}</p>
            {data.moved_up || data.slipped ? (
              <div className="mt-2 flex items-center gap-3 text-xs">
                <Badge tone="success">↑ {data.moved_up} moved up</Badge>
                <Badge tone={data.slipped ? "warning" : "neutral"}>↓ {data.slipped} slipped</Badge>
              </div>
            ) : null}
          </div>

          {data.stuck.length ? (
            <section>
              <h2 className="mb-2 text-sm font-semibold">Still in Band C</h2>
              <div className="space-y-2">
                {data.stuck.map((r) => (
                  <div key={`${r.student_id}-${r.subject_id}`}
                    className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
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
                          : r.owner_name ? " · never checked in" : ""}
                      </p>
                    </div>
                    <Button size="sm" variant={r.owner_name ? "outline" : "primary"}
                      onClick={() => setOwnerFor(r)}>
                      <UserPlus className="h-4 w-4" />
                      {r.owner_name ? "Reassign" : "Assign a teacher"}
                    </Button>
                  </div>
                ))}
              </div>
            </section>
          ) : null}

          {data.grid.length ? (
            <section>
              <h2 className="mb-2 text-sm font-semibold">By class and subject</h2>
              <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
                    <tr>
                      <th className="px-3 py-2">Class</th>
                      <th className="px-2 py-2">Subject</th>
                      <th className="px-2 py-2">In Band C</th>
                      <th className="px-2 py-2">Moved this term</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.grid.map((c) => (
                      <tr key={`${c.class_id}-${c.subject_id}`} className="border-t border-border">
                        <td className="px-3 py-1.5 font-medium">{c.class_label}</td>
                        <td className="px-2 py-1.5">{c.subject_name}</td>
                        <td className="px-2 py-1.5 tabular-nums">{c.c_count}</td>
                        <td className="px-2 py-1.5 text-xs">
                          <span className="font-medium">↑{c.moved_up}</span>
                          <span className="ml-2 text-muted-foreground">↓{c.slipped}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          {/* a class nobody assessed is a gap in the record — a word, never red */}
          {data.not_assessed.length ? (
            <section className="rounded-xl border border-dashed border-border p-4">
              <h2 className="text-sm font-semibold">Not assessed yet</h2>
              <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                {data.not_assessed.map((line) => <li key={line}>{line}</li>)}
              </ul>
            </section>
          ) : null}

          <section>
            <h2 className="mb-2 text-sm font-semibold">Assess a class</h2>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {classes.map((c) => (
                <Link key={c.id} href={`/students/bands/${c.id}`}
                  className="flex items-center justify-between rounded-lg border border-border bg-card px-4 py-3 text-sm hover:bg-muted/40">
                  <span className="font-medium">{c.name}{c.section ? `-${c.section}` : ""}</span>
                  <ChevronRight className="h-4 w-4 text-muted-foreground" />
                </Link>
              ))}
            </div>
            <p className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
              <ArrowUpRight className="h-3 w-3" />
              What a band means in your school — the monitored subjects and the
              descriptors — is set in Setup → Settings.
            </p>
          </section>
        </div>
      )}
      <OwnerSheet row={ownerFor} onClose={() => setOwnerFor(null)} />
    </div>
  );
}

export default function BandsPage() {
  return (
    <AuthGuard requireRole="admin">
      <BandsInner />
    </AuthGuard>
  );
}
