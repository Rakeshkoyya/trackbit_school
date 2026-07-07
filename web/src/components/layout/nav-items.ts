import {
  BarChart3,
  BookOpen,
  CalendarRange,
  CheckCircle2,
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
const planner: NavItem = { label: "Planner", href: "/planner", icon: CalendarRange };
const students: NavItem = { label: "Students", href: "/students", icon: GraduationCap };
const fees: NavItem = { label: "Fees", href: "/fees", icon: Wallet };
const setup: NavItem = { label: "Setup", href: "/academics", icon: BookOpen };
const dashboard: NavItem = { label: "Dashboard", href: "/dashboard", icon: BarChart3 };
const members: NavItem = { label: "Members", href: "/members", icon: Users, tour: "nav-members" };

// Role-aware primary nav (single source of truth for sidebar + bottom tabs).
// Hard rules (SPRD §3.3): teachers never see Fees; office sees only tasks + Fees.
export function navForRole(role: OrgRole | string | undefined): NavItem[] {
  switch (role) {
    case "admin":
      return [...memberNav, myDay, planner, students, fees, dashboard, setup, members];
    case "coordinator":
      return [...memberNav, myDay, planner, students, dashboard, setup];
    case "office":
      return [...memberNav, fees];
    case "teacher":
      return [...memberNav, myDay, planner, students];
    default:
      return memberNav;
  }
}

// Role-aware landing ("Today") after login (SPRD §6.2: director=Dashboard,
// teacher=My Day, office=Fees). Only the director's overview exists today; the
// teacher My Day (P1) and Fees home (P0-E) land later, so those roles route to
// the task Home for now. One place to extend as the module homes arrive.
export function landingForRole(role: OrgRole | string | undefined): string {
  return role === "admin" ? "/dashboard" : "/home";
}
