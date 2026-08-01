"use client";

// My leave — apply, and see where each application got to.
//
// The balance sits at the top because it is what a teacher wants to know before
// they ask. Applying over the school's allowance is allowed: the form warns, and
// the request reaches the admin flagged. Blocking it here would just push the
// conversation off the system.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarPlus, Loader2, Plane } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { LeaveRequest, LeaveStatus } from "@/lib/school-types";

type Tone = "neutral" | "success" | "warning" | "danger" | "primary" | "outline";

const STATUS: Record<LeaveStatus, { label: string; tone: Tone }> = {
  pending: { label: "Waiting for approval", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Declined", tone: "danger" },
  cancelled: { label: "Withdrawn", tone: "neutral" },
};

const iso = (d: Date) => d.toISOString().slice(0, 10);

function span(r: LeaveRequest): string {
  const opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  const from = new Date(`${r.start_date}T00:00:00`).toLocaleDateString("en-IN", opts);
  if (r.start_date === r.end_date) return from;
  return `${from} – ${new Date(`${r.end_date}T00:00:00`).toLocaleDateString("en-IN", opts)}`;
}

function ApplySheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [from, setFrom] = useState(() => iso(new Date()));
  const [to, setTo] = useState(() => iso(new Date()));
  const [reason, setReason] = useState("");
  // D-04 — half a day. It is one date by definition, so choosing it collapses
  // the range; the AM/PM half is what tells the cover board which periods (S-31).
  const [half, setHalf] = useState<null | "am" | "pm">(null);

  const apply = useMutation({
    mutationFn: () => schoolApi.applyLeave({
      start_date: from, end_date: half ? from : to, reason: reason.trim(),
      is_half_day: !!half, portion: half,
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["leave"] });
      toast.success(
        res.warnings.length
          ? "Sent — your admin will see it's over the usual allowance"
          : "Leave request sent");
      setReason(""); setHalf(null);
      onClose();
    },
    onError: (e) => showApiError(e, "Could not send the request"),
  });

  const backwards = !half && to < from;

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) { setHalf(null); onClose(); } }}
      title="Apply for leave">
      <form className="space-y-4"
        onSubmit={(e) => { e.preventDefault(); if (!backwards && reason.trim()) apply.mutate(); }}>
        <div className="flex gap-1.5">
          {([
            { key: null, label: "Full day(s)" },
            { key: "am" as const, label: "Half — morning" },
            { key: "pm" as const, label: "Half — afternoon" },
          ]).map((opt) => {
            const active = half === opt.key;
            return (
              <button key={opt.label} type="button" aria-pressed={active}
                onClick={() => setHalf(opt.key)}
                className={`flex-1 rounded-lg border px-2 py-2 text-xs font-medium transition-colors ${active ? "border-primary bg-accent text-accent-foreground" : "border-border bg-card text-muted-foreground"}`}>
                {opt.label}
              </button>
            );
          })}
        </div>

        <div className={half ? "" : "grid grid-cols-2 gap-3"}>
          <div>
            <Label htmlFor="from">{half ? "Date" : "From"}</Label>
            <Input id="from" type="date" value={from}
              onChange={(e) => {
                setFrom(e.target.value);
                if (to < e.target.value) setTo(e.target.value);
              }} />
          </div>
          {half ? null : (
            <div>
              <Label htmlFor="to">To</Label>
              <Input id="to" type="date" value={to} min={from}
                onChange={(e) => setTo(e.target.value)} />
            </div>
          )}
        </div>

        {half ? (
          <p className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
            Counts as half a day of your allowance. Your {half === "am" ? "morning" : "afternoon"}{" "}
            periods are the ones the school will arrange cover for.
          </p>
        ) : null}

        <div>
          <Label htmlFor="reason">Reason</Label>
          <Input id="reason" value={reason} onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. Fever, family function" />
          <p className="mt-1 text-xs text-muted-foreground">
            Your admin sees this, so a line is enough.
          </p>
        </div>

        <Button type="submit" className="w-full"
          disabled={apply.isPending || backwards || reason.trim().length < 3}>
          {apply.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarPlus className="h-4 w-4" />}
          Send request
        </Button>
      </form>
    </Sheet>
  );
}

