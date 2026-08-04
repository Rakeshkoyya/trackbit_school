"use client";

/**
 * **Import a year** — next year's dates from a spreadsheet (V1-20).
 *
 * `D-60` chose *fetch and store* over a file in the repo, and `S-151` named the
 * realistic shape: a small importer per source plus one annual human review.
 * This is that review. The operator collects 2028 however they like and drops
 * the file here.
 *
 * **Three rules the screen exists to enforce.**
 *
 *   1. **Nothing is written until the operator has seen every row.** Analyze
 *      and commit are separate calls; this component never posts a file.
 *   2. **Rows the parser could not read are SHOWN, not dropped.** An importer
 *      that silently discards eight rows of 150 reports "142 imported" and
 *      nobody ever finds the eight. For a calendar each one is a day a school
 *      stays open for, so blocked rows are listed first, in red, with the
 *      reason — and the count of them sits on the save button's own line.
 *   3. **The model maps columns; it never decides a date.** Where the keyword
 *      heuristic could not place a column the server asked a model, and those
 *      fields are flagged here for a glance (`ingest.py`). Asking a model when
 *      Diwali is would be `S-123`'s rejected row; asking it which column is
 *      the date column is a mapping problem a human confirms in one look.
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, FileSpreadsheet, Sparkles, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { showApiError } from "@/lib/errors";
import {
  eventsApi,
  type ObservanceImportPreview,
  type ObservanceImportRow,
} from "@/lib/events-api";
import { cn } from "@/lib/utils";

/** The columns the sheet may carry. Shown as guidance BEFORE a file is picked,
 *  because the cheapest fix for a bad import is a better file. */
const EXPECTED = [
  ["Name", "required — “Diwali”"],
  ["Date", "required — 17/10/2028, 17 Oct 2028, 2028-10-17"],
  ["End date", "only for a multi-day festival"],
  ["States", "blank or “All India”, else “Kerala; Lakshadweep”"],
  ["Kind", "holiday · festival · observance"],
  ["Tier", "major · minor"],
  ["Tradition", "Hindu, Muslim, Christian…"],
  ["Note", "anything the approver should know"],
  ["Source", "where the date came from"],
] as const;

/** The fields the confirmed preview is sent back under. Must match the server's
 *  `SPECS` names in `observance_import.py`. */
const FIELDS = [
  "name", "date", "end_date", "states", "kind", "tier",
  "tradition", "prep_days", "note", "source",
] as const;

function RowLine({ row }: { row: ObservanceImportRow }) {
  return (
    <div
      className={cn(
        "grid grid-cols-[6.5rem_minmax(0,1fr)] gap-3 border-b border-border/60 px-4 py-2 last:border-0",
        !row.importable && "bg-danger/[0.05]",
      )}
    >
      <span className="font-mono text-xs tabular-nums text-muted-foreground">
        {row.date ?? <span className="text-danger">no date</span>}
        {row.end_date ? <span className="block text-[10px]">→ {row.end_date}</span> : null}
      </span>
      <span className="min-w-0">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="truncate text-sm font-medium">{row.name}</span>
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
            {row.kind} · {row.tier}
          </span>
        </span>
        <span className="block truncate text-xs text-muted-foreground">
          {row.states?.length ? row.states.join(", ") : "All India"}
          {row.tradition ? ` · ${row.tradition}` : ""}
        </span>
        {row.problems.map((p, i) => (
          <span key={i} className="mt-0.5 flex items-start gap-1 text-xs text-danger">
            <AlertTriangle className="mt-px h-3 w-3 shrink-0" /> {p}
          </span>
        ))}
      </span>
    </div>
  );
}

