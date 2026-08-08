"use client";

import { useParams } from "next/navigation";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SetupPackScreen } from "@/components/school/setup-pack-screen";

/** The operator's setup screen for one school (SETUP-REDESIGN-PLAN §5).
 *  Super-admin only — schools do not set themselves up. */
export default function OrgSetupPage() {
  const params = useParams<{ orgId: string }>();
  return (
    <AuthGuard requireSuperAdmin>
      <SetupPackScreen orgId={params.orgId} />
    </AuthGuard>
  );
}
