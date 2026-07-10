import { SubTabs } from "@/components/layout/sub-tabs";

/** Plan area (SPRD2 §3): Year calendar · Classes · Syllabus · Week plan · Timetable. */
export default function PlanLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Year", href: "/plan" },
          { label: "Classes", href: "/plan/classes" },
          { label: "Syllabus", href: "/plan/syllabus" },
          { label: "Week plan", href: "/plan/week" },
          { label: "Timetable", href: "/plan/timetable" },
        ]}
      />
      {children}
    </div>
  );
}
