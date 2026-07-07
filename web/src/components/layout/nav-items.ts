import {
  BarChart3,
  CheckCircle2,
  Home,
  LayoutGrid,
  type LucideIcon,
  Users,
} from "lucide-react";

export type NavItem = {
  label: string;
  href: string;
  icon: LucideIcon;
  tour?: string; // data-tour anchor for the guided tour
};

// Bottom tab bar (mobile) + primary sidebar (desktop).
export const memberNav: NavItem[] = [
  { label: "Home", href: "/home", icon: Home },
  { label: "Boards", href: "/boards", icon: LayoutGrid, tour: "nav-boards" },
  { label: "Done", href: "/done", icon: CheckCircle2 },
];

// Appended for admins. Settings lives in the account menu (avatar popover),
// not the primary nav.
export const adminNav: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: BarChart3 },
  { label: "Members", href: "/members", icon: Users, tour: "nav-members" },
];

export function navForRole(role: string | undefined): NavItem[] {
  return role === "admin" ? [...memberNav, ...adminNav] : memberNav;
}
