"use client";

/**
 * Lock one student's fee (FE-2).
 *
 * The gap this closes, in the founder's words: *"the fee structure of school is
 * fixed; after talking to administration the school admin gives him a discount
 * and we lock that amount to that student"*. Every door into "set this child up"
 * used to bill the class's full price in the class's number of instalments, so
 * the one conversation a fee desk actually has had nowhere to be recorded until
 * after the record existed — and then only as an edit to something already
 * wrong.
 *
 * Two things this sheet refuses to do:
 *
 *   · **it never divides the money itself.** The schedule under the form is the
 *     server's `plan_installments` output, fetched as the office types. A
 *     browser doing its own arithmetic would drift from the write on the first
 *     rounding remainder, and the family would be shown one schedule and handed
 *     another;
 *   · **it never shows ₹0 for "unknown".** A class with no structure yet is a
 *     sentence and a way to fix it, because a zeroed form is one confident tap
 *     away from billing a family nothing for the year.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Lock } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";
import type { PlannedInstallment } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Never `new Date(iso)` on a bare `YYYY-MM-DD` — east of UTC that renders the
 *  previous day (`lib/format.ts` owns calendar dates for the same reason). */
function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${String(y).slice(2)}`;
}

/** Debounce the typing, not the reading — one preview per pause, not per key. */
function useDebounced<T>(value: T, ms = 300): T {
  const [out, setOut] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setOut(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return out;
}

function ScheduleTable({ rows }: { rows: PlannedInstallment[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead className="bg-muted/60 text-[10px] uppercase tracking-wide text-muted-foreground">
          <tr>
            <th className="px-2.5 py-1.5 text-left font-medium">#</th>
            <th className="px-2.5 py-1.5 text-left font-medium">Period</th>
            <th className="px-2.5 py-1.5 text-left font-medium">Due</th>
            <th className="px-2.5 py-1.5 text-right font-medium">Amount</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.installment_number} className="border-t border-border/60">
              <td className="px-2.5 py-1.5 text-muted-foreground">
                {r.installment_number}
              </td>
              <td className="px-2.5 py-1.5">{r.label || "—"}</td>
              <td className="px-2.5 py-1.5 text-muted-foreground">
                {shortDate(r.due_date)}
              </td>
              <td className="px-2.5 py-1.5 text-right font-medium">
                {money(r.amount)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Line({ label, value, accent }: {
  label: string; value: string; accent?: "brand" | "rose";
}) {
  return (
    <div className="flex items-baseline justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className={cn("font-medium tabular-nums",
        accent === "brand" && "text-primary",
        accent === "rose" && "text-rose-600 dark:text-rose-400")}>
        {value}
      </span>
    </div>
  );
}

export function FeeSetupSheet({ studentId, yearId, onClose }: {
  studentId: string | null;
  yearId: string | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<"default" | "custom">("default");
  const [discount, setDiscount] = useState("");
  const [parts, setParts] = useState("");
  const [dues, setDues] = useState("");
  const [seeded, setSeeded] = useState<string | null>(null);

  // Reset per student, during render (React's documented pattern) — a sheet
  // reopened on the next child must never carry the last one's discount.
  if (studentId !== seeded) {
    setSeeded(studentId);
    setMode("default");
    setDiscount(""); setParts(""); setDues("");
  }

  const { data: setup, isLoading } = useQuery({
    queryKey: ["fee-setup", studentId, yearId],
    queryFn: () => schoolApi.feeSetup(studentId!, yearId!),
    enabled: !!studentId && !!yearId,
  });

  const custom = mode === "custom";
  const debounced = useDebounced({ discount, parts, dues });
  const { data: preview } = useQuery({
    queryKey: ["fee-setup-preview", studentId, yearId, debounced],
    queryFn: () => schoolApi.feeSetupPreview({
      student_id: studentId!, academic_year_id: yearId!,
      discount: debounced.discount || "0",
      opening_dues: debounced.dues || "0",
      num_installments: debounced.parts ? Number(debounced.parts) : null,
    }),
    enabled: !!studentId && !!yearId && !!setup?.structure,
  });

  const lock = useMutation({
    mutationFn: () => schoolApi.enroll({
      student_id: studentId,
      academic_year_id: yearId,
      fee_structure_id: setup?.structure?.id ?? null,
      total_fee: setup?.structure?.total_amount ?? "0",
      discount: custom ? (discount || "0") : "0",
      opening_dues: custom ? (dues || "0") : "0",
      num_installments: custom && parts ? Number(parts) : null,
    }),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: ["student-fees"] });
      qc.invalidateQueries({ queryKey: ["structure-coverage"] });
      qc.invalidateQueries({ queryKey: ["fee-setup"] });
      toast.success(
        `${row.student_name} locked at ${money(row.net_fee)}`);
      onClose();
    },
    onError: (e) => showApiError(e, "Could not lock the fees"),
  });

  // The schedule on screen: the server's, always. In default mode that is the
  // class's own terms; in custom it is the live preview of what was typed.
  const rows = custom ? (preview?.installments ?? []) : (setup?.default_plan ?? []);
  const shown = custom && preview ? preview : null;
  const blocked = !!shown?.warning || !setup?.structure;

  return (
    <Sheet open={!!studentId} onOpenChange={(v) => { if (!v) onClose(); }}
      title={setup ? `Set up fees · ${setup.student_name}` : "Set up fees"}>
      {isLoading || !setup ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : setup.already_locked ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {setup.student_name}&rsquo;s fees are already locked for this year.
            Discounts, instalments and payments are all on her record.
          </p>
          <Link href={`/fees/students/${setup.student_id}`}
            className="flex h-10 w-full items-center justify-center rounded-md bg-primary text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90">
            Open her fee record
          </Link>
        </div>
      ) : !setup.structure ? (
        // A state with a sentence and a door, never a ₹0 form.
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Class <span className="font-medium text-foreground">
              {setup.class_label ?? "—"}
            </span> has no fee structure yet, so there is no price to start from.
          </p>
          <Link href="/fees/structure"
            className="flex h-10 w-full items-center justify-center rounded-md border border-border bg-card text-sm font-medium transition-colors hover:bg-muted">
            Set the class structure
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
            {setup.class_label}
            {setup.category_name ? ` · ${setup.category_name}` : ""} ·{" "}
            <span className="font-medium text-foreground">
              {money(setup.structure.total_amount)}
            </span>{" "}
            in {setup.structure.num_installments} instalment
            {setup.structure.num_installments === 1 ? "" : "s"}
            {setup.structure.category_name
              ? ` — the ${setup.structure.category_name.toLowerCase()} price`
              : ""}
          </p>

          <div className="grid gap-2 sm:grid-cols-2">
            {([
              ["default", "Class structure",
                "Bill her exactly what the class is priced at."],
              ["custom", "Custom for this student",
                "A discount agreed at the counter, and how many payments."],
            ] as const).map(([key, title, hint]) => (
              <button key={key} type="button" onClick={() => setMode(key)}
                aria-pressed={mode === key}
                className={cn(
                  "rounded-lg border px-3 py-2 text-left transition-colors",
                  mode === key
                    ? "border-primary bg-primary/5"
                    : "border-border bg-card hover:bg-muted/50")}>
                <span className="block text-sm font-medium">{title}</span>
                <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                  {hint}
                </span>
              </button>
            ))}
          </div>

          {custom ? (
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label>Discount (₹)</Label>
                <Input type="number" min={0} inputMode="numeric" placeholder="0"
                  value={discount} onChange={(e) => setDiscount(e.target.value)} />
              </div>
              <div>
                <Label>Instalments</Label>
                <Input type="number" min={1} max={24} inputMode="numeric"
                  placeholder={String(setup.structure.num_installments)}
                  value={parts} onChange={(e) => setParts(e.target.value)} />
              </div>
              <div>
                <Label>Previous dues</Label>
                <Input type="number" min={0} inputMode="numeric" placeholder="0"
                  value={dues} onChange={(e) => setDues(e.target.value)} />
              </div>
            </div>
          ) : null}

          {shown?.warning ? (
            <p className="rounded-lg border border-warning/40 bg-warning-soft px-3 py-2 text-xs text-warning">
              {shown.warning}
            </p>
          ) : null}

          <div className="space-y-1 rounded-lg border border-border bg-card px-3 py-2.5">
            <Line label="Class fee"
              value={money(shown?.total_fee ?? setup.structure.total_amount)} />
            {custom && Number(shown?.discount ?? 0) > 0 ? (
              <Line label="Discount" value={`− ${money(shown!.discount)}`}
                accent="rose" />
            ) : null}
            <Line label="Net for the year"
              value={money(shown?.net_fee ?? setup.structure.total_amount)} />
            {custom && Number(shown?.opening_dues ?? 0) > 0 ? (
              <Line label="Previous dues" value={money(shown!.opening_dues)}
                accent="rose" />
            ) : null}
            <div className="border-t border-border/60 pt-1">
              <Line label="Payable"
                value={money(shown?.total_payable ?? setup.structure.total_amount)}
                accent="brand" />
            </div>
          </div>

          <div>
            <p className="mb-1.5 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <Link2 className="h-3.5 w-3.5" />
              {custom
                ? "What she will be billed"
                : "The class's own terms and due dates"}
            </p>
            <ScheduleTable rows={rows} />
          </div>

          <Button className="w-full" disabled={lock.isPending || blocked}
            onClick={() => lock.mutate()}>
            <Lock className="h-4 w-4" />
            {lock.isPending
              ? "Locking…"
              : `Lock fees for ${setup.student_name.split(" ")[0]}`}
          </Button>
          <p className="text-[11px] leading-snug text-muted-foreground">
            Locking creates her record and her instalments. Everything here stays
            editable afterwards — and every change is recorded against your name.
          </p>
        </div>
      )}
    </Sheet>
  );
}
