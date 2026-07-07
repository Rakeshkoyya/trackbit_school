"use client";

import { type QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarDays, Check, ChevronDown, ChevronLeft, ChevronRight, CornerUpLeft, MoreHorizontal, Plus, Repeat2, Trash2, UserPlus, X } from "lucide-react";
import { forwardRef, useImperativeHandle, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Avatar } from "@/components/ui/avatar";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { dayLabel, GROUP_PALETTE, groupColor, PRIORITY, priorityMeta, timeLabel } from "@/lib/format";
import { appendRow, patchRowEverywhere, restoreRowCaches, snapshotRowCaches } from "@/lib/optimistic";
import type { BoardGroup, BoardRow, Member, MyTaskRow } from "@/lib/types";
import { cn } from "@/lib/utils";

export type GroupBy = "none" | "status" | "assignee" | "category" | "board" | "priority";
export type ColumnKey = "person" | "due" | "priority";
export type SortBy = "created" | "urgency";
export type TaskTableHandle = { focusAdd: () => void };

function invalidateTables(qc: QueryClient) {
  qc.invalidateQueries({ queryKey: ["board-table"] });
  qc.invalidateQueries({ queryKey: ["my-tasks"] });
  qc.invalidateQueries({ queryKey: ["home"] });
  qc.invalidateQueries({ queryKey: ["boards"] });
}

function colsFor(columns: ColumnKey[]): string {
  const parts = ["2.25rem", "minmax(0,1fr)"];
  if (columns.includes("person")) parts.push("11rem");
  if (columns.includes("due")) parts.push("9.5rem");
  if (columns.includes("priority")) parts.push("8rem");
  return parts.join(" ");
}

function gridStyle(cols: string): React.CSSProperties {
  return { display: "grid", gridTemplateColumns: cols, alignItems: "center" };
}

/** Portal popover positioned against an anchor — never clipped by overflow. */
function Popover({
  open,
  onClose,
  rect,
  width = 240,
  children,
}: {
  open: boolean;
  onClose: () => void;
  rect: DOMRect | null;
  width?: number;
  children: React.ReactNode;
}) {
  if (!open || typeof document === "undefined" || !rect) return null;
  const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
  const spaceBelow = window.innerHeight - rect.bottom;
  const pos: React.CSSProperties =
    spaceBelow < 300
      ? { bottom: window.innerHeight - rect.top + 4, left, width }
      : { top: rect.bottom + 4, left, width };

  return createPortal(
    <>
      <div className="fixed inset-0 z-[55]" onClick={onClose} />
      <div
        style={{ position: "fixed", ...pos }}
        className="z-[56] rounded-lg border border-border bg-card p-2 shadow-lg"
      >
        {children}
      </div>
    </>,
    document.body,
  );
}

