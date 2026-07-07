import { toast } from "sonner";

import { ApiError } from "@/lib/api-client";

/**
 * Surface an API error. Plan-limit (402) errors are never silent (plan
 * P4-BE-01): they show the upgrade prompt with a one-tap route to billing.
 */
export function showApiError(e: unknown, fallback = "Something went wrong"): void {
  if (e instanceof ApiError && e.code === "plan_limit") {
    toast(e.message, {
      action: {
        label: "Upgrade",
        onClick: () => {
          window.location.href = "/settings";
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
