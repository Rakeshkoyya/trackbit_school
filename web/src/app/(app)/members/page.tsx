"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, MoreVertical, Plus, Search, Shield, UserMinus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BulkAddPanel } from "@/components/members/bulk-add-panel";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { ORG_ROLES, ROLE_LABELS, type Member, type OrgRole } from "@/lib/types";

function timeAgo(iso: string | null): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

/** Email invite → emails the join link to the invitee, with a copyable fallback link. */
function InvitePanel() {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<OrgRole>("teacher");
  const [result, setResult] = useState<{
    name: string;
    email: string;
    invite_url: string;
    pending: boolean;
  } | null>(null);

  const invite = useMutation({
    mutationFn: () => appApi.inviteMember({ name: name.trim(), email: email.trim(), role }),
    onSuccess: (res) => {
      setResult({ name: res.name, email: email.trim(), invite_url: res.invite_url, pending: res.pending });
      qc.invalidateQueries({ queryKey: ["members"] });
    },
    onError: (e) => showApiError(e, "Could not invite"),
  });

  function reset() {
    setName("");
    setEmail("");
    setRole("teacher");
    setResult(null);
  }

  if (result) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{result.name}</span> was added and we emailed
          an invite to <span className="font-medium text-foreground">{result.email}</span>. If it
          doesn’t arrive, share this link so they can{" "}
          {result.pending ? "set a password and sign in" : "sign in"}:
        </p>
        <div className="flex items-center gap-2 rounded-md border border-border bg-muted/40 px-3 py-2">
          <span className="min-w-0 flex-1 truncate text-xs">{result.invite_url}</span>
          <button
            type="button"
            onClick={() => {
              navigator.clipboard.writeText(result.invite_url);
              toast.success("Link copied");
            }}
            className="inline-flex shrink-0 items-center gap-1 text-xs font-medium text-primary"
          >
            <Copy className="h-3.5 w-3.5" /> Copy
          </button>
        </div>
        <p className="text-xs text-muted-foreground">This link works once and expires in 7 days.</p>
        <Button variant="ghost" className="w-full" onClick={reset}>
          <Plus className="h-4 w-4" /> Invite another
        </Button>
      </div>
    );
  }

  return (
    <form
      className="space-y-4"
      onSubmit={(e) => {
        e.preventDefault();
        if (name.trim() && email.trim()) invite.mutate();
      }}
    >
      <div>
        <Label htmlFor="m-name">Name</Label>
        <Input id="m-name" autoFocus required value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <div>
        <Label htmlFor="m-email">Email</Label>
        <Input
          id="m-email"
          type="email"
          required
          placeholder="name@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>
      <div>
        <Label>Role</Label>
        <div className="grid grid-cols-2 gap-2">
          {ORG_ROLES.map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRole(r)}
              className={`rounded-md border px-3 py-2.5 text-sm ${
                role === r ? "border-primary bg-accent" : "border-border"
              }`}
            >
              {ROLE_LABELS[r]}
            </button>
          ))}
        </div>
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <Button type="submit" disabled={invite.isPending || !name.trim() || !email.trim()}>
          {invite.isPending ? "Sending…" : "Send invite"}
        </Button>
      </div>
    </form>
  );
}

