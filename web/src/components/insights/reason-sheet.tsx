"use client";

// D-02 step 3 — "why is this child away?", recorded after the fact.
//
// Shared rather than local to the attendance tab (V1-14): the dashboard's
// presence block offers the same button, and a sheet that exists on one screen
// makes the button on the other a dead end. Recording a reason is what turns a
// red row amber for *everyone* who looks at it (D-86), so it has to be
// available wherever the red row is.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { cn } from "@/lib/utils";

export type ReasonTarget = { student_id: string; full_name: string };

/**
 * A calendar date as the school would write it, from LOCAL parts.
 *
 * Never `toISOString().slice(0, 10)`: that serialises through UTC, so in any
 * timezone east of it a local date between midnight and the offset comes back as
 * the previous day. An office recording an absence reason at 9am is fine; the
 * same click at 5am in India filed it against yesterday.
 */
function localISO(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`
    + `-${String(d.getDate()).padStart(2, "0")}`;
}

export function ReasonSheet({
  target, onClose,
}: {
  target: ReasonTarget | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [code, setCode] = useState("sick");
  const [note, setNote] = useState("");
  const [days, setDays] = useState(1);

  const save = useMutation({
    mutationFn: async () => {
      const today = localISO(new Date());
      // The reason always lands on today's absence; more than one day ALSO
      // records a planned absence, which pre-explains the days ahead and
      // suppresses their guardian alerts (S-24).
      await schoolApi.setAbsenceReason({
        student_id: target!.student_id, date: today,
        reason_code: code, note: note.trim() || null,
      });
      if (days > 1) {
        const to = new Date();
        to.setDate(to.getDate() + days - 1);
        await schoolApi.addAbsenceNote({
          student_id: target!.student_id, from_date: today,
          to_date: localISO(to),
          reason_code: code, note: note.trim() || null, source: "office",
        });
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["insights"] });
      toast.success("Reason recorded");
      setNote(""); setDays(1);
      onClose();
    },
    onError: (e) => showApiError(e, "Could not record the reason"),
  });

  return (
    <Sheet open={!!target} onOpenChange={(v) => { if (!v) onClose(); }}
      title={target ? `Why is ${target.full_name} away?` : ""}>
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          Recording this tells everyone the school has dealt with it — the row turns amber
          and stops asking.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {["sick", "family", "travel", "informed", "other"].map((c) => (
            <button key={c} type="button" onClick={() => setCode(c)}
              className={cn("rounded-full border px-3 py-1 text-sm capitalize",
                code === c ? "border-primary bg-primary/10 font-medium" : "border-border")}>
              {c}
            </button>
          ))}
        </div>
        <Input placeholder="What did the family say? (optional)" value={note}
          onChange={(e) => setNote(e.target.value)} />
        <div>
          <label className="text-xs text-muted-foreground" htmlFor="away-days">
            Away for how many days?
          </label>
          <Input id="away-days" type="number" min={1} max={30} value={days}
            onChange={(e) => setDays(Math.max(1, Math.min(30, Number(e.target.value) || 1)))} />
          <p className="mt-1 text-xs text-muted-foreground">
            More than one day records a planned absence: those days are explained ahead of
            time and the family is not messaged again about them.
          </p>
        </div>
        <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Record reason"}
        </Button>
      </div>
    </Sheet>
  );
}