export const TaskTable = forwardRef<TaskTableHandle, {
  rows: BoardRow[];
  groupBy: GroupBy;
  columns?: ColumnKey[];
  groupDefs?: BoardGroup[];
  members?: Member[];
  addContext?: { boardId: string };
  hideEmptyGroups?: boolean;
  /** "created" (default) appends new tasks to the bottom; "urgency" sorts
   *  overdue → due today → later → no date, with done tasks sinking last. */
  sortBy?: SortBy;
  /** Show each task's board as a small tag — for the cross-board "My tasks" list. */
  showBoard?: boolean;
  /** False on a privacy board for a non-owner: the person cell is read-only. */
  canAssignPerson?: boolean;
  onComplete: (row: BoardRow) => void;
  onReopen: (row: BoardRow) => void;
  onOpen: (row: BoardRow) => void;
}>(function TaskTable(
  { rows, groupBy, columns = ["person", "due", "priority"], groupDefs, addContext, hideEmptyGroups, sortBy = "created", showBoard = false, canAssignPerson = true, onComplete, onReopen, onOpen },
  ref,
) {
  const firstAddRef = useRef<HTMLInputElement>(null);
  useImperativeHandle(ref, () => ({ focusAdd: () => firstAddRef.current?.focus() }), []);

  const cols = colsFor(columns);
  const groups = buildGroups(rows, groupBy, groupDefs, hideEmptyGroups, sortBy);
  const canAddRows = addContext != null && (groupBy === "category" || groupBy === "none");
  const boardId = addContext?.boardId;
  const rowProps = { columns, cols, groups: groupDefs, boardId, showBoard, canAssignPerson, onComplete, onReopen, onOpen };

  const colHeader = (
    <div
      style={gridStyle(cols)}
      className="border-b border-border bg-muted/20 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground"
    >
      <span />
      <span>Task</span>
      {columns.includes("person") ? <span>Person</span> : null}
      {columns.includes("due") ? <span>Due</span> : null}
      {columns.includes("priority") ? <span>Priority</span> : null}
    </div>
  );

  if (groupBy === "none") {
    const g = groups[0];
    return (
      <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
        {colHeader}
        {g.rows.map((row) => <Row key={`${row.kind}-${row.id}`} row={row} {...rowProps} />)}
        {canAddRows ? <AddRow boardId={addContext!.boardId} category={null} inputRef={firstAddRef} /> : null}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {groups.map((g, gi) => (
        <div key={g.key} className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <GroupHeader g={g} boardId={addContext?.boardId} />
          {colHeader}
          {g.rows.map((row) => <Row key={`${row.kind}-${row.id}`} row={row} {...rowProps} />)}
          {g.rows.length === 0 && !canAddRows ? (
            <p className="px-3 py-3 text-xs text-muted-foreground">No tasks.</p>
          ) : null}
          {canAddRows ? (
            <AddRow boardId={addContext!.boardId} category={g.category}
              inputRef={gi === 0 ? firstAddRef : undefined} />
          ) : null}
        </div>
      ))}
      {addContext != null && groupBy === "category" && !hideEmptyGroups ? (
        <AddGroupButton boardId={addContext.boardId} groupDefs={groupDefs ?? []} />
      ) : null}
    </div>
  );
});

function GroupHeader({ g, boardId }: { g: Group; boardId?: string }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [colorOpen, setColorOpen] = useState(false);
  const [colorRect, setColorRect] = useState<DOMRect | null>(null);
  const canEdit = g.editable && !!boardId && g.category != null;
  const color = g.color || "#888780";

  const rename = useMutation({
    mutationFn: (newName: string) => appApi.updateCategory(boardId!, g.category!, { new_name: newName }),
    onSuccess: () => { invalidateTables(qc); setEditing(false); },
    onError: (e) => { showApiError(e, "Could not rename group"); setEditing(false); },
  });
  const recolor = useMutation({
    mutationFn: (c: string) => appApi.updateCategory(boardId!, g.category!, { color: c }),
    onSuccess: () => { invalidateTables(qc); setColorOpen(false); },
    onError: (e) => showApiError(e, "Could not recolor group"),
  });
  const del = useMutation({
    mutationFn: () => appApi.deleteCategory(boardId!, g.category!),
    onSuccess: () => invalidateTables(qc),
    onError: (e) => showApiError(e, "Could not delete group"),
  });

  return (
    <div
      className="flex items-center gap-2 border-b border-border bg-muted/40 px-3 py-2 text-sm font-semibold"
      style={{ borderLeft: `3px solid ${color}` }}
    >
      {canEdit ? (
        <button
          onClick={(e) => { setColorRect(e.currentTarget.getBoundingClientRect()); setColorOpen(true); }}
          className="h-3.5 w-3.5 shrink-0 rounded-full hover:ring-2 hover:ring-border"
          style={{ backgroundColor: color }}
          aria-label="Group color"
        />
      ) : (
        <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      )}

      {editing && canEdit ? (
        <input
          autoFocus
          defaultValue={g.label}
          onBlur={(e) => {
            const v = e.target.value.trim();
            if (v && v !== g.label) rename.mutate(v);
            else setEditing(false);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
            else if (e.key === "Escape") setEditing(false);
          }}
          className="rounded border border-input bg-card px-1.5 py-0.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      ) : (
        <button
          onClick={() => canEdit && setEditing(true)}
          style={{ color }}
          className={canEdit ? "hover:underline" : "cursor-default"}
        >
          {g.label}
        </button>
      )}
      <span className="text-xs font-normal text-muted-foreground">{g.rows.length}</span>

      {canEdit ? (
        <button
          onClick={() => del.mutate()}
          className="ml-auto text-muted-foreground hover:text-danger"
          aria-label="Delete group"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      ) : null}

      <Popover open={colorOpen} onClose={() => setColorOpen(false)} rect={colorRect} width={160}>
        <div className="flex flex-wrap gap-1.5 p-1">
          {GROUP_PALETTE.map((c) => (
            <button
              key={c}
              onClick={() => recolor.mutate(c)}
              className="h-6 w-6 rounded-full border border-border"
              style={{ backgroundColor: c }}
              aria-label={`Color ${c}`}
            />
          ))}
        </div>
      </Popover>
    </div>
  );
}

function Row({
  row,
  columns,
  cols,
  groups,
  boardId,
  showBoard,
  canAssignPerson = true,
  onComplete,
  onReopen,
  onOpen,
}: {
  row: BoardRow;
  columns: ColumnKey[];
  cols: string;
  groups?: BoardGroup[];
  boardId?: string;
  showBoard?: boolean;
  canAssignPerson?: boolean;
  onComplete: (row: BoardRow) => void;
  onReopen: (row: BoardRow) => void;
  onOpen: (row: BoardRow) => void;
}) {
  const done = row.status === "done";
  const overdue = row.due_at != null && !done && new Date(row.due_at) < new Date();
  const boardName = showBoard ? (row as MyTaskRow).board_name : null;

  return (
    <div
      onClick={() => onOpen(row)}
      style={gridStyle(cols)}
      className={cn(
        "group relative cursor-pointer border-b border-border px-3 py-2 text-sm transition-colors last:border-0 hover:bg-muted/30",
        overdue && "bg-warning-soft/30",
      )}
    >
      <div onClick={(e) => e.stopPropagation()}>
        <CheckButton row={row} onComplete={() => onComplete(row)} onReopen={() => onReopen(row)} />
      </div>

      <div className="flex min-w-0 items-center gap-2 pr-3">
        <TitleCell row={row} />
        {row.kind === "recurring" ? (
          <Repeat2 className="h-3.5 w-3.5 shrink-0 text-primary" />
        ) : null}
        {row.pass_count > 0 ? (
          <span className="inline-flex shrink-0 items-center text-xs text-warning">
            <CornerUpLeft className="h-3 w-3" />
            {row.pass_count > 1 ? row.pass_count : ""}
          </span>
        ) : null}
        {boardName ? (
          <span className="max-w-[40%] shrink-0 truncate rounded-md bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
            {boardName}
          </span>
        ) : null}
      </div>

      {columns.includes("person") ? (
        <div className="min-w-0 pr-2" onClick={(e) => e.stopPropagation()}>
          <AssigneeCell row={row} canAssign={canAssignPerson} />
        </div>
      ) : null}

      {columns.includes("due") ? (
        <div onClick={(e) => e.stopPropagation()}>
          <DueCell row={row} />
        </div>
      ) : null}

      {columns.includes("priority") ? (
        <div onClick={(e) => e.stopPropagation()}>
          <PriorityCell row={row} />
        </div>
      ) : null}

      <RowMenu row={row} groups={groups} boardId={boardId} onOpen={onOpen} />
    </div>
  );
}

/** Task title: click the text to rename inline; the rest of the row opens it. */
function TitleCell({ row }: { row: BoardRow }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const done = row.status === "done";

  const save = useMutation({
    mutationFn: (title: string): Promise<unknown> =>
      row.kind === "recurring"
        ? appApi.updateTemplate(row.id, { title })
        : appApi.editTask(row.id, { title }),
    onSuccess: () => { invalidateTables(qc); setEditing(false); },
    onError: (e) => { showApiError(e, "Could not rename task"); setEditing(false); },
  });

  if (editing) {
    return (
      <input
        autoFocus
        defaultValue={row.title}
        onClick={(e) => e.stopPropagation()}
        onBlur={(e) => {
          const v = e.target.value.trim();
          if (v && v !== row.title) save.mutate(v);
          else setEditing(false);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }
          else if (e.key === "Escape") setEditing(false);
        }}
        className="min-w-0 flex-1 rounded border border-input bg-card px-1.5 py-0.5 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
    );
  }
  return (
    <button
      onClick={(e) => { e.stopPropagation(); setEditing(true); }}
      className={cn("truncate text-left font-medium", done && "text-muted-foreground line-through")}
    >
      {row.title}
    </button>
  );
}

