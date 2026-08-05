"use client";

import { SubTabs } from "@/components/layout/sub-tabs";
import { useAuth } from "@/contexts/auth-context";

/**
 * Plan area (SPRD2 §3): Year calendar · Syllabus · Week plan · Timetable ·
 * Hostel — plus **My subjects** for a teacher (V1-6, `S-46`).
 *
 * "Year" stays first because `SubTabs` treats `tabs[0]` as the area root and
 * matches it exactly; anything else in that slot would leave `/plan` matching
 * every nested route and light up the wrong tab everywhere. Her *landing* is
 * handled by the nav instead — `navForRole` points a teacher's Plan item
 * straight at `/plan/my-subjects`.
 *
 * **Classes is gone (founder, SY-1).** It answered "is my year sound?" with a
 * row per class and a column per way a year quietly fails. Everything it
 * checked now has a louder home: the unapproved plans and missing syllabus read
 * off the Syllabus board (which names the chapter, not just the count), and
 * teacher load lives on Dashboard → Staff, which computes it from real
 * timetable and timesheet rows rather than a second roll-up of its own.
 */
export default function PlanLayout({ children }: { children: React.ReactNode }) {
  const { me } = useAuth();
  const isTeacher = me?.org_role === "teacher";

  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Year", href: "/plan" },
          ...(isTeacher ? [{ label: "My subjects", href: "/plan/my-subjects" }] : []),
          { label: "Syllabus", href: "/plan/syllabus" },
          { label: "Week plan", href: "/plan/week" },
          { label: "Timetable", href: "/plan/timetable" },
          { label: "Hostel", href: "/plan/hostel" },
        ]}
      />
      {children}
    </div>
  );
}
