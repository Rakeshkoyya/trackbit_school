"use client";

import { SubTabs } from "@/components/layout/sub-tabs";
import { useAuth } from "@/contexts/auth-context";

/**
 * Plan area (SPRD2 §3): Year calendar · Classes · Syllabus · Week plan ·
 * Timetable · Hostel — plus **My subjects** for a teacher (V1-6, `S-46`).
 *
 * "Year" stays first because `SubTabs` treats `tabs[0]` as the area root and
 * matches it exactly; anything else in that slot would leave `/plan` matching
 * every nested route and light up the wrong tab everywhere. Her *landing* is
 * handled by the nav instead — `navForRole` points a teacher's Plan item
 * straight at `/plan/my-subjects`.
 *
 * The tab is hidden from an admin who owns no class-subjects: a tab that is
 * always empty is worse than no tab.
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
          { label: "Classes", href: "/plan/classes" },
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
