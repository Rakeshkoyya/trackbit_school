import {
  BarChart3,
  Building2,
  CalendarClock,
  CalendarRange,
  CheckSquare,
  GraduationCap,
  Settings2,
  Sparkles,
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
const lucy: NavItem = { label: "Lucy", href: "/lucy", icon: Sparkles };
const platform: NavItem = { label: "Schools", href: "/platform", icon: Building2 };

// Role-aware primary nav (single source of truth for sidebar + bottom tabs).
// SPRD2 §3 + Lucy (founder decision 2026-07-12) — both roles get the agent.
// Hard rule (§2): teachers never see Fees/Setup. NOTE: bottom tabs cap at 5,
// so Tasks falls off MOBILE tabs for both roles with Lucy inserted; it stays
// in the desktop sidebar. Reorder here if that's the wrong trade.
export function navForRole(
  role: OrgRole | string | undefined,
  isSuperAdmin = false,
): NavItem[] {
  // The platform operator gets the Schools item on top of whatever role they
  // hold in the org they're currently inside.
  const extra = isSuperAdmin ? [platform] : [];
  switch (role) {
    case "admin":
      return [...extra, dashboard, lucy, plan, students, fees, tasks, setup];
    case "teacher":
      return [...extra, myDay, lucy, sessions, plan, students, tasks];
    default:
      return [...extra, tasks];
  }
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
  return "/tasks";
}
