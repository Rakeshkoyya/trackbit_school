"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { ORG_ROLES, ROLE_LABELS, type BulkMembersResult, type OrgRole } from "@/lib/types";

type CheckStatus = "idle" | "checking" | "ok" | "taken" | "invalid";
interface Row {
  id: number;
  username: string;
  password: string;
  role: OrgRole;
  check: CheckStatus;
}

let rowSeq = 0; // stable keys so per-row state survives add/remove
const blankRow = (): Row => ({ id: ++rowSeq, username: "", password: "", role: "teacher", check: "idle" });

/**
 * Username + password staff onboarding. Lives inside the "Add members" sheet as
 * the alternative to an email invite — for people who don't have email. No name
 * field: each staffer sets their own name on first login. Usernames are checked
 * for availability on blur so the admin sees collisions before saving.
 */
export function BulkAddPanel() {
  const qc = useQueryClient();
  const [rows, setRows] = useState<Row[]>([blankRow(), blankRow(), blankRow()]);
  const [result, setResult] = useState<BulkMembersResult | null>(null);
  const [copied, setCopied] = useState(false);

  const save = useMutation({
    mutationFn: () => {
      const valid = rows.filter((r) => r.username.trim() && r.password.length >= 8);
      return appApi.bulkAddMembers(
        valid.map((r) => ({ username: r.username.trim(), password: r.password, role: r.role })),
      );
    },
    onSuccess: (res) => {
      setResult(res);
      qc.invalidateQueries({ queryKey: ["members"] });
      const failed = res.results.filter((r) => !r.ok);
      if (failed.length) toast.error(`${res.created} added · ${failed.length} failed`);
      else toast.success(`${res.created} member(s) added`);
    },
    onError: (e) => showApiError(e, "Could not add members"),
  });

  function update(id: number, patch: Partial<Row>) {
    setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  }
  function reset() {
    setRows([blankRow(), blankRow(), blankRow()]);
    setResult(null);
    setCopied(false);
  }

  async function checkUsername(row: Row) {
    const raw = row.username.trim();
    if (!raw) {
      update(row.id, { check: "idle" });
      return;
    }
    update(row.id, { check: "checking" });
    try {
      const res = await appApi.checkUsername(raw);
      setRows((rs) =>
        rs.map((r) => {
          // Ignore stale responses (the field changed while we were checking).
          if (r.id !== row.id || r.username.trim().toLowerCase() !== raw.toLowerCase()) return r;
          const check: CheckStatus = res.available
            ? "ok"
            : res.error === "invalid_username"
              ? "invalid"
              : "taken";
          return { ...r, check };
        }),
      );
    } catch {
      // Network hiccup: don't block — bulk save re-validates server-side anyway.
      update(row.id, { check: "idle" });
    }
  }

  async function copySummary() {
    if (!result) return;
    const text = result.results
      .filter((r) => r.ok)
      .map((r) => `${r.username}\t${r.password}`)
      .join("\n");
    await navigator.clipboard.writeText(`Username\tPassword\n${text}`);
    setCopied(true);
    toast.success("Credentials copied");
  }

  const canSave = rows.some((r) => r.username.trim() && r.password.length >= 8);

  if (result) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          {result.created} added. Copy these credentials and share them — passwords aren&apos;t
          shown again. Each person picks their name on first login.
        </p>
        <div className="space-y-1 rounded-md border border-border bg-muted p-3 text-xs">
          {result.results.map((r, i) => (
            <div key={i} className={r.ok ? "" : "text-danger"}>
              {r.ok ? `${r.username} / ${r.password}` : `${r.username} — failed: ${r.error}`}
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <Button onClick={copySummary} className="flex-1">
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? "Copied" : "Copy credentials"}
          </Button>
          <Button variant="outline" onClick={reset}>
            Add more
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        For staff who don&apos;t have email. Give each a username + password to sign in with;
        they&apos;ll set their name and change the password on first login.
      </p>
      <div className="space-y-3">
        {rows.map((r) => (
          <div key={r.id} className="space-y-1">
            <div className="flex items-center gap-2">
              <Input
                placeholder="username"
                autoCapitalize="none"
                aria-invalid={r.check === "taken" || r.check === "invalid"}
                className={
                  r.check === "taken" || r.check === "invalid"
                    ? "border-danger focus-visible:ring-danger"
                    : undefined
                }
                value={r.username}
                onChange={(e) => update(r.id, { username: e.target.value, check: "idle" })}
                onBlur={() => checkUsername(r)}
              />
              <Input
                placeholder="password"
                value={r.password}
                onChange={(e) => update(r.id, { password: e.target.value })}
              />
              <select
                className="rounded-md border border-border bg-background px-2 py-2 text-sm"
                value={r.role}
                onChange={(e) => update(r.id, { role: e.target.value as OrgRole })}
              >
                {ORG_ROLES.map((r2) => (
                  <option key={r2} value={r2}>
                    {ROLE_LABELS[r2]}
                  </option>
                ))}
              </select>
              <button
                type="button"
                aria-label="Remove row"
                onClick={() => setRows((rs) => (rs.length > 1 ? rs.filter((x) => x.id !== r.id) : rs))}
              >
                <Trash2 className="h-4 w-4 text-muted-foreground" />
              </button>
            </div>
            {r.check === "taken" ? (
              <p className="px-1 text-xs text-danger">Username already taken.</p>
            ) : r.check === "invalid" ? (
              <p className="px-1 text-xs text-danger">
                Use 3–32 lowercase letters, numbers, dot, dash, or underscore.
              </p>
            ) : r.check === "checking" ? (
              <p className="px-1 text-xs text-muted-foreground">Checking…</p>
            ) : r.check === "ok" ? (
              <p className="px-1 text-xs text-success">Username available.</p>
            ) : null}
          </div>
        ))}
      </div>
      <Button variant="ghost" size="sm" onClick={() => setRows((rs) => [...rs, blankRow()])}>
        <Plus className="h-4 w-4" /> Add row
      </Button>
      <div className="flex justify-end pt-2">
        <Button disabled={!canSave || save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save staff"}
        </Button>
      </div>
    </div>
  );
}
