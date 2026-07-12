"use client";

/**
 * Bands landing (SC-5) — pick a class, see its A/B/C categorization as three
 * columns, configure the percentage thresholds, and (admin) record a band test
 * that re-categorizes the class. Bands stay staff-only (P4).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardPen, Settings2, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BandBoard, TIER_TONE, useClassPick } from "@/components/school/assessments";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { BandRow } from "@/lib/school-types";

function ConfigSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const { data: cfg } = useQuery({ queryKey: ["band-config"], queryFn: schoolApi.bandConfig, enabled: open });
  const [aMin, setAMin] = useState("");
  const [bMin, setBMin] = useState("");
  const effA = aMin || String(cfg?.a_min ?? 75);
  const effB = bMin || String(cfg?.b_min ?? 50);
  const save = useMutation({
    mutationFn: () => schoolApi.setBandConfig({ a_min: Number(effA), b_min: Number(effB) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["band-config"] });
      qc.invalidateQueries({ queryKey: ["bands"] });
      toast.success("Thresholds saved");
      onOpenChange(false);
    },
    onError: (e) => showApiError(e, "Could not save"),
  });
  const valid = Number(effB) > 0 && Number(effB) < Number(effA) && Number(effA) <= 100;
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Band thresholds">
      <div className="space-y-3">
        <p className="text-xs text-muted-foreground">
          After a band test, a student&apos;s percentage decides the tier:
          ≥ A-threshold → Band A, ≥ B-threshold → Band B, below it → Band C.
        </p>
        <div>
          <Label>Band A from (%)</Label>
          <Input type="number" min={2} max={100} value={effA} onChange={(e) => setAMin(e.target.value)} />
        </div>
        <div>
          <Label>Band B from (%)</Label>
          <Input type="number" min={1} max={99} value={effB} onChange={(e) => setBMin(e.target.value)} />
        </div>
        {!valid ? <p className="text-xs text-muted-foreground">The B threshold must be below the A threshold.</p> : null}
        <Button className="w-full" disabled={save.isPending || !valid} onClick={() => save.mutate()}>
          Save thresholds
        </Button>
      </div>
    </Sheet>
  );
}

/** The three-column categorization table. */
function TierColumns({ rows }: { rows: BandRow[] }) {
  const byTier: Record<string, BandRow[]> = { A: [], B: [], C: [] };
  const unbanded: BandRow[] = [];
  for (const r of rows) {
    if (r.current_tier && byTier[r.current_tier]) byTier[r.current_tier].push(r);
    else unbanded.push(r);
  }
  return (
    <div>
      <div className="grid grid-cols-3 gap-3">
        {(["A", "B", "C"] as const).map((t) => (
          <div key={t} className="rounded-xl border border-border bg-card">
            <div className="flex items-center justify-between border-b border-border px-3 py-2">
              <Badge tone={TIER_TONE[t]}>Band {t}</Badge>
              <span className="text-xs text-muted-foreground">{byTier[t].length}</span>
            </div>
            <div className="space-y-1 p-2">
              {byTier[t].map((r) => (
                <div key={r.student_id} className="rounded-md px-2 py-1.5 text-sm hover:bg-muted/40">
                  <p className="truncate font-medium">{r.full_name}</p>
                  {r.latest_pct != null ? (
                    <p className="text-[11px] text-muted-foreground">latest {r.latest_pct}%</p>
                  ) : null}
                </div>
              ))}
              {byTier[t].length === 0 ? (
                <p className="px-2 py-3 text-center text-xs text-muted-foreground">nobody</p>
              ) : null}
            </div>
          </div>
        ))}
      </div>
      {unbanded.length > 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Not categorized yet: {unbanded.map((r) => r.full_name).join(", ")}
        </p>
      ) : null}
    </div>
  );
}

function BandsInner() {
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";
  const { yearId } = useYear();
  const { classes, classId, setClassId } = useClassPick(yearId);
  const [config, setConfig] = useState(false);
  const [manage, setManage] = useState(false);
  const { data: terms = [] } = useQuery({ queryKey: ["terms", yearId], queryFn: () => schoolApi.terms(yearId ?? undefined), enabled: !!yearId });
  const { data: cfg } = useQuery({ queryKey: ["band-config"], queryFn: schoolApi.bandConfig });
  const { data: board } = useQuery({
    queryKey: ["bands", classId, terms[0]?.id ?? null],
    queryFn: () => schoolApi.bandBoard(classId, terms[0]?.id ?? undefined),
    enabled: !!classId,
  });
  const termId = terms[0]?.id ?? null;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <PageHeader title="Bands" subtitle="Private support tiers — never shared with parents" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          {isAdmin ? (
            <Button size="sm" variant="outline" onClick={() => setConfig(true)}>
              <SlidersHorizontal className="h-4 w-4" />
              A ≥ {cfg?.a_min ?? 75}% · B ≥ {cfg?.b_min ?? 50}%
            </Button>
          ) : null}
        </div>
      </div>

      {/* 1 · pick a class */}
      <div className="mb-4 flex flex-wrap gap-2">
        {classes.map((c) => (
          <button key={c.id} type="button" onClick={() => setClassId(c.id)}
            className={`rounded-lg border px-4 py-2.5 text-sm font-semibold transition-colors ${c.id === classId ? "border-primary bg-primary/10 text-primary" : "border-border bg-card hover:bg-muted/40"}`}>
            Class {c.name}{c.section ? `-${c.section}` : ""}
          </button>
        ))}
      </div>

      {classId ? (
        <div className="space-y-4">
          {isAdmin ? (
            <Link href={`/students/bands/${classId}`}
              className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted/40 active:scale-[0.995]">
              <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
                <ClipboardPen className="h-5 w-5" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-semibold">Record a band test</span>
                <span className="block text-xs text-muted-foreground">
                  Enter the special test&apos;s results — the class is re-categorized into A/B/C by the thresholds.
                </span>
              </span>
            </Link>
          ) : null}

          {/* 2 · the categorization */}
          {board ? <TierColumns rows={board.rows} /> : null}

          {/* 3 · manage individually (manual overrides, interventions) */}
          <div>
            <button type="button" className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
              onClick={() => setManage((v) => !v)}>
              <Settings2 className="h-3.5 w-3.5" /> {manage ? "Hide" : "Manage students individually"}
            </button>
            {manage ? <BandBoard classId={classId} termId={termId} canEdit={isAdmin} /> : null}
          </div>
        </div>
      ) : null}

      <ConfigSheet open={config} onOpenChange={setConfig} />
    </div>
  );
}

export default function BandsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <BandsInner />
    </AuthGuard>
  );
}
