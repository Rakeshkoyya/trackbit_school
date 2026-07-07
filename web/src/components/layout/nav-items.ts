import {
  BarChart3,
  BookOpen,
  CalendarClock,
  CalendarRange,
  CheckCircle2,
  ClipboardList,
  GraduationCap,
  Home,
  LayoutGrid,
  type LucideIcon,
  Sun,
  Users,
  Wallet,
} from "lucide-react";

import type { OrgRole } from "@/lib/types";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  tour?: string; // data-tour anchor for the guided tour
};

// The existing task module (M5) surfaces — available to all staff roles.
export const memberNav: NavItem[] = [
  { label: "Home", href: "/home", icon: Home },
  { label: "Boards", href: "/boards", icon: LayoutGrid, tour: "nav-boards" },
  { label: "Done", href: "/done", icon: CheckCircle2 },
];

const myDay: NavItem = { label: "My Day", href: "/classroom", icon: Sun };
const sessions: NavItem = { label: "Sessions", href: "/sessions", icon: CalendarClock };
const planner: NavItem = { label: "Planner", href: "/planner", icon: CalendarRange };
const students: NavItem = { label: "Students", href: "/students", icon: GraduationCap };
const assessments: NavItem = { label: "Assessments", href: "/assessments", icon: ClipboardList };
const fees: NavItem = { label: "Fees", href: "/fees", icon: Wallet };
const setup: NavItem = { label: "Setup", href: "/academics", icon: BookOpen };
const dashboard: NavItem = { label: "Dashboard", href: "/insights", icon: BarChart3 };
const members: NavItem = { label: "Members", href: "/members", icon: Users, tour: "nav-members" };

// Role-aware primary nav (single source of truth for sidebar + bottom tabs).
// Hard rule (SPRD v2 §2): teachers never see Fees/Dashboard/Setup/Members.
export function navForRole(role: OrgRole | string | undefined): NavItem[] {
  switch (role) {
    case "admin":
      return [...memberNav, myDay, sessions, planner, students, assessments, fees, dashboard, setup, members];
    case "teacher":
      return [...memberNav, myDay, sessions, planner, students, assessments];
    default:
      return memberNav;
  }
}

// Role-aware landing ("Today") after login (SPRD v2 §2): admin → school
// dashboard, teacher → My Day. One place to extend as module homes evolve.
export function landingForRole(role: OrgRole | string | undefined): string {
  if (role === "admin") return "/insights";      // Director → school dashboard
  if (role === "teacher") return "/classroom";    // Teacher → My Day
  return "/home";
}
