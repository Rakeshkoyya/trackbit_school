"use client";

/**
 * The fee structure editor (FE-1, `D-116`/`D-118`).
 *
 * Plutus's best idea is kept and re-worded: a **reconciliation bar** under the
 * schedule that shows, live, whether the parts add up to the total. What changed
 * is what it says. "Difference: ₹2,000" is a fact; *"₹2,000 still to allocate"*
 * is an instruction, and this is a form somebody fills in at speed.
 *
 * Two rules the old screen broke:
 *
 *   · the class is **picked, not typed** (`D-116`). It is one of the year's real
 *     class names, and the editor says underneath which sections the price
 *     covers — per-class pricing has to make that obvious or nobody can tell
 *     whether 6-C was included;
 *   · **saving does not reprice anybody already set up** (`D-118`), and when
 *     students are on the current price the editor says so above Save, with the
 *     count. A warning after the fact is not a warning.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";
import type { ClassCoverageRow } from "@/lib/school-types";
import { cn } from "@/lib/utils";

interface Row {
  label: string;
  due_date: string;
  amount: string;
}

/** Remainder on the last part — the same rule `fee_math.even_split` uses, so the
 *  bar agrees with the server instead of arguing with it by a paisa. */
function evenSplit(total: number, parts: number): number[] {
  if (parts < 1) return [];
  const base = Math.round((total / parts) * 100) / 100;
  const out = Array<number>(parts - 1).fill(base);
  out.push(Math.round((total - base * (parts - 1)) * 100) / 100);
  return out;
}

/** Three months on, keeping the day of the month. Built from the row above
 *  rather than from "today", so a school planning next year's schedule in
 *  February does not get dates in the past. UTC arithmetic on a plain
 *  `YYYY-MM-DD` — never a local-midnight Date, which shifts a day east of UTC. */
function addMonths(iso: string, months: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1 + months, d)).toISOString().slice(0, 10);
}

