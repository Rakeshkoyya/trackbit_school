"use client";

/**
 * ABC bands — the support programme's own area (founder 2026-08-04).
 *
 * Bands used to live as a tab under Students, which is where you go to look a
 * child *up*; running a programme — assess, group, give every C child an owner,
 * work, re-assess — is a different job with a different cadence, and it kept
 * colliding with the directory.
 *
 * The tab set differs by role because the two people genuinely do different
 * things here (module §1: *"the module dies if they are given the same
 * screen"*). An admin allocates owners and reads the school; a teacher bands her
 * own classes and works her own children. So Allocation is admin-only, and a
 * teacher gets "My students" instead — the same `/support` list she already has,
 * reachable from the area that now owns the subject.
 */

import { AuthGuard } from "@/components/auth/auth-guard";
import { SubTabs } from "@/components/layout/sub-tabs";
import { useAuth } from "@/contexts/auth-context";

export default function BandsLayout({ children }: { children: React.ReactNode }) {
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";

  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <div>
        <SubTabs
          tabs={[
            { label: "Overview", href: "/bands" },
            { label: "Manage bands", href: "/bands/manage" },
            ...(isAdmin
              ? [{ label: "Teacher allocation", href: "/bands/allocation" }]
              : [{ label: "My students", href: "/bands/my-students" }]),
            { label: "Reports", href: "/bands/reports" },
          ]}
        />
        {children}
      </div>
    </AuthGuard>
  );
}
