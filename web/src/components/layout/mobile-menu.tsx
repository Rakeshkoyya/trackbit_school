"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

import { menuNavForRole, type NavItem } from "./nav-items";

const isUnder = (pathname: string, href: string) =>
  pathname === href || pathname.startsWith(href + "/");

const rowClass = (active: boolean) =>
  cn("flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
    active ? "bg-accent text-accent-foreground" : "text-foreground hover:bg-muted");

/**
 * A group's halves, OPEN — under the group's name, never behind a press.
 *
 * This menu is already a popover; a drawer inside it would be a second layer of
 * open-to-find for two words that cost one row each. So the halves are always
 * on screen, and the group's name sits above them as a label rather than a link
 * — pressing "Students" here would only repeat Directory, and the bottom bar
 * already carries that press.
 */
function MenuGroup({ item, pathname, onNavigate }: {
  item: NavItem; pathname: string; onNavigate: () => void;
}) {
  const Icon = item.icon;
  return (
    <div className="py-1">
      <div className="flex items-center gap-3 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className="h-4 w-4 shrink-0" strokeWidth={1.8} aria-hidden />
        {item.label}
      </div>
      {/* Indented and tied to the label by a hairline, exactly as the sidebar
          draws it, so the halves read as one thing with two doors. */}
      <div className="ml-[1.4rem] border-l border-border pl-2">
        {item.children!.map((child) => {
          const active = isUnder(pathname, child.href);
          const ChildIcon = child.icon;
          return (
            <Link
              key={child.href}
              href={child.href}
              role="menuitem"
              onClick={onNavigate}
              className={cn(rowClass(active), "py-2")}
            >
              <ChildIcon className="h-4 w-4 shrink-0" strokeWidth={active ? 2.2 : 1.8} />
              {child.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Mobile-only hamburger (top-left of the Topbar). Holds every nav item that
 * isn't in the four-slot bottom bar — Dashboard/Fees/Setup for an admin,
 * Sessions/Plan for a teacher, plus Schools for the platform operator. Hidden on
 * lg+ where the full sidebar takes over. Same lightweight popover pattern as
 * AccountMenu (no popover primitive: absolute panel, close on outside-click /
 * Escape / navigation).
 *
 * A grouped item keeps its level here (MenuGroup). It used to be flattened to
 * its children, which read as unlabelled rows — and for an admin it was worse
 * than that: the bar carries the Students group's own href, the group was
 * filtered out of this menu wholesale, and Academics had no door on a phone.
 */
export function MobileMenu() {
  const pathname = usePathname();
  const { me } = useAuth();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const items = menuNavForRole(me?.org_role, me?.is_super_admin, me?.is_class_teacher, me?.has_band_scope);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (items.length === 0) return null;

  return (
    <div ref={rootRef} className="relative lg:hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Menu"
        className="-ml-1 rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      >
        <Menu className="h-5 w-5" />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="More"
          style={{ transformOrigin: "top left" }}
          className="tb-menu-in absolute left-0 top-full z-50 mt-2 w-56 overflow-hidden rounded-xl border border-border bg-card p-1.5 shadow-xl"
        >
          {items.map((item) => {
            if (item.children?.length) {
              return (
                <MenuGroup
                  key={item.href}
                  item={item}
                  pathname={pathname}
                  onNavigate={() => setOpen(false)}
                />
              );
            }
            const active = isUnder(pathname, item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                role="menuitem"
                data-tour={item.tour}
                onClick={() => setOpen(false)}
                className={rowClass(active)}
              >
                <Icon className="h-5 w-5 shrink-0" strokeWidth={active ? 2.2 : 1.8} />
                {item.label}
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
