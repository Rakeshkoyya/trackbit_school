"use client";

import { useRouter } from "next/navigation";
import { Globe, Lock } from "lucide-react";

import type { BoardListItem } from "@/lib/types";

export function BoardCard({ board }: { board: BoardListItem }) {
  const router = useRouter();
  const has = board.total > 0;
  const pct = has ? Math.round((board.done / board.total) * 100) : 0;
  return (
    <button
      onClick={() => router.push(`/boards/${board.id}`)}
      className="group flex h-full flex-col rounded-xl border border-border bg-card p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-sm"
    >
      <div className="flex items-start justify-between gap-2">
        <span className="flex items-center gap-2 font-semibold">
          {board.visibility === "public" ? (
            <Globe className="h-4 w-4 shrink-0 text-muted-foreground" />
          ) : (
            <Lock className="h-4 w-4 shrink-0 text-warning" />
          )}
          <span className="line-clamp-2">{board.name}</span>
        </span>
        {board.is_owner ? (
          <span className="shrink-0 rounded-full bg-accent px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-accent-foreground">
            Owner
          </span>
        ) : null}
      </div>

      <div className="mt-auto pt-5">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-success transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          {has ? `${board.done}/${board.total} tasks done` : "No tasks yet"}
        </p>
      </div>
    </button>
  );
}
