"use client";

/**
 * One family's fee record (FE-1, `D-125`).
 *
 * Routed by **student**, not by fee record. A child nobody has set up yet still
 * has a page — that page is where you set her up — and the old
 * `/fees/{student_fee_id}` route could not render one at all.
 *
 * The instalment row is the screen's signature: the **counterfoil** from the
 * receipt book a school already keeps. Number, period, due date, amount, and a
 * stub on the right carrying undo and the row's other actions.
 *
 * Underneath it, the two sections the founder asked for — *"we can showw the
 * converstaion history and transcation history"* — as tabs, with **Conversation
 * first**: the question at the counter is "what did they say", not "what did we
 * record".
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Camera, Lock, MoreHorizontal, Paperclip, Pencil, Trash2, Undo2 } from "lucide-react";
import Link from "next/link";
import { use, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { FeeConversation } from "@/components/school/fee-conversation";
import { FeeReviseSheet } from "@/components/school/fee-revise-sheet";
import { FeeSetupSheet } from "@/components/school/fee-setup-sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { Sheet } from "@/components/ui/sheet";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";
import type { Installment, StudentFeeDetail } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const TONE: Record<string, "success" | "neutral" | "warning" | "outline"> = {
  paid: "success", partial: "outline", overdue: "warning",
  pending: "neutral", closed: "neutral",
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Never `new Date(iso)` on a bare `YYYY-MM-DD` — that parses as UTC midnight
 *  and renders the previous day west of UTC. Split the string instead. */
