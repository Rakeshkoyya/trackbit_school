"use client";

// A saved composed view (GA §5): titled sections of narrative + widgets, built
// once in chat and reopenable here. Refresh re-executes every widget's source
// tool with the viewer's live role; Print gives the parent-meeting handout.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Printer, RefreshCw, Trash2 } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use } from "react";

import { WidgetBody } from "@/components/lucy/widget-renderer";
import { showApiError } from "@/lib/errors";
import { lucyApi } from "@/lib/lucy-api";
import type { LucyViewWidget } from "@/lib/lucy-types";

export default function LucyViewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const router = useRouter();

  const { data: view, isLoading } = useQuery({
    queryKey: ["lucy", "view", id],
    queryFn: () => lucyApi.view(id),
  });

  const refresh = useMutation({
    mutationFn: () => lucyApi.refreshView(id),
    onSuccess: (v) => qc.setQueryData(["lucy", "view", id], v),
    onError: (e) => showApiError(e, "Could not refresh the view."),
  });

  const remove = useMutation({
    mutationFn: () => lucyApi.deleteView(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lucy", "views"] });
      router.push("/lucy");
    },
    onError: (e) => showApiError(e, "Could not delete the view."),
  });

  if (isLoading || !view) {
    return (
      <div className="mx-auto max-w-3xl space-y-3 p-4">
        <div className="h-8 w-2/3 animate-pulse rounded-lg bg-muted" />
        <div className="h-40 animate-pulse rounded-xl bg-muted" />
      </div>
    );
  }

  const byId = new Map<string, LucyViewWidget>(view.widgets.map((w) => [w.id, w]));

  return (
    <div className="mx-auto max-w-3xl p-4 pb-24">
      <div className="mb-4 flex items-start gap-2 print:hidden">
        <Link href="/lucy" title="Back to Lucy home"
          className="mt-0.5 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <div className="min-w-0 flex-1">
          <h1 className="text-lg font-semibold">{view.title}</h1>
          {view.summary ? (
            <p className="text-sm text-muted-foreground">{view.summary}</p>
          ) : null}
          <p className="mt-0.5 text-xs text-muted-foreground">
            {view.refreshed_at
              ? `data as of ${new Date(view.refreshed_at).toLocaleString()}`
              : `composed ${new Date(view.created_at).toLocaleString()}`}
          </p>
        </div>
        <div className="flex shrink-0 gap-1">
          <button type="button" title="Refresh all data"
            onClick={() => refresh.mutate()}
            className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground">
            <RefreshCw className={`h-4 w-4 ${refresh.isPending ? "animate-spin" : ""}`} />
          </button>
          <button type="button" title="Print" onClick={() => window.print()}
            className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-foreground">
            <Printer className="h-4 w-4" />
          </button>
          <button type="button" title="Delete view"
            onClick={() => { if (window.confirm("Delete this view?")) remove.mutate(); }}
            className="rounded-md p-2 text-muted-foreground hover:bg-muted hover:text-danger">
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Print header (screen header is hidden in print). */}
      <div className="mb-4 hidden print:block">
        <h1 className="text-lg font-semibold">{view.title}</h1>
        {view.summary ? <p className="text-sm">{view.summary}</p> : null}
      </div>

      <div className="space-y-6">
        {view.sections.map((s, i) => (
          <section key={i} className="break-inside-avoid">
            <h2 className="mb-1 text-sm font-semibold">{s.heading}</h2>
            {s.narrative ? (
              <p className="mb-2 text-sm text-muted-foreground">{s.narrative}</p>
            ) : null}
            <div className="space-y-3">
              {s.widget_ids.map((wid) => {
                const w = byId.get(wid);
                if (!w) return null;
                return (
                  <div key={wid}
                    className="rounded-xl border border-border bg-card p-3 shadow-sm">
                    {w.title ? (
                      <p className="mb-2 text-sm font-semibold">{w.title}</p>
                    ) : null}
                    <WidgetBody type={w.type} data={w.data} />
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
