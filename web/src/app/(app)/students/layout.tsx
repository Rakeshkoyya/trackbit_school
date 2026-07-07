import { SubTabs } from "@/components/layout/sub-tabs";

/** Students area (SPRD2 §3): Directory · Scores · Bands · Trends. Assessments
 *  (v1) now lives here — the admin thinks "students", not "assessment cycles". */
export default function StudentsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Directory", href: "/students" },
          { label: "Scores", href: "/students/scores" },
          { label: "Bands", href: "/students/bands" },
          { label: "Trends", href: "/students/trends" },
        ]}
      />
      {children}
    </div>
  );
}
