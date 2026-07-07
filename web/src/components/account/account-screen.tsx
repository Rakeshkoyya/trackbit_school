"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";

/** Personal account: edit your name, view your sign-in identifiers, change password. */
export function AccountScreen() {
  const { me, updateProfile } = useAuth();
  const [name, setName] = useState<string | null>(null);
  const [savingName, setSavingName] = useState(false);

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [savingPw, setSavingPw] = useState(false);

  if (!me) return <div className="h-64 animate-pulse rounded-xl bg-muted" />;
  const user = me.user;
  const nameVal = name ?? user.name;
  const nameDirty = name !== null && name.trim().length > 0 && name.trim() !== user.name;

  async function saveName() {
    if (!nameDirty) return;
    setSavingName(true);
    try {
      await updateProfile(name!.trim());
      setName(null);
      toast.success("Name updated");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not update name");
    } finally {
      setSavingName(false);
    }
  }

  async function changePassword(e: React.FormEvent) {
    e.preventDefault();
    if (next.length < 8) {
      toast.error("Use at least 8 characters.");
      return;
    }
    if (next !== confirm) {
      toast.error("New passwords don't match.");
      return;
    }
    setSavingPw(true);
    try {
      await authApi.changePassword(current, next);
      setCurrent("");
      setNext("");
      setConfirm("");
      toast.success("Password changed");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not change password");
    } finally {
      setSavingPw(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Account settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">Your profile and password.</p>
      </header>

      {/* Profile */}
      <section className="mb-8 rounded-xl border border-border bg-card p-5">
        <h2 className="mb-4 text-sm font-semibold">Profile</h2>
        <div className="space-y-4">
          <div>
            <Label htmlFor="acc-name">Name</Label>
            <Input id="acc-name" value={nameVal} onChange={(e) => setName(e.target.value)} />
          </div>
          {user.username ? (
            <div>
              <Label htmlFor="acc-username">Username</Label>
              <Input id="acc-username" value={user.username} disabled />
              <p className="mt-1 text-xs text-muted-foreground">
                Your sign-in handle — it can&apos;t be changed.
              </p>
            </div>
          ) : null}
          {user.email ? (
            <div>
              <Label htmlFor="acc-email">Email</Label>
              <Input id="acc-email" value={user.email} disabled />
            </div>
          ) : null}
          {user.phone ? (
            <div>
              <Label htmlFor="acc-phone">Phone</Label>
              <Input id="acc-phone" value={user.phone} disabled />
            </div>
          ) : null}
          <Button onClick={saveName} disabled={!nameDirty || savingName}>
            {savingName ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </section>

      {/* Password */}
      <section className="rounded-xl border border-border bg-card p-5">
        <h2 className="mb-4 text-sm font-semibold">Password</h2>
        <form className="space-y-4" onSubmit={changePassword}>
          <div>
            <Label htmlFor="cur-pw">Current password</Label>
            <PasswordInput
              id="cur-pw"
              autoComplete="current-password"
              required
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="new-pw">New password</Label>
            <PasswordInput
              id="new-pw"
              autoComplete="new-password"
              required
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
          </div>
          <div>
            <Label htmlFor="conf-pw">Confirm new password</Label>
            <PasswordInput
              id="conf-pw"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={savingPw || !current || !next || !confirm}>
            {savingPw ? "Saving…" : "Change password"}
          </Button>
        </form>
      </section>
    </div>
  );
}
