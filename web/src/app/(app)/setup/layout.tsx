"use client";

import { SubTabs } from "@/components/layout/sub-tabs";
import { useAuth } from "@/contexts/auth-context";

/** Setup area (SPRD2 §3, admin): Academics · Members · Settings. The Wizard tab
 *  is operator-only now — schools no longer self-onboard (founder decision
 *  2026-07-20); the TrackBit operator runs setup and hands over credentials. */
export default function SetupLayout({ children }: { children: React.ReactNode }) {
  const { me } = useAuth();
  return (
    <div>
      <SubTabs
        tabs={[
          ...(me?.is_super_admin ? [{ label: "Wizard", href: "/setup/wizard" }] : []),
          { label: "Academics", href: "/setup" },
          { label: "Members", href: "/setup/members" },
          { label: "Settings", href: "/setup/settings" },
        ]}
      />
      {children}
    </div>
  );
}
