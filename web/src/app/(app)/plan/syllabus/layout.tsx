"use client";

/**
 * Plan → Syllabus is two questions, not one (SY-1):
 *
 *   **Syllabus** — where is every chapter, and is it late?
 *   **Exam mapping** — which chapters does each exam actually examine?
 *
 * They share the same chapters and nothing else: one is read every week and
 * sorted and filtered; the other is decided once a term and is a set of ticks.
 * Putting them on one screen would have made the table carry a column that is
 * only meaningful next to an exam date.
 */

import { SubTabs } from "@/components/layout/sub-tabs";

export default function SyllabusLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Syllabus", href: "/plan/syllabus" },
          { label: "Exam mapping", href: "/plan/syllabus/exams" },
        ]}
      />
      {children}
    </div>
  );
}
