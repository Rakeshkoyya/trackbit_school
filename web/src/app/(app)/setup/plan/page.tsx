"use client";

/**
 * Setup → Plan (`D-106`).
 *
 * Where a school reads what it is on, what the next tier would cost **it**, and
 * asks to move. Ungated on purpose: paywalling the paywall would be absurd, and
 * every 402 toast in the app routes here.
 *
 * There is no checkout. A request reaches the operator, who phones the school,
 * takes the money and sets the plan by hand — so the copy says so plainly
 * rather than implying a card form is coming.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Lock } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { ApiError } from "@/lib/api-client";
import { appApi } from "@/lib/app-api";
import { formatPaise } from "@/lib/features";
import type { OrgPlan, TierQuote } from "@/lib/types";
import { cn } from "@/lib/utils";

/** What each tier adds, in the school's language. Copy only — the server owns
 *  the real map, and `tier.features` carries the machine-readable list. */
const SELLS: Record<string, string[]> = {
  free: [
    "Attendance, every period",
    "Homework and classwork logging",
    "Syllabus, plans and the timetable",
    "Events, birthdays and the calendar",
    "ABC support programme",
    "The daily report, written for you",
  ],
  pro: [
    "The academic record over time",
    "Homework check-sheet and day book",
    "Exams end to end, with trends",
    "Fee collection and ledgers",
    "Report cards",
  ],
  max: [
    "Staff, leave and timesheets",
    "Teacher workload",
    "Task management, unmetered",
    "Hostel and activity sessions",
    "Parent portal and communications",
    "Lucy, your AI assistant",
  ],
  ultra: ["Agent connections (MCP)", "Connect TrackBit to your own tools"],
};

function TierCard({
  tier,
  plan,
  onRequest,
  pendingPlan,
}: {
  tier: TierQuote;
  plan: OrgPlan;
  onRequest: (t: TierQuote) => void;
  pendingPlan: string | null;
}) {
  const asked = plan.open_request?.requested_plan === tier.plan;
  return (
    <div
      className={cn(
        "flex flex-col rounded-2xl border bg-card p-5",
        tier.is_current ? "border-primary ring-1 ring-primary" : "border-border",
      )}
    >
      <div className="flex items-center justify-between">
        <h3 className="text-base font-semibold">{tier.label}</h3>
        {tier.is_current ? (
          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
            Current
          </span>
        ) : null}
      </div>

      <div className="mt-3">
        <span className="text-2xl font-semibold">
          {tier.unit_paise_per_student === 0
            ? "Free"
            : formatPaise(tier.unit_paise_per_student)}
        </span>
        {tier.unit_paise_per_student > 0 ? (
          <span className="ml-1 text-sm text-muted-foreground">
            per student / month
          </span>
        ) : null}
      </div>
      {tier.unit_paise_per_student > 0 ? (
        // Always shows its working. A bare monthly total is a number the school
        // has to take on faith; this one it can check.
        <p className="mt-1 text-sm text-muted-foreground">
          {formatPaise(tier.monthly_paise)} / month for your {tier.students}{" "}
          {tier.students === 1 ? "student" : "students"}
        </p>
      ) : (
        <p className="mt-1 text-sm text-muted-foreground">
          The whole capture loop, at no cost
        </p>
      )}

      <ul className="mt-4 flex-1 space-y-1.5 text-sm">
        {(SELLS[tier.plan] ?? []).map((line) => (
          <li key={line} className="flex items-start gap-2 text-muted-foreground">
            <Check className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>{line}</span>
          </li>
        ))}
      </ul>

      <div className="mt-5">
        {tier.is_current ? (
          <Button variant="outline" disabled className="w-full">
            Your plan
          </Button>
        ) : asked ? (
          <Button variant="outline" disabled className="w-full">
            Requested
          </Button>
        ) : tier.is_upgrade ? (
          <Button
            className="w-full"
            disabled={!plan.can_request || pendingPlan !== null}
            onClick={() => onRequest(tier)}
          >
            {pendingPlan === tier.plan ? "Sending…" : `Request ${tier.label}`}
          </Button>
        ) : (
          <Button variant="ghost" disabled className="w-full">
            Included
          </Button>
        )}
      </div>
    </div>
  );
}

export default function PlanPage() {
  const qc = useQueryClient();
  const [pendingPlan, setPendingPlan] = useState<string | null>(null);
  const { data, isLoading } = useQuery<OrgPlan>({
    queryKey: ["org-plan"],
    queryFn: appApi.plan,
  });

  const ask = useMutation({
    mutationFn: (tier: TierQuote) =>
      appApi.requestUpgrade({ plan: tier.plan, feature_id: null, message: null }),
    onMutate: (tier: TierQuote) => setPendingPlan(tier.plan),
    onSettled: () => setPendingPlan(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org-plan"] });
      toast.success("Request sent — we'll be in touch shortly.");
    },
    onError: (e: unknown) =>
      // A teacher gets `admin_only` with copy she can act on (`D-110`).
      toast.error(e instanceof ApiError ? e.message : "Could not send the request."),
  });

  return (
    <div className="space-y-6 p-4 sm:p-6">
      <PageHeader
        title="Your plan"
        subtitle="Priced per student, per month. Nothing you have recorded is ever affected by a plan change."
      />

      {data?.open_request ? (
        <div className="rounded-xl border border-border bg-muted/40 p-4 text-sm">
          <p className="font-medium">
            {data.open_request.requested_plan.toUpperCase()} requested
          </p>
          <p className="mt-1 text-muted-foreground">
            We&apos;ll call to arrange it and switch you over. No need to ask again.
          </p>
        </div>
      ) : null}

      {!data?.can_request && !isLoading ? (
        <div className="flex items-start gap-2 rounded-xl border border-border bg-muted/40 p-4 text-sm">
          <Lock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <p className="text-muted-foreground">
            Only admins can change your school&apos;s plan. You can see what each
            plan includes here — ask your school admin to request a change.
          </p>
        </div>
      ) : null}

      {isLoading || !data ? (
        <p className="text-sm text-muted-foreground">Loading your plan…</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {data.quote.tiers.map((tier) => (
            <TierCard
              key={tier.plan}
              tier={tier}
              plan={data}
              pendingPlan={pendingPlan}
              onRequest={(t) => ask.mutate(t)}
            />
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground">
        Prices are per active student, per month, and are billed at the rate agreed
        when you signed up — a later price change does not move it.
      </p>
    </div>
  );
}
