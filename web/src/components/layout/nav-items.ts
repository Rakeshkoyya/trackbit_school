import {
  BarChart3,
  Building2,
  CalendarClock,
  CalendarRange,
  CheckSquare,
  ClipboardCheck,
  Clock,
  GraduationCap,
  HeartHandshake,
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
const students: NavItem = { label: "Students", href: "/students", icon: GraduationCap };
// V1-5 (D-36). Checking homework is a DESK activity, not a between-classes tap,
// so it gets its own screen instead of a block at the top of My Day.
const homework: NavItem = { label: "Homework", href: "/homework", icon: ClipboardCheck };
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
// V1-9 (D-71/D-87). The owner of a handful of Band C children: her list, and
// the weekly check-in. The 9:02 teacher never opens it — her band-aware surface
// is the checks section of the period card, which differentiates already.
const support: NavItem = { label: "Support", href: "/support", icon: HeartHandshake };
// Founder 2026-08-04. The programme's own area — bands were reachable only as a
// tab under Students, which is where you go to look a child up, not where you go
// to run a support programme. Shown only to members with a monitored
// class-subject (`me.has_band_scope`): an admin always, a teacher only for the
// subjects the school actually monitors.
const bands: NavItem = { label: "ABC bands", href: "/bands", icon: Layers };

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
      return [
        ...extra, myDay, ...(isClassTeacher ? [myClass] : []),
        lucy, sessions, planForTeacher, homework, students,
        ...(hasBandScope ? [bands] : []), support, timesheet, tasks,
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
      return [plan, tasks, students, lucy];
    case "teacher":
      return [myDay, tasks, students, lucy];
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
