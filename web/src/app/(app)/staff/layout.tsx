"use client";

import { usePathname } from "next/navigation";

import { SubTabs } from "@/components/layout/sub-tabs";

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
  if (pathname.startsWith("/staff/member/")) return <div>{children}</div>;

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