function CheckButton({
  row,
  onComplete,
  onReopen,
}: {
  row: BoardRow;
  onComplete: () => void;
  onReopen: () => void;
}) {
  const done = row.status === "done";
  const scheduled = row.status === "scheduled";
  const disabled = scheduled || (row.kind === "recurring" && !row.today_instance_id);

  if (done) {
    return (
      <button
        onClick={onReopen}
        aria-label="Reopen"
        className="flex h-6 w-6 items-center justify-center rounded-full bg-success text-success-foreground transition-opacity hover:opacity-80"
      >
        <Check className="h-3.5 w-3.5" />
      </button>
    );
  }
  return (
    <button
      disabled={disabled}
      onClick={onComplete}
      aria-label="Mark done"
      className={cn(
        "h-6 w-6 rounded-full border-2 transition-colors",
        row.status === "missed" ? "border-warning" : "border-muted-foreground/30",
        disabled ? "cursor-not-allowed opacity-40" : "hover:border-success hover:bg-success/10",
      )}
    />
  );
}

/** Person column: avatar / add-person icon → member picker (search + list). */
function AssigneeCell({ row, canAssign = true }: { row: BoardRow; canAssign?: boolean }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [query, setQuery] = useState("");
  const members = useQuery({ queryKey: ["members"], queryFn: appApi.members, enabled: open });

  const assign = useMutation({
    mutationFn: (userId: string | null) => appApi.assignTask(row.id, userId),
    onMutate: (userId) => {
      const m = userId ? (members.data?.members ?? []).find((x) => x.user_id === userId) : null;
      const snap = snapshotRowCaches(qc);
      patchRowEverywhere(qc, row.id, { assignee: m ? { id: m.user_id, name: m.name } : null });
      setOpen(false);
      setQuery("");
      return { snap };
    },
    onError: (e, _v, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      showApiError(e, "Could not assign");
    },
    onSettled: () => invalidateTables(qc),
  });

  // Recurring rows carry the template's default assignee — change it in detail.
  // Privacy boards (canAssign=false) render the assignee read-only too: a member
  // can't reassign here, so don't offer the picker (the backend blocks it anyway).
  if (row.kind === "recurring" || !canAssign) {
    return row.assignee ? (
      <span className="flex items-center gap-1.5 truncate text-sm">
        <Avatar name={row.assignee.name} /> <span className="truncate">{row.assignee.name}</span>
      </span>
    ) : (
      <span className="text-xs text-muted-foreground">—</span>
    );
  }

  const list = (members.data?.members ?? []).filter((m) =>
    m.name.toLowerCase().includes(query.toLowerCase()),
  );

  return (
    <div>
      <button
        onClick={(e) => { setRect(e.currentTarget.getBoundingClientRect()); setOpen(true); }}
        className="flex max-w-full items-center gap-1.5 rounded-md py-0.5 text-left hover:bg-muted"
        aria-label="Assign person"
      >
        {row.assignee ? (
          <>
            <Avatar name={row.assignee.name} />
            <span className="truncate text-sm">{row.assignee.name}</span>
          </>
        ) : (
          <span className="flex h-6 w-6 items-center justify-center rounded-full border border-dashed border-muted-foreground/40 text-muted-foreground">
            <UserPlus className="h-3.5 w-3.5" />
          </span>
        )}
      </button>

      <Popover open={open} onClose={() => { setOpen(false); setQuery(""); }} rect={rect} width={250}>
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search members…"
          className="mb-1 w-full rounded-md border border-input bg-card px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <div className="max-h-60 overflow-y-auto">
          {row.assignee ? (
            <button
              onClick={() => assign.mutate(null)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted"
            >
              <X className="h-3.5 w-3.5" /> Unassign
            </button>
          ) : null}
          {list.map((m) => (
            <button
              key={m.user_id}
              onClick={() => assign.mutate(m.user_id)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
            >
              <Avatar name={m.name} /> {m.name}
            </button>
          ))}
          {members.isLoading ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">Loading…</p>
          ) : list.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">No members.</p>
          ) : null}
        </div>
      </Popover>
    </div>
  );
}