export function ObservanceImportModal({
  open, onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("");
  const [yearHint, setYearHint] = useState("");
  const [preview, setPreview] = useState<ObservanceImportPreview | null>(null);

  const reset = () => {
    setFile(null); setPreview(null); setSource(""); setYearHint("");
    if (fileRef.current) fileRef.current.value = "";
  };

  const analyze = useMutation({
    mutationFn: (f: File) =>
      eventsApi.analyzeObservanceFile(f, source.trim(),
        yearHint ? Number(yearHint) : undefined),
    onSuccess: (data) => setPreview(data),
    onError: (e) => { showApiError(e, "Could not read that file"); setFile(null); },
  });

  const save = useMutation({
    mutationFn: () => eventsApi.commitObservanceFile({
      // What goes back is what the server PARSED and the operator then looked
      // at — already-canonical values under their own field names, hence the
      // identity mapping. Re-sending the raw sheet would let commit re-derive
      // and, on any parser change between the two calls, save something nobody
      // ever saw. The preview is the contract.
      mapping: Object.fromEntries(FIELDS.map((f) => [f, f])),
      rows: preview!.rows
        .filter((r) => r.importable)
        .map((r) => ({
          name: r.name, date: r.date, end_date: r.end_date, kind: r.kind,
          tier: r.tier, states: (r.states ?? []).join("|"), tradition: r.tradition,
          prep_days: r.prep_days, note: r.note, source: r.source,
        })),
      source: source.trim() || "Imported spreadsheet",
      year_hint: yearHint ? Number(yearHint) : null,
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["observances"] });
      toast.success(`${res.created} added, ${res.updated} updated`);
      if (res.duplicates.length) {
        toast.warning(`${res.duplicates.length} duplicate row(s) skipped`);
      }
      reset();
      onClose();
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  const pick = (f: File | undefined) => {
    if (!f) return;
    setFile(f);
    setPreview(null);
    analyze.mutate(f);
  };

  return (
    <Modal
      open={open}
      onOpenChange={(v) => { if (!v) { reset(); onClose(); } }}
      title="Import a year"
      description="An .xlsx of next year's dates. Nothing is saved until you have seen the rows."
      size="xl"
    >
      <div className="space-y-4 p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="imp-src">Where did these dates come from?</Label>
            <Input id="imp-src" value={source} placeholder="e.g. Kerala gazette 2028"
                   onChange={(e) => setSource(e.target.value)} />
            <p className="mt-1 text-xs text-muted-foreground">
              Shown to every admin who approves one of these dates. A row whose
              own Source column is filled keeps that instead.
            </p>
          </div>
          <div>
            <Label htmlFor="imp-year">Year (optional)</Label>
            <Input id="imp-year" value={yearHint} inputMode="numeric" placeholder="2028"
                   onChange={(e) => setYearHint(e.target.value.replace(/\D/g, "").slice(0, 4))} />
            <p className="mt-1 text-xs text-muted-foreground">
              Only needed if the sheet says “15 August” without a year.
            </p>
          </div>
        </div>

        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xlsm"
            className="sr-only"
            onChange={(e) => pick(e.target.files?.[0])}
          />
          <Button variant="outline" onClick={() => fileRef.current?.click()}
                  disabled={analyze.isPending}>
            <Upload className="h-4 w-4" />
            {analyze.isPending ? "Reading…" : file ? "Choose a different file" : "Choose a file"}
          </Button>
          {file ? (
            <span className="ml-2 inline-flex items-center gap-1.5 text-xs text-muted-foreground">
              <FileSpreadsheet className="h-3.5 w-3.5" /> {file.name}
            </span>
          ) : null}
        </div>

        {!preview ? (
          <div className="rounded-xl border border-dashed border-border p-4">
            <p className="text-xs font-medium">Columns we look for</p>
            <dl className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2">
              {EXPECTED.map(([name, hint]) => (
                <div key={name} className="flex gap-2 text-xs">
                  <dt className="w-20 shrink-0 font-mono text-muted-foreground">{name}</dt>
                  <dd className="min-w-0 text-muted-foreground">{hint}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-xs text-muted-foreground">
              Headers can be named anything close — we match them, and ask you about
              any we cannot place. Dates are read <strong>day first</strong>:
              03/04/2028 is 3 April.
            </p>
          </div>
        ) : null}

        {preview ? (
          <>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={preview.ready ? "primary" : "neutral"}>
                {preview.ready} ready
              </Badge>
              {preview.blocked ? (
                <Badge tone="danger">{preview.blocked} need fixing</Badge>
              ) : null}
              {preview.source === "ai" ? (
                <Badge tone="outline">
                  <Sparkles className="h-3 w-3" /> some columns matched by AI
                </Badge>
              ) : null}
            </div>

            <div className="rounded-lg border border-border">
              <p className="border-b border-border bg-muted/40 px-4 py-2 text-xs text-muted-foreground">
                Read as:{" "}
                {Object.entries(preview.mapping).map(([field, column], i) => (
                  <span key={field}>
                    {i ? " · " : ""}
                    <span className={cn(
                      "font-medium",
                      preview.low_confidence.includes(field) && "text-warning",
                    )}>{column}</span>
                    <span className="text-muted-foreground"> → {field}</span>
                  </span>
                ))}
                {preview.unmapped_columns.length ? (
                  <span className="block pt-1">
                    Ignored: {preview.unmapped_columns.join(", ")}
                  </span>
                ) : null}
              </p>
              <div className="max-h-[38dvh] overflow-y-auto">
                {/* Blocked rows first — they are the only ones that need a
                    decision, and burying them under 300 good rows is how they
                    get missed. */}
                {[...preview.rows].sort((a, b) =>
                  Number(a.importable) - Number(b.importable)).map((r) => (
                  <RowLine key={r.index} row={r} />
                ))}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
              {preview.blocked ? (
                <p className="mr-auto text-xs text-muted-foreground">
                  {preview.blocked} row(s) will not be imported. Fix them in the
                  sheet and choose the file again.
                </p>
              ) : null}
              <Button variant="ghost" onClick={() => { reset(); onClose(); }}>Cancel</Button>
              <Button onClick={() => save.mutate()}
                      disabled={!preview.ready || save.isPending}>
                {save.isPending ? "Saving…" : `Save ${preview.ready} date(s)`}
              </Button>
            </div>
          </>
        ) : null}
      </div>
    </Modal>
  );
}
