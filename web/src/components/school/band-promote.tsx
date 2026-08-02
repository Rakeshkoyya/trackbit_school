"use client";

/**
 * *"Use this as the band test"* (V1-9, `D-76`/`S-182`/`S-184`/`S-187`/`Q-81`).
 *
 * It sits at the bottom of the exam she has just verified and locked — one
 * action on a screen she is on anyway, **not** a new place to go and not a
 * decision she has to remember to make.
 *
 * The four rules on this one action:
 *
 * - **A flag, never a type change** (`S-182`). It stays a slip test in every
 *   exam roll-up. Re-typing it would trade the test for the band.
 * - **Locked only** (`S-184`, `D-53`). An unverified transcription must not move
 *   a child between support tiers.
 * - **The size is shown, and a small test warns but does not block** (`S-184`).
 *   A teacher who knows the test was small can still be right about the child,
 *   and a validator that refuses a legitimate case is a rule staff route around
 *   by hand.
 * - **The moves are reviewed before they commit** (`Q-81`). `student_bands` is
 *   append-only, so a mistaken re-band is permanent in a child's record — and a
 *   child slipping B → C is the most consequential thing this module ever does.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowDown, ArrowUp, Check, Layers } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

export function BandPromoteCard({ cycleId }: { cycleId: string }) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["band-promote", cycleId],
    queryFn: () => schoolApi.bandPromotePreview(cycleId),
  });

  const commit = useMutation({
    mutationFn: () => schoolApi.bandPromote(cycleId),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["band-promote", cycleId] });
      qc.invalidateQueries({ queryKey: ["band-programme"] });
      toast.success(res.applied
        ? `${res.applied} child${res.applied === 1 ? "" : "ren"} re-banded in ${res.subject_name}`
        : "Nobody moved — everyone is already in the right band");
    },
    onError: (e) => showApiError(e, "Could not use this as the band test"),
  });

  if (!data) return null;
  // Blocked is not a failure to hide — it says exactly what is missing.
  if (data.blocked) {
    return (
      <section className="rounded-xl border border-dashed border-border p-4">
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <Layers className="h-4 w-4" /> Use this as the band test
        </p>
        <p className="mt-1 text-xs text-muted-foreground">{data.blocked}</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-sm font-semibold">
          <Layers className="h-4 w-4" />
          Use this as the band test for {data.class_label} {data.subject_name}
        </p>
        {data.already_promoted ? <Badge tone="success">already used</Badge> : null}
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        out of {data.total_marks ?? "?"} marks · {data.sat} of {data.roster} children sat it
        {" "}· it stays a normal test in every other report
      </p>

      {data.warnings.map((w) => (
        <p key={w} className="mt-2 flex items-start gap-1.5 rounded-md bg-muted/40 px-3 py-2 text-xs">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {w}
        </p>
      ))}

      {data.moves.length ? (
        <ul className="mt-3 space-y-1.5">
          {data.moves.map((mv) => (
            <li key={mv.student_id} className="flex items-center gap-2 text-sm">
              {mv.direction === "down"
                ? <ArrowDown className="h-3.5 w-3.5 text-[color:var(--warning,#8a6d1a)]" />
                : <ArrowUp className="h-3.5 w-3.5 text-[color:var(--success,#234a37)]" />}
              <span className="min-w-0 flex-1 truncate">{mv.full_name}</span>
              <span className="text-xs text-muted-foreground">{mv.pct}%</span>
              <Badge tone={mv.direction === "down" ? "warning" : "success"}>
                {mv.from_tier ?? "—"} → {mv.to_tier}
              </Badge>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">
          Nobody would move — everyone who sat it is already in the right band.
        </p>
      )}

      <p className="mt-3 text-xs text-muted-foreground">
        {data.unchanged} unchanged
        {data.not_sat ? ` · ${data.not_sat} didn't sit it, bands unchanged` : ""}
      </p>

      <Button className="mt-3" size="sm"
        disabled={commit.isPending || !data.moves.length}
        onClick={() => commit.mutate()}>
        <Check className="h-4 w-4" /> Confirm {data.moves.length} move
        {data.moves.length === 1 ? "" : "s"}
      </Button>
    </section>
  );
}
