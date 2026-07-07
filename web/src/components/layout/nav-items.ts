import {
  BarChart3,
  CalendarClock,
  CalendarRange,
  CheckSquare,
  GraduationCap,
  Settings2,
  Sun,
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
const students: NavItem = { label: "Students", href: "/students", icon: GraduationCap };
const tasks: NavItem = { label: "Tasks", href: "/tasks", icon: CheckSquare, tour: "nav-boards" };
const fees: NavItem = { label: "Fees", href: "/fees", icon: Wallet };
const dashboard: NavItem = { label: "Dashboard", href: "/dashboard", icon: BarChart3 };
const setup: NavItem = { label: "Setup", href: "/setup", icon: Settings2, tour: "nav-members" };

// Role-aware primary nav (single source of truth for sidebar + bottom tabs).
// SPRD2 §3 — teacher sidebar (5): My Day · Sessions · Plan · Students · Tasks.
// Admin sidebar (6): Dashboard · Plan · Students · Fees · Tasks · Setup
// (Members lives inside Setup). Hard rule (§2): teachers never see Fees/Setup.
export function navForRole(role: OrgRole | string | undefined): NavItem[] {
  switch (role) {
    case "admin":
      return [dashboard, plan, students, fees, tasks, setup];
    case "teacher":
      return [myDay, sessions, plan, students, tasks];
    default:
      return [tasks];
  }
}

// Role-aware landing after login (SPRD2 §3): admin → Dashboard (leads with the
// daily report), teacher → My Day. One place to extend as module homes evolve.
export function landingForRole(role: OrgRole | string | undefined): string {
  if (role === "admin") return "/dashboard"; // school dashboard / daily report
  if (role === "teacher") return "/my-day"; // My Day period timeline
  return "/tasks";
}
