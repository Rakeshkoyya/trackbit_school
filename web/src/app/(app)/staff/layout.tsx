"use client";

import { usePathname } from "next/navigation";

import { SubTabs } from "@/components/layout/sub-tabs";
import { FeatureGate } from "@/components/plan/upgrade";
import { FEATURES } from "@/lib/features";

/** Staff area (SF-1, admin): the daily people work — who came in, who wants
 *  time off, and what everyone is doing today. Configuration for all of it
 *  (the leave allowance) stays in Setup → Settings; this area is for the
 *  decisions an admin makes every morning. */
export default function StaffLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // V1-16: a person's record (`/staff/member/…`) is open to that person as well
  // as to an admin, so the area's tabs are hidden there — four links a teacher
  // would get a 403 from are worse than no tabs at all. It also is not a tab: it
  // is a detail page you arrive at from a name, and it carries its own way back.
  // Staff is a Max feature (`D-106`). The gate wraps BOTH exits, so the member
  // detail page below is covered too — a screen reachable by URL is a screen
  // that has to be gated.
  if (pathname.startsWith("/staff/member/")) {
    return (
      <FeatureGate feature={FEATURES.staffRoster}>
        <div>{children}</div>
      </FeatureGate>
    );
  }

  return (
    <FeatureGate feature={FEATURES.staffRoster}>
    <div>
      <SubTabs
        tabs={[
          // `/staff` stays first because `SubTabs` treats the FIRST tab as the
          // area root and matches it exactly — every other tab also matches its
          // nested routes, so moving `/staff` down would light "Attendance" up
          // on every page in the area.
          { label: "Attendance", href: "/staff" },
          // Founder, 2026-08-05: the roster the other four tabs are ABOUT, and
          // the one place a class teacher gets assigned.
          { label: "People", href: "/staff/directory" },
          { label: "Leave", href: "/staff/leave" },
          { label: "Today", href: "/staff/today" },
          { label: "Month", href: "/staff/month" },
        ]}
      />
      {children}
    </div>
    </FeatureGate>
  );
}
