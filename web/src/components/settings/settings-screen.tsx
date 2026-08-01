"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { AttendanceMode, OrgSettings, WorkCategory } from "@/lib/types";
import { cn } from "@/lib/utils";

/** D-01: how often attendance is taken — drives what teachers are asked for,
 *  what the capture heatmap expects, and what "absent today" means. */
const ATTENDANCE_MODES: { value: AttendanceMode; label: string; hint: string }[] = [
  { value: "every_period", label: "Every period",
    hint: "A mark per timetabled period — the fullest record." },
  { value: "first_period", label: "First period only",
    hint: "One roll call a day, in period 1." },
  { value: "twice_daily", label: "Twice a day",
    hint: "Period 1 and the first period after lunch — catches who left at lunch." },
];

function SchoolSection({ s }: { s: OrgSettings }) {
  const qc = useQueryClient();
  const [address, setAddress] = useState<string | null>(null);
  const [state, setState] = useState<string | null>(null);
  const [board, setBoard] = useState<string | null>(null);
  const dirty = address !== null || state !== null || board !== null;

  const save = useMutation({
    mutationFn: () => appApi.updateSettings({
      ...(address !== null ? { address } : {}),
      ...(state !== null ? { state } : {}),
      ...(board !== null ? { board } : {}),
    }),
    onSuccess: (res) => {
      qc.setQueryData(["settings"], res);
      setAddress(null); setState(null); setBoard(null);
      toast.success("School details saved");
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  return (
    <section className="mt-5 rounded-xl border border-border bg-card p-5">
      <h2 className="mb-1 text-sm font-semibold">School</h2>
      <p className="mb-4 text-xs text-muted-foreground">
        The school code is what parents type to find the school at login. The state and
        board decide which holiday suggestions the school is offered.
      </p>
      <div className="space-y-4">
        {s.school_code ? (
          <div>
            <Label>School code</Label>
            <div className="flex items-center gap-2">
              <code className="rounded-md border border-border bg-muted/40 px-3 py-1.5 font-mono text-sm tracking-widest">
                {s.school_code}
              </code>
              <Button variant="ghost" size="sm" onClick={() => {
                navigator.clipboard.writeText(s.school_code!);
                toast.success("Code copied");
              }}>
                <Copy className="h-4 w-4" /> Copy
              </Button>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Hand it to parents; never publish it.
            </p>
          </div>
        ) : null}
        <div>
          <Label htmlFor="addr">Address</Label>
          <Input id="addr" value={address ?? s.address ?? ""}
            onChange={(e) => setAddress(e.target.value)} placeholder="Street, city" />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="state">State</Label>
            <Input id="state" value={state ?? s.state ?? ""}
              onChange={(e) => setState(e.target.value)} placeholder="e.g. Telangana" />
          </div>
          <div>
            <Label htmlFor="board">Board</Label>
            <Input id="board" value={board ?? s.board ?? ""}
              onChange={(e) => setBoard(e.target.value)} placeholder="CBSE / State board" />
          </div>
        </div>
        <Button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
          {save.isPending ? "Saving…" : "Save school details"}
        </Button>
      </div>
    </section>
  );
}

function CaptureSection({ s }: { s: OrgSettings }) {
  const qc = useQueryClient();
  const [mode, setMode] = useState<AttendanceMode | null>(null);
  const [minPct, setMinPct] = useState<number | null>(null);
  const [gapDays, setGapDays] = useState<number | null>(null);
  const dirty = mode !== null || minPct !== null || gapDays !== null;

  const save = useMutation({
    mutationFn: () => appApi.updateSettings({
      ...(mode !== null ? { attendance_mode: mode } : {}),
      ...(minPct !== null ? { min_attendance_pct: minPct } : {}),
      ...(gapDays !== null ? { homework_gap_days: gapDays } : {}),
    }),
    onSuccess: (res) => {
      qc.setQueryData(["settings"], res);
      setMode(null); setMinPct(null); setGapDays(null);
      toast.success("Capture settings saved");
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  const modeVal = mode ?? s.attendance_mode;
  return (
    <section className="mt-5 rounded-xl border border-border bg-card p-5">
      <h2 className="mb-4 text-sm font-semibold">Attendance &amp; homework</h2>
      <div className="space-y-4">
        <div>
          <Label>How often is attendance taken?</Label>
          <div className="mt-1 space-y-1.5">
            {ATTENDANCE_MODES.map((m) => (
              <button key={m.value} type="button" onClick={() => setMode(m.value)}
                className={cn(
                  "flex w-full items-start gap-2 rounded-lg border px-3 py-2 text-left",
                  modeVal === m.value ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40",
                )}>
                <span className={cn("mt-1 h-3 w-3 shrink-0 rounded-full border-2",
                  modeVal === m.value ? "border-primary bg-primary" : "border-muted-foreground/40")} />
                <span>
                  <span className="block text-sm font-medium">{m.label}</span>
                  <span className="block text-xs text-muted-foreground">{m.hint}</span>
                </span>
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label htmlFor="min-att">Minimum attendance %</Label>
            <Input id="min-att" type="number" min={0} max={100}
              value={minPct ?? s.min_attendance_pct}
              onChange={(e) => setMinPct(Math.max(0, Math.min(100, Number(e.target.value))))} />
            <p className="mt-1 text-xs text-muted-foreground">Below this, a student is drifting.</p>
          </div>
          <div>
            <Label htmlFor="gap-days">Homework unchecked after (days)</Label>
            <Input id="gap-days" type="number" min={1} max={30}
              value={gapDays ?? s.homework_gap_days}
              onChange={(e) => setGapDays(Math.max(1, Math.min(30, Number(e.target.value))))} />
            <p className="mt-1 text-xs text-muted-foreground">
              Nothing checked for this long tells the admin — never the child&apos;s record.
            </p>
          </div>
        </div>
        <Button onClick={() => save.mutate()} disabled={!dirty || save.isPending}>
          {save.isPending ? "Saving…" : "Save capture settings"}
        </Button>
      </div>
    </section>
  );
}

/** D-19/S-69: work categories — stable keys, mutable labels, retire never
 *  delete. Unticking hides a category from the picker; its historical rows keep
 *  rendering. `other` cannot be retired. */
function WorkCategoriesSection({ s }: { s: OrgSettings }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState<WorkCategory[] | null>(null);
  const [newLabel, setNewLabel] = useState("");
  const cats = draft ?? s.work_categories;

  const save = useMutation({
    mutationFn: () => appApi.updateSettings({
      // A locally-added row has a temp key; sending none lets the server mint
      // the STABLE key from the label, once (D-19 rule 1).
      work_categories: cats.map((c) => ({
        key: c.key.startsWith("__new") ? undefined : c.key,
        label: c.label, active: c.active,
      })),
    }),
    onSuccess: (res) => {
      qc.setQueryData(["settings"], res);
      qc.invalidateQueries({ queryKey: ["work-types"] });
      setDraft(null);
      toast.success("Categories saved");
    },
    onError: (e) => showApiError(e, "Could not save categories"),
  });

  const patch = (key: string, p: Partial<WorkCategory>) =>
    setDraft(cats.map((c) => (c.key === key ? { ...c, ...p } : c)));

  return (
    <section className="mt-5 rounded-xl border border-border bg-card p-5">
      <h2 className="mb-1 text-sm font-semibold">Timesheet categories</h2>
      <p className="mb-4 text-xs text-muted-foreground">
        What a teacher can pick for a non-teaching period. Rename freely — old entries
        follow the new name. Unticked categories leave the picker but keep showing on
        past days; nothing is ever deleted.
      </p>
      <div className="space-y-1.5">
        {cats.map((c) => (
          <div key={c.key} className="flex items-center gap-2">
            <input type="checkbox" checked={c.active}
              disabled={c.key === "other"}
              onChange={(e) => patch(c.key, { active: e.target.checked })}
              className="h-4 w-4 accent-[var(--primary)]" />
            <Input value={c.label} onChange={(e) => patch(c.key, { label: e.target.value })}
              className={cn("h-8", !c.active && "opacity-50")} />
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2">
        <Input value={newLabel} onChange={(e) => setNewLabel(e.target.value)}
          placeholder="Add your own, e.g. Assembly duty" className="h-8" />
        <Button variant="outline" size="sm" disabled={!newLabel.trim()}
          onClick={() => {
            setDraft([...cats.filter((c) => c.key !== "other"),
              { key: `__new_${Date.now()}`, label: newLabel.trim(), active: true },
              ...cats.filter((c) => c.key === "other")]);
            setNewLabel("");
          }}>
          <Plus className="h-4 w-4" /> Add
        </Button>
      </div>
      <Button className="mt-4" onClick={() => save.mutate()}
        disabled={draft === null || save.isPending}>
        {save.isPending ? "Saving…" : "Save categories"}
      </Button>
    </section>
  );
}

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

      <SchoolSection s={s} />
      <CaptureSection s={s} />
      <WorkCategoriesSection s={s} />
      <LeavePolicySection />
    </div>
  );
}
