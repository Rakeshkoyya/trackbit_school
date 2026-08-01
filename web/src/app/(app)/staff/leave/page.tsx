"use client";

// Leave approvals — the admin's inbox.
//
// Pending sits at the top because it is the only thing here that needs a
// decision; everything else is a record. Opening a request shows its full
// history, which is rows in an append-only log (law 3), not a status field
// somebody overwrote.
//
// A request that breaks the school's own allowance still arrives — flagged, with
// the reason spelled out next to the Approve button. A validator that refuses an
// emergency is a validator staff route around with a phone call, and then the
// school has no record at all.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle, CalendarClock, CalendarDays, Check, Inbox, Loader2, X,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { CoverSheet } from "@/components/insights/cover-sheet";
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
  pending: { label: "Waiting", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Declined", tone: "danger" },
  cancelled: { label: "Withdrawn", tone: "neutral" },
};

const FILTERS: { key: LeaveStatus | "all"; label: string }[] = [
  { key: "pending", label: "Waiting" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Declined" },
  { key: "all", label: "Everything" },
];

function span(r: LeaveRequest): string {
  const opts: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  const from = new Date(`${r.start_date}T00:00:00`).toLocaleDateString("en-IN", opts);
  if (r.start_date === r.end_date) return from;
  return `${from} – ${new Date(`${r.end_date}T00:00:00`).toLocaleDateString("en-IN", opts)}`;
}

function stamp(isoStr: string): string {
  return new Date(isoStr).toLocaleString("en-IN", {
    day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
  });
}

function DecisionSheet({ request, onClose, onArrangeCover }: {
  request: LeaveRequest | null;
  onClose: () => void;
  onArrangeCover: (memberId: string, name: string, date: string) => void;
}) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  // D-27 — what the approval just created work for. Held in state because the
  // request in the list is refetched and we want the days that were returned by
  // the decision itself.
  const [coverDates, setCoverDates] = useState<string[]>([]);

  const decide = useMutation({
    mutationFn: (action: "approved" | "rejected") =>
      schoolApi.decideLeave(request!.id, { action, note: note.trim() || null }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["leave"] });
      qc.invalidateQueries({ queryKey: ["staff-attendance"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["insights"] });
      toast.success(res.status === "approved" ? "Leave approved" : "Leave declined");
      setNote("");
      // Approving hands back the cover flow instead of closing the sheet: the
      // periods are known NOW, and the alternative is remembering on the
      // morning it starts, which is the morning nobody has a spare minute.
      if (res.status === "approved" && res.cover_dates.length) {
        setCoverDates(res.cover_dates);
      } else {
        onClose();
      }
    },
    onError: (e) => showApiError(e, "Could not record the decision"),
  });

  const close = () => { setNote(""); setCoverDates([]); onClose(); };
  // An already-approved request reopened from the list carries its own days.
  const days = coverDates.length ? coverDates : (request?.cover_dates ?? []);

  return (
    <Sheet open={!!request} onOpenChange={(v) => { if (!v) close(); }}
      title="Leave request">
      {request ? (
        <div className="space-y-4">
          <div>
            <p className="text-base font-semibold">{request.member_name}</p>
            <p className="text-sm text-muted-foreground">
              {span(request)} · {request.is_half_day
                ? `half day (${request.portion === "pm" ? "afternoon" : "morning"})`
                : `${request.days} day${request.days === 1 ? "" : "s"}`}
            </p>
          </div>

          {request.status === "approved" && days.length ? (
            <div className="rounded-lg border border-warning/40 bg-warning-soft p-3">
              <p className="text-sm font-medium">
                Arrange cover for {days.length} day{days.length === 1 ? "" : "s"}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                One sheet per day — the classes {request.member_name.split(" ")[0]} would have
                taken, and who is genuinely free to take them.
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {days.map((d) => (
                  <Button key={d} size="sm" variant="outline"
                    onClick={() => onArrangeCover(request.member_id, request.member_name, d)}>
                    <CalendarClock className="h-3.5 w-3.5" />
                    {new Date(`${d}T00:00:00`).toLocaleDateString("en-IN",
                      { weekday: "short", day: "numeric", month: "short" })}
                  </Button>
                ))}
              </div>
            </div>
          ) : null}

          <div className="rounded-lg bg-muted/50 px-3 py-2">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Reason</p>
            <p className="mt-0.5 whitespace-pre-wrap text-sm">{request.reason}</p>
          </div>

          {request.warnings.length > 0 ? (
            <ul className="space-y-1.5">
              {request.warnings.map((w, i) => (
                <li key={i} className="flex items-start gap-2 rounded-lg border border-warning/40 bg-warning-soft px-3 py-2 text-xs text-warning">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  <span>{w}</span>
                </li>
              ))}
            </ul>
          ) : null}

          {request.status === "pending" ? (
            <div className="space-y-3">
              <div>
                <Label htmlFor="leave-note">Note (optional)</Label>
                <Input id="leave-note" value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder="Anything they should know" />
              </div>
              <div className="flex gap-2">
                <Button className="flex-1" disabled={decide.isPending}
                  onClick={() => decide.mutate("approved")}>
                  {decide.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                  Approve
                </Button>
                <Button className="flex-1" variant="outline" disabled={decide.isPending}
                  onClick={() => decide.mutate("rejected")}>
                  <X className="h-4 w-4" /> Decline
                </Button>
              </div>
            </div>
          ) : (
            <Badge tone={STATUS[request.status].tone}>{STATUS[request.status].label}</Badge>
          )}

          <div>
            <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              History
            </p>
            <ul className="space-y-2">
              {request.events.map((e, i) => (
                <li key={i} className="border-l-2 border-border pl-3">
                  <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground">{e.actor_name ?? "Someone"}</span>
                    <span>·</span>
                    <span>{stamp(e.created_at)}</span>
                    <Badge tone={e.action === "approved" ? "success" : e.action === "rejected" ? "danger" : "outline"}>
                      {e.action}
                    </Badge>
                  </div>
                  {e.note ? <p className="mt-0.5 whitespace-pre-wrap text-sm">{e.note}</p> : null}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </Sheet>
  );
}

function LeaveInner() {
  const [filter, setFilter] = useState<LeaveStatus | "all">("pending");
  const [openId, setOpenId] = useState<string | null>(null);
  const [coverFor, setCoverFor] =
    useState<{ id: string; name: string; date: string } | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["leave", "all"],
    queryFn: () => schoolApi.leaveRequests(),
  });

  const requests = data?.requests ?? [];
  const shown = filter === "all" ? requests : requests.filter((r) => r.status === filter);
  const open = requests.find((r) => r.id === openId) ?? null;

  // Counts come off the unfiltered list, so a chip can never contradict itself.
  const countOf = (key: LeaveStatus | "all") =>
    key === "all" ? requests.length : requests.filter((r) => r.status === key).length;

  return (
    <div className="pb-8">
      <PageHeader title="Leave" subtitle="Approve or decline time off, and see who is away." />

      <div className="mb-4 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => {
          const active = filter === f.key;
          return (
            <button key={f.key} type="button" onClick={() => setFilter(f.key)}
              className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${active ? "border-primary bg-accent text-accent-foreground" : "border-border text-muted-foreground hover:text-foreground"}`}>
              {f.label} · {countOf(f.key)}
            </button>
          );
        })}
      </div>

      {isLoading ? (
        <div className="h-48 animate-pulse rounded-xl border border-border bg-card" />
      ) : shown.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title={filter === "pending" ? "Nothing waiting on you" : "Nothing here"}
          body={filter === "pending"
            ? "Leave requests land here the moment a teacher applies."
            : "No requests with this status yet."} />
      ) : (
        <div className="space-y-2">
          {shown.map((r) => (
            <button key={r.id} type="button" onClick={() => setOpenId(r.id)}
              className="flex w-full items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 text-left transition-colors hover:bg-muted/40">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
                <CalendarDays className="h-4 w-4" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-1.5 text-sm font-medium">
                  {r.member_name}
                  {r.warnings.length > 0 && r.status === "pending" ? (
                    <AlertTriangle className="h-3.5 w-3.5 text-warning" />
                  ) : null}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {span(r)} · {r.is_half_day ? "half day" : `${r.days} day${r.days === 1 ? "" : "s"}`} · {r.reason}
                </p>
              </div>
              {/* D-27 — approved leave with days still to cover says so on the
                  row, so the work is visible without opening anything. */}
              {r.cover_dates.length ? (
                <Badge tone="warning">
                  {r.cover_dates.length} day{r.cover_dates.length === 1 ? "" : "s"} to cover
                </Badge>
              ) : null}
              <Badge tone={STATUS[r.status].tone}>{STATUS[r.status].label}</Badge>
            </button>
          ))}
        </div>
      )}

      <DecisionSheet request={open} onClose={() => setOpenId(null)}
        onArrangeCover={(id, name, date) => {
          setOpenId(null);
          setCoverFor({ id, name, date });
        }} />
      <CoverSheet memberId={coverFor?.id ?? null} memberName={coverFor?.name}
        onDate={coverFor?.date} onClose={() => setCoverFor(null)} />
    </div>
  );
}

export default function LeaveApprovalsPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <LeaveInner />
    </AuthGuard>
  );
}
