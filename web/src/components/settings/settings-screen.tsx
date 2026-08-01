"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

/** Leave allowance (SF-1). These two numbers are the school's own policy, not a
 *  hard rule the app enforces: an application over either one still reaches the
 *  admin, flagged, so an emergency stays on the record instead of becoming a
 *  phone call nobody logged. */
function LeavePolicySection() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["leave-policy"], queryFn: schoolApi.leavePolicy });
  const [perYear, setPerYear] = useState<number | null>(null);
  const [perMonth, setPerMonth] = useState<number | null>(null);

  const save = useMutation({
    mutationFn: () => schoolApi.setLeavePolicy({
      leaves_per_year: perYear ?? data!.leaves_per_year,
      leaves_per_month: perMonth ?? data!.leaves_per_month,
    }),
    onSuccess: (p) => {
      qc.setQueryData(["leave-policy"], p);
      qc.invalidateQueries({ queryKey: ["leave"] });
      setPerYear(null);
      setPerMonth(null);
      toast.success("Leave policy saved");
    },
    onError: (e) => showApiError(e, "Could not save the leave policy"),
  });

  if (!data) return <div className="mt-5 h-48 animate-pulse rounded-xl bg-muted" />;

  const yearVal = perYear ?? data.leaves_per_year;
  const monthVal = perMonth ?? data.leaves_per_month;
  const dirty = perYear !== null || perMonth !== null;

  return (
    <section className="mt-5 rounded-xl border border-border bg-card p-5">
      <h2 className="mb-1 text-sm font-semibold">Leave</h2>
      <p className="mb-4 text-xs text-muted-foreground">
        How much time off each staff member gets. Requests over these limits still reach you —
        they arrive marked so you can decide.
      </p>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="leave-year">Days a year</Label>
            <Input id="leave-year" type="number" min={0} max={365} value={yearVal}
              onChange={(e) => setPerYear(Math.max(0, Math.min(365, Number(e.target.value))))} />
          </div>
          <div>
            <Label htmlFor="leave-month">Days a month</Label>
            <Input id="leave-month" type="number" min={0} max={31} value={monthVal}
              onChange={(e) => setPerMonth(Math.max(0, Math.min(31, Number(e.target.value))))} />
          </div>
        </div>
        <Button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
          {save.isPending ? "Saving…" : "Save leave policy"}
        </Button>
      </div>
    </section>
  );
}

export function SettingsScreen() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: appApi.settings });

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

  if (settings.isLoading || !settings.data) {
    return <div className="h-64 animate-pulse rounded-xl bg-muted" />;
  }
  const s = settings.data;
  const nameVal = name ?? s.name;
  const hourVal = hour ?? s.report_card_hour;
  const dirty = name !== null || hour !== null;

  return (
    <div className="max-w-2xl">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Organization settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">Your organization&apos;s details.</p>
      </header>

      {/* Org settings */}
      <section className="rounded-xl border border-border bg-card p-5">
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
            />
            <p className="mt-1 text-xs text-muted-foreground">
              When the daily wrap-up is sent to admins.
            </p>
          </div>
          <Button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
            {save.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </section>

      <LeavePolicySection />
    </div>
  );
}
