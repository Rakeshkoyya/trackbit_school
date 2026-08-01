"use client";

import { SubTabs } from "@/components/layout/sub-tabs";

/** My time (SF-1, teacher): the week's periods and time off. Everything about a
 *  teacher's own time lives here so they never hunt for it in two places. */
export default function TimesheetLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "My time", href: "/timesheet" },
          { label: "My month", href: "/timesheet/month" },
          { label: "Leave", href: "/timesheet/leave" },
        ]}
      />
      {children}
    </div>
  );
}
