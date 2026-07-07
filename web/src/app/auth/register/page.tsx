"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, CheckCircle2, LayoutGrid, type LucideIcon, Repeat2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/ui/password-input";
import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/api-client";

// All customers are India-based — fixed to IST, no timezone picker.
const ORG_TIMEZONE = "Asia/Kolkata";

const FEATURES: [LucideIcon, string, string][] = [
  [LayoutGrid, "Boards & tasks", "A Monday-style table for every area of work."],
  [Repeat2, "Recurring routines", "Set it once; it shows up on the right days."],
  [CheckCircle2, "Assign or claim", "Everyone knows exactly what's theirs."],
  [Bell, "Gentle nudges", "Reminders that prompt, never shame."],
];

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [orgName, setOrgName] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await register({ org_name: orgName, name, email, password, timezone: ORG_TIMEZONE });
      // Land on Home and kick off the in-product guided tour.
      router.replace("/home?tour=1");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not create your organization.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-dvh lg:grid-cols-2">
      {/* Left — form */}
      <div className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-sm">
          <Link href="/" className="mb-8 block text-xl font-semibold text-primary">
            TrackBit
          </Link>
          <h1 className="text-2xl font-semibold tracking-tight">Create your organization</h1>
          <p className="mt-1 text-sm text-muted-foreground">Set up TrackBit in under a minute.</p>

          <form onSubmit={onSubmit} className="mt-6 space-y-4">
            <div>
              <Label htmlFor="org_name">Organization name</Label>
              <Input id="org_name" required value={orgName} onChange={(e) => setOrgName(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="name">Your name</Label>
              <Input id="name" required value={name} onChange={(e) => setName(e.target.value)} />
            </div>
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
              <p className="mt-1 text-xs text-muted-foreground">
                At least 8 characters. Times run on IST (India).
              </p>
            </div>
            <Button type="submit" size="lg" className="w-full" disabled={busy}>
              {busy ? "Creating…" : "Create organization"}
            </Button>
          </form>

          <p className="mt-4 text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/auth/login" className="font-medium text-primary">
              Sign in
            </Link>
          </p>
        </div>
      </div>

      {/* Right — visual panel (desktop) */}
      <aside className="relative hidden overflow-hidden bg-primary px-12 text-primary-foreground lg:flex lg:flex-col lg:justify-center">
        <div className="pointer-events-none absolute -right-16 -top-16 h-72 w-72 rounded-full bg-white/10" />
        <div className="pointer-events-none absolute -bottom-20 -left-10 h-72 w-72 rounded-full bg-white/5" />

        <div className="relative max-w-md">
          <h2 className="text-3xl font-semibold leading-tight">Run the day, not the chaos.</h2>
          <p className="mt-3 text-primary-foreground/80">
            Boards, tasks and routines your whole team can see — with calm reminders that keep
            everyone on track.
          </p>

          <ul className="mt-8 space-y-4">
            {FEATURES.map(([Icon, title, body]) => (
              <li key={title} className="flex items-start gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/15">
                  <Icon className="h-5 w-5" />
                </span>
                <span>
                  <span className="block font-medium">{title}</span>
                  <span className="block text-sm text-primary-foreground/75">{body}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>
    </main>
  );
}
