"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Archive, Pause, Play, Repeat, Trash2, UserPlus, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";
import { recurrenceSummary } from "@/lib/format";
import type { Board } from "@/lib/types";

export function BoardSettingsSheet({
  board,
  open,
  onOpenChange,
}: {
  board: Board;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const qc = useQueryClient();
  const router = useRouter();
  const [name, setName] = useState(board.name);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const members = useQuery({ queryKey: ["members"], queryFn: appApi.members, enabled: open });
  const templates = useQuery({
    queryKey: ["templates", board.id],
    queryFn: () => appApi.templates(board.id),
    enabled: open,
  });

  const toggleTpl = useMutation({
    mutationFn: ({ id, active }: { id: string; active: boolean }) =>
      appApi.toggleTemplate(id, active),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["templates", board.id] }),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not update"),
  });
  const deleteTpl = useMutation({
    mutationFn: (id: string) => appApi.deleteTemplate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["templates", board.id] });
      toast.success("Recurring task removed");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not remove"),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["board", board.id] });
    qc.invalidateQueries({ queryKey: ["boards"] });
    qc.invalidateQueries({ queryKey: ["home"] });
  };

  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => appApi.updateBoard(board.id, body),
    onSuccess: () => {
      refresh();
      toast.success("Board updated");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not update"),
  });

  const addMember = useMutation({
    mutationFn: (userId: string) => appApi.addBoardMember(board.id, userId),
    onSuccess: () => refresh(),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not add"),
  });
  const removeMember = useMutation({
    mutationFn: (userId: string) => appApi.removeBoardMember(board.id, userId),
    onSuccess: () => refresh(),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not remove"),
  });

  const archive = useMutation({
    mutationFn: () => appApi.updateBoard(board.id, { archived: true }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["boards"] });
      toast.success("Board archived");
      onOpenChange(false);
      router.push("/boards");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not archive"),
  });

  const del = useMutation({
    mutationFn: () => appApi.deleteBoard(board.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["boards"] });
      toast.success("Board deleted");
      onOpenChange(false);
      router.push("/boards");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not delete"),
  });

  const memberIds = new Set(board.members.map((m) => m.user_id));
  const nonMembers = (members.data?.members ?? []).filter((m) => !memberIds.has(m.user_id));

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Board settings">
      <div className="space-y-6">
        <div>
          <Label htmlFor="bs-name">Name</Label>
          <div className="flex gap-2">
            <Input id="bs-name" value={name} onChange={(e) => setName(e.target.value)} />
            <Button
              variant="outline"
              disabled={name.trim() === board.name || !name.trim()}
              onClick={() => save.mutate({ name: name.trim() })}
            >
              Save
            </Button>
          </div>
        </div>

        <div>
          <Label>Visibility</Label>
          <div className="flex gap-2">
            {(["public", "private"] as const).map((v) => (
              <button
                key={v}
                onClick={() => v !== board.visibility && save.mutate({ visibility: v })}
                className={`flex-1 rounded-md border px-3 py-2.5 text-sm capitalize ${
                  board.visibility === v ? "border-primary bg-accent" : "border-border"
                }`}
              >
                {v}
              </button>
            ))}
          </div>
          {board.visibility === "public" ? (
            <p className="mt-1.5 text-xs text-muted-foreground">
              Making it private unassigns open tasks held by non-members.
            </p>
          ) : null}
        </div>

        <div>
          <Label>Who sees tasks</Label>
          <div className="flex gap-2">
            {(
              [
                ["all", "Everyone"],
                ["assigned", "Only assignee"],
              ] as const
            ).map(([v, label]) => (
              <button
                key={v}
                onClick={() => v !== board.task_scope && save.mutate({ task_scope: v })}
                className={`flex-1 rounded-md border px-3 py-2.5 text-sm ${
                  board.task_scope === v ? "border-primary bg-accent" : "border-border"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground">
            {board.task_scope === "assigned"
              ? "Members see only tasks assigned to them. You (the owner) and admins still see everything, including the report. Nothing is unassigned by this change."
              : "Everyone on the board sees every task."}
          </p>
        </div>

        {board.visibility === "private" ? (
          <div>
            <Label>Members ({board.members.length})</Label>
            <div className="space-y-1.5">
              {board.members.map((m) => (
                <div key={m.user_id} className="flex items-center justify-between rounded-md border border-border px-2.5 py-1.5">
                  <span className="flex items-center gap-2 text-sm">
                    <Avatar name={m.name} /> {m.name}
                  </span>
                  {board.members.length > 1 ? (
                    <button
                      onClick={() => removeMember.mutate(m.user_id)}
                      className="text-muted-foreground hover:text-danger"
                      aria-label="Remove"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
            {nonMembers.length > 0 ? (
              <div className="mt-3">
                <p className="mb-1.5 text-xs text-muted-foreground">Add a member</p>
                <div className="flex flex-wrap gap-1.5">
                  {nonMembers.map((m) => (
                    <button
                      key={m.user_id}
                      onClick={() => addMember.mutate(m.user_id)}
                      className="inline-flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-xs hover:bg-muted"
                    >
                      <UserPlus className="h-3 w-3" /> {m.name}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        {templates.data && templates.data.length > 0 ? (
          <div>
            <Label>Recurring tasks ({templates.data.length})</Label>
            <div className="space-y-1.5">
              {templates.data.map((t) => (
                <div key={t.id} className="flex items-center gap-2 rounded-md border border-border px-2.5 py-2">
                  <Repeat className={`h-4 w-4 ${t.active ? "text-primary" : "text-muted-foreground"}`} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{t.title}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {recurrenceSummary(t.recurrence)}
                      {!t.active ? " · paused" : ""}
                    </p>
                  </div>
                  <button
                    onClick={() => toggleTpl.mutate({ id: t.id, active: !t.active })}
                    className="text-muted-foreground hover:text-foreground"
                    aria-label={t.active ? "Pause" : "Resume"}
                  >
                    {t.active ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                  </button>
                  <button
                    onClick={() => deleteTpl.mutate(t.id)}
                    className="text-muted-foreground hover:text-danger"
                    aria-label="Delete recurring task"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="space-y-2 border-t border-border pt-4">
          <Button variant="ghost" className="text-muted-foreground" onClick={() => archive.mutate()}>
            <Archive className="h-4 w-4" /> Archive board
          </Button>
          {confirmDelete ? (
            <div className="rounded-md border border-danger/40 bg-danger/5 p-3">
              <p className="text-sm">
                Delete <span className="font-semibold">{board.name}</span> and all its tasks?
                This can&apos;t be undone.
              </p>
              <div className="mt-2 flex gap-2">
                <Button variant="ghost" onClick={() => setConfirmDelete(false)}>
                  Cancel
                </Button>
                <Button
                  className="bg-danger text-danger-foreground hover:bg-danger/90"
                  disabled={del.isPending}
                  onClick={() => del.mutate()}
                >
                  {del.isPending ? "Deleting…" : "Delete permanently"}
                </Button>
              </div>
            </div>
          ) : (
            <Button variant="ghost" className="text-danger" onClick={() => setConfirmDelete(true)}>
              <Trash2 className="h-4 w-4" /> Delete board permanently
            </Button>
          )}
        </div>
      </div>
    </Sheet>
  );
}
