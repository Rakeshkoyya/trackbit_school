"use client";

// The human-confirm surface for Lucy's write proposals (pending actions).
// The agent only PROPOSES a write; nothing runs until Confirm is tapped here.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ShieldQuestion, XCircle } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { showApiError } from "@/lib/errors";
import { lucyApi } from "@/lib/lucy-api";

export function ConfirmCard({
  id, tool, summary, paramsPreview, status: initialStatus, error: initialError,
}: {
  id: string;
  tool: string;
  summary: string;
  paramsPreview: { label: string; value: string }[];
  status: string;
  error?: string | null;
}) {
  const qc = useQueryClient();
  const [status, setStatus] = useState(initialStatus);
  const [error, setError] = useState(initialError ?? null);

  const settle = (next: { status: string; error: string | null }) => {
    setStatus(next.status);
    setError(next.error);
    qc.invalidateQueries({ queryKey: ["lucy", "conversation"] });
  };

  const confirm = useMutation({
    mutationFn: () => lucyApi.confirmAction(id),
    onSuccess: (a) => settle(a),
    onError: (e) => showApiError(e, "Could not run the action."),
  });
  const cancel = useMutation({
    mutationFn: () => lucyApi.cancelAction(id),
    onSuccess: (a) => settle(a),
    onError: (e) => showApiError(e, "Could not cancel the action."),
  });

  const pending = status === "proposed";

  return (
    <div className={`rounded-xl border p-3 ${
      pending ? "border-warning/50 bg-warning-soft/40" : "border-border bg-card"}`}>
      <div className="flex items-start gap-2">
        {status === "executed"
          ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
          : status === "failed"
            ? <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
            : <ShieldQuestion className="mt-0.5 h-4 w-4 shrink-0 text-warning" />}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{summary}</p>
          <p className="text-xs text-muted-foreground">
            action: {tool.replace(/_/g, " ")}
          </p>
          {paramsPreview.length ? (
            <dl className="mt-1.5 space-y-0.5">
              {paramsPreview.map((p) => (
                <div key={p.label} className="flex gap-2 text-xs">
                  <dt className="shrink-0 text-muted-foreground">{p.label}:</dt>
                  <dd className="min-w-0 truncate font-medium">{p.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {error ? <p className="mt-1 text-xs text-danger">{error}</p> : null}
        </div>
        {!pending ? <Badge tone={status === "executed" ? "success" : "neutral"}>{status}</Badge> : null}
      </div>
      {pending ? (
        <div className="mt-2 flex gap-2">
          <Button size="sm" onClick={() => confirm.mutate()}
            disabled={confirm.isPending || cancel.isPending}>
            {confirm.isPending ? "Running…" : "Confirm"}
          </Button>
          <Button size="sm" variant="outline" onClick={() => cancel.mutate()}
            disabled={confirm.isPending || cancel.isPending}>
            Cancel
          </Button>
        </div>
      ) : null}
    </div>
  );
}