function MyLeaveInner() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();

  const { data: balance } = useQuery({ queryKey: ["leave", "balance"], queryFn: () => schoolApi.leaveBalance() });
  const { data, isLoading } = useQuery({
    queryKey: ["leave", "mine"],
    queryFn: () => schoolApi.leaveRequests({ mine: true }),
  });

  const withdraw = useMutation({
    mutationFn: (id: string) => schoolApi.cancelLeave(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leave"] });
      toast.success("Request withdrawn");
    },
    onError: (e) => showApiError(e, "Could not withdraw"),
  });

  const requests = data?.requests ?? [];

  return (
    <div className="pb-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="My leave" subtitle="Apply for time off and track each request." />
        <Button size="sm" onClick={() => setOpen(true)}>
          <CalendarPlus className="h-4 w-4" /> Apply for leave
        </Button>
      </div>

      {balance ? (
        <div className="mb-5 grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-border bg-card px-4 py-3">
            <p className="text-xs text-muted-foreground">Left this year</p>
            <p className="mt-0.5 text-xl font-semibold tabular-nums">{balance.remaining}</p>
            <p className="text-xs text-muted-foreground">of {balance.allowed_per_year} days</p>
          </div>
          <div className="rounded-xl border border-border bg-card px-4 py-3">
            <p className="text-xs text-muted-foreground">Taken</p>
            <p className="mt-0.5 text-xl font-semibold tabular-nums">{balance.approved_days}</p>
            <p className="text-xs text-muted-foreground">approved days</p>
          </div>
          <div className="rounded-xl border border-border bg-card px-4 py-3">
            <p className="text-xs text-muted-foreground">Waiting</p>
            <p className="mt-0.5 text-xl font-semibold tabular-nums">{balance.pending_days}</p>
            <p className="text-xs text-muted-foreground">
              {balance.allowed_per_month} day{balance.allowed_per_month === 1 ? "" : "s"} a month
            </p>
          </div>
        </div>
      ) : null}

      {isLoading ? (
        <div className="h-40 animate-pulse rounded-xl border border-border bg-card" />
      ) : requests.length === 0 ? (
        <EmptyState icon={Plane} title="No leave requested yet"
          body="When you apply, it appears here with its status."
          action={<Button size="sm" onClick={() => setOpen(true)}>
            <CalendarPlus className="h-4 w-4" /> Apply for leave
          </Button>} />
      ) : (
        <div className="space-y-2">
          {requests.map((r) => (
            <div key={r.id} className="rounded-lg border border-border bg-card px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium">
                  {span(r)} · {r.is_half_day
                    ? `half day (${r.portion === "pm" ? "afternoon" : "morning"})`
                    : `${r.days} day${r.days === 1 ? "" : "s"}`}
                </p>
                <Badge tone={STATUS[r.status].tone}>{STATUS[r.status].label}</Badge>
                {r.status === "pending" ? (
                  <Button size="sm" variant="ghost" className="ml-auto"
                    disabled={withdraw.isPending} onClick={() => withdraw.mutate(r.id)}>
                    Withdraw
                  </Button>
                ) : null}
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">{r.reason}</p>

              {r.warnings.length > 0 ? (
                <p className="mt-1.5 flex items-start gap-1.5 text-xs text-warning">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{r.warnings.join(" · ")}</span>
                </p>
              ) : null}

              {/* The admin's note is the part a teacher actually wants to read. */}
              {r.events.filter((e) => e.note && e.action !== "applied").map((e, i) => (
                <p key={i} className="mt-1.5 border-l-2 border-border pl-2.5 text-xs">
                  <span className="font-medium">{e.actor_name ?? "Admin"}:</span> {e.note}
                </p>
              ))}
            </div>
          ))}
        </div>
      )}

      <ApplySheet open={open} onClose={() => setOpen(false)} />
    </div>
  );
}

export default function MyLeavePage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyLeaveInner />
    </AuthGuard>
  );
}
