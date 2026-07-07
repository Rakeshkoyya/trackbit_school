"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { IndianRupee, Layers, Plus, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";

const STATUS_TONE: Record<string, "success" | "neutral" | "warning" | "outline"> = {
  paid: "success", partial: "outline", overdue: "warning", pending: "neutral",
};

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-xl font-semibold">{value}</p>
    </div>
  );
}

function EnrollSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [studentId, setStudentId] = useState("");
  const [total, setTotal] = useState("");
  const [discount, setDiscount] = useState("0");
  const [structureId, setStructureId] = useState("");
  const { data: students = [] } = useQuery({ queryKey: ["students"], queryFn: () => schoolApi.students() });
  const { data: structures = [] } = useQuery({ queryKey: ["structures", yearId], queryFn: () => schoolApi.structures(yearId ?? undefined), enabled: !!yearId });

  const enroll = useMutation({
    mutationFn: () => schoolApi.enroll({
      student_id: studentId, academic_year_id: yearId, total_fee: total,
      discount: discount || "0", fee_structure_id: structureId || null,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["student-fees"] });
      toast.success("Student enrolled for fees");
      setStudentId(""); setTotal(""); setDiscount("0"); setStructureId("");
      onOpenChange(false);
    },
    onError: (e) => showApiError(e, "Could not enrol"),
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Enrol student for fees">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (studentId && total && yearId) enroll.mutate(); }}>
        <div>
          <Label>Student</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={studentId} onChange={(e) => setStudentId(e.target.value)} required>
            <option value="">Select…</option>
            {students.map((s) => <option key={s.id} value={s.id}>{s.full_name} · {s.admission_no}</option>)}
          </select>
        </div>
        <div>
          <Label>Fee structure (optional — scales installments)</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={structureId} onChange={(e) => setStructureId(e.target.value)}>
            <option value="">None (single installment)</option>
            {structures.map((s) => <option key={s.id} value={s.id}>{s.class_name}{s.category_name ? ` · ${s.category_name}` : ""} · {money(s.total_amount)}</option>)}
          </select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div><Label>Total fee</Label><Input type="number" value={total} onChange={(e) => setTotal(e.target.value)} required /></div>
          <div><Label>Discount</Label><Input type="number" value={discount} onChange={(e) => setDiscount(e.target.value)} /></div>
        </div>
        <Button type="submit" className="w-full" disabled={enroll.isPending || !studentId || !total || !yearId}>
          {enroll.isPending ? "Enrolling…" : "Enrol"}
        </Button>
      </form>
    </Sheet>
  );
}

function FeesInner() {
  const router = useRouter();
  const { yearId } = useYear();
  const [query, setQuery] = useState("");
  const [enrollOpen, setEnrollOpen] = useState(false);
  const { data: summary } = useQuery({ queryKey: ["fee-summary", yearId], queryFn: () => schoolApi.feeSummary(yearId ?? undefined), enabled: !!yearId });
  const { data: rows = [] } = useQuery({
    queryKey: ["student-fees", yearId, query],
    queryFn: () => schoolApi.studentFees({ year_id: yearId ?? undefined, search: query.trim() || undefined }),
    enabled: !!yearId,
  });

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Fees</h1>
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <Link href="/fees/structures"><Button size="sm" variant="outline"><Layers className="h-4 w-4" /> Structures</Button></Link>
          <Button size="sm" onClick={() => setEnrollOpen(true)}><Plus className="h-4 w-4" /> Enrol</Button>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Net fee (year)" value={money(summary?.total_fee ?? "0")} />
        <Stat label="Collected" value={money(summary?.collected_fee ?? "0")} />
        <Stat label="Overdue" value={money(summary?.overdue_amount ?? "0")} />
        <Stat label="Pending installments" value={String(summary?.pending_installments ?? 0)} />
      </div>

      <div className="relative mb-4">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input className="pl-9" placeholder="Search student…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>

      {rows.length === 0 ? (
        <EmptyState icon={IndianRupee} title="No fee records yet" body="Enrol a student to start tracking installments and payments." />
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <button key={r.id} onClick={() => router.push(`/fees/${r.id}`)} className="flex w-full items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 text-left hover:bg-muted/40">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{r.student_name}</p>
                <p className="truncate text-xs text-muted-foreground">{r.class_label ?? "—"}{r.category_name ? ` · ${r.category_name}` : ""}</p>
              </div>
              <div className="text-right text-xs">
                <p className="font-medium">{money(r.paid)} <span className="text-muted-foreground">/ {money(r.net_fee)}</span></p>
                <p className="text-muted-foreground">{money(r.pending)} due</p>
              </div>
              <Badge tone={STATUS_TONE[r.status] ?? "neutral"}>{r.status}</Badge>
            </button>
          ))}
        </div>
      )}
      <EnrollSheet open={enrollOpen} onOpenChange={setEnrollOpen} />
    </div>
  );
}

export default function FeesPage() {
  return (
    <AuthGuard allow={["admin", "office"]}>
      <FeesInner />
    </AuthGuard>
  );
}
