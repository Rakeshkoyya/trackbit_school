"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowLeft, BarChart3, Check, ChevronDown, Globe, ListTodo, Lock, Plus, Settings2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { useCelebration } from "@/components/celebration/celebration-provider";
import { BoardKanban } from "@/components/boards/board-kanban";
import { BoardMobile } from "@/components/boards/board-mobile";
import { BoardSettingsSheet } from "@/components/boards/board-settings-sheet";
import { TaskTable, type GroupBy } from "@/components/boards/board-table";
import { CreateTaskSheet } from "@/components/tasks/create-task-sheet";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";
import { patchRowEverywhere, restoreRowCaches, snapshotRowCaches } from "@/lib/optimistic";
import type { BoardRow } from "@/lib/types";
import { cn } from "@/lib/utils";

type Scope = "all" | "mine";

function instanceFor(row: BoardRow): string | null {
  return row.kind === "recurring" ? row.today_instance_id : row.id;
}

export function BoardView({ boardId }: { boardId: string }) {
  const qc = useQueryClient();
  const router = useRouter();
  const { me } = useAuth();
  const { onCompletion } = useCelebration();
  const [createOpen, setCreateOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [view] = useState<"table" | "board">("table"); // Kanban hidden for now
  const [groupBy, setGroupBy] = useState<GroupBy>("category");
  const [scope, setScope] = useState<Scope>("all");

  const board = useQuery({ queryKey: ["board", boardId], queryFn: () => appApi.board(boardId) });
  const table = useQuery({
    queryKey: ["board-table", boardId],
    queryFn: () => appApi.boardTable(boardId),
  });
  const members = useQuery({ queryKey: ["members"], queryFn: appApi.members });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["board-table", boardId] });
    qc.invalidateQueries({ queryKey: ["boards"] });
    qc.invalidateQueries({ queryKey: ["home"] });
  };

  const complete = useMutation({
    mutationFn: (row: BoardRow) => {
      const id = instanceFor(row);
      if (!id) return Promise.reject(new Error("Not actionable today"));
      return appApi.completeTask(id);
    },
    onMutate: (row) => {
      const snap = snapshotRowCaches(qc);
      patchRowEverywhere(qc, row.id, { status: "done" });
      return { snap };
    },
    onSuccess: () => onCompletion(),
    onError: (e, _r, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      toast.error(e instanceof ApiError ? e.message : "Could not complete");
    },
    onSettled: () => invalidate(),
  });
  const claim = useMutation({
    mutationFn: (row: BoardRow) => {
      const id = instanceFor(row);
      if (!id) return Promise.reject(new Error("Not actionable today"));
      return appApi.claimTask(id);
    },
    onMutate: (row) => {
      const snap = snapshotRowCaches(qc);
      patchRowEverywhere(qc, row.id, { assignee: me ? { id: me.user.id, name: me.user.name } : null });
      return { snap };
    },
    onSuccess: () => toast.success("Claimed — it's yours"),
    onError: (e, _r, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      toast.error(e instanceof ApiError ? e.message : "Already taken");
    },
    onSettled: () => invalidate(),
  });
  const reopen = useMutation({
    mutationFn: (row: BoardRow) => {
      const id = instanceFor(row);
      if (!id) return Promise.reject(new Error("Not actionable today"));
      return appApi.reopenTask(id);
    },
    onMutate: (row) => {
      const snap = snapshotRowCaches(qc);
      patchRowEverywhere(qc, row.id, { status: "open" });
      return { snap };
    },
    onError: (e, _r, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      toast.error(e instanceof ApiError ? e.message : "Could not reopen");
    },
    onSettled: () => invalidate(),
  });

  function openRow(row: BoardRow) {
    router.push(row.kind === "recurring" ? `/recurring/${row.id}` : `/task/${row.id}`);
  }

  if (board.isLoading) return <div className="h-40 animate-pulse rounded-lg bg-muted" />;
  if (board.isError || !board.data) {
    return (
      <EmptyState
        title="Board not found"
        body="It may be private, archived, or removed."
        action={<Button onClick={() => router.push("/boards")}>Back to boards</Button>}
      />
    );
  }

  const b = board.data;
  // Privacy board + not owner/admin: backend already returns only the member's
  // own tasks and 404s the report, so drop the now-meaningless controls.
  const restricted = b.task_scope === "assigned" && !b.can_manage;
  const allRows = table.data?.rows ?? [];
  const myId = me?.user.id;
  const rows =
    scope === "mine"
      ? allRows.filter((r) => !r.assignee || r.assignee.id === myId)
      : allRows;
  const memberList = members.data?.members ?? [];

  return (
    <div>
      <header className="mb-5">
        <button
          onClick={() => router.push("/boards")}
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Boards
        </button>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {b.visibility === "public" ? (
              <Globe className="h-5 w-5 text-muted-foreground" />
            ) : (
              <Lock className="h-5 w-5 text-warning" />
            )}
            <h1 className="text-2xl font-semibold tracking-tight">{b.name}</h1>
          </div>
          <div className="flex items-center gap-2">
            {!restricted ? (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => router.push(`/boards/${boardId}/report`)}
                aria-label="Board report"
              >
                <BarChart3 className="h-5 w-5" />
              </Button>
            ) : null}
            {b.can_manage ? (
              <Button variant="ghost" size="icon" onClick={() => setSettingsOpen(true)} aria-label="Board settings">
                <Settings2 className="h-5 w-5" />
              </Button>
            ) : null}
            <Button size="sm" data-tour="new-task" onClick={() => setCreateOpen(true)}>
              <Plus className="h-4 w-4" /> Task
            </Button>
          </div>
        </div>
        {b.visibility === "private" ? (
          <p className="mt-1 text-xs text-muted-foreground">{b.member_count} members</p>
        ) : null}
      </header>

      {table.isLoading ? (
        <div className="space-y-2">
          {[0, 1].map((i) => (
            <div key={i} className="h-16 animate-pulse rounded-lg bg-muted" />
          ))}
        </div>
      ) : table.isError ? (
        <EmptyState
          title="Couldn't load tasks"
          body="The board's tasks failed to load. If you just updated the app, make sure the backend is restarted."
          action={<Button onClick={() => table.refetch()}>Retry</Button>}
        />
      ) : (
        <>
          {/* ── Desktop: Monday-style table / Kanban ── */}
          <div className="hidden lg:block">
            <div className="mb-3 flex items-center gap-2">
              {!restricted ? (
                <Dropdown
                  label="Show"
                  value={scope}
                  options={[["all", "Everyone"], ["mine", "Mine + unclaimed"]]}
                  onChange={(v) => setScope(v as Scope)}
                />
              ) : null}
              <Dropdown
                label="Group by"
                value={groupBy}
                options={[
                  ["category", "Category"],
                  ["none", "None"],
                  ["status", "Status"],
                  ["assignee", "Owner"],
                  ["priority", "Priority"],
                ]}
                onChange={(v) => setGroupBy(v as GroupBy)}
              />
            </div>

            {view === "table" ? (
              <TaskTable
                rows={rows}
                members={memberList}
                groupBy={groupBy}
                columns={["person", "due", "priority"]}
                groupDefs={table.data?.groups}
                canAssignPerson={!restricted}
                addContext={{ boardId }}
                onComplete={(r) => complete.mutate(r)}
                onReopen={(r) => reopen.mutate(r)}
                onOpen={openRow}
              />
            ) : rows.length === 0 ? (
              <EmptyState icon={ListTodo} title="No tasks yet" body="Switch to Table view to add your first task." />
            ) : (
              <BoardKanban
                rows={rows}
                onComplete={(r) => complete.mutate(r)}
                onClaim={(r) => claim.mutate(r)}
                onOpen={openRow}
              />
            )}
          </div>

          {/* ── Mobile: simple checkable list ── */}
          <div className="lg:hidden">
            {rows.length === 0 ? (
              <EmptyState
                icon={ListTodo}
                title="No tasks yet"
                body="Add the first task to this board."
                action={
                  <Button onClick={() => setCreateOpen(true)}>
                    <Plus className="h-4 w-4" /> Add a task
                  </Button>
                }
              />
            ) : (
              <BoardMobile
                rows={rows}
                onComplete={(r) => complete.mutate(r)}
                onClaim={(r) => claim.mutate(r)}
                onOpen={openRow}
              />
            )}
            {/* Floating add (mobile) */}
            <button
              onClick={() => setCreateOpen(true)}
              className="fixed bottom-20 right-5 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105"
              aria-label="New task"
            >
              <Plus className="h-6 w-6" />
            </button>
          </div>
        </>
      )}

      <CreateTaskSheet open={createOpen} onOpenChange={setCreateOpen} defaultBoardId={boardId} />
      {b.can_manage ? (
        <BoardSettingsSheet board={b} open={settingsOpen} onOpenChange={setSettingsOpen} />
      ) : null}
    </div>
  );
}

function Dropdown({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const current = options.find(([v]) => v === value)?.[1] ?? value;
  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-sm hover:bg-muted"
      >
        <span className="text-muted-foreground">{label}:</span>
        <span className="font-medium">{current}</span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full z-50 mt-1 min-w-[11rem] rounded-lg border border-border bg-card p-1 shadow-lg">
            {options.map(([v, lbl]) => (
              <button
                key={v}
                onClick={() => { onChange(v); setOpen(false); }}
                className={cn(
                  "flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-sm hover:bg-muted",
                  v === value && "font-medium",
                )}
              >
                {lbl} {v === value ? <Check className="h-3.5 w-3.5 text-primary" /> : null}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
