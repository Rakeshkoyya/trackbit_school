"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Phone } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { DayCellStatus, RegisterCell, RegisterRow } from "@/lib/school-types";
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
const CELL: Record<DayCellStatus, { cls: string; label: string }> = {
  present: { cls: "bg-[color:var(--success,#234a37)]/20", label: "present" },
  partial: { cls: "bg-warning/40", label: "in for part of the day" },
  left_after_lunch: { cls: "bg-warning/60", label: "left after lunch" },
  absent: { cls: "bg-danger/70", label: "absent" },
  not_marked: { cls: "bg-muted", label: "not marked" },
  no_school: { cls: "bg-transparent border border-dashed border-border", label: "—" },
};

const MODE_LABEL: Record<string, string> = {
  every_period: "every period",
  first_period: "first period only",
  twice_daily: "twice a day",
};

function shiftMonth(month: string, by: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, (m - 1) + by, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function monthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

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
  const [month, setMonth] = useState<string>(() => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  });
  const [reasonFor, setReasonFor] =
    useState<{ studentId: string; name: string; date: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["class-register", classId, month],
    queryFn: () => schoolApi.classRegister(classId, month),
  });

  if (isLoading || !data) return <div className="h-64 animate-pulse rounded-xl bg-muted" />;

  const openReason = (row: RegisterRow, cell: RegisterCell) => {
    if (cell.status !== "absent" && cell.status !== "left_after_lunch") return;
    setReasonFor({ studentId: row.student_id, name: row.full_name, date: cell.date });
  };

  const unexplained = data.rows.reduce(
    (n, r) => n + r.cells.filter((c) => c.status === "absent" && !c.has_reason).length, 0);

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="icon" aria-label="Previous month"
            onClick={() => setMonth(shiftMonth(month, -1))}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="text-sm font-medium">{monthLabel(data.month)}</span>
          <Button variant="ghost" size="icon" aria-label="Next month"
            onClick={() => setMonth(shiftMonth(month, 1))}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {data.school_days} school day{data.school_days === 1 ? "" : "s"} ·
          attendance taken {MODE_LABEL[data.mode] ?? data.mode}
        </p>
      </div>

      {unexplained > 0 ? (
        <p className="mb-3 rounded-lg border border-border bg-danger/5 px-3 py-2 text-sm">
          <span className="font-medium">{unexplained} absence{unexplained === 1 ? "" : "s"}</span>{" "}
          with no reason on record — tap a red square to say why.
        </p>
      ) : null}

      <div className="overflow-x-auto rounded-xl border border-border bg-card">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-muted-foreground">
              <th className="sticky left-0 z-10 bg-card px-3 py-2 text-left font-medium">Student</th>
              {data.days.map((d) => (
                <th key={d} className="w-7 px-0 py-2 text-center font-normal tabular-nums">
                  {Number(d.slice(8, 10))}
                </th>
              ))}
              <th className="px-3 py-2 text-right font-medium">Present</th>
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => (
              <tr key={row.student_id} className="border-b border-border/60 last:border-0">
                <td className="sticky left-0 z-10 max-w-[11rem] truncate bg-card px-3 py-1.5">
                  <Link href={`/students/${row.student_id}`} className="hover:text-primary">
                    {row.roll_no ? `${row.roll_no}. ` : ""}{row.full_name}
                  </Link>
                </td>
                {row.cells.map((c) => {
                  const meta = CELL[c.status];
                  // D-86: an absence with a reason on record reads amber, not red.
                  const amber = c.status === "absent" && c.has_reason;
                  return (
                    <td key={c.date} className="px-0 py-1.5 text-center">
                      <button
                        type="button"
                        onClick={() => openReason(row, c)}
                        title={`${new Date(c.date).toLocaleDateString()} — ${meta.label}${
                          c.late ? " (late)" : ""}${c.has_reason ? " · reason recorded" : ""}`}
                        aria-label={`${row.full_name} ${c.date} ${meta.label}`}
                        className={cn(
                          "mx-auto block h-5 w-5 rounded-[3px]",
                          amber ? "bg-warning/70" : meta.cls,
                          c.late && "ring-1 ring-inset ring-warning",
                          (c.status === "absent" || c.status === "left_after_lunch")
                            && "cursor-pointer hover:opacity-80",
                        )}
                      />
                    </td>
                  );
                })}
                <td className="whitespace-nowrap px-3 py-1.5 text-right text-xs text-muted-foreground">
                  {row.marked_days > 0
                    ? `${row.present_days} of ${row.marked_days}`
                    : "not marked"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-2 flex flex-wrap gap-3 text-xs text-muted-foreground">
        {(["present", "partial", "left_after_lunch", "absent", "not_marked"] as DayCellStatus[])
          .map((s) => (
            <span key={s} className="inline-flex items-center gap-1.5">
              <span className={cn("h-3 w-3 rounded-[3px]", CELL[s].cls)} />
              {CELL[s].label}
            </span>
          ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="h-3 w-3 rounded-[3px] bg-warning/70" /> absent · reason recorded
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        “Present” counts the days this class actually marked — never the days nobody took.
      </p>

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
