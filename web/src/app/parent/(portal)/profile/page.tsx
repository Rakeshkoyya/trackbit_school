"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { ApiError } from "@/lib/api-client";
import { parentApi } from "@/lib/parent-api";

import { useParentPortal } from "../parent-context";

/** Optional credentials: OTP always works; a username/email + password is a
 *  convenience for parents who prefer a normal sign-in. */
export default function ParentProfilePage() {
  const { me } = useParentPortal();
  const qc = useQueryClient();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await parentApi.setCredentials({
        username: username.trim() || undefined,
        email: email.trim() || undefined,
        password,
      });
      toast.success("Saved. You can now sign in with a password too.");
      setPassword("");
      qc.invalidateQueries({ queryKey: ["parent", "me"] });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }

  if (!me) return null;

  return (
    <div className="space-y-4">
      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-3 text-sm font-semibold">Your account</h2>
        <dl className="space-y-1.5 text-sm">
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Name</dt>
            <dd>{me.name}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-muted-foreground">Mobile</dt>
            <dd>{me.phone ?? "—"}</dd>
          </div>
          {me.username ? (
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Username</dt>
              <dd>{me.username}</dd>
            </div>
          ) : null}
          {me.email ? (
            <div className="flex justify-between gap-2">
              <dt className="text-muted-foreground">Email</dt>
              <dd>{me.email}</dd>
            </div>
          ) : null}
        </dl>
        <p className="mt-3 text-xs text-muted-foreground">
          Number changed? Ask the school office to update it — your sign-in follows
          the number on the school&apos;s records.
        </p>
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="text-sm font-semibold">
          {me.has_password ? "Change password sign-in" : "Add a password sign-in"}
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          Optional — the OTP sign-in always works. Add a username or email plus a
          password if you prefer signing in that way.
        </p>
        <form onSubmit={save} className="mt-4 space-y-3">
          <div>
            <Label htmlFor="username">Username (optional)</Label>
            <Input
              id="username"
              autoCapitalize="none"
              placeholder={me.username ?? "e.g. ravi.kumar"}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="email">Email (optional)</Label>
            <Input
              id="email"
              type="email"
              placeholder={me.email ?? "you@example.com"}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="password">Password</Label>
            <PasswordInput
              id="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <Button type="submit" className="w-full" disabled={busy}>
            {busy ? "Saving…" : "Save credentials"}
          </Button>
        </form>
      </section>
    </div>
  );
}
