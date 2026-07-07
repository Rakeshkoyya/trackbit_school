"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";

import { tokenStore } from "@/lib/api-client";

const emptySubscribe = () => () => {};

/**
 * On the public landing page (`/`), send already-signed-in visitors straight to
 * the app. Without this they see the marketing page's "Sign in" CTA and think
 * they've been logged out — but the session is intact (tokens persist in
 * localStorage, which is why deep links like /home stay logged in).
 *
 * The token lives in localStorage, so it's a client-only read. useSyncExternalStore
 * gives a hydration-safe value (false on the server, real value after mount)
 * without a setState-in-effect. If the stored token is stale, /home's AuthGuard
 * handles the refresh/redirect from there.
 */
export function RedirectIfAuthed() {
  const router = useRouter();
  const authed = useSyncExternalStore(
    emptySubscribe,
    () => !!tokenStore.access,
    () => false,
  );

  useEffect(() => {
    if (authed) router.replace("/home");
  }, [authed, router]);

  if (!authed) return null;
  // Cover the marketing page while the client-side redirect happens.
  return (
    <div className="fixed inset-0 z-50 flex min-h-dvh items-center justify-center bg-background">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}
