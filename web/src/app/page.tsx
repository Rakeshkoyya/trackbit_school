import type { Metadata } from "next";
import Link from "next/link";
import { Bell, Check, Hand, LayoutGrid, Sparkles } from "lucide-react";

import { RedirectIfAuthed } from "@/components/auth/redirect-if-authed";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "TrackBit — simple, stress-free task management for small teams",
  description:
    "Stop tracking work in Excel and WhatsApp. Create boards, assign or leave tasks claimable, and everyone sees what's done. Free to start; Pro is ₹500/month for the whole team.",
};

const steps = [
  {
    icon: LayoutGrid,
    title: "Create a board for each area of work",
    body: "Daily ops, exam reports, an event — anyone in your team can spin one up in seconds.",
  },
  {
    icon: Hand,
    title: "Assign it, or leave it for anyone to claim",
    body: "Push work to a person, or drop it on a public board and let ground staff claim it themselves.",
  },
  {
    icon: Check,
    title: "Everyone sees what's done",
    body: "Every assignment and hand-off is recorded and visible. Trust through traceability, not permissions.",
  },
];

const audiences = ["Schools", "Shops & sellers", "Clinics", "Agencies"];

export default function LandingPage() {
  return (
    <div className="min-h-dvh">
      <RedirectIfAuthed />
      {/* Nav */}
      <header className="mx-auto flex max-w-5xl items-center justify-between px-5 py-4">
        <span className="text-lg font-semibold tracking-tight text-primary">TrackBit</span>
        <nav className="flex items-center gap-2">
          <Link href="/auth/login">
            <Button variant="ghost" size="sm">
              Sign in
            </Button>
          </Link>
          <Link href="/auth/register">
            <Button size="sm">Get started</Button>
          </Link>
        </nav>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-3xl px-5 pb-16 pt-12 text-center sm:pt-20">
        <p className="mb-4 inline-flex items-center gap-1.5 rounded-full bg-accent px-3 py-1 text-xs font-medium text-accent-foreground">
          <Sparkles className="h-3.5 w-3.5" /> Built for teams of 5–25
        </p>
        <h1 className="text-balance text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
          The whole team&apos;s work, in one calm place.
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-pretty text-lg text-muted-foreground">
          Anyone can create boards and tasks, assign work to anyone, and everyone sees what&apos;s
          done. No heavy permissions, no dread — just today&apos;s work, finished.
        </p>
        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/auth/register" className="w-full sm:w-auto">
            <Button size="lg" className="w-full sm:w-auto">
              Create your organization
            </Button>
          </Link>
          <Link href="/auth/login" className="w-full sm:w-auto">
            <Button size="lg" variant="outline" className="w-full sm:w-auto">
              Sign in
            </Button>
          </Link>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">Free to start · no card required</p>
      </section>

      {/* Problem */}
      <section className="border-y border-border bg-card">
        <div className="mx-auto max-w-3xl px-5 py-14 text-center">
          <h2 className="text-2xl font-semibold tracking-tight">
            Excel and WhatsApp groups weren&apos;t built for this.
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
            Tasks get lost in chat. Nobody&apos;s sure who&apos;s doing what. The big project tools
            are overkill. TrackBit does one job well: track work, celebrate done, forgive missed.
          </p>
        </div>
      </section>

      {/* How it works */}
      <section className="mx-auto max-w-5xl px-5 py-16">
        <h2 className="text-center text-2xl font-semibold tracking-tight">How it works</h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-3">
          {steps.map((s, i) => {
            const Icon = s.icon;
            return (
              <div key={s.title} className="rounded-lg border border-border bg-card p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent text-accent-foreground">
                  <Icon className="h-5 w-5" />
                </div>
                <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Step {i + 1}
                </p>
                <h3 className="mt-1 font-medium">{s.title}</h3>
                <p className="mt-2 text-sm text-muted-foreground">{s.body}</p>
              </div>
            );
          })}
        </div>
      </section>

      {/* Who it's for */}
      <section className="border-y border-border bg-card">
        <div className="mx-auto flex max-w-3xl flex-col items-center px-5 py-12">
          <p className="text-sm font-medium text-muted-foreground">Made for small teams like</p>
          <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
            {audiences.map((a) => (
              <span
                key={a}
                className="rounded-full border border-border bg-background px-4 py-1.5 text-sm font-medium"
              >
                {a}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="mx-auto max-w-3xl px-5 py-16">
        <h2 className="text-center text-2xl font-semibold tracking-tight">
          One simple price for the whole team
        </h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-2">
          <div className="rounded-lg border border-border bg-card p-6">
            <h3 className="font-medium">Free</h3>
            <p className="mt-1 text-3xl font-semibold">₹0</p>
            <p className="mt-1 text-sm text-muted-foreground">To get going.</p>
            <ul className="mt-5 space-y-2 text-sm">
              {["Up to 2 boards", "Up to 8 members", "The full daily loop", "Board reports"].map(
                (f) => (
                  <li key={f} className="flex items-center gap-2">
                    <Check className="h-4 w-4 text-success" /> {f}
                  </li>
                ),
              )}
            </ul>
          </div>
          <div className="rounded-lg border-2 border-primary bg-card p-6">
            <div className="flex items-center justify-between">
              <h3 className="font-medium">Pro</h3>
              <span className="rounded-full bg-primary px-2.5 py-0.5 text-xs font-medium text-primary-foreground">
                Everything
              </span>
            </div>
            <p className="mt-1 text-3xl font-semibold">
              ₹500<span className="text-base font-normal text-muted-foreground">/month</span>
            </p>
            <p className="mt-1 text-sm text-muted-foreground">Flat — for the whole organization.</p>
            <ul className="mt-5 space-y-2 text-sm">
              {[
                "Unlimited boards & members",
                "Org dashboard & report cards",
                "Reminders & nudges",
                "Photo proof & attachments",
              ].map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <Check className="h-4 w-4 text-success" /> {f}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <p className="mt-4 text-center text-xs text-muted-foreground">
          No per-seat math. One price, your whole team.
        </p>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-3xl px-5 pb-20">
        <div className="rounded-xl border border-border bg-accent px-6 py-12 text-center">
          <Bell className="mx-auto h-7 w-7 text-accent-foreground" />
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-accent-foreground">
            Set it up in under five minutes.
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-accent-foreground/80">
            Create your organization, add your team, assign the first task. They&apos;ll get a link
            and they&apos;re in — no passwords to manage.
          </p>
          <Link href="/auth/register" className="mt-6 inline-block">
            <Button size="lg">Create your organization</Button>
          </Link>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto max-w-5xl px-5 py-8 text-center text-xs text-muted-foreground">
          © {new Date().getFullYear()} TrackBit · Simple, open, stress-free task management.
        </div>
      </footer>
    </div>
  );
}
