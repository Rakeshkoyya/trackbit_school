"use client";

import { SubTabs } from "@/components/layout/sub-tabs";

/** Staff area (SF-1, admin): the daily people work — who came in, who wants
 *  time off, and what everyone is doing today. Configuration for all of it
 *  (the leave allowance) stays in Setup → Settings; this area is for the
 *  decisions an admin makes every morning. */
export default function StaffLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Attendance", href: "/staff" },
          { label: "Leave", href: "/staff/leave" },
          { label: "Today", href: "/staff/today" },
          { label: "Month", href: "/staff/month" },
        ]}
      />
      {children}
    </div>
  );
}
