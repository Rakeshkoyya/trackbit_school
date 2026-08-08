"use client";

/**
 * The lock, in its three renderings (`D-111`).
 *
 * The founder's rule is that nothing disappears: "we show everything on the
 * screen like as it is now, but when they navigate to that page or try to
 * access based on their plan we block it or show upgrade option". So a school
 * on Free still sees Fees in the sidebar, still sees the red row on the
 * dashboard, still sees the button — it just cannot pass through.
 *
 *   <FeatureGate>   a whole screen  → replaced by the wall
 *   <UpgradeGate>   one control     → the row stays, the button opens the dialog
 *   (nav lock)      a sidebar item  → a padlock chip, handled in nav-items
 *
 * All three read `me.org.features`, which the server computed. Nothing here
 * knows which tier unlocks what beyond the copy in `lib/features.ts`.
 *
 * `D-110`: only an admin may actually ask. A teacher sees the same wall and the
 * same price — hiding the number would only make her ask the admin what it
 * costs — but is told to contact her admin instead of being handed a form.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Lock, Sparkles } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";
import { formatPaise, tierLabelFor } from "@/lib/features";
import { useFeature } from "@/lib/use-feature";
import { cn } from "@/lib/utils";
import type { OrgPlan, TierQuote } from "@/lib/types";

/** What each locked surface is called, in the school's language rather than
 *  ours. Keyed by feature id; falls back to a generic line. */
const BLURB: Record<string, string> = {
  "students.academics":
    "the academic record — class logs, homework history, trends and report cards",
  "homework.desk": "the homework check-sheet and the day book",
  "exams.board": "exams end to end — cycles, marks, result sheets and trends",
  "fees.collection": "fee collection, structures and the ledger",
  "staff.roster": "staff, leave, timesheets and teacher workload",
  "tasks.boards": "task management — boards, assignments and recurring work",
  "insights.actions": "acting on the dashboard in one tap",
  "sessions.hostel": "hostel and activity sessions",
  "parent.portal": "the parent portal",
  "comms.guardian": "parent communications",
  "agent.lucy": "Lucy, your AI assistant",
  "agent.mcp": "agent connections (MCP)",
};

function blurbFor(feature: string): string {
  return BLURB[feature] ?? "this part of TrackBit";
}

function usePlan() {
  return useQuery<OrgPlan>({ queryKey: ["org-plan"], queryFn: appApi.plan });
}

/** The price line. Always shows its working — "₹25 per student × 480" —
 *  because a bare monthly total is a number a school has to take on faith. */
function PriceLine({ tier }: { tier: TierQuote }) {
  return (
    <p className="text-sm text-muted-foreground">
      <span className="text-2xl font-semibold text-foreground">
        {formatPaise(tier.monthly_paise)}
      </span>
      <span className="ml-1">/ month</span>
      <span className="mx-2 text-border">·</span>
      {formatPaise(tier.unit_paise_per_student)} per student × {tier.students}{" "}
      {tier.students === 1 ? "student" : "students"}
    </p>
  );
}

