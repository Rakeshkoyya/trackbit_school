"use client";

/**
 * The consent screen Claude sends the user to.
 *
 * It lives inside the `(app)` shell on purpose: that shell already requires a
 * signed-in staff member, so consent is always tied to a real member of this
 * school rather than to whoever happens to hold the browser.
 *
 * The screen never builds the redirect back to Claude itself — it posts the
 * approval and follows the URL the server returns. That keeps the authorization
 * code on the server side of the trust boundary until the moment it is handed
 * over.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ApiError } from "@/lib/api-client";
import { connectionsApi, serverOrigin, type ConsentSummary } from "@/lib/connections-api";

export default function OAuthConsentPage() {
  const params = useSearchParams();
  const router = useRouter();

  const grant = useMemo(
    () => ({
      client_id: params.get("client_id") ?? "",
      redirect_uri: params.get("redirect_uri") ?? "",
      code_challenge: params.get("code_challenge") ?? "",
      code_challenge_method: params.get("code_challenge_method") ?? "S256",
      scope: params.get("scope"),
      state: params.get("state"),
      resource: params.get("resource"),
      issuer: serverOrigin(),
    }),
    [params],
  );

  const [summary, setSummary] = useState<ConsentSummary | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // A malformed link is a fact about the URL, not something that happens — so
  // it is derived, not set from an effect.
  const paramsError = grant.client_id
    ? null
    : "This link is missing its connector details. Start again from Claude.";
  const error = paramsError ?? loadError;

  useEffect(() => {
    if (!grant.client_id) return;
    let cancelled = false;
    void (async () => {
      try {
        const s = await connectionsApi.consentSummary(grant.client_id, grant.scope);
        if (!cancelled) setSummary(s);
      } catch (e) {
        if (!cancelled) {
          setLoadError(
            e instanceof ApiError ? e.message : "Could not load this connection.",
          );
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [grant.client_id, grant.scope]);

  const approve = useCallback(async () => {
    setBusy(true);
    setLoadError(null);
    try {
      const { redirect_to } = await connectionsApi.grantConsent(grant);
      // A full navigation, not a router push: the destination is Claude, not us.
      window.location.href = redirect_to;
    } catch (e) {
      setLoadError(
        e instanceof ApiError ? e.message : "Could not complete the connection.",
      );
      setBusy(false);
    }
  }, [grant]);

  if (error) {
    return (
      <div className="mx-auto w-full max-w-lg px-4 py-16">
        <div className="rounded-xl border border-red-200 bg-red-50 p-6 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/50 dark:text-red-200">
          <p className="font-medium">This connection could not be completed.</p>
          <p className="mt-1">{error}</p>
        </div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="mx-auto w-full max-w-lg px-4 py-16 text-sm text-slate-500 dark:text-slate-400">
        Loading…
      </div>
    );
  }

  const writes = summary.mode === "read_write" && summary.writes.length > 0;

  return (
    <div className="mx-auto w-full max-w-lg space-y-6 px-4 py-12">
      <header className="space-y-2">
        <h1 className="text-xl font-semibold text-slate-900 dark:text-slate-50">
          Connect {summary.client_name} to {summary.org_name}?
        </h1>
        <p className="text-sm text-slate-600 dark:text-slate-300">
          It will act as <strong>{summary.member_name}</strong> and can see exactly what you can
          see — no more.
        </p>
      </header>

      <section className="space-y-4 rounded-xl border border-slate-200 p-5 dark:border-slate-700">
        <div className="space-y-1">
          <p className="text-sm font-medium text-slate-800 dark:text-slate-100">
            {summary.mode === "read_write" ? "Read and write" : "Read only"}
          </p>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            {summary.tool_count} tools across {summary.domains.length}{" "}
            {summary.domains.length === 1 ? "area" : "areas"}.
          </p>
        </div>

        <ul className="space-y-1.5">
          {summary.domains.map((d) => (
            <li
              key={d}
              className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-200"
            >
              <span aria-hidden className="text-slate-400">
                •
              </span>
              {d}
            </li>
          ))}
        </ul>

        {writes ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 dark:border-amber-800 dark:bg-amber-950/30">
            <p className="text-xs font-medium text-amber-900 dark:text-amber-100">
              This connection can change {summary.writes.length}{" "}
              {summary.writes.length === 1 ? "thing" : "things"}
            </p>
            <p className="mt-1 text-xs text-amber-800 dark:text-amber-200">
              {summary.writes.join(", ")}
            </p>
          </div>
        ) : (
          <p className="text-xs text-slate-500 dark:text-slate-400">
            It cannot change anything — this connection is read only.
          </p>
        )}

        {summary.scopes.includes("fees") ? (
          <p className="text-xs text-amber-800 dark:text-amber-200">Includes fee data.</p>
        ) : null}
      </section>

      <div className="flex gap-3">
        <button
          type="button"
          disabled={busy}
          onClick={() => void approve()}
          className="flex-1 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-slate-800 disabled:opacity-50 dark:bg-slate-100 dark:text-slate-900 dark:hover:bg-white"
        >
          {busy ? "Connecting…" : "Connect"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => router.back()}
          className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-600 dark:text-slate-200 dark:hover:bg-slate-800"
        >
          Cancel
        </button>
      </div>

      <p className="text-xs text-slate-500 dark:text-slate-400">
        You can revoke this at any time from Setup → Connections. Revoking stops it
        immediately, not at the next sign-in.
      </p>
    </div>
  );
}
