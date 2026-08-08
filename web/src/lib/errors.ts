import { toast } from "sonner";

import { ApiError } from "@/lib/api-client";

/**
 * Surface an API error. Plan-limit (402) errors are never silent: they show the
 * upgrade prompt with a one-tap route to the plan screen.
 *
 * The 402 carries `required_tier` (`D-106`), so the toast names the tier rather
 * than saying "upgrade" and leaving the school to work out which one. It used
 * to point at `/settings`, which redirects to a screen with no plan section on
 * it at all — a dead end, since no billing screen was ever built.
 */
export function showApiError(e: unknown, fallback = "Something went wrong"): void {
  if (e instanceof ApiError && e.code === "plan_limit") {
    const tier = (e.details as { required_tier?: string } | undefined)?.required_tier;
    toast(e.message, {
      action: {
        label: tier ? `See ${tier[0].toUpperCase()}${tier.slice(1)}` : "Upgrade",
        onClick: () => {
          window.location.href = "/setup/plan";
        },
      },
      duration: 8000,
    });
    return;
  }
  toast.error(e instanceof ApiError ? e.message : fallback);
}

export function isPlanLimit(e: unknown): e is ApiError {
  return e instanceof ApiError && e.code === "plan_limit";
}
