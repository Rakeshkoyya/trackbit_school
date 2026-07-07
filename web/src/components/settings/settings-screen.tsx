"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Crown, ExternalLink } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";

const PRO_FEATURES = [
  "Unlimited boards & members",
  "End-of-day report card",
  "Notes & photo attachments",
  "Critical alarm-style reminders",
  "Full report history",
];

export function SettingsScreen() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: appApi.settings });
  const billing = useQuery({ queryKey: ["billing"], queryFn: appApi.billing });

  const [name, setName] = useState<string | null>(null);
  const [hour, setHour] = useState<number | null>(null);

  const save = useMutation({
    mutationFn: () =>
      appApi.updateSettings({
        ...(name !== null ? { name } : {}),
        ...(hour !== null ? { report_card_hour: hour } : {}),
      }),
    onSuccess: (s) => {
      qc.setQueryData(["settings"], s);
      setName(null);
      setHour(null);
      toast.success("Settings saved");
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  const checkout = useMutation({
    mutationFn: () => appApi.startCheckout(),
    onSuccess: (res) => {
      if (!res.configured) {
        toast(res.message ?? "Billing isn't set up yet.");
        return;
      }
      if (res.short_url) window.location.href = res.short_url;
    },
    onError: (e) => showApiError(e, "Could not start checkout"),
  });

  if (settings.isLoading || !settings.data) {
    return <div className="h-64 animate-pulse rounded-xl bg-muted" />;
  }
  const s = settings.data;
  const b = billing.data;
  const isPro = s.plan === "pro";
  const nameVal = name ?? s.name;
  const hourVal = hour ?? s.report_card_hour;
  const dirty = name !== null || hour !== null;

  return (
    <div className="max-w-2xl">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Organization settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">Organization & billing.</p>
      </header>

      {/* Org settings */}
      <section className="mb-8 rounded-xl border border-border bg-card p-5">
        <h2 className="mb-4 text-sm font-semibold">Organization</h2>
        <div className="space-y-4">
          <div>
            <Label htmlFor="org-name">Name</Label>
            <Input id="org-name" value={nameVal} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="tz">Timezone</Label>
            <Input id="tz" value={s.timezone} disabled />
            <p className="mt-1 text-xs text-muted-foreground">
              Days, due times, and digests follow this zone.
            </p>
          </div>
          <div>
            <Label htmlFor="rc-hour">Report-card hour (0–23)</Label>
            <Input
              id="rc-hour"
              type="number"
              min={0}
              max={23}
              value={hourVal}
              onChange={(e) => setHour(Math.max(0, Math.min(23, Number(e.target.value))))}
              disabled={!s.limits.report_card}
            />
            <p className="mt-1 text-xs text-muted-foreground">
              {s.limits.report_card
                ? "When the daily wrap-up is sent to admins."
                : "End-of-day report card is a Pro feature."}
            </p>
          </div>
          <Button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </section>

      {/* Billing */}
      <section className="rounded-xl border border-border bg-card p-5">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Plan</h2>
          <span
            className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
              isPro ? "bg-success/15 text-success" : "bg-muted text-muted-foreground"
            }`}
          >
            {isPro ? <Crown className="h-3 w-3" /> : null}
            {isPro ? "Pro" : "Free"}
            {s.plan_status === "grace" ? " · payment due" : ""}
          </span>
        </div>

        {!isPro ? (
          <div className="mt-3">
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-semibold">₹500</span>
              <span className="text-sm text-muted-foreground">/ month · whole org</span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              One flat price — no per-seat math. You&apos;re using {s.usage.boards}/
              {s.limits.boards} boards and {s.usage.members}/{s.limits.members} members.
            </p>
            <ul className="mt-4 space-y-1.5">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-center gap-2 text-sm">
                  <Check className="h-4 w-4 text-success" /> {f}
                </li>
              ))}
            </ul>
            <Button className="mt-4" onClick={() => checkout.mutate()} disabled={checkout.isPending}>
              <Crown className="h-4 w-4" /> Upgrade to Pro
            </Button>
            {b && !b.configured ? (
              <p className="mt-2 text-xs text-muted-foreground">
                Checkout isn&apos;t live yet — billing keys aren&apos;t configured on this server.
              </p>
            ) : null}
          </div>
        ) : (
          <div className="mt-3 text-sm text-muted-foreground">
            <p>You&apos;re on Pro — ₹500/month, the whole org.</p>
            {s.plan_renews_at ? (
              <p className="mt-1">
                Renews {new Date(s.plan_renews_at).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                })}
                .
              </p>
            ) : null}
          </div>
        )}

        {/* Invoices */}
        {b && b.invoices.length > 0 ? (
          <div className="mt-5 border-t border-border pt-4">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Invoices
            </h3>
            <ul className="space-y-1.5">
              {b.invoices.map((inv) => (
                <li key={inv.id} className="flex items-center justify-between text-sm">
                  <span>{new Date(inv.created_at).toLocaleDateString()}</span>
                  <span className="flex items-center gap-2 text-muted-foreground">
                    ₹{(inv.amount / 100).toFixed(0)} · {inv.status}
                    <ExternalLink className="h-3 w-3 opacity-40" />
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>
    </div>
  );
}
