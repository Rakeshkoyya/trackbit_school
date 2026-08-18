import { AlertTriangle } from "lucide-react";

import { ApiError } from "@/lib/api-client";
import { EmptyState } from "@/components/ui/empty-state";

/**
 * What a data screen shows when its query FAILED.
 *
 * Every roster screen used to read `if (isLoading || !sheet) return
 * <PageLoading/>`, which looks complete and is not: a query that errors leaves
 * `isLoading` false and the data undefined, so the page spun on "Loading
 * roster…" forever with no message and no way out. That is how a plain 403 —
 * the class teacher of a class whose subjects were never mapped being refused
 * her own register — reached the founder as "it's stuck loading" rather than as
 * the sentence the server actually sent.
 *
 * So the rule is: a failed query renders THIS, never a spinner. The backend's
 * `AppError` messages are written for the person reading them ("You don't teach
 * this class."), so prefer the server's own words and keep `fallback` for the
 * cases where there are none.
 */
export function PageError({ error, fallback = "Something went wrong.", action }: {
  error: unknown;
  fallback?: string;
  action?: React.ReactNode;
}) {
  const message = error instanceof ApiError ? error.message : fallback;
  return (
    <EmptyState
      icon={AlertTriangle}
      title="This didn’t load"
      body={message}
      action={action}
    />
  );
}