/** Hover 3-dots row menu: open, move to group, move to board, delete. */
function RowMenu({
  row,
  groups,
  boardId,
  onOpen,
}: {
  row: BoardRow;
  groups?: BoardGroup[];
  boardId?: string;
  onOpen: (row: BoardRow) => void;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const boards = useQuery({ queryKey: ["boards"], queryFn: appApi.boards, enabled: open });

  const update = useMutation({
    mutationFn: (body: Record<string, unknown>): Promise<unknown> =>
      row.kind === "recurring" ? appApi.updateTemplate(row.id, body) : appApi.editTask(row.id, body),
    onSuccess: () => { invalidateTables(qc); setOpen(false); },
    onError: (e) => showApiError(e, "Could not move task"),
  });
  const del = useMutation({
    mutationFn: (): Promise<unknown> =>
      row.kind === "recurring" ? appApi.deleteTemplate(row.id) : appApi.cancelTask(row.id),
    onSuccess: () => { invalidateTables(qc); setOpen(false); },
    onError: (e) => showApiError(e, "Could not delete task"),
  });

  const currentBoard = boardId ?? (row as MyTaskRow).board_id;
  const allBoards = boards.data ? [...boards.data.my_boards, ...boards.data.other_public] : [];
  const otherBoards = allBoards.filter((b) => b.id !== currentBoard);

  return (
    <>
      <button
        onClick={(e) => {
          e.stopPropagation();
          setRect(e.currentTarget.getBoundingClientRect());
          setOpen(true);
        }}
        className={cn(
          "absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md border border-border bg-card text-muted-foreground transition-opacity hover:bg-muted",
          open ? "opacity-100" : "opacity-0 group-hover:opacity-100",
        )}
        aria-label="Task actions"
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      <Popover open={open} onClose={() => setOpen(false)} rect={rect} width={230}>
        <button
          onClick={() => { setOpen(false); onOpen(row); }}
          className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
        >
          Open this task
        </button>

        {groups && groups.length > 0 ? (
          <div className="mt-1 border-t border-border pt-1">
            <p className="px-2 py-1 text-[11px] uppercase tracking-wide text-muted-foreground">Move to group</p>
            <div className="max-h-40 overflow-y-auto">
              {groups.map((grp) => (
                <button
                  key={grp.name}
                  disabled={row.category === grp.name}
                  onClick={() => update.mutate({ category: grp.name })}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted disabled:opacity-40"
                >
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: grp.color }} />
                  {grp.name}
                </button>
              ))}
              {row.category ? (
                <button
                  onClick={() => update.mutate({ category: null })}
                  className="w-full rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted"
                >
                  Remove from group
                </button>
              ) : null}
            </div>
          </div>
        ) : null}

        {otherBoards.length > 0 ? (
          <div className="mt-1 border-t border-border pt-1">
            <p className="px-2 py-1 text-[11px] uppercase tracking-wide text-muted-foreground">Move to board</p>
            <div className="max-h-40 overflow-y-auto">
              {otherBoards.map((b) => (
                <button
                  key={b.id}
                  onClick={() => update.mutate({ board_id: b.id })}
                  className="w-full truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                >
                  {b.name}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="mt-1 border-t border-border pt-1">
          <button
            onClick={() => del.mutate()}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-danger hover:bg-danger/5"
          >
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </button>
        </div>
      </Popover>
    </>
  );
}

function PriorityCell({ row }: { row: BoardRow }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const meta = priorityMeta(row.priority);

  const save = useMutation({
    mutationFn: (priority: number): Promise<unknown> =>
      row.kind === "recurring"
        ? appApi.updateTemplate(row.id, { priority })
        : appApi.editTask(row.id, { priority }),
    onMutate: (priority) => {
      const snap = snapshotRowCaches(qc);
      patchRowEverywhere(qc, row.id, { priority });
      setOpen(false);
      return { snap };
    },
    onError: (e, _v, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      showApiError(e, "Could not set priority");
    },
    onSettled: () => invalidateTables(qc),
  });

  return (
    <div className="pr-2">
      <button
        onClick={(e) => {
          setRect(e.currentTarget.getBoundingClientRect());
          setOpen((v) => !v);
        }}
        className={cn(
          "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
          row.priority > 0 ? meta.cls : "text-muted-foreground hover:bg-muted",
        )}
      >
        {row.priority > 0 ? meta.label : "Set"}
      </button>

      <Popover open={open} onClose={() => setOpen(false)} rect={rect} width={170}>
        {PRIORITY.map((p) => (
          <button
            key={p.v}
            onClick={() => save.mutate(p.v)}
            className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
          >
            {p.v > 0 ? (
              <span className={cn("rounded px-2 py-0.5 text-xs font-medium", p.cls)}>{p.label}</span>
            ) : (
              <span className="text-muted-foreground">None</span>
            )}
          </button>
        ))}
      </Popover>
    </div>
  );
}

// ---- date helpers (themed calendar) ----------------------------------
const WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}
function addMonths(d: Date, n: number): Date {
  return new Date(d.getFullYear(), d.getMonth() + n, 1);
}
function hhmm(d: Date): string {
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}
function sameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
}
/** 42 cells (6 weeks), Monday-first, covering the displayed month. */
function monthMatrix(view: Date): Date[] {
  const first = startOfMonth(view);
  const offset = (first.getDay() + 6) % 7; // Mon=0 … Sun=6
  const start = new Date(first.getFullYear(), first.getMonth(), 1 - offset);
  return Array.from({ length: 42 }, (_, i) =>
    new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
  );
}

function time12(h: number, m: number): string {
  const ap = h < 12 ? "AM" : "PM";
  const hr = h % 12 === 0 ? 12 : h % 12;
  return `${hr}:${String(m).padStart(2, "0")} ${ap}`;
}
function timeLabel12(v: string): string {
  const [h, m] = v.split(":").map(Number);
  return time12(h || 0, m || 0);
}
// 30-minute intervals across the day.
const TIME_OPTIONS: { v: string; label: string }[] = (() => {
  const out: { v: string; label: string }[] = [];
  for (let h = 0; h < 24; h += 1) {
    for (const m of [0, 30]) {
      out.push({ v: `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`, label: time12(h, m) });
    }
  }
  return out;
})();

function TimeSelect({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1 rounded-md border border-input bg-card px-2 py-1 text-xs hover:bg-muted"
      >
        {timeLabel12(value)} <ChevronDown className="h-3 w-3 text-muted-foreground" />
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-[57]" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-[58] mt-1 max-h-48 w-28 overflow-y-auto rounded-md border border-border bg-card p-1 shadow-lg">
            {TIME_OPTIONS.map((o) => (
              <button
                key={o.v}
                onClick={() => { onChange(o.v); setOpen(false); }}
                className={cn(
                  "block w-full rounded px-2 py-1 text-left text-xs hover:bg-muted",
                  o.v === value && "bg-accent font-medium",
                )}
              >
                {o.label}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

function DueCell({ row }: { row: BoardRow }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [viewMonth, setViewMonth] = useState(() =>
    startOfMonth(row.due_at ? new Date(row.due_at) : new Date()),
  );
  const [time, setTime] = useState(() => (row.due_at ? hhmm(new Date(row.due_at)) : "09:00"));

  const save = useMutation({
    mutationFn: (due_at: string | null) => appApi.editTask(row.id, { due_at, all_day: false }),
    onMutate: (due_at) => {
      const snap = snapshotRowCaches(qc);
      patchRowEverywhere(qc, row.id, { due_at, all_day: false });
      return { snap };
    },
    onError: (e, _v, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      showApiError(e, "Could not set due date");
    },
    onSettled: () => invalidateTables(qc),
  });

  // Recurring rows are due "today" on the days they occur (cadence owns the time).
  if (row.kind === "recurring") {
    return <span className="text-xs text-muted-foreground">{row.occurs_today ? "Today" : "—"}</span>;
  }

  const selected = row.due_at ? new Date(row.due_at) : null;

  function openPicker(e: React.MouseEvent<HTMLButtonElement>) {
    setRect(e.currentTarget.getBoundingClientRect());
    setViewMonth(startOfMonth(row.due_at ? new Date(row.due_at) : new Date()));
    setTime(row.due_at ? hhmm(new Date(row.due_at)) : "09:00");
    setOpen(true);
  }
  function pickDay(day: Date, t: string) {
    const [h, m] = t.split(":").map(Number);
    const dt = new Date(day.getFullYear(), day.getMonth(), day.getDate(), h || 0, m || 0);
    save.mutate(dt.toISOString());
    setOpen(false);
  }
  function changeTime(v: string) {
    setTime(v);
    if (selected) {
      const [h, m] = v.split(":").map(Number);
      const dt = new Date(selected.getFullYear(), selected.getMonth(), selected.getDate(), h || 0, m || 0);
      save.mutate(dt.toISOString());
    }
  }

  return (
    <div className="inline-flex items-center">
      <button
        type="button"
        onClick={openPicker}
        className={cn(
          "inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-xs hover:bg-muted",
          row.due_at ? "text-foreground" : "text-muted-foreground",
        )}
      >
        <CalendarDays className="h-3.5 w-3.5 text-muted-foreground" />
        {row.due_at ? (
          <>
            {dayLabel(row.due_at)}
            {timeLabel(row.due_at) ? (
              <span className="text-[10px] text-muted-foreground">{timeLabel(row.due_at)}</span>
            ) : null}
          </>
        ) : (
          "Set date"
        )}
      </button>

      <Popover open={open} onClose={() => setOpen(false)} rect={rect} width={296}>
        <div className="p-1">
          <div className="mb-2 flex items-center gap-2">
            <button
              onClick={() => pickDay(new Date(), time)}
              className="rounded-md border border-border px-2.5 py-1 text-xs font-medium hover:bg-muted"
            >
              Today
            </button>
            <span className="flex-1 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
              {selected ? selected.toLocaleDateString() : "No date"}
            </span>
            <TimeSelect value={time} onChange={changeTime} />
          </div>

          <div className="mb-1 flex items-center justify-between px-1">
            <span className="text-sm font-medium">
              {viewMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
            </span>
            <div className="flex gap-1">
              <button onClick={() => setViewMonth(addMonths(viewMonth, -1))} className="rounded p-1 hover:bg-muted" aria-label="Previous month">
                <ChevronLeft className="h-4 w-4" />
              </button>
              <button onClick={() => setViewMonth(addMonths(viewMonth, 1))} className="rounded p-1 hover:bg-muted" aria-label="Next month">
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-7 text-center text-[11px] text-muted-foreground">
            {WEEKDAYS.map((d) => <span key={d} className="py-1">{d}</span>)}
          </div>
          <div className="grid grid-cols-7 gap-0.5">
            {monthMatrix(viewMonth).map((d, i) => {
              const inMonth = d.getMonth() === viewMonth.getMonth();
              const isSel = selected != null && sameDay(d, selected);
              const isToday = sameDay(d, new Date());
              return (
                <button
                  key={i}
                  onClick={() => pickDay(d, time)}
                  className={cn(
                    "h-8 rounded-md text-sm hover:bg-muted",
                    !inMonth && "text-muted-foreground/40",
                    isSel && "bg-primary text-primary-foreground hover:bg-primary",
                    !isSel && isToday && "border border-primary text-primary",
                  )}
                >
                  {d.getDate()}
                </button>
              );
            })}
          </div>

          {selected ? (
            <button
              onClick={() => { save.mutate(null); setOpen(false); }}
              className="mt-2 w-full rounded-md px-2 py-1.5 text-left text-xs text-muted-foreground hover:bg-muted hover:text-danger"
            >
              Clear due date
            </button>
          ) : null}
        </div>
      </Popover>
    </div>
  );
}

function AddRow({
  boardId,
  category,
  inputRef,
}: {
  boardId: string;
  category: string | null;
  inputRef?: React.RefObject<HTMLInputElement | null>;
}) {
  const qc = useQueryClient();
  const localRef = useRef<HTMLInputElement>(null);
  const ref = inputRef ?? localRef;
  const [title, setTitle] = useState("");

  const create = useMutation({
    mutationFn: (t: string) =>
      appApi.createTask({ board_id: boardId, title: t, category, priority: 0 }),
    onMutate: (t) => {
      const temp: BoardRow = {
        kind: "task", id: `temp-${Date.now()}`, title: t, description: null,
        category, priority: 0, assignee: null, due_at: null, all_day: false,
        status: "open", recurrence: null, today_instance_id: null, occurs_today: true,
        pass_count: 0, is_critical: false, passed_by: null, created_at: new Date().toISOString(),
      };
      const snap = snapshotRowCaches(qc);
      appendRow(qc, boardId, temp);
      return { snap };
    },
    onError: (e, _v, ctx) => {
      restoreRowCaches(qc, ctx?.snap);
      showApiError(e, "Could not add task");
    },
    onSettled: () => invalidateTables(qc),
  });

  function commit(keepFocus: boolean) {
    const t = title.trim();
    if (!t) {
      if (!keepFocus) ref.current?.blur();
      return;
    }
    setTitle("");
    create.mutate(t);
    if (keepFocus) requestAnimationFrame(() => ref.current?.focus());
    else ref.current?.blur();
  }

  return (
    <div className="flex items-center gap-2 border-b border-border bg-muted/10 px-3 py-2 text-sm last:border-0">
      <Plus className="h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="flex min-w-0 flex-1 flex-col">
        <input
          ref={ref}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit(e.shiftKey);
            } else if (e.key === "Tab") {
              e.preventDefault();
              commit(false);
            }
          }}
          placeholder="Add a task"
          className="bg-transparent py-0.5 text-sm focus:outline-none"
        />
        {title ? (
          <span className="text-[11px] text-muted-foreground">
            Press Shift + Enter to add another item
          </span>
        ) : null}
      </div>
    </div>
  );
}

function AddGroupButton({ boardId, groupDefs }: { boardId: string; groupDefs: BoardGroup[] }) {
  const qc = useQueryClient();
  const add = useMutation({
    mutationFn: () => {
      const names = new Set(groupDefs.map((d) => d.name));
      let name = "New group";
      let i = 2;
      while (names.has(name)) {
        name = `New group ${i}`;
        i += 1;
      }
      const color = GROUP_PALETTE[groupDefs.length % GROUP_PALETTE.length];
      return appApi.createCategory(boardId, name, color);
    },
    onSuccess: () => invalidateTables(qc),
    onError: (e) => showApiError(e, "Could not add group"),
  });

  return (
    <div>
      <button
        onClick={() => add.mutate()}
        disabled={add.isPending}
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-muted px-3 py-1.5 text-sm font-medium text-foreground hover:bg-accent disabled:opacity-50"
      >
        <Plus className="h-4 w-4" /> Add new group
      </button>
    </div>
  );
}

// ---- grouping ---------------------------------------------------------
type Group = {
  key: string;
  label: string;
  color: string;
  rows: BoardRow[];
  category: string | null;
  editable: boolean;
};

const STATUS_ORDER = ["open", "missed", "scheduled", "done"];
const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  missed: "Missed",
  scheduled: "Scheduled",
  done: "Done",
};

/** Stable creation order — new tasks always append to the bottom of their group. */
function sortRows(rows: BoardRow[]): BoardRow[] {
  return [...rows].sort((a, b) =>
    a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0,
  );
}

/** Urgency bucket: overdue (0) → due today (1) → due later (2) → no date (3) →
 *  done (4, sinks to the bottom). Recurring rows due today count as bucket 1. */
function urgencyRank(row: BoardRow): number {
  if (row.status === "done") return 4;
  if (row.due_at) {
    const due = new Date(row.due_at);
    const now = new Date();
    if (due.getTime() < now.getTime()) return 0;
    if (
      due.getFullYear() === now.getFullYear() &&
      due.getMonth() === now.getMonth() &&
      due.getDate() === now.getDate()
    ) {
      return 1;
    }
    return 2;
  }
  if (row.kind === "recurring" && row.occurs_today) return 1;
  return 3;
}

/** "Do-next" order for the flat My-tasks list. */
function sortByUrgency(rows: BoardRow[]): BoardRow[] {
  return [...rows].sort((a, b) => {
    const ra = urgencyRank(a);
    const rb = urgencyRank(b);
    if (ra !== rb) return ra - rb;
    const da = a.due_at ? new Date(a.due_at).getTime() : Infinity;
    const db = b.due_at ? new Date(b.due_at).getTime() : Infinity;
    if (da !== db) return da - db;
    return a.created_at < b.created_at ? -1 : a.created_at > b.created_at ? 1 : 0;
  });
}

function buildGroups(
  rows: BoardRow[],
  groupBy: GroupBy,
  groupDefs?: BoardGroup[],
  hideEmpty = false,
  sortBy: SortBy = "created",
): Group[] {
  const sorted = sortBy === "urgency" ? sortByUrgency(rows) : sortRows(rows);
  if (groupBy === "none") {
    return [{ key: "all", label: "", color: "", rows: sorted, category: null, editable: false }];
  }

  if (groupBy === "category") {
    const byCat = new Map<string, BoardRow[]>();
    for (const r of sorted) {
      const k = r.category ?? "_none";
      if (!byCat.has(k)) byCat.set(k, []);
      byCat.get(k)!.push(r);
    }
    const defs = groupDefs ?? [];
    const defNames = new Set(defs.map((d) => d.name));
    const groups: Group[] = defs.map((d) => ({
      key: d.name, label: d.name, color: d.color,
      rows: byCat.get(d.name) ?? [], category: d.name, editable: true,
    }));
    for (const [k, rs] of byCat) {
      if (k === "_none" || defNames.has(k)) continue;
      groups.push({ key: k, label: k, color: groupColor(k), rows: rs, category: k, editable: true });
    }
    if (byCat.has("_none")) {
      groups.push({
        key: "_none", label: "No category", color: "#888780",
        rows: byCat.get("_none")!, category: null, editable: false,
      });
    }
    return hideEmpty ? groups.filter((g) => g.rows.length > 0) : groups;
  }

  const map = new Map<string, Group>();
  const keyFor = (r: BoardRow): { key: string; label: string } => {
    if (groupBy === "status") return { key: r.status, label: STATUS_LABEL[r.status] ?? r.status };
    if (groupBy === "priority") {
      const labels = ["No priority", "Low", "Medium", "High"];
      return { key: String(r.priority), label: labels[r.priority] ?? "No priority" };
    }
    if (groupBy === "assignee")
      return r.assignee ? { key: r.assignee.id, label: r.assignee.name } : { key: "_none", label: "Unassigned" };
    const b = r as MyTaskRow;
    return { key: b.board_id ?? "_none", label: b.board_name ?? "—" };
  };
  for (const r of sorted) {
    const { key, label } = keyFor(r);
    if (!map.has(key)) {
      map.set(key, { key, label, color: groupColor(key), rows: [], category: null, editable: false });
    }
    map.get(key)!.rows.push(r);
  }
  const groups = [...map.values()];
  if (groupBy === "status") {
    groups.sort((a, b) => STATUS_ORDER.indexOf(a.key) - STATUS_ORDER.indexOf(b.key));
  } else if (groupBy === "priority") {
    groups.sort((a, b) => Number(b.key) - Number(a.key)); // High → None
  } else {
    groups.sort((a, b) => a.label.localeCompare(b.label));
  }
  return hideEmpty ? groups.filter((g) => g.rows.length > 0) : groups;
}
