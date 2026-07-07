"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, Inbox, ListTodo, Lock, Plus, UserCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { BoardMobile } from "@/components/boards/board-mobile";
import { TaskTable, type ColumnKey, type GroupBy } from "@/components/boards/board-table";
import { useCelebration } from "@/components/celebration/celebration-provider";
import { MondayRecap } from "@/components/history/monday-recap";
import { CreateTaskSheet } from "@/components/tasks/create-task-sheet";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";
import { patchRowEverywhere, restoreRowCaches, snapshotRowCaches } from "@/lib/optimistic";
import { ritualLine } from "@/lib/ritual";
import type { BoardRow, History } from "@/lib/types";
import { cn } from "@/lib/utils";

/** "mine" = My tasks across boards; otherwise the active board id. */
type Tab = "mine" | string;

function instanceId(row: BoardRow): string | null {
  return row.kind === "recurring" ? row.today_instance_id : row.id;
}

export default function HomePage() {
  const qc = useQueryClient();
  const router = useRouter();
  const { me } = useAuth();
  const { onCompletion, showRitual } = useCelebration();
  const [tab, setTab] = useState<Tab>("mine");
  const [sheetOpen, setSheetOpen] = useState(false);

  const { data: home } = useQuery({ queryKey: ["home"], queryFn: appApi.today });
  const { data: hist } = useQuery({ queryKey: ["history"], queryFn: appApi.history });
  const { data: boards } = useQuery({ queryKey: ["boards"], queryFn: appApi.boards });
  const myTasks = useQuery({ queryKey: ["my-tasks"], queryFn: appApi.myTasks });
  const boardTable = useQuery({
    queryKey: ["board-table", tab],
    queryFn: () => appApi.boardTable(tab),
    enabled: tab !== "mine",
  });

  const myId = me?.user.id;

  function refreshTables() {
    qc.invalidateQueries({ queryKey: ["my-tasks"] });
    qc.invalidateQueries({ queryKey: ["board-table"] });
    qc.invalidateQueries({ queryKey: ["boards"] });
  }

  const complete = useMutation({
    mutationFn: (row: BoardRow) => {
      const id = instanceId(row);
      if (!id) return Promise.reject(new Error("Not actionable today"));
      return appApi.completeTask(id);
    },
    onMutate: (row) => {
      const snap = snapshotRowCaches(qc);
      patchRowEverywhere(qc, row.id, { status: "done" });
      return { snap };
    },
    onSuccess: (_res, row) => {
      const prevHist = qc.getQueryData<History>(["history"]);
      const firstEver = (prevHist?.total_completed ?? 0) === 0;
      onCompletion({ force: firstEver });
      // After the celebration, refetch today (progress + ritual) and the tables.
      window.setTimeout(async () => {
        const fresh = await appApi.today();
        qc.setQueryData(["home"], fresh);
        const freshHist = await appApi.history();
        qc.setQueryData(["history"], freshHist);
        refreshTables();
        const remaining = fresh.overdue.length + fresh.due_today.length + fresh.anytime.length;
        if (remaining === 0 && fresh.done_today > 0) {
          showRitual({ doneCount: fresh.done_today, line: ritualLine(fresh, freshHist, firstEver) });
        }
      }, 720);

      toast("Done ✓", {
        action: {
          label: "Undo",
          onClick: async () => {
            const id = instanceId(row);
            if (!id) return;
            try {
              await appApi.reopenTask(id);
              qc.invalidateQueries({ queryKey: ["home"] });
              refreshTables();
            } catch {
              toast.error("Could not undo");
            }
          },
        },
        duration: 5000,
      });
    },
    onError: (e, _row, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      refreshTables();
      toast.error(e instanceof ApiError ? e.message : "Could not complete");
    },
  });

  const reopen = useMutation({
    mutationFn: (row: BoardRow) => {
      const id = instanceId(row);
      if (!id) return Promise.reject(new Error("Not actionable today"));
      return appApi.reopenTask(id);
    },
    onMutate: (row) => {
      const snap = snapshotRowCaches(qc);
      patchRowEverywhere(qc, row.id, { status: "open" });
      return { snap };
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["home"] }),
    onError: (e, _row, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      toast.error(e instanceof ApiError ? e.message : "Could not reopen");
    },
    onSettled: () => refreshTables(),
  });

  const claim = useMutation({
    mutationFn: (row: BoardRow) => {
      const id = instanceId(row);
      if (!id) return Promise.reject(new Error("Not actionable today"));
      return appApi.claimTask(id);
    },
    onMutate: (row) => {
      const snap = snapshotRowCaches(qc);
      patchRowEverywhere(qc, row.id, { assignee: me ? { id: me.user.id, name: me.user.name } : null });
      return { snap };
    },
    onSuccess: () => toast.success("Claimed — it's yours"),
    onError: (e, _row, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      toast.error(e instanceof ApiError ? e.message : "Already taken");
    },
    onSettled: () => refreshTables(),
  });

  function openRow(row: BoardRow) {
    router.push(row.kind === "recurring" ? `/recurring/${row.id}` : `/task/${row.id}`);
  }

  const allBoards = boards ? [...boards.my_boards, ...boards.other_public] : [];

  // Rows + table config for the active tab.
  const onBoardTab = tab !== "mine";
  const rows: BoardRow[] = onBoardTab
    ? (boardTable.data?.rows ?? []).filter((r) => !r.assignee || r.assignee.id === myId)
    : (myTasks.data?.rows ?? []);
  // My tasks = one flat, ungrouped list across all boards, ordered by urgency so
  // the next thing to do is on top. Board tabs keep their category grouping.
  const groupBy: GroupBy = onBoardTab ? "category" : "none";
  const columns: ColumnKey[] = onBoardTab ? ["person", "due", "priority"] : ["due", "priority"];
  const loading = onBoardTab ? boardTable.isLoading : myTasks.isLoading;

  return (
    <div>
      {/* Tab bar: My tasks + each board */}
      <div className="mb-5 flex gap-1 overflow-x-auto border-b border-border" data-tour="home-tabs">
        <TabButton active={tab === "mine"} onClick={() => setTab("mine")} icon={UserCheck} label="My tasks" />
        {allBoards.map((b) => (
          <TabButton
            key={b.id}
            active={tab === b.id}
            onClick={() => setTab(b.id)}
            icon={b.visibility === "private" ? Lock : Globe}
            label={b.name}
          />
        ))}
      </div>

      {tab === "mine" ? <MondayRecap hist={hist} /> : null}

      {/* Slim day-progress header */}
      <header className="mb-4">
        <h1 className="text-xl font-semibold tracking-tight">
          {greeting()}
          {home?.greeting_name ? `, ${home.greeting_name}` : ""}
        </h1>
        {home && home.total_today > 0 ? (
          <>
            <p className="mt-1 text-sm text-muted-foreground">
              {home.done_today} of {home.total_today} done today
            </p>
            <div className="mt-2 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-success transition-all duration-500"
                style={{ width: `${Math.round((home.done_today / home.total_today) * 100)}%` }}
              />
            </div>
          </>
        ) : null}
      </header>

      {loading ? (
        <TableSkeleton />
      ) : rows.length === 0 ? (
        onBoardTab ? (
          <EmptyState
            icon={ListTodo}
            title="Nothing here for you"
            body="No tasks on this board are assigned to you or open to claim."
            action={
              <Button onClick={() => setSheetOpen(true)}>
                <Plus className="h-4 w-4" /> New task
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={Inbox}
            title="Your day is clear"
            body="Tasks assigned to you across all boards show up here."
            action={
              <Button onClick={() => setSheetOpen(true)}>
                <Plus className="h-4 w-4" /> New task
              </Button>
            }
          />
        )
      ) : (
        <>
          {/* ── Desktop: Monday-style table ── */}
          <div className="hidden lg:block">
            <TaskTable
              rows={rows}
              groupBy={groupBy}
              columns={columns}
              sortBy={onBoardTab ? "created" : "urgency"}
              showBoard={!onBoardTab}
              groupDefs={onBoardTab ? boardTable.data?.groups : undefined}
              addContext={onBoardTab ? { boardId: tab } : undefined}
              hideEmptyGroups
              onComplete={(r) => complete.mutate(r)}
              onReopen={(r) => reopen.mutate(r)}
              onOpen={openRow}
            />
          </div>

          {/* ── Mobile: simple checkable list (matches the board screen) ── */}
          <div className="lg:hidden">
            <BoardMobile
              rows={rows}
              onComplete={(r) => complete.mutate(r)}
              onClaim={(r) => claim.mutate(r)}
              onOpen={openRow}
            />
          </div>
        </>
      )}

      {/* Floating create button */}
      <button
        onClick={() => setSheetOpen(true)}
        data-tour="new-task"
        className="fixed bottom-20 right-5 z-30 flex h-14 w-14 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105 lg:bottom-8 lg:right-8"
        aria-label="New task"
      >
        <Plus className="h-6 w-6" />
      </button>

      <CreateTaskSheet
        open={sheetOpen}
        onOpenChange={setSheetOpen}
        defaultBoardId={tab !== "mine" ? tab : undefined}
      />
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon: Icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: typeof UserCheck;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
        active
          ? "border-primary text-foreground"
          : "border-transparent text-muted-foreground hover:text-foreground",
      )}
    >
      <Icon className="h-4 w-4" /> {label}
    </button>
  );
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function TableSkeleton() {
  return (
    <div className="animate-pulse space-y-2">
      <div className="h-10 rounded-lg bg-muted" />
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-12 rounded-lg bg-muted" />
      ))}
    </div>
  );
}
