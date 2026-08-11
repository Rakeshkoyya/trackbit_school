"use client";

/**
 * The staff logins, edited before the school is handed over.
 *
 * The import generates a username from each person's name — `asha.rao`, plus a
 * digit when that is taken — and a random password, and shows them once. Both
 * are right often enough to be worth generating and wrong often enough to be
 * worth correcting: a school with its own employee IDs, a name misspelt in the
 * pack, two teachers whose slug collided.
 *
 * This is the only window in which a password can still be **chosen**. After it
 * the hash is all that exists and the only move is a reset — which is why the
 * generated passwords are carried into these fields rather than only printed.
 *
 * Two rules the form follows, both from `services/setup_pack/logins.py`:
 *
 *   * a username is checked **as it is typed**, against every school —
 *     `users.username` is global, so a name free here can still be taken at
 *     another school, and finding that out on submit wastes the whole batch;
 *   * a **blank password means leave it alone**. After a reload the generated
 *     ones are unreadable, so an empty field has to mean "keep", never "clear".
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Check, Loader2, RefreshCw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api-client";
import {
  type PackCredential,
  type StaffLoginRow,
  platformApi,
} from "@/lib/platform-api";
import { cn } from "@/lib/utils";

/** Mirrors `USERNAME_RE` in the service. Checked here only to keep the network
 *  quiet while somebody is mid-word — the server is still the authority. */
const SHAPE = /^[a-z0-9._-]+$/;
const MIN_USERNAME = 3;
const MIN_PASSWORD = 8;

type Draft = { username: string; password: string };
type Verdict =
  | { state: "idle" | "checking" }
  | { state: "ok" }
  | { state: "bad"; reason: string };

function localProblem(username: string): string | null {
  const u = username.trim();
  if (!u) return "A username is needed.";
  if (u.length < MIN_USERNAME) return `Too short — at least ${MIN_USERNAME} characters.`;
  if (!SHAPE.test(u)) return "Letters, numbers, dot, underscore and hyphen only.";
  return null;
}

/** One row's availability check, debounced. Lives per row so a slow answer for
 *  one teacher never overwrites a fresh answer for another — the classic bug
 *  when a single shared "checking" flag is hoisted to the table.
 *
 *  Only the SERVER's answer is state. Everything decidable here — unchanged,
 *  too short, bad characters, and "no answer for this value yet" — is derived
 *  during render, so the effect never sets state synchronously and typing does
 *  not cascade a re-render per keystroke.
 */
