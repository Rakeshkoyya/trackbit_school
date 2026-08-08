"use client";

import { SubTabs } from "@/components/layout/sub-tabs";
import { useAuth } from "@/contexts/auth-context";

/** Setup area (SPRD2 §3, admin): Academics · Members · Settings · Connections.
 *
 *  The ten-step Wizard tab is gone (SETUP-REDESIGN-PLAN §9). Schools never
 *  self-onboarded — founder decision 2026-07-20 — and setup is now one uploaded
 *  workbook on the operator's own screen, `/platform/orgs/{id}/setup`, reached
 *  from the schools list. The operator link stays here because this is where
 *  they land when they think "set this school up". */
export default function SetupLayout({ children }: { children: React.ReactNode }) {
  const { me } = useAuth();
  return (
    <div>
      <SubTabs
        tabs={[
          ...(me?.is_super_admin ? [{ label: "Schools", href: "/platform" }] : []),
          { label: "Academics", href: "/setup" },
          { label: "Members", href: "/setup/members" },
          { label: "Settings", href: "/setup/settings" },
          { label: "Connections", href: "/setup/connections" },
        ]}
      />
      {children}
    </div>
  );
}
