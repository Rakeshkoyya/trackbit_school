"use client";

import Link from "next/link";
import { useState } from "react";

import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/auth-api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await authApi.forgotPassword(email.trim());
      setSent(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Reset password"
      subtitle="We'll email you a link to choose a new password."
      footer={
        <Link href="/auth/login" className="font-medium text-primary">
          Back to sign in
        </Link>
      }
    >
      {sent ? (
        <p className="text-sm text-muted-foreground">
          If that email is registered, a reset link is on its way. Username-only accounts don&apos;t
          have email — ask your admin to reset your password.
        </p>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={busy}>
            {busy ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
