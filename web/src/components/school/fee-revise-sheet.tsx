"use client";

/**
 * Correct a fee record that was set up wrong (FE-3).
 *
 * The founder's ask: *"if I entered wrong data of installment I should be able
 * to edit them by deleting the entire installments and adding them newly and
 * spliting the amount or manually enter … and even the final fee discount and
 * final total fee amount I should able to change it as admin"*.
 *
 * Everything the office typed at enrolment comes back here — the total, the
 * discount, the previous dues and the whole schedule — and it saves as **one**
 * request. That is the point, not a convenience: as a sequence of small edits
 * every intermediate state has to balance, so "₹60,000 in 4 should have been
 * ₹45,000 in 6" is refused at the first step and cannot be expressed at all.
 *
 * Three rules this sheet holds to:
 *
 *   · **the grid is what gets written.** Unlike the setup sheet there is no
 *     separate preview to drift from — these exact rows are the request body,
 *     and the server checks they sum to the net before anything moves. The one
 *     server call is "re-plan into N", so a fresh schedule still comes out of
 *     `plan_installments` with the class's own labels and dates;
 *   · **money that has landed is visible and locked.** A row with a payment on
 *     it wears a lock, cannot be deleted, and cannot be typed below what was
 *     collected. The server refuses all three anyway — this is so the office is
 *     never surprised by the refusal;
 *   · **it says what is wrong while you type.** The one number that decides
 *     whether this can be saved is the remainder, and it is on screen.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Lock, Plus, RotateCcw, Trash2, Wand2, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";
import type { StudentFeeDetail } from "@/lib/school-types";
import { cn } from "@/lib/utils";

/** A row being edited. `id` present = an existing instalment being kept, with
 *  its payments; absent = a new one. `paid` is carried so the row can lock
 *  itself rather than waiting for the server to refuse. */
interface Row {
  id: string | null;
  label: string;
  amount: string;
  due_date: string | null;
  paid: number;
}

const round2 = (n: number) => Math.round(n * 100) / 100;
const num = (v: string) => Number(v || 0) || 0;

function rowsFrom(detail: StudentFeeDetail): Row[] {
  return detail.installments
    // A voided row belongs to a closed transfer, and this sheet refuses to open
    // on a closed record at all. Filtered anyway so the sums here mean the same
    // thing `live_installments` means on the server.
    .filter((i) => !i.is_voided)
    .map((i) => ({
      id: i.id,
      label: i.label ?? "",
      amount: String(Number(i.amount)),
      due_date: i.due_date,
      paid: Number(i.paid_amount),
    }));
}

/** Spread `delta` across the rows that can still move, proportionally to what
 *  they currently carry — the browser-side twin of the server's
 *  `rebalance_unpaid`. Safe to compute here in a way the setup sheet's split is
 *  not: these rows ARE the request body, and the server re-checks the sum
 *  before it writes, so there is no second computation to drift from.
 *
 *  A row that has been paid can only move DOWN to its own paid amount, never
 *  below — money that has landed is never un-billed. */
function spread(rows: Row[], delta: number): Row[] {
  const movable = rows
    .map((r, i) => ({ i, room: num(r.amount) - r.paid }))
    .filter((r) => r.room > 0 || delta > 0);
  if (movable.length === 0) return rows;
  const base = movable.reduce((n, r) => n + Math.max(r.room, 0), 0);
  const next = [...rows];
  let left = delta;
  movable.forEach((m, idx) => {
    const share = idx === movable.length - 1
      ? left
      : round2(base > 0 ? (delta * Math.max(m.room, 0)) / base : delta / movable.length);
    const row = next[m.i];
    // Never below what was collected on this row.
    const amount = Math.max(round2(num(row.amount) + share), row.paid);
    left = round2(left - (amount - num(row.amount)));
    next[m.i] = { ...row, amount: String(amount) };
  });
  return next;
}

/** Why this cannot be saved yet — the same refusals the server would give, in
 *  the order the office hits them. The remainder is deliberately NOT in here:
 *  it has its own louder line under the table, and saying it twice makes the
 *  screen look angrier than the situation. */
