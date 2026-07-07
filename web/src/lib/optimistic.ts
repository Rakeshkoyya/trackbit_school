import type { QueryClient } from "@tanstack/react-query";

import type { BoardRow } from "@/lib/types";

/** Any cached query whose data is a list of task rows (board-table, my-tasks). */
type RowCache = { rows: BoardRow[] };

/** Patch a single row in every cached task list, in place, for instant UI. */
export function patchRowEverywhere(qc: QueryClient, rowId: string, patch: Partial<BoardRow>) {
  const update = (old: RowCache | undefined) =>
    old ? { ...old, rows: old.rows.map((r) => (r.id === rowId ? { ...r, ...patch } : r)) } : old;
  qc.setQueriesData<RowCache>({ queryKey: ["board-table"] }, update);
  qc.setQueriesData<RowCache>({ queryKey: ["my-tasks"] }, update);
}

/** Append a row to a specific board's cached table (optimistic add). */
export function appendRow(qc: QueryClient, boardId: string, row: BoardRow) {
  qc.setQueryData<RowCache>(["board-table", boardId], (old) =>
    old ? { ...old, rows: [...old.rows, row] } : old,
  );
}

export function snapshotRowCaches(qc: QueryClient) {
  return [
    ...qc.getQueriesData<RowCache>({ queryKey: ["board-table"] }),
    ...qc.getQueriesData<RowCache>({ queryKey: ["my-tasks"] }),
  ];
}

export function restoreRowCaches(qc: QueryClient, snap?: ReturnType<typeof snapshotRowCaches>) {
  if (!snap) return;
  for (const [key, data] of snap) qc.setQueryData(key, data);
}