function RequestBody({
  feature,
  plan,
  onDone,
}: {
  feature: string;
  plan: OrgPlan;
  onDone?: () => void;
}) {
  const qc = useQueryClient();
  const [message, setMessage] = useState("");
  const label = tierLabelFor(feature);
  const target = plan.quote.tiers.find((t) => t.label === label);
  const pending = plan.open_request;

  const ask = useMutation({
    mutationFn: () =>
      appApi.requestUpgrade({
        plan: target?.plan ?? "pro",
        feature_id: feature,
        message: message.trim() || null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org-plan"] });
      toast.success("Request sent — we'll be in touch shortly.");
      onDone?.();
    },
    onError: (e: unknown) => {
      // The service answers a teacher with `admin_only` and copy she can act
      // on, so surface it verbatim rather than a generic permission error.
      toast.error(e instanceof ApiError ? e.message : "Could not send the request.");
    },
  });

  if (pending) {
    return (
      <div className="rounded-xl border border-border bg-muted/40 p-4 text-sm">
        <p className="font-medium">Request already sent</p>
        <p className="mt-1 text-muted-foreground">
          You asked for {pending.requested_plan.toUpperCase()} on{" "}
          {new Date(pending.created_at).toLocaleDateString("en-IN", {
            day: "numeric",
            month: "short",
          })}
          . We&apos;ll call to arrange it — no need to ask again.
        </p>
      </div>
    );
  }

  if (!plan.can_request) {
    // D-110. No form at all — a button that 403s would be worse than no button.
    return (
      <div className="rounded-xl border border-border bg-muted/40 p-4 text-sm">
        <p className="font-medium">Only admins can change your school&apos;s plan</p>
        <p className="mt-1 text-muted-foreground">
          Please ask your school admin to request the upgrade.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        rows={2}
        placeholder="Anything we should know? (optional)"
        className="w-full resize-none rounded-lg border border-border bg-card px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <Button onClick={() => ask.mutate()} disabled={ask.isPending} className="w-full">
        <Sparkles className="h-4 w-4" />
        {ask.isPending ? "Sending…" : `Request ${label}`}
      </Button>
      <p className="text-center text-xs text-muted-foreground">
        No payment here — we&apos;ll call to arrange it and switch you over.
      </p>
    </div>
  );
}

function TierSummary({ feature, plan }: { feature: string; plan: OrgPlan }) {
  const label = tierLabelFor(feature);
  const tier = plan.quote.tiers.find((t) => t.label === label);
  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm text-muted-foreground">
          {label} unlocks <span className="text-foreground">{blurbFor(feature)}</span>.
        </p>
        {tier ? (
          <div className="mt-3">
            <PriceLine tier={tier} />
          </div>
        ) : null}
      </div>
      <ul className="space-y-1.5 text-sm">
        {[
          "Everything in your current plan, unchanged",
          "Nothing you have already recorded is affected",
          "Switch back at any time",
        ].map((line) => (
          <li key={line} className="flex items-start gap-2 text-muted-foreground">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>{line}</span>
          </li>
        ))}
      </ul>
      <RequestBody feature={feature} plan={plan} />
    </div>
  );
}

/** A whole screen the school has not bought. */
export function UpgradeWall({ feature, title }: { feature: string; title?: string }) {
  const { data, isLoading } = usePlan();
  const label = tierLabelFor(feature);

  return (
    <div className="mx-auto flex max-w-xl flex-col items-center px-4 py-14 text-center">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
        <Lock className="h-5 w-5 text-muted-foreground" />
      </div>
      <h1 className="mt-4 text-xl font-semibold">{title ?? `${label} unlocks this`}</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Your school is on{" "}
        <span className="font-medium text-foreground">
          {data ? data.quote.current_plan.toUpperCase() : "…"}
        </span>
        . Everything you have already recorded stays exactly where it is.
      </p>
      <div className="mt-8 w-full rounded-2xl border border-border bg-card p-5 text-left">
        {isLoading || !data ? (
          <p className="text-sm text-muted-foreground">Loading your plan…</p>
        ) : (
          <TierSummary feature={feature} plan={data} />
        )}
      </div>
    </div>
  );
}

/** Wrap a screen. Renders it when the school has the feature, the wall when not. */
export function FeatureGate({
  feature,
  title,
  children,
}: {
  feature: string;
  title?: string;
  children: React.ReactNode;
}) {
  const allowed = useFeature(feature);
  if (!allowed) return <UpgradeWall feature={feature} title={title} />;
  return <>{children}</>;
}

/** The dialog behind an in-place lock. */
export function UpgradeDialog({
  feature,
  open,
  onOpenChange,
}: {
  feature: string;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const { data, isLoading } = usePlan();
  const label = tierLabelFor(feature);
  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      size="md"
      title={`${label} unlocks this`}
      description={`Your school is on ${data ? data.quote.current_plan.toUpperCase() : "…"}.`}
    >
      <div className="p-5">
        {isLoading || !data ? (
          <p className="text-sm text-muted-foreground">Loading your plan…</p>
        ) : (
          <TierSummary feature={feature} plan={data} />
        )}
      </div>
    </Modal>
  );
}

/**
 * Wrap ONE control on a screen the school can otherwise use — the dashboard's
 * quick actions being the case that prompted this (`D-111`).
 *
 * The row, the number and the diagnosis all still render. Only the button is
 * intercepted, so a Free school still learns that three children are absent; it
 * just cannot dispatch a follow-up task in one tap.
 */
export function UpgradeGate({
  feature,
  children,
  className,
}: {
  feature: string;
  children: React.ReactNode;
  className?: string;
}) {
  const allowed = useFeature(feature);
  const [open, setOpen] = useState(false);
  if (allowed) return <>{children}</>;
  const label = `${tierLabelFor(feature)} unlocks this`;
  return (
    <>
      {/* The real control renders inert underneath and the intercepting button
          is a SIBLING laid over it, not a parent: what we wrap is usually
          itself a <button>, and a button inside a button is invalid HTML that
          React will warn about and screen readers cannot make sense of.
          Overlaying also keeps the control's exact size and place in the row. */}
      <span className={cn("relative inline-flex", className)}>
        <span className="pointer-events-none opacity-60" aria-hidden>
          {children}
        </span>
        <button
          type="button"
          onClick={() => setOpen(true)}
          title={label}
          aria-label={label}
          className="absolute inset-0 z-10 flex cursor-pointer items-center justify-end rounded-md pr-1 hover:bg-muted/30"
        >
          <Lock className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      </span>
      <UpgradeDialog feature={feature} open={open} onOpenChange={setOpen} />
    </>
  );
}