export function FeeStructureEditor({
  open, onOpenChange, row, yearId, classNames,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  /** The coverage row being edited. `structure_id === null` means "not priced
   *  yet", so this is a create. */
  row: ClassCoverageRow | null;
  yearId: string | null;
  /** Every class name in the year, so the picker offers real classes only. */
  classNames: string[];
}) {
  const qc = useQueryClient();
  const editing = Boolean(row?.structure_id);

  const [className, setClassName] = useState(row?.class_name ?? classNames[0] ?? "");
  const [categoryId, setCategoryId] = useState(row?.category_id ?? "");
  const [total, setTotal] = useState(
    row?.total_amount ? String(Number(row.total_amount)) : "",
  );
  const [rows, setRows] = useState<Row[]>(() =>
    Array.from({ length: row?.num_installments ?? 3 }, () => ({
      label: "", due_date: "", amount: "",
    })),
  );

  const { data: categories = [] } = useQuery({
    queryKey: ["categories"], queryFn: schoolApi.categories, enabled: open,
  });

  const totalNum = Number(total) || 0;
  const sum = useMemo(
    () => rows.reduce((acc, r) => acc + (Number(r.amount) || 0), 0),
    [rows],
  );
  // Rounded to the paisa before comparing: 0.1 + 0.2 is not 0.3 in binary
  // floating point, and a bar that says "₹0 still to allocate" while refusing
  // to save is the worst version of this control.
  const short = Math.round((totalNum - sum) * 100) / 100;
  const balanced = totalNum > 0 && short === 0;

  const setCount = (n: number) => {
    setRows((prev) =>
      Array.from({ length: n }, (_, i) => prev[i] ?? {
        label: "", due_date: "", amount: "",
      }),
    );
  };

  const splitEvenly = () => {
    const parts = evenSplit(totalNum, rows.length);
    setRows((prev) => prev.map((r, i) => ({ ...r, amount: String(parts[i] ?? 0) })));
  };

  const spreadQuarterly = () => {
    setRows((prev) => {
      const first = prev[0]?.due_date || `${new Date().getFullYear()}-04-10`;
      return prev.map((r, i) => ({
        ...r,
        due_date: i === 0 ? first : addMonths(first, 3 * i),
        label: r.label || `Instalment ${i + 1}`,
      }));
    });
  };

  const save = useMutation({
    mutationFn: () => {
      const payload = {
        total_amount: String(totalNum),
        num_installments: rows.length,
        category_id: categoryId || null,
        installments: rows.map((r, i) => ({
          installment_number: i + 1,
          label: r.label.trim() || null,
          amount: String(Number(r.amount) || 0),
          due_date: r.due_date || null,
        })),
      };
      return editing
        ? schoolApi.updateStructure(row!.structure_id!, payload)
        : schoolApi.createStructure({
            ...payload, class_name: className, academic_year_id: yearId,
          });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["structure-coverage"] });
      qc.invalidateQueries({ queryKey: ["structures"] });
      toast.success(editing ? "Fee structure saved" : "Class priced");
      onOpenChange(false);
    },
    onError: (e) => showApiError(e, "Could not save the structure"),
  });

  const covers = row?.sections?.length
    ? `covers ${row.sections.map((s) => `${row.class_name}-${s}`).join(", ")}`
    : null;

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={editing ? `Class ${row?.class_name} fee` : "Price a class"}
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (balanced && yearId) save.mutate();
        }}
      >
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Class</Label>
            <select
              className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={className}
              disabled={editing}
              onChange={(e) => setClassName(e.target.value)}
            >
              {classNames.map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div>
            <Label>Category</Label>
            <select
              className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
            >
              <option value="">All categories</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        </div>
        {covers ? (
          // Per-class pricing has to say what it covers, or the first question
          // anybody asks is whether 6-C was included.
          <p className="text-xs text-muted-foreground">One price, {covers}.</p>
        ) : null}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Total fee (₹)</Label>
            <Input type="number" min={0} value={total} required
              onChange={(e) => setTotal(e.target.value)} />
          </div>
          <div>
            <Label>Instalments</Label>
            <select
              className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={rows.length}
              onChange={(e) => setCount(Number(e.target.value))}
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((n) => (
                <option key={n} value={n}>{n}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={splitEvenly}
            disabled={!totalNum}>
            Split evenly
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={spreadQuarterly}>
            Space dates quarterly
          </Button>
        </div>

        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-2 py-2 text-left font-medium">#</th>
                <th className="px-2 py-2 text-left font-medium">Period</th>
                <th className="px-2 py-2 text-left font-medium">Due date</th>
                <th className="px-2 py-2 text-left font-medium">Amount</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, idx) => (
                <tr key={idx} className="border-t border-border">
                  <td className="px-2 py-1.5 text-muted-foreground">{idx + 1}</td>
                  <td className="px-2 py-1.5">
                    <Input className="h-8" placeholder={`Instalment ${idx + 1}`}
                      value={r.label}
                      onChange={(e) => setRows((p) =>
                        p.map((x, i) => (i === idx ? { ...x, label: e.target.value } : x)))} />
                  </td>
                  <td className="px-2 py-1.5">
                    <Input type="date" className="h-8" value={r.due_date}
                      onChange={(e) => setRows((p) =>
                        p.map((x, i) => (i === idx ? { ...x, due_date: e.target.value } : x)))} />
                  </td>
                  <td className="px-2 py-1.5">
                    <Input type="number" min={0} className="h-8" value={r.amount}
                      onChange={(e) => setRows((p) =>
                        p.map((x, i) => (i === idx ? { ...x, amount: e.target.value } : x)))} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* The reconciliation bar. Says what to DO, not what the difference is. */}
        <div className={cn(
          "flex items-center justify-between rounded-lg px-3 py-2 text-sm",
          balanced
            ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
            : "bg-amber-500/10 text-amber-700 dark:text-amber-400",
        )}>
          <span>{money(String(sum))} of {money(String(totalNum))} allocated</span>
          <span className="font-medium">
            {balanced
              ? "Balanced"
              : short > 0
                ? `${money(String(short))} still to allocate`
                : `${money(String(-short))} over-allocated`}
          </span>
        </div>

        {editing && (row?.students_on ?? 0) > 0 ? (
          // `D-118`, said BEFORE the click rather than after it.
          <p className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-xs leading-snug text-muted-foreground">
            <span className="font-medium text-foreground">
              {row!.students_on} student{row!.students_on === 1 ? " is" : "s are"} on
              the current {money(row!.total_amount ?? "0")}.
            </span>{" "}
            Saving prices new students only — nobody already set up is repriced.
          </p>
        ) : null}

        <Button type="submit" className="w-full"
          disabled={!balanced || save.isPending || !yearId}>
          {save.isPending ? "Saving…" : editing ? "Save structure" : "Price this class"}
        </Button>
      </form>
    </Sheet>
  );
}