/** One "Add" entry point: invite by email, or username+password for staff without email. */
function AddMemberSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [mode, setMode] = useState<"invite" | "bulk">("invite");
  return (
    <Sheet
      open={open}
      onOpenChange={(v) => {
        if (!v) setMode("invite");
        onOpenChange(v);
      }}
      title="Add members"
    >
      <div className="mb-4 grid grid-cols-2 gap-1 rounded-lg bg-muted p-1 text-sm">
        {(
          [
            ["invite", "Invite by email"],
            ["bulk", "Username & password"],
          ] as const
        ).map(([m, label]) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={`rounded-md px-3 py-1.5 font-medium transition-colors ${
              mode === m ? "bg-card text-foreground shadow-sm" : "text-muted-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      {mode === "invite" ? <InvitePanel /> : <BulkAddPanel />}
    </Sheet>
  );
}

function MembersInner() {
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  const [actionsFor, setActionsFor] = useState<Member | null>(null);
  const [query, setQuery] = useState("");
  const { data } = useQuery({ queryKey: ["members"], queryFn: appApi.members });

  const changeRole = useMutation({
    mutationFn: ({ m, role }: { m: Member; role: OrgRole }) => appApi.changeRole(m.user_id, role),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["members"] });
      toast.success("Role updated");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not change role"),
  });
  const remove = useMutation({
    mutationFn: (m: Member) => appApi.removeMember(m.user_id),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["members"] });
      toast.success(
        res.orphaned_tasks > 0
          ? `Removed · ${res.orphaned_tasks} task(s) now unassigned`
          : "Member removed",
      );
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not remove"),
  });
  const resetPw = useMutation({
    mutationFn: ({ m, password }: { m: Member; password?: string }) =>
      appApi.resetMemberPassword(m.user_id, password),
    onSuccess: (res) => {
      if (res.mode === "link_sent") toast.success("Reset link sent");
      else toast.success(`Temp password set: ${res.password}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not reset"),
  });

  function onReset(m: Member) {
    if (m.email) {
      resetPw.mutate({ m });
      return;
    }
    const pw = window.prompt(`New temporary password for ${m.name} (min 8 chars):`);
    if (pw === null) return;
    if (pw.length < 8) {
      toast.error("Password must be at least 8 characters.");
      return;
    }
    resetPw.mutate({ m, password: pw });
  }

  const members = data?.members ?? [];
  const needle = query.trim().toLowerCase();
  const filtered = needle
    ? members.filter((m) =>
        [m.name, m.email, m.username, m.phone].some((f) => f?.toLowerCase().includes(needle)),
      )
    : members;

  return (
    <div>
      <header className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Members ({members.length})</h1>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </header>

      <div className="relative mb-4">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          className="pl-9"
          placeholder="Search by name, email, or username…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search members"
        />
      </div>

      {filtered.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          {needle ? `No members match “${query.trim()}”.` : "No members yet."}
        </p>
      ) : (
        <div className="space-y-2">
          {filtered.map((m) => (
            <div key={m.user_id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3">
              <Avatar name={m.name} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">
                  {m.name}
                  <Badge tone={m.role === "admin" ? "primary" : "neutral"} className="ml-2">
                    {m.role === "admin" ? <Shield className="h-3 w-3" /> : null} {ROLE_LABELS[m.role]}
                  </Badge>
                  {m.pending ? <Badge className="ml-2">pending</Badge> : null}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {m.email || m.username || m.phone || "no contact"} · active {timeAgo(m.last_active_at)}
                </p>
              </div>
              {/* Desktop: inline actions. Mobile: collapse into a kebab → sheet so
                  the buttons don't crowd out the member name (narrow screens). */}
              <div className="hidden shrink-0 items-center gap-1 lg:flex">
                <Button variant="ghost" size="sm" onClick={() => onReset(m)}>
                  Reset password
                </Button>
                <select
                  aria-label={`Change role for ${m.name}`}
                  value={m.role}
                  onChange={(e) => changeRole.mutate({ m, role: e.target.value as OrgRole })}
                  className="rounded-md border border-border bg-card px-2 py-1.5 text-sm"
                >
                  {ORG_ROLES.map((r) => (
                    <option key={r} value={r}>
                      {ROLE_LABELS[r]}
                    </option>
                  ))}
                </select>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Remove member"
                  onClick={() => remove.mutate(m)}
                >
                  <UserMinus className="h-4 w-4 text-danger" />
                </Button>
              </div>
              <Button
                variant="ghost"
                size="icon"
                aria-label={`Actions for ${m.name}`}
                className="shrink-0 lg:hidden"
                onClick={() => setActionsFor(m)}
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      )}

      <AddMemberSheet open={addOpen} onOpenChange={setAddOpen} />

      {/* Mobile action menu — mirrors the desktop inline buttons. */}
      <Sheet
        open={actionsFor !== null}
        onOpenChange={(v) => {
          if (!v) setActionsFor(null);
        }}
        title={actionsFor?.name ?? "Member"}
      >
        {actionsFor ? (
          <div className="space-y-2">
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={() => {
                onReset(actionsFor);
                setActionsFor(null);
              }}
            >
              Reset password
            </Button>
            <div className="rounded-md border border-border px-3 py-2">
              <Label htmlFor="role-select" className="mb-1 flex items-center gap-2">
                <Shield className="h-4 w-4" /> Role
              </Label>
              <select
                id="role-select"
                value={actionsFor.role}
                onChange={(e) => {
                  changeRole.mutate({ m: actionsFor, role: e.target.value as OrgRole });
                  setActionsFor(null);
                }}
                className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              >
                {ORG_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {ROLE_LABELS[r]}
                  </option>
                ))}
              </select>
            </div>
            <Button
              variant="outline"
              className="w-full justify-start text-danger"
              onClick={() => {
                remove.mutate(actionsFor);
                setActionsFor(null);
              }}
            >
              <UserMinus className="h-4 w-4" />
              Remove member
            </Button>
          </div>
        ) : null}
      </Sheet>
    </div>
  );
}

export default function MembersPage() {
  return (
    <AuthGuard requireRole="admin">
      <MembersInner />
    </AuthGuard>
  );
}
