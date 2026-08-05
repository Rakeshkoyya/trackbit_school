"use client";

// My Class (founder, 2026-08-05) — the class teacher's area.
//
// V1-3 shipped it as one page: the month register, the class's syllabus, the
// evening homework load. That is her record, but it is not her desk — the
// questions she actually arrives with (who is away, did the work come back, how
// did they do, who needs support, what do I know about this child) each had to
// be answered somewhere else, on a screen scoped to the whole school.
//
// Six tabs, in the order her morning runs. Attendance is second, not first,
// because the Overview already answers "has it been taken?" — the tab is where
// she goes to DO something about the answer.

import { Suspense } from "react";

import { SubTabs } from "@/components/layout/sub-tabs";
import { PageLoading } from "@/components/ui/page-loading";

export default function MyClassLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Overview", href: "/my-class" },
          { label: "Attendance", href: "/my-class/attendance" },
          { label: "Students", href: "/my-class/students" },
          { label: "Syllabus", href: "/my-class/syllabus" },
          { label: "Homework", href: "/my-class/homework" },
          { label: "ABC bands", href: "/my-class/bands" },
        ]}
      />
      {/* Every tab reads the picked class from `?class=`, so each one needs a
          Suspense boundary for `useSearchParams`. */}
      <Suspense fallback={<PageLoading label="Loading your class…" />}>
        {children}
      </Suspense>
    </div>
  );
}
