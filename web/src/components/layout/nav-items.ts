import {
  BarChart3,
  Building2,
  CalendarClock,
  CalendarRange,
  CheckSquare,
  ClipboardCheck,
  ClipboardList,
  Clock,
  GraduationCap,
  Layers,
  Settings2,
  Sparkles,
  Sun,
  UserCheck,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";

import type { OrgRole } from "@/lib/types";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  tour?: string; // data-tour anchor for the guided tour
  // A nav item that opens into a short list rather than navigating (founder,
  // 2026-08-05). Used by Students, whose two halves are two different KINDS of
  // fact about a child — the administration record and the record the school
  // makes — and which a single link cannot land you in the right one of.
  // Deliberately one level deep and deliberately rare: a sidebar of drawers is
  // a sidebar nobody reads. `href` stays the group's own landing page, so a
  // press on the parent is never a dead press.
  children?: NavItem[];
};

// Consolidated v2 IA (SPRD2 §3). Each item is one area; areas group their old
// v1 screens into internal tabs (see the area layouts).
const myDay: NavItem = { label: "My Day", href: "/my-day", icon: Sun };
const sessions: NavItem = { label: "Sessions", href: "/sessions", icon: CalendarClock };
const plan: NavItem = { label: "Plan", href: "/plan", icon: CalendarRange };
// V1-6 (`S-46`). Same area, different door: the rest of Plan is admin-shaped
// (pick a year, pick a class, pick a subject), so a teacher lands on the list of
// the class-subjects she actually owns instead of picking her way to each one.
const planForTeacher: NavItem = { ...plan, href: "/plan/my-subjects" };
// Founder 2026-08-05. A school holds two different kinds of fact about a child
// and this area used to offer one door for both:
//
//   Directory — the ADMINISTRATION record. Name, parents, phone, date of birth,
//               class, category. Entered once, corrected occasionally, and the
//               thing the office opens.
//   Academics — the record the school MAKES. The register, the class log, the
//               homework, the exams, the report. Written every day by teachers
//               and read as a trend.
//
// They answer different questions ("who is this child" vs "how is this child
// doing"), are edited by different people at different rhythms, and a single
// table that tried to carry both columns could serve neither. So Students opens
// into the two, and its own href lands on Directory.
const studentsDirectory: NavItem = {
  label: "Directory", href: "/students/directory", icon: ClipboardList,
};
const studentsAcademics: NavItem = {
  label: "Academics", href: "/students/academics", icon: ClipboardCheck,
};
const students: NavItem = {
  label: "Students", href: "/students/directory", icon: GraduationCap,
  children: [studentsDirectory, studentsAcademics],
};
// A teacher gets the Academics half ONLY, and gets it flat — no drawer. She
// does not maintain the roster (every write on Directory is admin-only), so a
// group whose first entry is read-only would be a drawer with one useful thing
// in it. Scoping is the service's job, not the nav's: `/students/records`
// returns the classes she teaches ∪ the homeroom she owns.
const studentsForTeacher: NavItem = {
  label: "Students", href: "/students/academics", icon: GraduationCap,
};
const tasks: NavItem = { label: "Tasks", href: "/tasks", icon: CheckSquare, tour: "nav-boards" };
const fees: NavItem = { label: "Fees", href: "/fees", icon: Wallet };
const dashboard: NavItem = { label: "Dashboard", href: "/dashboard", icon: BarChart3 };
const setup: NavItem = { label: "Setup", href: "/setup", icon: Settings2, tour: "nav-members" };
const lucy: NavItem = { label: "Lucy", href: "/lucy", icon: Sparkles };
const platform: NavItem = { label: "Schools", href: "/platform", icon: Building2 };
// SF-1. Two sides of the same module: the admin marks who came in and approves
// leave; the teacher records their own periods and applies for it.
const staff: NavItem = { label: "Staff", href: "/staff", icon: UserCheck };
const timesheet: NavItem = { label: "My time", href: "/timesheet", icon: Clock };
// V1-3 (D-03). Only for the teacher who owns a class + section: her children,
// her register, who to call. Everyone else never sees it.
const myClass: NavItem = { label: "My Class", href: "/my-class", icon: Users };
// V1-9 (D-71/D-87) had a "Support" item here for the owner of a handful of Band
// C children. **Founder 2026-08-05: removed.** ABC bands is the programme's
// area, and it carries her list as "My students" — two doors to one job put the
// weekly check-in in one place and the assessments in another. `/support` still
// redirects (next.config.ts) and `/support/[id]`, the child page, is unchanged.
//
// Founder 2026-08-04. The programme's own area — bands were reachable only as a
// tab under Students, which is where you go to look a child up, not where you go
// to run a support programme. Shown only to members with a monitored
// class-subject OR an active support plan of their own (`me.has_band_scope`) —
// the second half added when Support lost its item, so an owner who teaches none
// of the monitored subjects is not left with children and no door.
const bands: NavItem = { label: "ABC bands", href: "/bands", icon: Layers };
// Founder 2026-08-05. Attendance had no door of its own: it was reachable only
// from a My Day period card, so the teacher COVERING for an absent class teacher
// — the exact case the school's rule exists for — had nowhere to go. Every
// teacher gets it, because the rule is "the class teacher takes it, and if she
// is away anyone who teaches the class can".
const attendance: NavItem = { label: "Attendance", href: "/attendance", icon: ClipboardList };

