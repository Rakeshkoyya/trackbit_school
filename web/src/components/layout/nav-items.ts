import {
  BarChart3,
  CheckCircle2,
  Home,
  LayoutGrid,
  type LucideIcon,
  Users,
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

// Whole-school dashboard — director + coordinator (SPRD §3.3). Members/settings
// live in the account menu (avatar popover), admin-only.
const dashboardNav: NavItem[] = [{ label: "Dashboard", href: "/dashboard", icon: BarChart3 }];
const membersNav: NavItem[] = [{ label: "Members", href: "/members", icon: Users, tour: "nav-members" }];

// Role-aware primary nav. As the academic (Planner/Classroom/Sessions/Students/
// Assessments) and Fees routes land per SPRD §6.2, extend the per-role lists
// here — this is the single source of truth for both sidebar and bottom tabs.
export function navForRole(role: OrgRole | string | undefined): NavItem[] {
  switch (role) {
    case "admin":
      return [...memberNav, ...dashboardNav, ...membersNav];
    case "coordinator":
      return [...memberNav, ...dashboardNav];
    case "office":
    case "teacher":
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
