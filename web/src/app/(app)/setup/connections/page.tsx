"use client";

/**
 * Setup → Connections. Where a school connects Claude to its own data.
 *
 * Organised the way the task actually runs, not the way the data is modelled:
 * first the URL you paste, then the credential you generate, then the list of
 * what is connected with a way to cut each one off. The secret is rendered once,
 * in place, because that is the only moment it exists.
 */

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/lib/api-client";
import {
  TOOLSETS,
  connectionsApi,
  mcpUrl,
  type AgentAccess,
  type ApiTokenRow,
  type OAuthClient,
} from "@/lib/connections-api";

type Mode = "read" | "read_write";

function CopyField({ label, value, hint }: { label: string; value: string; hint?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <label className="text-sm font-medium text-slate-700 dark:text-slate-200">{label}</label>
        {hint ? <span className="text-xs text-slate-500 dark:text-slate-400">{hint}</span> : null}
      </div>
      <div className="flex items-stretch gap-2">
        <code className="min-w-0 flex-1 truncate rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-sm text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
          {value}
        </code>
        <button
          type="button"
          onClick={() => {
            void navigator.clipboard.writeText(value);
            setCopied(true);
            setTimeout(() => setCopied(false), 1600);
          }}
          className="shrink-0 rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}

function ScopePicker({
  selected,
  onToggle,
}: {
  selected: Set<string>;
  onToggle: (name: string) => void;
}) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {TOOLSETS.map((t) => {
        const on = selected.has(t.name);
        const sensitive = t.name === "fees" || t.name === "bands";
        return (
          <label
            key={t.name}
            className={`flex cursor-pointer gap-3 rounded-lg border p-3 transition ${
              on
                ? "border-slate-900 bg-slate-50 dark:border-slate-300 dark:bg-slate-800"
                : "border-slate-200 hover:border-slate-300 dark:border-slate-700 dark:hover:border-slate-600"
            }`}
          >
            <input
              type="checkbox"
              checked={on}
              onChange={() => onToggle(t.name)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-slate-900 dark:accent-slate-200"
            />
            <span className="min-w-0">
              <span className="block text-sm font-medium text-slate-800 dark:text-slate-100">
                {t.label}
                {sensitive ? (
                  <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
                    opt in
                  </span>
                ) : null}
              </span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">{t.hint}</span>
            </span>
          </label>
        );
      })}
    </div>
  );
}

type Issued =
  | { kind: "oauth"; clientId: string; secret: string | null }
  | { kind: "token"; secret: string };

export default function ConnectionsPage() {
  const [access, setAccess] = useState<AgentAccess | null>(null);
  const [clients, setClients] = useState<OAuthClient[]>([]);
  const [tokens, setTokens] = useState<ApiTokenRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("Claude");
  const [mode, setMode] = useState<Mode>("read");
  const [scopes, setScopes] = useState<Set<string>>(
    () => new Set(["students", "attendance", "capture", "planning", "tasks"]),
  );
  const [busy, setBusy] = useState(false);

  // The one moment the secret exists. Component state only — never written
  // anywhere it could be read back.
  const [issued, setIssued] = useState<Issued | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [c, t] = await Promise.all([
        connectionsApi.listClients(),
        connectionsApi.listTokens(),
      ]);
      setClients(c);
      setTokens(t);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load connections.");
    } finally {
      setLoading(false);
    }
  }, []);

  // The awaits matter: every setState below lands in a promise callback rather
  // than synchronously in the effect body, which is what the effect is for.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const [a, c, t] = await Promise.all([
          connectionsApi.agentAccess(),
          connectionsApi.listClients(),
          connectionsApi.listTokens(),
        ]);
        if (cancelled) return;
        setAccess(a);
        setClients(c);
        setTokens(t);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof ApiError ? e.message : "Could not load connections.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const toggle = (n: string) =>
    setScopes((prev) => {
      const next = new Set(prev);
      if (next.has(n)) next.delete(n);
      else next.add(n);
      return next;
    });

  async function changeAccess(next: AgentAccess) {
    setBusy(true);
    setError(null);
    try {
      const res = await connectionsApi.setAgentAccess(next);
      setAccess(res.agent_access);
    } catch (e) {
      setError(
        e instanceof ApiError ? e.message : "Could not change agent access.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function createOAuthClient() {
    setBusy(true);
    setError(null);
    try {
      const res = await connectionsApi.createClient({
        name,
        scopes: [...scopes],
        mode,
        confidential: true,
      });
      setIssued({ kind: "oauth", clientId: res.client.client_id, secret: res.client_secret });
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the connection.");
    } finally {
      setBusy(false);
    }
  }

  async function createToken() {
    setBusy(true);
    setError(null);
    try {
      const res = await connectionsApi.createToken({ name, scopes: [...scopes], mode });
      setIssued({ kind: "token", secret: res.secret });
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not create the token.");
    } finally {
      setBusy(false);
    }
  }

  const url = mcpUrl();

  return (
    <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-50">Connections</h1>
        <p className="max-w-prose text-sm text-slate-600 dark:text-slate-300">
          Connect Claude to this school. A connection acts with <em>your</em> authority and
          never sees more than you can see yourself — and you can cut it off at any moment.
        </p>
      </header>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </div>
      ) : null}

      {/* 0 — the gate. A new school starts with agent access off, so without
          this the screen would dead-end on "switched off" with nowhere to go. */}
      {access === "off" ? (
        <section className="space-y-3 rounded-xl border border-amber-300 bg-amber-50 p-5 dark:border-amber-700 dark:bg-amber-950/30">
          <div className="space-y-1">
            <h2 className="text-sm font-semibold text-amber-900 dark:text-amber-100">
              Agent access is off for this school
            </h2>
            <p className="text-sm text-amber-800 dark:text-amber-200">
              Nothing can connect until you turn it on. You can switch it back off at any
              time — doing so also stops every connection that is already running.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() => void changeAccess("admins")}
              className="rounded-lg bg-amber-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-amber-800 disabled:opacity-50 dark:bg-amber-200 dark:text-amber-950 dark:hover:bg-amber-100"
            >
              Allow admins to connect
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void changeAccess("all_staff")}
              className="rounded-lg border border-amber-400 px-4 py-2 text-sm font-medium text-amber-900 transition hover:bg-amber-100 disabled:opacity-50 dark:border-amber-600 dark:text-amber-100 dark:hover:bg-amber-900/40"
            >
              Allow all staff
            </button>
          </div>
        </section>
      ) : access ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 px-4 py-3 dark:border-slate-700">
          <p className="text-sm text-slate-600 dark:text-slate-300">
            Agent access:{" "}
            <strong className="text-slate-900 dark:text-slate-100">
              {access === "admins" ? "admins only" : "all staff"}
            </strong>
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                void changeAccess(access === "admins" ? "all_staff" : "admins")
              }
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
            >
              {access === "admins" ? "Allow all staff" : "Admins only"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void changeAccess("off")}
              className="rounded-lg border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/40"
            >
              Turn off
            </button>
          </div>
        </div>
      ) : null}

      {/* 1 — the URL */}
      <section className="space-y-3 rounded-xl border border-slate-200 p-5 dark:border-slate-700">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Step 1 · The server address
        </h2>
        <CopyField label="MCP server URL" value={url} hint="paste this into Claude" />
        <p className="text-xs text-slate-500 dark:text-slate-400">
          In Claude: <strong>Settings → Connectors → Add custom connector</strong>, paste this
          URL, then open <strong>Advanced settings</strong> and paste the Client ID and Secret
          from step 2.
        </p>
      </section>

      {/* 2 — the credential */}
      <section className="space-y-4 rounded-xl border border-slate-200 p-5 dark:border-slate-700">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Step 2 · Create a connection
        </h2>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Claude Desktop"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            />
            <p className="text-xs text-slate-500 dark:text-slate-400">
              What makes revoking the right one possible later.
            </p>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
              What it may do
            </label>
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as Mode)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            >
              <option value="read">Read only</option>
              <option value="read_write">Read and write</option>
            </select>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Read only is the safe default and answers most questions.
            </p>
          </div>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
            What it may reach
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Orientation and search are always included. Everything else is off unless you tick
            it — and a toolset you cannot use yourself cannot be granted.
          </p>
          <ScopePicker selected={scopes} onToggle={toggle} />
        </div>

        <div className="flex flex-wrap gap-3 pt-1">
          <button
            type="button"
            disabled={busy || scopes.size === 0}
            onClick={() => void createOAuthClient()}
            className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
          >
            {busy ? "Creating…" : "Create Client ID & Secret"}
          </button>
          <button
            type="button"
            disabled={busy || scopes.size === 0}
            onClick={() => void createToken()}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
          >
            Create a token instead
          </button>
        </div>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          <strong>Client ID &amp; Secret</strong> is what claude.ai, Desktop and mobile need. A{" "}
          <strong>token</strong> suits Claude Code and Cursor, which send a fixed header.
        </p>
      </section>

      {/* the one-time reveal */}
      {issued ? (
        <section className="space-y-4 rounded-xl border-2 border-amber-300 bg-amber-50 p-5 dark:border-amber-700 dark:bg-amber-950/30">
          <div className="space-y-1">
            <h2 className="text-sm font-semibold text-amber-900 dark:text-amber-100">
              Copy this now — you will not see it again
            </h2>
            <p className="text-xs text-amber-800 dark:text-amber-200">
              It is stored only as a hash. If you lose it, create another connection; there is
              no way to read this one back.
            </p>
          </div>
          {issued.kind === "oauth" ? (
            <div className="space-y-3">
              <CopyField label="Client ID" value={issued.clientId} />
              {issued.secret ? <CopyField label="Client Secret" value={issued.secret} /> : null}
            </div>
          ) : (
            <CopyField
              label="Token"
              value={issued.secret}
              hint="send as an Authorization header"
            />
          )}
          <button
            type="button"
            onClick={() => setIssued(null)}
            className="rounded-lg border border-amber-400 px-3 py-1.5 text-sm font-medium text-amber-900 transition hover:bg-amber-100 dark:border-amber-600 dark:text-amber-100 dark:hover:bg-amber-900/40"
          >
            I have copied it
          </button>
        </section>
      ) : null}

      {/* 3 — what is connected */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Step 3 · What is connected
        </h2>

        {loading ? (
          <p className="text-sm text-slate-500 dark:text-slate-400">Loading…</p>
        ) : clients.length === 0 && tokens.length === 0 ? (
          <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:text-slate-400">
            Nothing is connected yet.
          </p>
        ) : (
          <div className="space-y-3">
            {clients.map((c) => (
              <ConnectionRow
                key={c.id}
                title={c.name}
                subtitle={c.client_id}
                kind="Client ID & Secret"
                scopes={c.scopes}
                mode={c.mode}
                lastUsed={c.last_used_at}
                revokedAt={c.revoked_at}
                onRevoke={async () => {
                  await connectionsApi.revokeClient(c.id);
                  await refresh();
                }}
              />
            ))}
            {tokens.map((t) => (
              <ConnectionRow
                key={t.id}
                title={t.name}
                subtitle={`${t.prefix}…`}
                kind="Token"
                scopes={t.scopes}
                mode={t.mode}
                lastUsed={t.last_used_at}
                revokedAt={t.revoked_at}
                onRevoke={async () => {
                  await connectionsApi.revokeToken(t.id);
                  await refresh();
                }}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function ConnectionRow({
  title,
  subtitle,
  kind,
  scopes,
  mode,
  lastUsed,
  revokedAt,
  onRevoke,
}: {
  title: string;
  subtitle: string;
  kind: string;
  scopes: string[];
  mode: string;
  lastUsed: string | null;
  revokedAt: string | null;
  onRevoke: () => Promise<void>;
}) {
  const [working, setWorking] = useState(false);
  const revoked = Boolean(revokedAt);
  return (
    <div
      className={`flex flex-wrap items-start justify-between gap-4 rounded-xl border p-4 ${
        revoked
          ? "border-slate-200 bg-slate-50 opacity-60 dark:border-slate-800 dark:bg-slate-900/50"
          : "border-slate-200 dark:border-slate-700"
      }`}
    >
      <div className="min-w-0 space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-slate-900 dark:text-slate-50">{title}</span>
          <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {kind}
          </span>
          {revoked ? (
            <span className="rounded bg-red-100 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-red-700 dark:bg-red-950 dark:text-red-300">
              revoked
            </span>
          ) : null}
        </div>
        <code className="block truncate font-mono text-xs text-slate-500 dark:text-slate-400">
          {subtitle}
        </code>
        <p className="text-xs text-slate-500 dark:text-slate-400">
          {mode === "read_write" ? "Read and write" : "Read only"} · {scopes.join(", ")}
        </p>
        {/* Never-used is a state, not a zero. */}
        <p className="text-xs text-slate-400 dark:text-slate-500">
          {lastUsed ? `Last used ${new Date(lastUsed).toLocaleString()}` : "Never used"}
        </p>
      </div>
      {!revoked ? (
        <button
          type="button"
          disabled={working}
          onClick={async () => {
            setWorking(true);
            try {
              await onRevoke();
            } finally {
              setWorking(false);
            }
          }}
          className="shrink-0 rounded-lg border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-950/40"
        >
          {working ? "Revoking…" : "Revoke"}
        </button>
      ) : null}
    </div>
  );
}