function whatIsWrong(o: {
  total: number; discount: number; dues: number; net: number;
  rows: Row[]; collected: number;
}): string | null {
  if (o.total < 0 || o.discount < 0 || o.dues < 0) {
    return "Fees, discounts and dues cannot be negative.";
  }
  if (o.net < 0) return "The discount is more than the total fee.";
  if (o.rows.length === 0) return "A fee record needs at least one instalment.";
  if (o.rows.some((r) => num(r.amount) <= 0)) {
    return "Every instalment has to be more than zero.";
  }
  const under = o.rows.find((r) => num(r.amount) < r.paid);
  if (under) {
    return `${money(String(under.paid))} has already been paid against `
      + `${under.label || "an instalment"}, so it cannot be set lower.`;
  }
  if (o.net < o.collected) {
    return `${money(String(o.collected))} has already been collected, so the `
      + "payable cannot be lower. Undo a payment first.";
  }
  return null;
}


export function FeeReviseSheet({ detail, onClose }: {
  detail: StudentFeeDetail | null;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [seeded, setSeeded] = useState<string | null>(null);
  const [total, setTotal] = useState("");
  const [discount, setDiscount] = useState("");
  const [dues, setDues] = useState("");
  const [parts, setParts] = useState("");
  const [reason, setReason] = useState("");
  const [rows, setRows] = useState<Row[]>([]);

  // Re-seed per record, during render (React's documented pattern) — a sheet
  // reopened on the next child must never carry the last one's numbers.
  const key = detail ? `${detail.id}:${detail.net_fee}:${detail.installments.length}` : null;
  if (key !== seeded) {
    setSeeded(key);
    setTotal(detail ? String(Number(detail.total_fee)) : "");
    setDiscount(detail ? String(Number(detail.discount)) : "");
    setDues(detail ? String(Number(detail.opening_dues)) : "");
    setParts(detail ? String(detail.installments.filter((i) => !i.is_voided).length) : "");
    setReason("");
    setRows(detail ? rowsFrom(detail) : []);
  }

  const net = round2(num(total) - num(discount));
  const allocated = round2(rows.reduce((n, r) => n + num(r.amount), 0));
  const remaining = round2(net - allocated);
  const collected = round2(rows.reduce((n, r) => n + r.paid, 0));
  const anyPaid = collected > 0;

  const edit = (i: number, patch: Partial<Row>) =>
    setRows(rows.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  // Re-plan through the server's one splitter, so a fresh schedule keeps the
  // class's own labels and due dates exactly as `enroll` would have written
  // them. Only offered when nothing has been paid — it discards every row.
  const replan = useMutation({
    mutationFn: async () => {
      const n = Number(parts) || rows.length || 1;
      return schoolApi.feeSetupPreview({
        student_id: detail!.student_id,
        academic_year_id: detail!.academic_year_id,
        fee_structure_id: detail!.fee_structure_id,
        total_fee: String(num(total)),
        discount: String(num(discount)),
        opening_dues: String(num(dues)),
        num_installments: n,
      });
    },
    onSuccess: (preview) => {
      setRows(preview.installments.map((p) => ({
        id: null, label: p.label ?? "", amount: String(Number(p.amount)),
        due_date: p.due_date, paid: 0,
      })));
    },
    onError: (e) => showApiError(e, "Could not re-plan the instalments"),
  });

  const save = useMutation({
    mutationFn: () => schoolApi.reviseFee(detail!.id, {
      total_fee: String(num(total)),
      discount: String(num(discount)),
      opening_dues: String(num(dues)),
      installments: rows.map((r) => ({
        id: r.id,
        label: r.label.trim() || null,
        amount: String(num(r.amount)),
        due_date: r.due_date || null,
      })),
      reason: reason.trim() || null,
    }),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: ["student-fee-detail", row.id] });
      qc.invalidateQueries({ queryKey: ["fee-activity", row.id] });
      qc.invalidateQueries({ queryKey: ["fee-transactions", row.id] });
      qc.invalidateQueries({ queryKey: ["student-fees"] });
      qc.invalidateQueries({ queryKey: ["fee-summary"] });
      toast.success(`${row.student_name} revised to ${money(row.net_fee)} payable`);
      onClose();
    },
    onError: (e) => showApiError(e, "Could not revise the record"),
  });

  const problem = whatIsWrong({
    total: num(total), discount: num(discount), dues: num(dues),
    net, rows, collected,
  });
  return (
    <Sheet open={!!detail} onOpenChange={(v) => { if (!v) onClose(); }}
      title={detail ? `Edit fees · ${detail.student_name}` : "Edit fees"}>
      {!detail ? null : (
        <div className="space-y-4">
          <p className="rounded-lg bg-muted px-3 py-2 text-xs text-muted-foreground">
            Everything set up at enrolment is editable here, and it saves as one
            change against your name.{" "}
            {anyPaid ? (
              <span className="font-medium text-foreground">
                {money(String(collected))} has already been collected — those
                instalments are locked and cannot be removed.
              </span>
            ) : (
              <>Nothing has been paid yet, so the schedule can be cleared and
                typed again from scratch.</>
            )}
          </p>

          {/* ── the money ── */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div>
              <Label>Total fee (₹)</Label>
              <Input type="number" min={0} inputMode="numeric" value={total}
                onChange={(e) => setTotal(e.target.value)} />
            </div>
            <div>
              <Label>Discount (₹)</Label>
              <Input type="number" min={0} inputMode="numeric" value={discount}
                onChange={(e) => setDiscount(e.target.value)} />
            </div>
            <div>
              <Label>Previous dues (₹)</Label>
              <Input type="number" min={0} inputMode="numeric" value={dues}
                onChange={(e) => setDues(e.target.value)} />
            </div>
            <div>
              <Label>Instalments</Label>
              <Input type="number" min={1} max={24} inputMode="numeric"
                value={parts} onChange={(e) => setParts(e.target.value)} />
            </div>
          </div>

          <div className="space-y-1 rounded-lg border border-border bg-card px-3 py-2.5 text-sm">
            <div className="flex items-baseline justify-between">
              <span className="text-muted-foreground">Net for the year</span>
              <span className="font-medium tabular-nums">
                {money(String(net))}
              </span>
            </div>
            {num(dues) > 0 ? (
              <div className="flex items-baseline justify-between">
                <span className="text-muted-foreground">Previous dues</span>
                <span className="font-medium tabular-nums text-rose-600 dark:text-rose-400">
                  {money(String(num(dues)))}
                </span>
              </div>
            ) : null}
            <div className="flex items-baseline justify-between border-t border-border/60 pt-1">
              <span className="text-muted-foreground">Payable</span>
              <span className="font-medium tabular-nums text-primary">
                {money(String(round2(net + num(dues))))}
              </span>
            </div>
          </div>

          {/* ── the schedule ── */}
          <div>
            <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-medium text-muted-foreground">
                The instalments she will be billed
              </p>
              <div className="flex items-center gap-1.5">
                <button type="button" disabled={anyPaid || replan.isPending}
                  onClick={() => replan.mutate()}
                  title={anyPaid
                    ? "Some instalments have been paid, so they cannot be discarded"
                    : "Split the net evenly, through the same planner that set her up"}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40">
                  <Wand2 className="h-3 w-3" />
                  {replan.isPending ? "Planning…" : `Split into ${Number(parts) || rows.length || 1}`}
                </button>
                <button type="button" disabled={anyPaid}
                  onClick={() => setRows([])}
                  title={anyPaid
                    ? "Some instalments have been paid, so they cannot be cleared"
                    : "Clear every row and type the schedule from scratch"}
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40">
                  <Trash2 className="h-3 w-3" /> Clear all
                </button>
                <button type="button"
                  onClick={() => setRows(detail ? rowsFrom(detail) : [])}
                  title="Put the schedule back the way it is saved"
                  className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs transition-colors hover:bg-muted">
                  <RotateCcw className="h-3 w-3" /> Reset
                </button>
              </div>
            </div>

            {rows.length === 0 ? (
              <p className="rounded-lg border border-dashed border-border px-3 py-5 text-center text-xs text-muted-foreground">
                No instalments. Add the rows you want, or split the net evenly.
              </p>
            ) : (
              <div className="overflow-hidden rounded-lg border border-border">
                <table className="w-full text-sm">
                  <thead className="bg-muted/60 text-[10px] uppercase tracking-wide text-muted-foreground">
                    <tr>
                      <th className="w-7 px-1.5 py-1.5 text-left font-medium">#</th>
                      <th className="px-1.5 py-1.5 text-left font-medium">Period</th>
                      <th className="px-1.5 py-1.5 text-left font-medium">Due</th>
                      <th className="px-1.5 py-1.5 text-right font-medium">Amount</th>
                      <th className="w-8 px-1.5 py-1.5" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => {
                      const under = num(r.amount) < r.paid;
                      return (
                        <tr key={r.id ?? `new-${i}`} className="border-t border-border/60">
                          <td className="px-1.5 py-1 text-muted-foreground">{i + 1}</td>
                          <td className="px-1.5 py-1">
                            <Input className="h-8" placeholder={`Instalment ${i + 1}`}
                              aria-label={`Label for instalment ${i + 1}`}
                              value={r.label}
                              onChange={(e) => edit(i, { label: e.target.value })} />
                          </td>
                          <td className="px-1.5 py-1">
                            <Input className="h-8 w-[8.5rem]" type="date"
                              aria-label={`Due date for instalment ${i + 1}`}
                              value={r.due_date ?? ""}
                              onChange={(e) => edit(i, { due_date: e.target.value || null })} />
                          </td>
                          <td className="px-1.5 py-1">
                            <Input className={cn("h-8 w-28 text-right",
                              under && "border-rose-500 focus-visible:ring-rose-500")}
                              type="number" min={0} inputMode="numeric"
                              aria-label={`Amount for instalment ${i + 1}`}
                              value={r.amount}
                              onChange={(e) => edit(i, { amount: e.target.value })} />
                            {r.paid > 0 ? (
                              <span className={cn("mt-0.5 block text-right text-[10px]",
                                under ? "font-medium text-rose-600 dark:text-rose-400"
                                  : "text-muted-foreground")}>
                                {money(String(r.paid))} paid
                              </span>
                            ) : null}
                          </td>
                          <td className="px-1.5 py-1 text-center">
                            {r.paid > 0 ? (
                              <Lock className="mx-auto h-3.5 w-3.5 text-muted-foreground"
                                aria-label="Paid — cannot be removed" />
                            ) : (
                              <button type="button" aria-label={`Remove instalment ${i + 1}`}
                                onClick={() => setRows(rows.filter((_, idx) => idx !== i))}
                                className="rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-rose-600 dark:hover:text-rose-400">
                                <X className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2">
              <button type="button"
                onClick={() => setRows([...rows, {
                  id: null, label: "", amount: String(Math.max(remaining, 0)),
                  due_date: null, paid: 0,
                }])}
                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                <Plus className="h-3 w-3" /> Add an instalment
              </button>
              {/* The one number that decides whether this can be saved. */}
              <p className={cn("text-xs",
                remaining === 0 ? "text-muted-foreground"
                  : "font-medium text-rose-600 dark:text-rose-400")}>
                {remaining === 0
                  ? "The instalments add up to the net payable."
                  : remaining > 0
                    ? `${money(String(remaining))} still to allocate.`
                    : `${money(String(-remaining))} over the net payable.`}
                {remaining !== 0 && rows.length > 0 ? (
                  <>
                    <button type="button"
                      onClick={() => setRows(spread(rows, remaining))}
                      className="ml-1.5 font-medium text-primary hover:underline">
                      spread it
                    </button>
                    <span className="mx-1 text-muted-foreground">·</span>
                    <button type="button"
                      onClick={() => {
                        const last = rows.length - 1;
                        edit(last, {
                          amount: String(round2(num(rows[last].amount) + remaining)),
                        });
                      }}
                      className="font-medium text-primary hover:underline">
                      put it on the last row
                    </button>
                  </>
                ) : null}
              </p>
            </div>
          </div>

          <div>
            <Label>Why (optional)</Label>
            <Input placeholder="e.g. admitted at the concessional rate"
              maxLength={300} value={reason}
              onChange={(e) => setReason(e.target.value)} />
            <p className="mt-1 text-[11px] leading-snug text-muted-foreground">
              This goes into the record&rsquo;s history with your name, so the
              next person who asks &ldquo;why is this child paying less&rdquo;
              can read the answer instead of asking around.
            </p>
          </div>

          {problem ? (
            <p className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-600 dark:text-rose-400">
              {problem}
            </p>
          ) : null}

          <Button className="w-full"
            disabled={save.isPending || !!problem || remaining !== 0}
            onClick={() => save.mutate()}>
            {save.isPending ? "Saving…" : "Save the corrected record"}
          </Button>
        </div>
      )}
    </Sheet>
  );
}
