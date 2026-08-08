"use client";

/**
 * Package tiers, client side — the React half (`D-106`).
 *
 * Split from `lib/features.ts` because `nav-items.ts` needs the feature
 * constants and `auth-context.tsx` imports `nav-items` — putting a hook that
 * reads auth into that file would close an import cycle.
 */

import { useAuth } from "@/contexts/auth-context";

/**
 * Does this school's package include `feature`?
 *
 * Returns `true` while auth is still hydrating, so a lock never flashes over a
 * page the school actually owns. The server is the real gate — a wrong
 * optimistic `true` costs a 402 and the same upgrade prompt, whereas a wrong
 * `false` shows a paying school a wall it has already bought.
 */
export function useFeature(feature: string): boolean {
  const { me, loading } = useAuth();
  if (loading || !me) return true;
  return (me.org.features ?? []).includes(feature);
}

/** The whole set, for screens rendering several locks at once. */
export function useFeatures(): Set<string> {
  const { me } = useAuth();
  return new Set(me?.org.features ?? []);
}

/** Only an admin may ask for an upgrade (`D-110`). A teacher who hits a wall is
 *  told to contact her admin — one locked screen must not generate forty
 *  requests from forty teachers for the operator to dedupe by hand. */
export function useCanRequestUpgrade(): boolean {
  const { me } = useAuth();
  return me?.org_role === "admin";
}
