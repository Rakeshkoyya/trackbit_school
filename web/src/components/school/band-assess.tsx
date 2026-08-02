"use client";

/**
 * Assess a class, for one subject (V1-9, `D-70`/`D-75`/`Q-79`).
 *
 * This is the one screen in the product that legitimately touches every child in
 * a class — and it does not break P1v2, whose one-minute budget is about *daily*
 * capture. It still defaults: **a chosen test's marks pre-fill every row and the
 * teacher moves only the ones she disagrees with.** Assessment by hand, with
 * nothing pre-filled, is the `D-70` route for a school with no test yet.
 *
 * The rules the layout holds:
 *
 * - **Entry only** (`S-185`). Once a class is filed, a child changes band on a
 *   band test or a promoted test — a teacher's action on the exam screen, not
 *   an admin's slider here. That is what makes every later band row evidenced
 *   without anyone remembering to attach evidence.
 * - **The descriptor sits beside the slider**, not in a help menu (`S-166`). It
 *   is the only way two teachers band the same child the same way.
 * - **Not assessed is a word** — a child absent for the test gets no suggestion,
 *   never a C and never a zero.
 * - **No class total and no rank.** The tier is not a merit list.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { BandTier } from "@/lib/school-types";

export const TIERS: BandTier[] = ["A", "B", "C"];
export const TIER_TONE_MAP: Record<BandTier, "success" | "neutral" | "warning"> = {
  A: "success", B: "neutral", C: "warning",
};

export function BandAssess({ classId, subjectId, termId, cycleId, onFiled }: {
  classId: string;
  subjectId: string;
  termId: string | null;
  /** A locked test whose marks pre-fill the rows (`Q-79`). */
  cycleId?: string;
  onFiled?: () => void;
}) {
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<string, BandTier | null>>({});
  const [showDescriptors, setShowDescriptors] = useState(false);

  const { data: board } = useQuery({
    queryKey: ["band-class", classId, subjectId, termId, cycleId],
    queryFn: () => schoolApi.bandClassBoard({
      classId, subjectId, termId: termId ?? undefined, cycleId }),
  });

  const tierOf = (sid: string, current: BandTier | null, suggested: BandTier | null) =>
    sid in edits ? edits[sid] : (current ?? suggested);

  const file = useMutation({
    mutationFn: () => schoolApi.fileBands({
      class_id: classId, subject_id: subjectId, term_id: termId!,
      source: cycleId ? "test" : "observation",
      cycle_id: cycleId ?? null,
      rows: (board?.rows ?? []).map((r) => ({
        student_id: r.student_id,
        tier: tierOf(r.student_id, r.current_tier, r.suggested_tier),
      })),
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["band-class"] });
      qc.invalidateQueries({ queryKey: ["band-programme"] });
      setEdits({});
      toast.success(res.message);
      onFiled?.();
    },
    onError: (e) => showApiError(e, "Could not file the bands"),
  });

  if (!board) return <div className="h-48 animate-pulse rounded-xl bg-muted" />;

  const counts = TIERS.reduce<Record<string, number>>((acc, t) => {
    acc[t] = board.rows.filter(
      (r) => tierOf(r.student_id, r.current_tier, r.suggested_tier) === t).length;
    return acc;
  }, {});
  const unassessed = board.rows.filter(
    (r) => !tierOf(r.student_id, r.current_tier, r.suggested_tier)).length;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-sm font-semibold">
              {board.class_label} · {board.subject_name}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {board.cycle_name
                ? `Pre-filled from “${board.cycle_name}” — move only what you disagree with.`
                : "Your own assessment against the descriptors — nothing is pre-filled."}
              {" "}A ≥ {board.a_min}% · B ≥ {board.b_min}%
            </p>
          </div>
          <Button size="sm" variant="outline" onClick={() => setShowDescriptors(!showDescriptors)}>
            <BookOpen className="h-4 w-4" /> what the bands mean
          </Button>
        </div>
        {showDescriptors ? (
          <ul className="mt-3 space-y-1.5">
            {board.descriptors.map((d) => (
              <li key={d.tier} className="flex gap-2 text-xs">
                <Badge tone={TIER_TONE_MAP[d.tier as BandTier]}>Band {d.tier}</Badge>
                <span className="text-muted-foreground">{d.text}</span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2">Student</th>
              <th className="px-2 py-2">Marks</th>
              <th className="px-2 py-2">Band</th>
            </tr>
          </thead>
          <tbody>
            {board.rows.map((r) => {
              const tier = tierOf(r.student_id, r.current_tier, r.suggested_tier);
              const moved = r.suggested_tier && tier && tier !== r.suggested_tier;
              return (
                <tr key={r.student_id} className="border-t border-border">
                  <td className="whitespace-nowrap px-3 py-1.5 font-medium">
                    {r.full_name}
                    {r.roll_no ? <span className="ml-1.5 text-xs text-muted-foreground">#{r.roll_no}</span> : null}
                  </td>
                  <td className="px-2 py-1.5 text-xs text-muted-foreground">
                    {r.pct != null ? `${r.pct}%`
                      : board.cycle_id ? "did not sit it" : "—"}
                  </td>
                  <td className="px-2 py-1.5">
                    <div className="flex items-center gap-1">
                      {TIERS.map((t) => (
                        <button key={t} type="button"
                          onClick={() => setEdits((p) => ({
                            ...p, [r.student_id]: p[r.student_id] === t ? null : t }))}
                          className={`h-7 w-7 rounded-md border text-xs font-semibold transition ${
                            tier === t ? "border-primary bg-primary text-primary-foreground"
                              : "border-border text-muted-foreground hover:bg-muted/40"}`}>
                          {t}
                        </button>
                      ))}
                      {!tier ? (
                        <span className="ml-1 text-xs text-muted-foreground">not assessed</span>
                      ) : null}
                      {moved ? (
                        <span className="ml-1 text-xs text-muted-foreground">
                          ← you moved this from {r.suggested_tier}
                        </span>
                      ) : null}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          A: {counts.A} · B: {counts.B} · C: {counts.C}
          {unassessed ? ` · not assessed: ${unassessed}` : ""}
        </p>
        <Button disabled={!termId || file.isPending} onClick={() => file.mutate()}>
          <Check className="h-4 w-4" /> File these bands
        </Button>
      </div>
      {counts.C ? (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Users className="h-3.5 w-3.5" />
          After filing, give each Band C child an owner — that is the moment the
          list exists and the only moment anyone is thinking about it.
        </p>
      ) : null}
    </div>
  );
}
