"use client";

import { SubTabs } from "@/components/layout/sub-tabs";
import { FeatureGate } from "@/components/plan/upgrade";
import { FEATURES } from "@/lib/features";

/** My time (SF-1, teacher): the week's periods and time off. Everything about a
 *  teacher's own time lives here so they never hunt for it in two places. */
export default function TimesheetLayout({ children }: { children: React.ReactNode }) {
  return (
    // The other half of the Staff module, so it rides the same feature
    // (`D-106`). This is the surface a TEACHER meets: she sees the wall and is
    // told to contact her admin (`D-110`), never handed a form.
    <FeatureGate feature={FEATURES.staffRoster}>
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
    </FeatureGate>
  );
}
