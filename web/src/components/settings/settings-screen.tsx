"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";

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
    </div>
  );
}
