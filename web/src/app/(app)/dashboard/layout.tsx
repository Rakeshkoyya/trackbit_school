import { SubTabs } from "@/components/layout/sub-tabs";

/** The admin operating board (DASH3 §1). Overview stays the ten-second read —
 *  briefing plus one summary card per module — and each tab is the answer to one
 *  question the admin arrives with ("who's out today?", "are we behind?"). Six
 *  modules of charts on one scroll would destroy the overview, which is why this
 *  is a route-based tab area like Plan, Students, Tasks and Setup. */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Overview", href: "/dashboard" },
          { label: "Attendance", href: "/dashboard/attendance" },
          { label: "Staff", href: "/dashboard/staff" },
          { label: "Syllabus", href: "/dashboard/syllabus" },
          { label: "Homework", href: "/dashboard/homework" },
          { label: "Tasks", href: "/dashboard/tasks" },
          { label: "Exams", href: "/dashboard/exams" },
        ]}
      />
      {children}
    </div>
  );
}
