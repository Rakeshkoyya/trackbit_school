"use client";

/**
 * Document import (V2-P7): drop a file, review what we understood, answer the gaps,
 * commit.
 *
 * The gap questions come from the server, where **deterministic validators** decide
 * what is missing and the model only phrases it. So this panel behaves identically
 * with or without an API key — which is also why it never blocks on AI: if parsing
 * yields nothing useful, `onManual` drops the admin into the hand-entry screen
 * rather than stranding them.
 */

import { AlertTriangle, FileUp, Loader2 } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AnalyzeResult } from "@/lib/school-types";

export function Dropzone({
  onFile,
  busy,
  hint,
}: {
  onFile: (f: File) => void;
  busy?: boolean;
  hint: string;
}) {
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const f = e.dataTransfer.files?.[0];
        if (f) onFile(f);
      }}
      className={cn(
        "rounded-2xl border-2 border-dashed p-6 text-center transition-colors",
        over ? "border-primary bg-accent" : "border-border bg-card",
      )}
    >
      <input
        ref={input}
        type="file"
        accept=".xlsx,.xls,.csv"
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
      {busy ? (
        <Loader2 className="mx-auto h-6 w-6 animate-spin text-muted-foreground" />
      ) : (
        <FileUp className="mx-auto h-6 w-6 text-muted-foreground" />
      )}
      <p className="mt-2 text-sm font-medium">Drop your file here</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="mt-3"
        disabled={busy}
        onClick={() => input.current?.click()}
      >
        Choose a file
      </Button>
    </div>
  );
}

/** The gaps a validator found. Answering one = picking which column holds it. */
export function GapQuestions({
  analysis,
  onAnswer,
}: {
  analysis: AnalyzeResult;
  onAnswer: (field: string, column: string | null) => void;
}) {
  if (!analysis.questions.length) return null;
  return (
    <div className="space-y-3 rounded-xl border border-border bg-warning-soft/50 p-3">
      <div className="flex items-center gap-2 text-sm font-medium text-warning">
        <AlertTriangle className="h-4 w-4" />
        We couldn&apos;t work out {analysis.questions.length === 1 ? "one thing" : "a few things"}
      </div>
      {analysis.questions.map((q) => (
        <div key={q.field} className="space-y-1.5">
          <p className="text-sm">{q.question}</p>
          <div className="flex flex-wrap gap-1.5">
            {q.options.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => onAnswer(q.field, opt)}
                className="rounded-full border border-border bg-card px-2.5 py-1 text-xs hover:bg-muted"
              >
                {opt}
              </button>
            ))}
            {q.skippable ? (
              <button
                type="button"
                onClick={() => onAnswer(q.field, null)}
                className="rounded-full px-2.5 py-1 text-xs text-muted-foreground underline underline-offset-2"
              >
                Skip this
              </button>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}

/** What we understood, before anything is written. */
export function MappingPreview({
  analysis,
  labels,
}: {
  analysis: AnalyzeResult;
  labels: Record<string, string>;
}) {
  const entries = Object.entries(analysis.mapping);
  if (!entries.length) return null;
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="border-b border-border px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {analysis.row_count} rows understood
      </div>
      <ul className="divide-y divide-border text-sm">
        {entries.map(([field, column]) => (
          <li key={field} className="flex items-center justify-between gap-3 px-3 py-2">
            <span className="text-muted-foreground">{labels[field] ?? field}</span>
            <span className="truncate font-medium">{column}</span>
          </li>
        ))}
      </ul>
      {analysis.low_confidence.length ? (
        <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
          Not sure about {analysis.low_confidence.map((f) => labels[f] ?? f).join(", ")} — worth a
          glance.
        </p>
      ) : null}
    </div>
  );
}