function useAvailability(username: string, userId: string, original: string): Verdict {
  // Keyed by the exact value it answers for: a reply that lands after the
  // operator has typed another character is simply no longer the answer.
  const [answer, setAnswer] = useState<{ value: string; verdict: Verdict } | null>(null);
  const value = username.trim().toLowerCase();
  const unchanged = value === original.toLowerCase();
  const problem = unchanged ? null : localProblem(value);
  const askable = !unchanged && !problem;

  useEffect(() => {
    if (!askable) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      platformApi
        .checkUsername(value, userId)
        .then((r) => {
          if (cancelled) return;
          setAnswer({
            value,
            verdict: r.available
              ? { state: "ok" }
              : { state: "bad", reason: r.reason ?? "Not available." },
          });
        })
        .catch(() => {
          // A failed CHECK is not a failed username. Falling back to idle
          // leaves the save to decide rather than blocking on our own outage.
          if (!cancelled) setAnswer({ value, verdict: { state: "idle" } });
        });
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [askable, value, userId]);

  if (unchanged) return { state: "idle" };
  if (problem) return { state: "bad", reason: problem };
  return answer?.value === value ? answer.verdict : { state: "checking" };
}

function Row({
  row, draft, onChange, generated,
}: {
  row: StaffLoginRow;
  draft: Draft;
  onChange: (next: Draft) => void;
  generated: string | undefined;
}) {
  const original = row.username ?? "";
  const verdict = useAvailability(draft.username, row.user_id, original);
  const pwProblem =
    draft.password.trim() && draft.password.length < MIN_PASSWORD
      ? `At least ${MIN_PASSWORD} characters.`
      : null;

  return (
    <tr className="border-t border-border/60 align-top">
      <td className="py-2 pr-3">
        <span className="text-sm">{row.name}</span>
        {row.org_role === "admin" ? (
          <Badge tone="neutral" className="ml-2">admin</Badge>
        ) : null}
      </td>
      <td className="py-2 pr-3">
        <Input
          value={draft.username}
          spellCheck={false}
          autoCapitalize="none"
          aria-label={`Username for ${row.name}`}
          className={cn("font-mono text-xs",
            verdict.state === "bad" && "border-danger")}
          onChange={(e) => onChange({ ...draft, username: e.target.value })}
        />
        <p className="mt-1 flex items-center gap-1 text-[11px]">
          {verdict.state === "checking" ? (
            <>
              <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
              <span className="text-muted-foreground">Checking…</span>
            </>
          ) : verdict.state === "ok" ? (
            <>
              <Check className="h-3 w-3 text-success" />
              <span className="text-success">Available</span>
            </>
          ) : verdict.state === "bad" ? (
            <>
              <AlertCircle className="h-3 w-3 text-danger" />
              <span className="text-danger">{verdict.reason}</span>
            </>
          ) : (
            <span className="text-muted-foreground">
              {original ? "Unchanged" : "No username yet"}
            </span>
          )}
        </p>
      </td>
      <td className="py-2">
        <Input
          value={draft.password}
          spellCheck={false}
          autoCapitalize="none"
          aria-label={`Password for ${row.name}`}
          placeholder={generated ? undefined : "leave blank to keep"}
          className={cn("font-mono text-xs", pwProblem && "border-danger")}
          onChange={(e) => onChange({ ...draft, password: e.target.value })}
        />
        <p className={cn("mt-1 text-[11px]",
          pwProblem ? "text-danger" : "text-muted-foreground")}>
          {pwProblem ?? (generated ? "Generated — change it or keep it"
            : "Blank keeps the current one")}
        </p>
      </td>
    </tr>
  );
}

export function StaffLoginsEditor({
  orgId, credentials, onSaved,
}: {
  orgId: string;
  /** What the import just generated, so the passwords are visible ONCE while
   *  they still exist. Empty after a reload, which is correct. */
  credentials: PackCredential[];
  onSaved?: () => void;
}) {
  const qc = useQueryClient();
  // Only what the operator has actually typed. Everything else is derived from
  // the server row plus the generated password, so there is no seeding effect
  // to race the fetch and no stale copy to clobber an edit in progress.
  const [edits, setEdits] = useState<Record<string, Draft>>({});
  const [savedOnce, setSavedOnce] = useState(false);

  const { data: rows, isLoading } = useQuery({
    queryKey: ["staff-logins", orgId],
    queryFn: () => platformApi.staffLogins(orgId),
  });

  const generated = useMemo(
    () => new Map(credentials.map((c) => [c.user_id, c.password])),
    [credentials],
  );

  const draftFor = (r: StaffLoginRow): Draft =>
    edits[r.user_id] ?? {
      username: r.username ?? "",
      password: generated.get(r.user_id) ?? "",
    };

  const save = useMutation({
    mutationFn: () =>
      platformApi.saveStaffLogins(orgId, (rows ?? []).map((r) => {
        const d = draftFor(r);
        return {
          user_id: r.user_id,
          username: d.username.trim().toLowerCase(),
          password: d.password.trim() ? d.password : null,
        };
      })),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["staff-logins", orgId] });
      setSavedOnce(true);
      toast.success(
        result.renamed || result.passwords_set
          ? `Saved — ${result.renamed} username${result.renamed === 1 ? "" : "s"}`
            + ` and ${result.passwords_set} password${result.passwords_set === 1 ? "" : "s"} changed`
          : "Saved — nothing needed changing");
      onSaved?.();
    },
    // The batch is all-or-nothing server-side, so the message is the whole
    // story: which username clashed, or which person's row is malformed.
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Could not save the logins"),
  });

  function copyAll() {
    const text = (rows ?? [])
      .map((r) => {
        const d = draftFor(r);
        return `${r.name}\t${d.username}\t${d.password}`;
      })
      .join("\n");
    void navigator.clipboard.writeText(text);
    toast.success("Logins copied");
  }

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Loading the staff list…</p>;
  }
  if (!rows?.length) {
    return (
      <p className="text-sm text-muted-foreground">
        This school has no staff accounts yet — import the pack first.
      </p>
    );
  }

  // Only the shapes we can judge here. A name taken at another school is the
  // server's call, and it refuses the batch with that person named.
  const blocked = rows.some((r) => {
    const d = draftFor(r);
    return Boolean(localProblem(d.username))
      || Boolean(d.password.trim() && d.password.length < MIN_PASSWORD);
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          {rows.length} staff account{rows.length === 1 ? "" : "s"}. Usernames are
          shared across every school, so each one is checked as you type.
        </p>
        <Button variant="outline" size="sm" onClick={copyAll}>Copy all</Button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="py-2 pr-3 font-medium">Name</th>
              <th className="py-2 pr-3 font-medium">Username</th>
              <th className="py-2 font-medium">Password</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <Row
                key={r.user_id}
                row={r}
                draft={draftFor(r)}
                generated={generated.get(r.user_id)}
                onChange={(next) =>
                  setEdits((prev) => ({ ...prev, [r.user_id]: next }))}
              />
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button onClick={() => save.mutate()} disabled={save.isPending || blocked}>
          {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Save the logins
        </Button>
        {savedOnce ? (
          <Badge tone="success">
            <Check className="h-3 w-3" /> Saved
          </Badge>
        ) : null}
        <Button variant="ghost" size="sm"
          onClick={() => qc.invalidateQueries({ queryKey: ["staff-logins", orgId] })}>
          <RefreshCw className="h-3.5 w-3.5" /> Reload
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">
        Every password set here is still a temporary one — the teacher is asked
        to choose her own at first sign-in. Copy this list before you leave the
        page: once saved, a password is hashed and cannot be read back.
      </p>
    </div>
  );
}
