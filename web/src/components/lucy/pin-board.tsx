"use client";

// The Lucy landing board: every widget the member pinned, snapshot-first with
// a per-widget refresh (re-executes the widget's source tool server-side).

import { useQuery } from "@tanstack/react-query";
import { Pin } from "lucide-react";

import { WidgetFrame } from "@/components/lucy/widget-frame";
import { lucyApi } from "@/lib/lucy-api";

export function PinBoard() {
  const { data: pins, isLoading } = useQuery({
    queryKey: ["lucy", "pins"],
    queryFn: lucyApi.pins,
  });

  if (isLoading) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {[0, 1].map((i) => (
          <div key={i} className="h-40 animate-pulse rounded-xl bg-muted" />
        ))}
      </div>
    );
  }
  if (!pins?.length) {
    return (
      <div className="rounded-xl border border-dashed border-border px-4 py-8 text-center">
        <Pin className="mx-auto mb-2 h-5 w-5 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          Nothing pinned yet. Ask Lucy something, then pin the widgets you want
          to keep on this page.
        </p>
      </div>
    );
  }
  return (
    <div className="columns-1 gap-3 space-y-3 md:columns-2">
      {pins.map((w) => (
        <div key={w.id} className="break-inside-avoid">
          <WidgetFrame id={w.id} type={w.type} title={w.title} data={w.data}
            sourceTool={w.source_tool} pinned={w.pinned}
            refreshedAt={w.refreshed_at} showRefresh />
        </div>
      ))}
    </div>
  );
}
