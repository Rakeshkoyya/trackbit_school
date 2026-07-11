import { Loader2 } from "lucide-react";

/** Consistent in-page loading state — the API is a remote round-trip, so every
 * data screen shows this instead of flashing empty content. */
export function PageLoading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 rounded-xl border border-dashed border-border px-4 py-10 text-sm text-muted-foreground">
      <Loader2 className="h-4 w-4 animate-spin" />
      {label}
    </div>
  );
}
