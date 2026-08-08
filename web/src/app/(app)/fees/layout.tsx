"use client";

import { FeatureGate } from "@/components/plan/upgrade";
import { FEATURES } from "@/lib/features";

/** Fees is a Pro feature (`D-106`). The gate sits on the AREA rather than each
 *  page so every sub-route — structures, a student's ledger, the collection
 *  board — is covered by one decision.
 *
 *  This composes with the fee fence and does not replace it: 19 of the 20 fee
 *  routes are admin-only whatever the school's plan is, enforced server-side. */
export default function FeesLayout({ children }: { children: React.ReactNode }) {
  return <FeatureGate feature={FEATURES.feesCollection}>{children}</FeatureGate>;
}
