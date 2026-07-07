"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Globe, LayoutGrid, Lock, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { BoardCard } from "@/components/boards/board-card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";

export default function BoardsPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [visibility, setVisibility] = useState<"public" | "private">("public");
  const [taskScope, setTaskScope] = useState<"all" | "assigned">("all");

  const { data, isLoading } = useQuery({ queryKey: ["boards"], queryFn: appApi.boards });

  const create = useMutation({
    mutationFn: () => appApi.createBoard({ name: name.trim(), visibility, task_scope: taskScope }),
    onSuccess: (board) => {
      qc.invalidateQueries({ queryKey: ["boards"] });
      toast.success("Board created");
      setName("");
      setVisibility("public");
      setTaskScope("all");
      setOpen(false);
      router.push(`/boards/${board.id}`);
    },
    onError: (e) => showApiError(e, "Could not create board"),
  });

  return (
    <div>
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Boards</h1>
        <Button size="sm" onClick={() => setOpen(true)}>
          <Plus className="h-4 w-4" /> New
        </Button>
      </header>

      {isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-28 animate-pulse rounded-xl bg-muted" />
          ))}
        </div>
      ) : data && data.my_boards.length + data.other_public.length === 0 ? (
        <EmptyState
          icon={LayoutGrid}
          title="No boards yet"
          body="Boards keep work separated — create one for each area of work."
          action={
            <Button onClick={() => setOpen(true)}>
              <Plus className="h-4 w-4" /> New board
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          {data!.my_boards.length > 0 ? (
            <div>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                My boards
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {data!.my_boards.map((b) => (
                  <BoardCard key={b.id} board={b} />
                ))}
              </div>
            </div>
          ) : null}
          {data!.other_public.length > 0 ? (
            <div>
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Other public boards
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {data!.other_public.map((b) => (
                  <BoardCard key={b.id} board={b} />
                ))}
              </div>
            </div>
          ) : null}
        </div>
      )}

      <Sheet open={open} onOpenChange={setOpen} title="New board">
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) create.mutate();
          }}
        >
          <div>
            <Label htmlFor="b-name">Board name</Label>
            <Input id="b-name" autoFocus required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label>Visibility</Label>
            <div className="flex gap-2">
              {(["public", "private"] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setVisibility(v)}
                  className={`flex flex-1 items-center justify-center gap-2 rounded-md border px-3 py-2.5 text-sm capitalize ${
                    visibility === v ? "border-primary bg-accent" : "border-border"
                  }`}
                >
                  {v === "public" ? <Globe className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
                  {v}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {visibility === "public"
                ? "Visible to the whole org; counts toward the org dashboard."
                : "Visible only to members you add."}
            </p>
          </div>
          <div>
            <Label>Who sees tasks</Label>
            <div className="flex gap-2">
              {(
                [
                  ["all", "Everyone"],
                  ["assigned", "Only assignee"],
                ] as const
              ).map((opt) => (
                <button
                  key={opt[0]}
                  type="button"
                  onClick={() => setTaskScope(opt[0])}
                  className={`flex-1 rounded-md border px-3 py-2.5 text-sm ${
                    taskScope === opt[0] ? "border-primary bg-accent" : "border-border"
                  }`}
                >
                  {opt[1]}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">
              {taskScope === "assigned"
                ? "Members see only tasks assigned to them; you and admins still see everything."
                : "Everyone on the board sees every task."}
            </p>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending || !name.trim()}>
              {create.isPending ? "Creating…" : "Create"}
            </Button>
          </div>
        </form>
      </Sheet>
    </div>
  );
}
