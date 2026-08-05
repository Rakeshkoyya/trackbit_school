"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Phone } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { RegisterBook } from "@/components/school/register-book";
import { showApiError } from "@/lib/errors";
import { thisMonth } from "@/lib/format";
import { schoolApi } from "@/lib/school-api";
import type { RegisterRow } from "@/lib/school-types";
import { cn } from "@/lib/utils";

/** The class teacher's month grid (V1-3, D-03) — student × school day.
 *
 *  A row's SHAPE is the point: "every Monday", "a block in October", "slowly
 *  fading" are three different problems and three different conversations, and
 *  the eye reads them off the grid faster than any percentage.
 *
 *  Colour is a rendering of the server's day status (S-22), and follows D-86:
 *  absent with a reason on record is amber (somebody dealt with it), absent with
 *  none is red. A day the class never marked is NEUTRAL with its own legend
 *  entry — a gap in the record is never evidence about a child (ux §5). */
/** D-02: the reason is recorded AFTER the fact, by whoever knows — never at
 *  capture. Recording it is what turns the row amber for everyone. */
function ReasonSheet({
  target, onClose,
}: {
  target: { studentId: string; name: string; date: string } | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [code, setCode] = useState("sick");
  const [note, setNote] = useState("");

  const save = useMutation({
    mutationFn: () => schoolApi.setAbsenceReason({
      student_id: target!.studentId, date: target!.date,
      reason_code: code, note: note.trim() || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["class-register"] });
      qc.invalidateQueries({ queryKey: ["insights", "calls"] });
      toast.success("Reason recorded");
      setNote("");
      onClose();
    },
    onError: (e) => showApiError(e, "Could not record the reason"),
  });

  return (
    <Sheet open={!!target} onOpenChange={(v) => { if (!v) onClose(); }}
      title={target ? `Why was ${target.name} away?` : ""}>
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {target ? new Date(target.date).toLocaleDateString(undefined, {
            weekday: "long", day: "numeric", month: "long" }) : ""}
          {" "}— recording this tells the school somebody has dealt with it.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {["sick", "family", "travel", "informed", "other"].map((c) => (
            <button key={c} type="button" onClick={() => setCode(c)}
              className={cn(
                "rounded-full border px-3 py-1 text-sm capitalize",
                code === c ? "border-primary bg-primary/10 font-medium" : "border-border",
              )}>
              {c}
            </button>
          ))}
        </div>
        <Input placeholder="What did the family say? (optional)" value={note}
          onChange={(e) => setNote(e.target.value)} />
        <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Record reason"}
        </Button>
      </div>
    </Sheet>
  );
}

export function ClassRegister({ classId }: { classId: string }) {
  const [month, setMonth] = useState<string>(thisMonth);
  const [reasonFor, setReasonFor] =
    useState<{ studentId: string; name: string; date: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["class-register", classId, month],
    queryFn: () => schoolApi.classRegister(classId, month),
  });

  if (isLoading || !data) return <div className="h-64 animate-pulse rounded-xl bg-muted" />;

  return (
    <div>
      {/* The DRAWING is `RegisterBook`, shared with the every-teacher attendance
          screen (founder, 2026-08-05) so the two cannot paint the same October
          differently. What this wrapper adds is the class teacher's own power
          over it: tapping an unexplained absence records why (`D-02`). */}
      <RegisterBook
        data={data} month={month} onMonth={setMonth}
        onCell={(row, cell) => setReasonFor({
          studentId: row.student_id, name: row.full_name, date: cell.date })} />

      <ReasonSheet target={reasonFor} onClose={() => setReasonFor(null)} />
    </div>
  );
}

/** The needs-a-call strip above the grid: today's absentees, red first. */
export function CallStrip({ rows }: { rows: RegisterRow[] }) {
  const today = rows.flatMap((r) => {
    const last = r.cells[r.cells.length - 1];
    return last && (last.status === "absent" || last.status === "left_after_lunch")
      ? [{ row: r, cell: last }] : [];
  });
  if (today.length === 0) return null;
  return (
    <div className="mb-4 space-y-1.5">
      {today.map(({ row, cell }) => (
        <div key={row.student_id}
          className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2 text-sm">
          <Badge tone={cell.has_reason ? "warning" : "danger"}>
            {cell.has_reason ? "explained" : "no reason"}
          </Badge>
          <Link href={`/students/${row.student_id}`} className="min-w-0 flex-1 truncate font-medium">
            {row.full_name}
          </Link>
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Phone className="h-3 w-3" /> call home
          </span>
        </div>
      ))}
    </div>
  );
}
