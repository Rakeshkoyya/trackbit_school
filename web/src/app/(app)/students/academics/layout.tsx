import { SubTabs } from "@/components/layout/sub-tabs";

/**
 * Students → Academics (founder, 2026-08-05) — the record the school MAKES.
 *
 * Six tabs, and the order is the order the day happens in: the children first,
 * then what was taught, then what was set, then what was tested, then the two
 * ways of reading it back.
 *
 *   Students    the roster, one row per child: attendance, exams, last homework
 *   Class logs  what each class was taught, and lines about individual children
 *   Homework    what was set and how it came back
 *   Exams       the exam-first capture (SC-5 / V1-8), unmoved — this tab is the
 *               same screen it always was, finally filed where it belongs
 *   Reports     report cards, per class and per child
 *   Analytics   the class-level trends (V1-8's `ClassAnalytics`)
 *
 * The same six for both roles. A teacher is scoped by the SERVICE, not by the
 * tab bar — `/students/records`, `/academics/classes?mine=true` and
 * `periods.visible_class_ids` all return her classes ∪ her homeroom — so there
 * is no such thing as a tab here that 403s, and no second nav to keep in step.
 */
export default function AcademicsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Students", href: "/students/academics" },
          { label: "Class logs", href: "/students/academics/class-logs" },
          { label: "Homework", href: "/students/academics/homework" },
          { label: "Exams", href: "/students/academics/exams" },
          { label: "Reports", href: "/students/academics/reports" },
          { label: "Analytics", href: "/students/academics/analytics" },
        ]}
      />
      {children}
    </div>
  );
}
