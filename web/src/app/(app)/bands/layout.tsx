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
 * own classes, works her own children, and now records her own assessments.
 *
 * **Founder 2026-08-05: Support lost its sidebar item and everything it held
 * lives here.** Two consequences the tabs have to carry:
 *
 *   · A support **owner who teaches none of the monitored subjects** — the admin
 *     may assign anyone; `OwnerSuggestion` suggests and never restricts — would
 *     otherwise have children assigned to her and no door to them. `has_scope`
 *     now means "gets the area at all", and `can_band` is the narrower signal
 *     that the class-banding tabs mean something for her.
 *   · So Manage bands is keyed on `can_band`, not on the area being visible. A
 *     tab that opens on "you have no classes here" is worse than an absent one
 *     (ux §13) — the same rule that hides the whole area from a teacher outside
 *     the programme.
 */

import { useQuery } from "@tanstack/react-query";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SubTabs } from "@/components/layout/sub-tabs";
import { useAuth } from "@/contexts/auth-context";
import { schoolApi } from "@/lib/school-api";

export default function BandsLayout({ children }: { children: React.ReactNode }) {
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";
  const { data: scope } = useQuery({
    queryKey: ["band-scope"],
    queryFn: () => schoolApi.bandScope(),
  });
  // Default true while it loads, so the tabs don't visibly rearrange under her.
  const canBand = scope?.can_band ?? true;

  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <div>
        <SubTabs
          tabs={[
            { label: "Overview", href: "/bands" },
            ...(canBand ? [{ label: "Manage bands", href: "/bands/manage" }] : []),
            ...(isAdmin
              ? [
                  { label: "Teacher allocation", href: "/bands/allocation" },
                  // The programme report is the school-wide read: movement by
                  // class and subject. A teacher's version of it would be her
                  // own children, which is exactly what My students already is —
                  // so she gets no Reports tab rather than one that opens on
                  // "this is the admin's view".
                  { label: "Reports", href: "/bands/reports" },
                ]
              : []),
            // Both roles, and last: an admin reading the programme still owns
            // children of her own often enough that hiding it would send her
            // hunting. Her list is her own; the school's is Reports.
            { label: "My students", href: "/bands/my-students" },
            { label: "Assessments", href: "/bands/assessments" },
            // Founder 2026-08-05. Keyed on `can_band` like Manage bands: the
            // band test is a monitored class-subject's exam, so an owner who
            // teaches none of them would open it on "nothing here".
            ...(canBand ? [{ label: "Exams", href: "/bands/exams" }] : []),
          ]}
        />
        {children}
      </div>
    </AuthGuard>
  );
}
