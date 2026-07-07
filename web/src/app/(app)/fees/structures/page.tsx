"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";

// Even split matching the backend even_split(): remainder on the last part.
function evenSplit(total: number, n: number): number[] {
  const base = Math.round((total / n) * 100) / 100;
  const parts = Array(n - 1).fill(base);
  parts.push(Math.round((total - base * (n - 1)) * 100) / 100);
  return parts;
}

function CreateStructureSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [className, setClassName] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [total, setTotal] = useState("");
  const [num, setNum] = useState("3");
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: schoolApi.categories });

  const create = useMutation({
    mutationFn: () => {
      const n = Math.max(1, parseInt(num, 10) || 1);
      const amounts = evenSplit(Number(total), n);
      return schoolApi.createStructure({
        class_name: className.trim(), academic_year_id: yearId,
        category_id: categoryId || null, total_amount: total, num_installments: n,
        installments: amounts.map((a, idx) => ({ installment_number: idx + 1, amount: String(a) })),
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["structures"] });
      toast.success("Fee structure saved");
      setClassName(""); setCategoryId(""); setTotal(""); setNum("3");
      onOpenChange(false);
    },
    onError: (e) => showApiError(e, "Could not save structure"),
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="New fee structure">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (className && total && yearId) create.mutate(); }}>
        <div><Label>Class (label)</Label><Input placeholder="6-B" value={className} onChange={(e) => setClassName(e.target.value)} required /></div>
        <div>
          <Label>Category (optional)</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Applies to all</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div><Label>Total fee</Label><Input type="number" value={total} onChange={(e) => setTotal(e.target.value)} required /></div>
          <div><Label>Installments</Label><Input type="number" min={1} max={24} value={num} onChange={(e) => setNum(e.target.value)} /></div>
        </div>
        <p className="text-xs text-muted-foreground">Installments are split evenly; adjust amounts later per student on enrolment.</p>
        <Button type="submit" className="w-full" disabled={create.isPending || !className || !total || !yearId}>
          {create.isPending ? "Saving…" : "Save structure"}
        </Button>
      </form>
    </Sheet>
  );
}

function StructuresInner() {
  const { yearId } = useYear();
  const [open, setOpen] = useState(false);
  const { data: structures = [] } = useQuery({
    queryKey: ["structures", yearId],
    queryFn: () => schoolApi.structures(yearId ?? undefined),
    enabled: !!yearId,
  });

  return (
    <div>
      <Link href="/fees" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Fees
      </Link>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Fee structures</h1>
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <Button size="sm" onClick={() => setOpen(true)}><Plus className="h-4 w-4" /> New</Button>
        </div>
      </div>
      {structures.length === 0 ? (
        <EmptyState icon={Plus} title="No fee structures yet" body="Define a per-class fee template; enrolling a student scales it into installments." />
      ) : (
        <div className="space-y-2">
          {structures.map((s) => (
            <div key={s.id} className="rounded-lg border border-border bg-card px-4 py-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium">{s.class_name}{s.category_name ? ` · ${s.category_name}` : ""}</p>
                <p className="text-sm font-semibold">{money(s.total_amount)}</p>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                {s.num_installments} installments · {s.templates.map((t) => money(t.amount)).join(", ")}
              </p>
            </div>
          ))}
        </div>
      )}
      <CreateStructureSheet open={open} onOpenChange={setOpen} />
    </div>
  );
}

export default function StructuresPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <StructuresInner />
    </AuthGuard>
  );
}
