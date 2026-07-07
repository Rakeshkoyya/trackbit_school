"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Undo2 } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";
import type { Installment } from "@/lib/school-types";

function PaySheet({ inst, sfId, onClose }: { inst: Installment | null; sfId: string; onClose: () => void }) {
  const qc = useQueryClient();
  const remaining = inst ? Number(inst.amount) - Number(inst.paid_amount) : 0;
  const [amount, setAmount] = useState("");
  const [mode, setMode] = useState("cash");

  const pay = useMutation({
    mutationFn: () => schoolApi.pay(inst!.id, { amount: amount || String(remaining), mode }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["student-fee", sfId] });
      qc.invalidateQueries({ queryKey: ["fee-transactions", sfId] });
      toast.success("Payment recorded");
      setAmount(""); onClose();
    },
    onError: (e) => showApiError(e, "Could not record payment"),
  });

  return (
    <Sheet open={!!inst} onOpenChange={(v) => { if (!v) onClose(); }} title="Record payment">
      {inst ? (
        <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); pay.mutate(); }}>
          <p className="text-sm text-muted-foreground">
            Installment #{inst.installment_number} · remaining <span className="font-medium text-foreground">{money(remaining)}</span>
          </p>
          <div><Label>Amount</Label><Input type="number" placeholder={String(remaining)} value={amount} onChange={(e) => setAmount(e.target.value)} /></div>
          <div>
            <Label>Mode</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="cash">Cash</option><option value="cheque">Cheque</option><option value="online">Online</option>
            </select>
          </div>
          <Button type="submit" className="w-full" disabled={pay.isPending}>{pay.isPending ? "Saving…" : `Pay ${money(amount || remaining)}`}</Button>
        </form>
      ) : null}
    </Sheet>
  );
}

function FeeDetailInner({ id }: { id: string }) {
  const qc = useQueryClient();
  const [payInst, setPayInst] = useState<Installment | null>(null);
  const [discount, setDiscount] = useState("");
  const { data } = useQuery({ queryKey: ["student-fee", id], queryFn: () => schoolApi.studentFee(id) });
  const { data: txns = [] } = useQuery({ queryKey: ["fee-transactions", id], queryFn: () => schoolApi.transactions(id) });

  const undo = useMutation({
    mutationFn: (instId: string) => schoolApi.undo(instId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["student-fee", id] }); qc.invalidateQueries({ queryKey: ["fee-transactions", id] }); toast.success("Payment reverted"); },
    onError: (e) => showApiError(e, "Could not undo"),
  });
  const setDisc = useMutation({
    mutationFn: () => schoolApi.updateDiscount(id, { discount }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["student-fee", id] }); qc.invalidateQueries({ queryKey: ["fee-transactions", id] }); toast.success("Discount updated"); setDiscount(""); },
    onError: (e) => showApiError(e, "Could not update discount"),
  });

  if (!data) return null;

  return (
    <div>
      <Link href="/fees" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Fees
      </Link>
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">{data.student_name}</h1>
        <p className="text-sm text-muted-foreground">{data.class_label ?? "—"}{data.category_name ? ` · ${data.category_name}` : ""}</p>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-xl border border-border bg-card p-3"><p className="text-xs text-muted-foreground">Net fee</p><p className="text-lg font-semibold">{money(data.net_fee)}</p></div>
        <div className="rounded-xl border border-border bg-card p-3"><p className="text-xs text-muted-foreground">Paid</p><p className="text-lg font-semibold">{money(data.paid)}</p></div>
        <div className="rounded-xl border border-border bg-card p-3"><p className="text-xs text-muted-foreground">Balance</p><p className="text-lg font-semibold">{money(data.balance)}</p></div>
        <div className="rounded-xl border border-border bg-card p-3"><p className="text-xs text-muted-foreground">Discount</p><p className="text-lg font-semibold">{money(data.discount)}</p></div>
      </div>

      <h2 className="mb-2 text-sm font-semibold">Installments</h2>
      <div className="mb-6 space-y-2">
        {data.installments.map((i) => {
          const remaining = Number(i.amount) - Number(i.paid_amount);
          return (
            <div key={i.id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium">#{i.installment_number} {i.label ? `· ${i.label}` : ""}</p>
                <p className="text-xs text-muted-foreground">{money(i.amount)}{i.due_date ? ` · due ${i.due_date}` : ""}</p>
              </div>
              <Badge tone={i.status === "paid" ? "success" : i.status === "overdue" ? "warning" : "neutral"}>{i.status}</Badge>
              {remaining > 0 ? (
                <Button size="sm" onClick={() => setPayInst(i)}>Pay</Button>
              ) : (
                <Button size="sm" variant="ghost" onClick={() => undo.mutate(i.id)}><Undo2 className="h-4 w-4" /> Undo</Button>
              )}
            </div>
          );
        })}
      </div>

      <div className="mb-6 flex items-end gap-2">
        <div className="flex-1"><Label>Update discount</Label><Input type="number" placeholder={data.discount} value={discount} onChange={(e) => setDiscount(e.target.value)} /></div>
        <Button variant="outline" onClick={() => discount && setDisc.mutate()} disabled={setDisc.isPending || !discount}>Apply</Button>
      </div>

      <h2 className="mb-2 text-sm font-semibold">Ledger</h2>
      <div className="space-y-1">
        {txns.map((t) => (
          <div key={t.id} className="flex items-center justify-between rounded-md border border-border bg-card px-3 py-2 text-xs">
            <span className="capitalize">{t.type}{t.note ? ` · ${t.note}` : ""}</span>
            <span className="font-medium">{money(t.amount)}</span>
          </div>
        ))}
      </div>

      <PaySheet inst={payInst} sfId={id} onClose={() => setPayInst(null)} />
    </div>
  );
}

export default function FeeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <AuthGuard allow={["admin", "office"]}>
      <FeeDetailInner id={id} />
    </AuthGuard>
  );
}
