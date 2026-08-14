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
 * Three rules this sheet holds to:
 *
 *   · **it always lets you finish.** The first cut refused to open when the
 *     class had no structure — which on the founder's own school meant seven
 *     children with no class at all could not be set up by any route. An
 *     unpriced class is now a prompt for the total, never a wall;
 *   · **it never divides the money itself.** The schedule is the server's
 *     `plan_installments` output, fetched as the office types. A browser doing
 *     its own arithmetic would drift from the write on the first rounding
 *     remainder, and the family would be shown one schedule and handed another.
 *     Typed amounts are the exception and are checked the other way round — the
 *     rows must *sum* to the net, and `enroll` is the authority on that;
 *   · **it never shows ₹0 for "unknown".** No price yet is a sentence and a
 *     field, because a zeroed form is one confident tap away from billing a
 *     family nothing for the year.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link2, Lock, RotateCcw } from "lucide-react";
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
function useDebounced<T>(value: T, ms = 350): T {
  const [out, setOut] = useState(value);
  useEffect(() => {
    const id = setTimeout(() => setOut(value), ms);
    return () => clearTimeout(id);
  }, [value, ms]);
  return out;
}

const round2 = (n: number) => Math.round(n * 100) / 100;

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

/** Read-only schedule — the class's own terms, in default mode. */
function PlanTable({ rows }: { rows: PlannedInstallment[] }) {
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

/** The editable schedule. Founder: *"I want flexibility for editing the
 *  instalment amounts also"* — a family that pays ₹30,000 in June and the rest
 *  across the year is not an even split, and it is not a split the school should
 *  have to fix afterwards by splitting and re-dating rows one at a time. */
function PlanEditor({ rows, onChange, remaining }: {
  rows: PlannedInstallment[];
  onChange: (next: PlannedInstallment[]) => void;
  remaining: number;
}) {
  const edit = (i: number, patch: Partial<PlannedInstallment>) =>
    onChange(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  return (
    <div className="space-y-1.5">
      <div className="overflow-hidden rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/60 text-[10px] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="w-7 px-1.5 py-1.5 text-left font-medium">#</th>
              <th className="px-1.5 py-1.5 text-left font-medium">Period</th>
              <th className="px-1.5 py-1.5 text-left font-medium">Due</th>
              <th className="px-1.5 py-1.5 text-right font-medium">Amount</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-t border-border/60">
                <td className="px-1.5 py-1 text-muted-foreground">{i + 1}</td>
                <td className="px-1.5 py-1">
                  <Input className="h-8" placeholder={`Instalment ${i + 1}`}
                    aria-label={`Label for instalment ${i + 1}`}
                    value={r.label ?? ""}
                    onChange={(e) => edit(i, { label: e.target.value || null })} />
                </td>
                <td className="px-1.5 py-1">
                  <Input className="h-8 w-[8.5rem]" type="date"
                    aria-label={`Due date for instalment ${i + 1}`}
                    value={r.due_date ?? ""}
                    onChange={(e) => edit(i, { due_date: e.target.value || null })} />
                </td>
                <td className="px-1.5 py-1">
                  <Input className="h-8 w-28 text-right" type="number" min={0}
                    inputMode="numeric"
                    aria-label={`Amount for instalment ${i + 1}`}
                    value={r.amount}
                    onChange={(e) => edit(i, { amount: e.target.value })} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {/* The one number that decides whether this can be saved. `enroll` refuses
          a schedule that does not sum to the net, so saying it here is the
          difference between a fixable form and a rejected one. */}
      <p className={cn("text-xs",
        remaining === 0 ? "text-muted-foreground"
          : "font-medium text-rose-600 dark:text-rose-400")}>
        {remaining === 0
          ? "The instalments add up to the net payable."
          : remaining > 0
            ? `${money(String(round2(remaining)))} still to allocate.`
            : `${money(String(round2(-remaining)))} over the net payable.`}
      </p>
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
  const [total, setTotal] = useState("");
  const [discount, setDiscount] = useState("");
  const [parts, setParts] = useState("");
  const [dues, setDues] = useState("");
  const [rows, setRows] = useState<PlannedInstallment[]>([]);
  const [planKey, setPlanKey] = useState<string | null>(null);
  const [seeded, setSeeded] = useState<string | null>(null);

  // Reset per student, during render (React's documented pattern) — a sheet
  // reopened on the next child must never carry the last one's discount.
  if (studentId !== seeded) {
    setSeeded(studentId);
    setMode("default");
    setTotal(""); setDiscount(""); setParts(""); setDues("");
    setRows([]); setPlanKey(null);
  }

  const { data: setup, isLoading } = useQuery({
    queryKey: ["fee-setup", studentId, yearId],
    queryFn: () => schoolApi.feeSetup(studentId!, yearId!),
    enabled: !!studentId && !!yearId,
  });

  // No structure = no default to offer, so the sheet opens straight into the
  // form rather than on a choice with one real option.
  const priced = !!setup?.structure;
  const custom = mode === "custom" || !priced;
  const effectiveTotal = total || setup?.structure?.total_amount || "";

  const debounced = useDebounced({ total: effectiveTotal, discount, parts, dues });
  const { data: preview } = useQuery({
    queryKey: ["fee-setup-preview", studentId, yearId, debounced],
    queryFn: () => schoolApi.feeSetupPreview({
      student_id: studentId!, academic_year_id: yearId!,
      total_fee: debounced.total || null,
      discount: debounced.discount || "0",
      opening_dues: debounced.dues || "0",
      num_installments: debounced.parts ? Number(debounced.parts) : null,
    }),
    enabled: !!studentId && !!yearId && !!setup,
  });

  // Re-seed the editable rows whenever the PLAN changes (total, discount or
  // count) — never on a row edit, or typing an amount would fight the reseed.
  const nextKey = preview
    ? `${preview.total_fee}|${preview.discount}|${preview.installments.length}`
    : null;
  if (preview && nextKey !== planKey) {
    setPlanKey(nextKey);
    setRows(preview.installments);
  }

  const net = Number(preview?.net_fee ?? 0);
  const allocated = rows.reduce((n, r) => n + (Number(r.amount) || 0), 0);
  const remaining = round2(net - allocated);
  // Rows are only sent when the office actually changed them; otherwise the
  // server's own plan is written, which keeps the class's labels and dates.
  const edited = !!preview && rows.some((r, i) => {
    const src = preview.installments[i];
    return !src || src.amount !== r.amount || src.due_date !== r.due_date
      || (src.label ?? "") !== (r.label ?? "");
  });

  const lock = useMutation({
    mutationFn: () => schoolApi.enroll({
      student_id: studentId,
      academic_year_id: yearId,
      fee_structure_id: setup?.structure?.id ?? null,
      total_fee: preview?.total_fee ?? effectiveTotal ?? "0",
      discount: custom ? (discount || "0") : "0",
      opening_dues: custom ? (dues || "0") : "0",
      num_installments: custom && parts ? Number(parts) : null,
      use_custom_schedule: custom && edited,
      installments: custom && edited
        ? rows.map((r, i) => ({
          installment_number: i + 1,
          label: r.label,
          amount: String(r.amount || 0),
          due_date: r.due_date,
        }))
        : [],
    }),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: ["student-fees"] });
      qc.invalidateQueries({ queryKey: ["structure-coverage"] });
      qc.invalidateQueries({ queryKey: ["fee-setup"] });
      toast.success(`${row.student_name} locked at ${money(row.net_fee)}`);
      onClose();
    },
    onError: (e) => showApiError(e, "Could not lock the fees"),
  });

  const noTotal = !effectiveTotal || Number(effectiveTotal) <= 0;
  const blocked = noTotal
    || net < 0
    || (custom && edited && remaining !== 0);

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
      ) : (
        <div className="space-y-4">
          {priced ? (
            <p className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
              {setup.class_label}
              {setup.category_name ? ` · ${setup.category_name}` : ""} ·{" "}
              <span className="font-medium text-foreground">
                {money(setup.structure!.total_amount)}
              </span>{" "}
              in {setup.structure!.num_installments} instalment
              {setup.structure!.num_installments === 1 ? "" : "s"}
              {setup.structure!.category_name
                ? ` — the ${setup.structure!.category_name.toLowerCase()} price`
                : ""}
            </p>
          ) : (
            // Informative, never blocking. The two ways to get here are a class
            // nobody has priced and a student not yet in a class — and in both
            // the school still has a family at the counter.
            <div className="rounded-lg border border-border bg-muted/40 px-3 py-2">
              <p className="text-xs text-muted-foreground">
                {setup.class_label
                  ? <>Class <span className="font-medium text-foreground">
                    {setup.class_label}</span> has no fee structure yet.</>
                  : <>{setup.student_name} is not in a class yet.</>}
                {" "}Type this student&rsquo;s fee below — you can price the class
                properly later, and it will not disturb her record.
              </p>
              <Link href="/fees/structure"
                className="mt-1 inline-block text-xs font-medium text-primary hover:underline">
                Set the class structure instead →
              </Link>
            </div>
          )}

          {priced ? (
            <div className="grid gap-2 sm:grid-cols-2">
              {([
                ["default", "Class structure",
                  "Bill her exactly what the class is priced at."],
                ["custom", "Custom for this student",
                  "A discount agreed at the counter, and the instalments to match."],
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
          ) : null}

          {custom ? (
            <div className={cn("grid gap-2",
              priced ? "grid-cols-3" : "grid-cols-2 sm:grid-cols-4")}>
              {!priced ? (
                <div>
                  <Label>Total fee (₹)</Label>
                  <Input type="number" min={0} inputMode="numeric" autoFocus
                    placeholder="e.g. 60000" value={total}
                    onChange={(e) => setTotal(e.target.value)} />
                </div>
              ) : null}
              <div>
                <Label>Discount (₹)</Label>
                <Input type="number" min={0} inputMode="numeric" placeholder="0"
                  value={discount} onChange={(e) => setDiscount(e.target.value)} />
              </div>
              <div>
                <Label>Instalments</Label>
                <Input type="number" min={1} max={24} inputMode="numeric"
                  placeholder={String(setup.structure?.num_installments ?? 1)}
                  value={parts} onChange={(e) => setParts(e.target.value)} />
              </div>
              <div>
                <Label>Previous dues</Label>
                <Input type="number" min={0} inputMode="numeric" placeholder="0"
                  value={dues} onChange={(e) => setDues(e.target.value)} />
              </div>
            </div>
          ) : null}

          {preview?.warning && !noTotal ? (
            <p className="rounded-lg border border-warning/40 bg-warning-soft px-3 py-2 text-xs text-warning">
              {preview.warning}
            </p>
          ) : null}

          <div className="space-y-1 rounded-lg border border-border bg-card px-3 py-2.5">
            <Line label={priced ? "Class fee" : "Total fee"}
              value={noTotal ? "—" : money(preview?.total_fee ?? effectiveTotal)} />
            {Number(preview?.discount ?? 0) > 0 ? (
              <Line label="Discount" value={`− ${money(preview!.discount)}`}
                accent="rose" />
            ) : null}
            <Line label="Net for the year"
              value={noTotal ? "—" : money(preview?.net_fee ?? effectiveTotal)} />
            {Number(preview?.opening_dues ?? 0) > 0 ? (
              <Line label="Previous dues" value={money(preview!.opening_dues)}
                accent="rose" />
            ) : null}
            <div className="border-t border-border/60 pt-1">
              <Line label="Payable"
                value={noTotal ? "—" : money(preview?.total_payable ?? effectiveTotal)}
                accent="brand" />
            </div>
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                <Link2 className="h-3.5 w-3.5" />
                {custom
                  ? "What she will be billed — edit any row"
                  : "The class's own terms and due dates"}
              </p>
              {custom && edited ? (
                <button type="button"
                  onClick={() => { if (preview) setRows(preview.installments); }}
                  className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                  <RotateCcw className="h-3 w-3" /> Spread evenly
                </button>
              ) : null}
            </div>
            {noTotal ? (
              <p className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-xs text-muted-foreground">
                Enter the total fee to see the instalments.
              </p>
            ) : custom ? (
              <PlanEditor rows={rows} onChange={setRows} remaining={remaining} />
            ) : (
              <PlanTable rows={setup.default_plan} />
            )}
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