function shortDate(iso: string | null): string {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${String(y).slice(2)}`;
}

function Stat({ label, value, accent }: {
  label: string; value: string; accent?: "brand" | "rose" | "emerald";
}) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
        {label}
      </p>
      <p className={cn("mt-0.5 text-lg font-semibold",
        accent === "brand" && "text-primary",
        accent === "rose" && "text-rose-600 dark:text-rose-400",
        accent === "emerald" && "text-emerald-600 dark:text-emerald-400")}>
        {value}
      </p>
    </div>
  );
}

// ── record a payment, with its proof ─────────────────────────────────────────
function PaySheet({ inst, sfId, onClose }: {
  inst: Installment | null; sfId: string; onClose: () => void;
}) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const remaining = inst ? Number(inst.amount) - Number(inst.paid_amount) : 0;
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState("cash");
  const [paidOn, setPaidOn] = useState(() => new Date().toISOString().slice(0, 10));
  const [receipt, setReceipt] = useState("");
  const [note, setNote] = useState("");
  const [proof, setProof] = useState<File | null>(null);

  const pay = useMutation({
    mutationFn: async () => {
      const detail = await schoolApi.pay(inst!.id, {
        amount: amount || String(remaining),
        mode, paid_on: paidOn,
        receipt_number: receipt.trim() || null,
        note: note.trim() || undefined,
      });
      if (proof) {
        // The proof rides the transaction the payment just wrote. Uploaded
        // AFTER the payment on purpose: a failed upload must never cost the
        // school the record that money came in.
        const txns = await schoolApi.transactions(sfId);
        const latest = txns.find((t) => t.type === "payment");
        if (latest) {
          try {
            await schoolApi.uploadFeeProof(latest.id, proof);
          } catch (err) {
            showApiError(err, "The payment saved, but the proof did not upload");
          }
        }
      }
      return detail;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["student-fee-detail", sfId] });
      qc.invalidateQueries({ queryKey: ["fee-transactions", sfId] });
      qc.invalidateQueries({ queryKey: ["fee-proofs", sfId] });
      qc.invalidateQueries({ queryKey: ["fee-activity", sfId] });
      qc.invalidateQueries({ queryKey: ["student-fees"] });
      toast.success("Payment recorded");
      setAmount(""); setProof(null); onClose();
    },
    onError: (e) => showApiError(e, "Could not record the payment"),
  });

  return (
    <Sheet open={!!inst} onOpenChange={(v) => { if (!v) onClose(); }}
      title="Record payment">
      {inst ? (
        <form className="space-y-3"
          onSubmit={(e) => { e.preventDefault(); pay.mutate(); }}>
          <p className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
            {inst.label || `Instalment ${inst.installment_number}`} · remaining{" "}
            <span className="font-semibold text-foreground">
              {money(String(remaining))}
            </span>
          </p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Amount</Label>
              <Input type="number" placeholder={String(remaining)} value={amount}
                onChange={(e) => setAmount(e.target.value)} />
            </div>
            <div>
              <Label>Date</Label>
              <Input type="date" value={paidOn}
                onChange={(e) => setPaidOn(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Mode</Label>
              <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
                value={mode} onChange={(e) => setMode(e.target.value)}>
                <option value="cash">Cash</option>
                <option value="cheque">Cheque</option>
                <option value="online">Online</option>
              </select>
            </div>
            <div>
              <Label>Receipt no.</Label>
              <Input placeholder="Generated if left blank" value={receipt}
                onChange={(e) => setReceipt(e.target.value)} />
            </div>
          </div>
          <div>
            <Label>Note (optional)</Label>
            <Input value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. part payment, rest after the 15th" />
          </div>

          <div>
            <Label>Proof (optional)</Label>
            <div className="flex flex-wrap gap-2">
              {/* `capture` opens the camera on a phone and falls back to a file
                  picker on desktop — one control, no second code path. */}
              <input ref={cameraRef} type="file" accept="image/*"
                capture="environment" className="hidden"
                onChange={(e) => setProof(e.target.files?.[0] ?? null)} />
              <input ref={fileRef} type="file"
                accept="image/*,application/pdf" className="hidden"
                onChange={(e) => setProof(e.target.files?.[0] ?? null)} />
              <Button type="button" size="sm" variant="outline"
                onClick={() => cameraRef.current?.click()}>
                <Camera className="h-4 w-4" /> Take photo
              </Button>
              <Button type="button" size="sm" variant="outline"
                onClick={() => fileRef.current?.click()}>
                <Paperclip className="h-4 w-4" /> Upload image or PDF
              </Button>
            </div>
            {proof ? (
              <p className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
                <span className="truncate">{proof.name}</span>
                <button type="button" onClick={() => setProof(null)}
                  className="text-rose-600 hover:underline dark:text-rose-400">
                  remove
                </button>
              </p>
            ) : (
              <p className="mt-1 text-[11px] text-muted-foreground">
                A receipt photo helps later, but never hold up a payment for it.
              </p>
            )}
          </div>

          <Button type="submit" className="w-full" disabled={pay.isPending}>
            {pay.isPending
              ? "Recording…"
              : `Record payment of ${money(amount || String(remaining))}`}
          </Button>
        </form>
      ) : null}
    </Sheet>
  );
}

// ── split an instalment ──────────────────────────────────────────────────────
function SplitModal({ inst, sfId, onClose }: {
  inst: Installment | null; sfId: string; onClose: () => void;
}) {
  const qc = useQueryClient();
  const [parts, setParts] = useState(2);
  const total = inst ? Number(inst.amount) : 0;
  const preview = useMemo(() => {
    if (!inst) return [];
    const base = Math.round((total / parts) * 100) / 100;
    const out = Array<number>(parts - 1).fill(base);
    out.push(Math.round((total - base * (parts - 1)) * 100) / 100);
    return out;
  }, [inst, parts, total]);

  const split = useMutation({
    mutationFn: () => schoolApi.splitInstallment(inst!.id, { parts }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["student-fee-detail", sfId] });
      qc.invalidateQueries({ queryKey: ["fee-activity", sfId] });
      toast.success("Instalment split");
      onClose();
    },
    onError: (e) => showApiError(e, "Could not split the instalment"),
  });

  return (
    <Modal open={!!inst} onOpenChange={(v) => { if (!v) onClose(); }}
      title="Split this instalment"
      description="For a family that needs to pay in smaller pieces.">
      {inst ? (
        <div className="space-y-3">
          <div>
            <Label>Into how many parts</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={parts} onChange={(e) => setParts(Number(e.target.value))}>
              {[2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div className="rounded-lg border border-border">
            {preview.map((amt, i) => (
              <div key={i}
                className="flex justify-between border-b border-border/60 px-3 py-1.5 text-sm last:border-0">
                <span className="text-muted-foreground">
                  {inst.label || `Instalment ${inst.installment_number}`} ({i + 1})
                </span>
                <span className="font-medium">{money(String(amt))}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground">
            The total does not change — {money(inst.amount)} either way. The new
            parts start with no due date; give them one when the family agrees.
          </p>
          <Button className="w-full" disabled={split.isPending}
            onClick={() => split.mutate()}>
            {split.isPending ? "Splitting…" : "Split instalment"}
          </Button>
        </div>
      ) : null}
    </Modal>
  );
}

// ── the ledger + activity feed ───────────────────────────────────────────────
function TransactionsTab({ sfId }: { sfId: string }) {
  const { data: txns = [] } = useQuery({
    queryKey: ["fee-transactions", sfId],
    queryFn: () => schoolApi.transactions(sfId),
  });
  const { data: events = [] } = useQuery({
    queryKey: ["fee-activity", sfId],
    queryFn: () => schoolApi.feeActivityForStudent(sfId),
  });

  // One chronology. Money rows carry their amount; actor rows are the narrative
  // — `D-124`'s whole point is that admin2 can see who did what and go ask.
  const merged = useMemo(() => {
    const rows = [
      ...txns.map((t) => ({
        id: `t-${t.id}`, at: t.created_at, kind: t.type,
        text: [t.note, t.receipt_number ? `receipt ${t.receipt_number}` : null,
          t.mode].filter(Boolean).join(" · "),
        amount: t.amount as string | null, who: t.created_by_name, isMoney: true,
      })),
      ...events.map((e) => ({
        id: `e-${e.id}`, at: e.created_at, kind: e.kind,
        text: e.summary, amount: null as string | null,
        who: e.actor_name, isMoney: false,
      })),
    ];
    return rows.sort((a, b) => (a.at < b.at ? 1 : -1));
  }, [txns, events]);

  if (merged.length === 0) {
    return (
      <p className="px-1 py-6 text-sm text-muted-foreground">
        Nothing has happened on this record yet.
      </p>
    );
  }

  return (
    <ul className="divide-y divide-border">
      {merged.map((row) => (
        <li key={row.id} className="flex items-start gap-3 py-2.5 text-sm">
          <span className="mt-0.5 w-20 shrink-0 font-mono text-[11px] text-muted-foreground">
            {shortDate(row.at.slice(0, 10))}
          </span>
          <span className={cn("min-w-0 flex-1",
            row.isMoney ? "text-foreground" : "text-muted-foreground")}>
            {row.text || row.kind.replace(/_/g, " ")}
            {row.who ? (
              <span className="ml-1.5 text-xs text-muted-foreground">
                — {row.who}
              </span>
            ) : null}
          </span>
          {row.amount && Number(row.amount) !== 0 ? (
            <span className={cn("shrink-0 font-medium",
              Number(row.amount) < 0
                ? "text-rose-600 dark:text-rose-400"
                : "text-emerald-600 dark:text-emerald-400")}>
              {money(row.amount)}
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

// ── the page ─────────────────────────────────────────────────────────────────
function FamilyInner({ studentId }: { studentId: string }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [tab, setTab] = useState<"conversation" | "transactions">("conversation");
  const [payFor, setPayFor] = useState<Installment | null>(null);
  const [splitFor, setSplitFor] = useState<Installment | null>(null);
  const [menuFor, setMenuFor] = useState<string | null>(null);
  const [discount, setDiscount] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  // FE-2 — the setup sheet, for a student who has no record yet.
  const [setupOpen, setSetupOpen] = useState(false);
  // FE-3 — the same numbers, editable again after they were saved.
  const [editOpen, setEditOpen] = useState(false);
  const [addAmount, setAddAmount] = useState("");
  const [addDate, setAddDate] = useState("");

  const { data: fees = [] } = useQuery({
    queryKey: ["student-fees", yearId],
    queryFn: () => schoolApi.studentFees({ year_id: yearId ?? undefined }),
    enabled: !!yearId,
  });
  const record = fees.find((f) => f.student_id === studentId);

  const { data: detail } = useQuery({
    queryKey: ["student-fee-detail", record?.id],
    queryFn: () => schoolApi.studentFee(record!.id),
    enabled: !!record,
  });
  const { data: proofs = [] } = useQuery({
    queryKey: ["fee-proofs", record?.id],
    queryFn: () => schoolApi.feeProofs(record!.id),
    enabled: !!record,
  });

  const act = useMutation({
    mutationFn: (fn: () => Promise<StudentFeeDetail>) => fn(),
    onSuccess: () => {
      if (record) {
        qc.invalidateQueries({ queryKey: ["student-fee-detail", record.id] });
        qc.invalidateQueries({ queryKey: ["fee-activity", record.id] });
        qc.invalidateQueries({ queryKey: ["fee-transactions", record.id] });
      }
      qc.invalidateQueries({ queryKey: ["student-fees"] });
      toast.success("Updated");
    },
    onError: (e) => showApiError(e, "That did not work"),
  });

  if (!record) {
    // `D-125`: a student with no fee record still has a page, and it is an
    // invitation rather than a dead end. FE-2 makes the invitation actionable —
    // it used to point at the Students tab and stop, which meant the one child
    // whose price was negotiated had to be billed the class price first and
    // corrected afterwards.
    return (
      <div>
        <Link href="/fees/students"
          className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Students
        </Link>
        <EmptyState
          icon={Lock}
          title="No fee record for this student yet"
          body="Set her up on the class structure, or on a price agreed with the family — a fixed discount and how many instalments."
          action={
            <Button onClick={() => setSetupOpen(true)}>
              <Lock className="h-4 w-4" /> Set up fees
            </Button>
          }
        />
        <FeeSetupSheet studentId={setupOpen ? studentId : null}
          yearId={yearId ?? null} onClose={() => setSetupOpen(false)} />
      </div>
    );
  }
  if (!detail) return <p className="text-sm text-muted-foreground">Loading…</p>;

  const closed = detail.status === "closed";

  return (
    <div>
      <Link href="/fees/students"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Students
      </Link>

      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-xl font-semibold tracking-tight">
              {detail.student_name}
            </h2>
            <Badge tone={TONE[detail.status] ?? "neutral"}>{detail.status}</Badge>
          </div>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {detail.class_label ?? "—"}
            {detail.category_name ? ` · ${detail.category_name}` : ""}
          </p>
        </div>
        {closed ? (
          <Button size="sm" variant="outline" disabled={act.isPending}
            onClick={() => act.mutate(() => schoolApi.reopenFeeRecord(record.id))}>
            Reopen record
          </Button>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            {/* FE-3 — everything typed at enrolment, editable again. */}
            <Button size="sm" variant="outline" onClick={() => setEditOpen(true)}>
              <Pencil className="h-4 w-4" /> Edit fee
            </Button>
            <Button size="sm" variant="outline" disabled={act.isPending}
              onClick={() => {
                if (window.confirm(
                  "Close this record on transfer?\n\nUnpaid instalments are voided "
                  + "and the balance comes off the total. You can undo this "
                  + "afterwards.")) {
                  act.mutate(() =>
                    schoolApi.closeFeeRecord(record.id, "Transferred"));
                }
              }}>
              Transfer out
            </Button>
          </div>
        )}
      </div>

      <div className="mb-6 grid grid-cols-2 gap-4 rounded-xl border border-border bg-card px-4 py-3 sm:grid-cols-4 lg:grid-cols-7">
        <Stat label="Total" value={money(detail.total_fee)} />
        <Stat label="Discount"
          value={Number(detail.discount) > 0 ? money(detail.discount) : "—"} />
        <Stat label="Net" value={money(detail.net_fee)} />
        <Stat label="Prev. dues"
          value={Number(detail.opening_dues) > 0 ? money(detail.opening_dues) : "—"}
          accent={Number(detail.opening_dues) > 0 ? "rose" : undefined} />
        <Stat label="Payable" value={money(detail.total_payable)} accent="brand" />
        <Stat label="Paid" value={money(detail.paid)} accent="emerald" />
        <Stat label="Balance" value={money(detail.balance)}
          accent={Number(detail.balance) > 0 ? "rose" : "emerald"} />
      </div>

      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold">Instalments</h3>
        {!closed ? (
          <Button size="sm" variant="outline" onClick={() => setAddOpen(true)}>
            Add instalment
          </Button>
        ) : null}
      </div>

      <div className="mb-6 overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-3 py-2.5 text-left font-medium">#</th>
              <th className="px-3 py-2.5 text-left font-medium">Period</th>
              <th className="px-3 py-2.5 text-left font-medium">Due</th>
              <th className="px-3 py-2.5 text-right font-medium">Amount</th>
              <th className="px-3 py-2.5 text-right font-medium">Paid</th>
              <th className="px-3 py-2.5 text-left font-medium">Status</th>
              <th className="px-3 py-2.5 text-right font-medium">&nbsp;</th>
            </tr>
          </thead>
          <tbody>
            {detail.installments.map((inst) => {
              const remaining = Number(inst.amount) - Number(inst.paid_amount);
              return (
                <tr key={inst.id}
                  className={cn("border-t border-border/60",
                    // A voided instalment stays on the page, struck through:
                    // what was originally scheduled is what people ask about.
                    inst.is_voided && "text-muted-foreground line-through")}>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {inst.installment_number}
                  </td>
                  <td className="px-3 py-2.5">{inst.label || "—"}</td>
                  <td className="px-3 py-2.5">
                    {closed || inst.is_voided ? (
                      <span className="text-muted-foreground">
                        {shortDate(inst.due_date)}
                      </span>
                    ) : (
                      <Input type="date" className="h-8 w-36"
                        defaultValue={inst.due_date ?? ""}
                        onBlur={(e) => {
                          const next = e.target.value || null;
                          if (next !== inst.due_date) {
                            act.mutate(() => schoolApi.setDueDate(inst.id, next));
                          }
                        }} />
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right font-medium">
                    {money(inst.amount)}
                  </td>
                  <td className="px-3 py-2.5 text-right text-emerald-600 dark:text-emerald-400">
                    {Number(inst.paid_amount) > 0 ? money(inst.paid_amount) : "—"}
                  </td>
                  <td className="px-3 py-2.5">
                    <Badge tone={inst.is_voided
                      ? "neutral"
                      : TONE[inst.status] ?? "neutral"}>
                      {inst.is_voided ? "voided" : inst.status}
                    </Badge>
                  </td>
                  <td className="px-3 py-2.5">
                    {closed || inst.is_voided ? null : (
                      <div className="flex items-center justify-end gap-1.5">
                        {remaining > 0 ? (
                          <Button size="sm" onClick={() => setPayFor(inst)}>
                            Record payment
                          </Button>
                        ) : (
                          <Button size="sm" variant="ghost" disabled={act.isPending}
                            onClick={() => act.mutate(() => schoolApi.undo(inst.id))}>
                            <Undo2 className="h-4 w-4" /> Undo
                          </Button>
                        )}
                        <div className="relative">
                          <Button size="sm" variant="ghost"
                            aria-label="More actions"
                            onClick={() => setMenuFor(
                              menuFor === inst.id ? null : inst.id)}>
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                          {menuFor === inst.id ? (
                            <div className="absolute right-0 z-10 mt-1 w-44 rounded-lg border border-border bg-card py-1 shadow-lg">
                              <button type="button"
                                className="block w-full px-3 py-1.5 text-left text-sm hover:bg-muted"
                                onClick={() => {
                                  setSplitFor(inst); setMenuFor(null);
                                }}>
                                Split into parts
                              </button>
                              {remaining > 0 ? (
                                <button type="button"
                                  className="block w-full px-3 py-1.5 text-left text-sm hover:bg-muted"
                                  onClick={() => {
                                    setMenuFor(null);
                                    act.mutate(() => schoolApi.markPaid(inst.id));
                                  }}>
                                  Mark fully paid
                                </button>
                              ) : null}
                              {Number(inst.paid_amount) === 0 ? (
                                <button type="button"
                                  className="block w-full px-3 py-1.5 text-left text-sm text-rose-600 hover:bg-muted dark:text-rose-400"
                                  onClick={() => {
                                    setMenuFor(null);
                                    act.mutate(() =>
                                      schoolApi.removeInstallment(inst.id));
                                  }}>
                                  Remove instalment
                                </button>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {!closed ? (
        <div className="mb-6 flex flex-wrap items-end gap-2">
          <div className="w-48">
            <Label>Discount (₹)</Label>
            <Input type="number" placeholder={detail.discount} value={discount}
              onChange={(e) => setDiscount(e.target.value)} />
          </div>
          <Button variant="outline" disabled={!discount || act.isPending}
            onClick={() => {
              act.mutate(() => schoolApi.updateDiscount(record.id, { discount }));
              setDiscount("");
            }}>
            Apply discount
          </Button>
          <p className="text-xs text-muted-foreground">
            Changes what is owed; the unpaid instalments re-scale to match.
          </p>
        </div>
      ) : null}

      {proofs.length > 0 ? (
        <div className="mb-6">
          <h3 className="mb-2 text-sm font-semibold">
            Payment proof{" "}
            <span className="font-normal text-muted-foreground">
              ({proofs.length})
            </span>
          </h3>
          <div className="flex flex-wrap gap-2">
            {proofs.map((p) => (
              <div key={p.id}
                className="w-32 overflow-hidden rounded-lg border border-border bg-card">
                <a href={p.url} target="_blank" rel="noreferrer" className="block">
                  {p.kind === "photo" ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={p.url} alt={p.caption ?? "Payment proof"}
                      className="h-24 w-full object-cover" />
                  ) : (
                    <div className="flex h-24 items-center justify-center bg-muted text-xs text-muted-foreground">
                      PDF
                    </div>
                  )}
                </a>
                <div className="flex items-center justify-between px-2 py-1">
                  <span className="truncate text-[10px] text-muted-foreground">
                    {p.uploaded_by_name ?? "—"}
                  </span>
                  <button type="button" aria-label="Remove proof"
                    onClick={() => {
                      if (window.confirm("Remove this proof? The file is deleted; "
                        + "the record that it existed stays.")) {
                        schoolApi.deleteFeeProof(p.id)
                          .then(() => {
                            qc.invalidateQueries({
                              queryKey: ["fee-proofs", record.id] });
                            qc.invalidateQueries({
                              queryKey: ["fee-activity", record.id] });
                          })
                          .catch((e) => showApiError(e, "Could not remove it"));
                      }
                    }}>
                    <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-rose-500" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* The two sections the founder asked for, UNDER the instalments so the
          money stays on screen while you read what was said. */}
      <div className="mb-2 flex gap-1 border-b border-border">
        {(["conversation", "transactions"] as const).map((t) => (
          <button key={t} type="button" onClick={() => setTab(t)}
            className={cn(
              "-mb-px border-b-2 px-4 py-2 text-sm font-medium capitalize transition-colors",
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground")}>
            {t}
          </button>
        ))}
      </div>
      {tab === "conversation"
        ? <FeeConversation studentFeeId={record.id} />
        : <TransactionsTab sfId={record.id} />}

      <FeeReviseSheet detail={editOpen ? detail : null}
        onClose={() => setEditOpen(false)} />
      <PaySheet inst={payFor} sfId={record.id} onClose={() => setPayFor(null)} />
      <SplitModal inst={splitFor} sfId={record.id}
        onClose={() => setSplitFor(null)} />

      <Modal open={addOpen} onOpenChange={setAddOpen} title="Add an instalment"
        description="Funded out of what is still unpaid — the total owed does not change.">
        <form className="space-y-3" onSubmit={(e) => {
          e.preventDefault();
          act.mutate(() => schoolApi.addInstallment(record.id, {
            amount: addAmount, due_date: addDate || null,
          }));
          setAddAmount(""); setAddDate(""); setAddOpen(false);
        }}>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Amount (₹)</Label>
              <Input type="number" value={addAmount} required
                onChange={(e) => setAddAmount(e.target.value)} />
            </div>
            <div>
              <Label>Due date</Label>
              <Input type="date" value={addDate}
                onChange={(e) => setAddDate(e.target.value)} />
            </div>
          </div>
          <Button type="submit" className="w-full" disabled={!addAmount}>
            Add instalment
          </Button>
        </form>
      </Modal>
    </div>
  );
}

export default function FeeFamilyPage({ params }: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return (
    <AuthGuard allow={["admin"]}>
      <FamilyInner studentId={id} />
    </AuthGuard>
  );
}