// Role-aware primary nav — the full ordered list, used by the DESKTOP sidebar.
// SPRD2 §3 + Lucy (founder decision 2026-07-12) — both roles get the agent.
// Hard rule (§2): teachers never see Fees/Setup.
// On MOBILE this list is split in two: bottomNavForRole (the 4-item bottom bar)
// and menuNavForRole (everything else, in the top hamburger menu).
export function navForRole(
  role: OrgRole | string | undefined,
  isSuperAdmin = false,
  isClassTeacher = false,
  hasBandScope = false,
): NavItem[] {
  // The platform operator gets the Schools item on top of whatever role they
  // hold in the org they're currently inside.
  const extra = isSuperAdmin ? [platform] : [];
  switch (role) {
    case "admin":
      return [...extra, dashboard, lucy, plan, students,
        ...(hasBandScope ? [bands] : []), staff, fees, tasks, setup];
    case "teacher":
      // My Class sits right after My Day — the two screens a class teacher
      // actually lives in (D-03). Absent entirely for a subject teacher.
      // Homework lost its own item (founder, 2026-08-05): the homework log now
      // lives inside Students → Academics, beside the class log and the exams
      // it belongs with. `/homework` itself is untouched and still reachable —
      // it is the check-sheet desk (`D-36`) and Academics links to it.
      return [
        ...extra, myDay, ...(isClassTeacher ? [myClass] : []),
        attendance, lucy, sessions, planForTeacher, studentsForTeacher,
        ...(hasBandScope ? [bands] : []), timesheet, tasks,
      ];
    case "parent":
      return []; // parents never see the staff shell — they live under /parent
    default:
      return [...extra, tasks];
  }
}

// The mobile bottom tab bar: exactly four thumb-reachable primaries (founder
// decision 2026-07-24). Same shape for both roles — only the first slot differs
// (admin plans the school, a teacher runs their day). Super-admin's Schools item
// is NOT here; it rides in the hamburger so the bar stays at four.
export function bottomNavForRole(role: OrgRole | string | undefined): NavItem[] {
  switch (role) {
    case "admin":
      // The bar navigates — it never opens a drawer, so Students lands on
      // Directory and the tabs inside the area carry you across.
      return [plan, tasks, { ...students, children: undefined }, lucy];
    case "teacher":
      return [myDay, tasks, studentsForTeacher, lucy];
    case "parent":
      return [];
    default:
      return [tasks];
  }
}

// The mobile hamburger menu: every nav item NOT already in the bottom bar,
// keeping the sidebar's order (admin → Dashboard/Fees/Setup, teacher →
// Sessions/Plan, plus Schools for the platform operator).
export function menuNavForRole(
  role: OrgRole | string | undefined,
  isSuperAdmin = false,
  isClassTeacher = false,
  hasBandScope = false,
): NavItem[] {
  const inBottom = new Set(bottomNavForRole(role).map((i) => i.href));
  return navForRole(role, isSuperAdmin, isClassTeacher, hasBandScope)
    .filter((i) => !inBottom.has(i.href));
}

// Role-aware landing after login (SPRD2 §3): admin → Dashboard (leads with the
// daily report), teacher → My Day. The platform operator lands on the school
// list instead — their day starts above any single org.
export function landingForRole(
  role: OrgRole | string | undefined,
  isSuperAdmin = false,
): string {
  if (isSuperAdmin) return "/platform";
  if (role === "admin") return "/dashboard"; // school dashboard / daily report
  if (role === "teacher") return "/my-day"; // My Day period timeline
  if (role === "parent") return "/parent"; // parent portal (child's day)
  return "/tasks";
}
