"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/api-client";

export default function SetPasswordPage() {
  const { me, loading, setPassword } = useAuth();
  const router = useRouter();
  const user = me?.user;
  const [name, setName] = useState("");
  const [seededFor, setSeededFor] = useState<string | undefined>(undefined);
  const [pw, setPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!loading && !me) router.replace("/auth/login");
  }, [loading, me, router]);

  // Seed the name once per user (React's "adjust state during render" pattern —
  // no effect needed). Leave it blank when the name is still the username
  // placeholder (bulk/username staff) so they're prompted to enter their own.
  if (user && seededFor !== user.id) {
    setSeededFor(user.id);
    setName(user.name && user.name !== user.username ? user.name : "");
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (pw.length < 8) {
      toast.error("Use at least 8 characters.");
      return;
    }
    if (pw !== confirm) {
      toast.error("Passwords don't match.");
      return;
    }
    setBusy(true);
    try {
      await setPassword(pw, name);
      router.replace("/tasks");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not set password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Finish setting up" subtitle="Add your name and choose a password.">
      <form onSubmit={onSubmit} className="space-y-4">
        {user?.email ? (
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              value={user.email}
              readOnly
              tabIndex={-1}
              aria-readonly
              className="cursor-not-allowed bg-muted text-muted-foreground"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              You&apos;ll sign in with this email — it can&apos;t be changed here.
            </p>
          </div>
        ) : null}
        {user?.username ? (
          <div>
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              value={user.username}
              readOnly
              tabIndex={-1}
              aria-readonly
              className="cursor-not-allowed bg-muted text-muted-foreground"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              This is how you&apos;ll sign in — it can&apos;t be changed.
            </p>
          </div>
        ) : null}
        <div>
          <Label htmlFor="name">Your name</Label>
          <Input
            id="name"
            autoFocus
            placeholder="e.g. Ravi Kumar"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="pw">New password</Label>
          <PasswordInput
            id="pw"
            autoComplete="new-password"
            required
            value={pw}
            onChange={(e) => setPw(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="confirm">Confirm password</Label>
          <PasswordInput
            id="confirm"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
          />
        </div>
        <Button type="submit" size="lg" className="w-full" disabled={busy}>
          {busy ? "Saving…" : "Save & continue"}
        </Button>
      </form>
    </AuthShell>
  );
}
