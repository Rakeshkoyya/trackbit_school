"use client";

// GA §5 — the in-chat card for a saved composed view. The view's widgets are
// already on the canvas/flow; this card is the durable handle: open the saved
// page (refreshable, printable) any time later.

import { LayoutDashboard } from "lucide-react";
import Link from "next/link";

export function ViewCard({ viewId, title, summary }: {
  viewId: string;
  title?: string;
  summary?: string | null;
}) {
  return (
    <Link href={`/lucy/views/${viewId}`}
      className="flex items-center gap-3 rounded-xl border border-primary/30 bg-accent/40 p-3 transition-colors hover:border-primary">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10">
        <LayoutDashboard className="h-4.5 w-4.5 text-primary" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold">
          {title ?? "Saved view"}
        </span>
        <span className="block truncate text-xs text-muted-foreground">
          {summary ?? "Open the saved view — refresh or print it any time"}
        </span>
      </span>
    </Link>
  );
}
