"use client";

// The card around every Lucy widget: title, pin toggle, source caption, and a
// framer-motion entrance (respecting prefers-reduced-motion). Pinning is an
// optimistic toggle — the pin board and conversation caches update on settle.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { Pin, RefreshCw } from "lucide-react";
import { useState } from "react";

import { WidgetBody } from "@/components/lucy/widget-renderer";
import { showApiError } from "@/lib/errors";
import { lucyApi } from "@/lib/lucy-api";
import type { WidgetType } from "@/lib/lucy-types";

export function WidgetFrame({
  id, type, title, data, sourceTool, pinned, refreshedAt, persisted = true, showRefresh = false,
}: {
  id: string;
  type: WidgetType;
  title: string;
  data: unknown;
  sourceTool?: string | null;
  pinned?: boolean;
  refreshedAt?: string | null;
  /** Streaming widgets aren't persisted yet — the pin toggle appears on settle. */
  persisted?: boolean;
  showRefresh?: boolean;
}) {
  const reduce = useReducedMotion();
  const qc = useQueryClient();
  const [isPinned, setIsPinned] = useState(!!pinned);
  const [freshData, setFreshData] = useState<unknown>(null);
  const [freshStamp, setFreshStamp] = useState<string | null>(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["lucy", "pins"] });
    qc.invalidateQueries({ queryKey: ["lucy", "conversation"] });
  };

  const pinMutation = useMutation({
    mutationFn: (next: boolean) => (next ? lucyApi.pin(id) : lucyApi.unpin(id)),
    onMutate: (next) => setIsPinned(next),
    onError: (e, next) => {
      setIsPinned(!next);
      showApiError(e, "Could not update the pin.");
    },
    onSettled: invalidate,
  });

  const refreshMutation = useMutation({
    mutationFn: () => lucyApi.refreshWidget(id),
    onSuccess: (w) => {
      setFreshData(w.data);
      setFreshStamp(w.refreshed_at);
      qc.invalidateQueries({ queryKey: ["lucy", "pins"] });
    },
    onError: (e) => showApiError(e, "Could not refresh the widget."),
  });

  const stamp = freshStamp ?? refreshedAt;

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="rounded-xl border border-border bg-card p-3 shadow-sm">
      <div className="mb-2 flex items-center gap-2">
        <p className="min-w-0 flex-1 truncate text-sm font-semibold">{title}</p>
        {showRefresh && sourceTool ? (
          <button type="button" title="Refresh data"
            onClick={() => refreshMutation.mutate()}
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
            <RefreshCw className={`h-3.5 w-3.5 ${refreshMutation.isPending ? "animate-spin" : ""}`} />
          </button>
        ) : null}
        {persisted ? (
          <button type="button" title={isPinned ? "Unpin from Lucy home" : "Pin to Lucy home"}
            onClick={() => pinMutation.mutate(!isPinned)}
            className={`rounded-md p-1 hover:bg-muted ${
              isPinned ? "text-primary" : "text-muted-foreground hover:text-foreground"}`}>
            {isPinned ? <Pin className="h-3.5 w-3.5 fill-current" /> : <Pin className="h-3.5 w-3.5" />}
          </button>
        ) : null}
      </div>
      <WidgetBody type={type} data={freshData ?? data} />
      {sourceTool || stamp ? (
        <p className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
          {sourceTool ? <span>from {sourceTool.replace(/^get_/, "").replace(/_/g, " ")}</span> : null}
          {stamp ? <span>· as of {new Date(stamp).toLocaleString()}</span> : null}
        </p>
      ) : null}
    </motion.div>
  );
}
