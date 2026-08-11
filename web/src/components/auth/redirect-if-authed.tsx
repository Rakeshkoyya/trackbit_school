"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";

import { landingForRole } from "@/components/layout/nav-items";
import { useAuth } from "@/contexts/auth-context";
import { tokenStore } from "@/lib/api-client";

const emptySubscribe = () => () => {};

/**
 * On the public landing page (`/`), send already-signed-in visitors straight to
 * the app. Without this they see the marketing page's "Sign in" CTA and think
 * they've been logged out — but the session is intact (tokens persist in
 * localStorage, which is why a deep link stays logged in).
 *
 * **Where they land is the role's decision, not this component's.** It used to
 * hardcode `/tasks` for everyone, which is how an admin opening the app URL
 * arrived at the task board instead of the dashboard and a teacher instead of
 * My Day — `landingForRole` had been right all along and simply was not asked.
 *
 * Two reads, deliberately: the TOKEN is a synchronous localStorage value and is
 * what covers the marketing page immediately, while the ROLE arrives with
 * `/auth/me` a moment later. Redirecting on the token alone is what forced a
 * hardcoded destination in the first place.
 */
export function RedirectIfAuthed() {
  const router = useRouter();
  const { me, loading } = useAuth();
  // useSyncExternalStore gives a hydration-safe value (false on the server, the
  // real one after mount) without a setState-in-effect.
  const authed = useSyncExternalStore(
    emptySubscribe,
    () => !!tokenStore.access,
    () => false,
  );

  useEffect(() => {
    if (authed && me) router.replace(landingForRole(me.org_role, me.is_super_admin));
  }, [authed, me, router]);

  // A token that resolved to no session — expired, or the API was unreachable
  // and `AuthProvider` deliberately kept the tokens for a later reload. Show the
  // marketing page rather than holding a spinner over it forever.
  if (!authed || (!loading && !me)) return null;
  // Cover the marketing page while the client-side redirect happens.
  return (
    <div className="fixed inset-0 z-50 flex min-h-dvh items-center justify-center bg-background">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}
