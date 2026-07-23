"use client";

import { Menu } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

import { menuNavForRole } from "./nav-items";

/**
 * Mobile-only hamburger (top-left of the Topbar). Holds every nav item that
 * isn't in the four-slot bottom bar — Dashboard/Fees/Setup for an admin,
 * Sessions/Plan for a teacher, plus Schools for the platform operator. Hidden on
 * lg+ where the full sidebar takes over. Same lightweight popover pattern as
 * AccountMenu (no popover primitive: absolute panel, close on outside-click /
 * Escape / navigation).
 */
export function MobileMenu() {
  const pathname = usePathname();
  const { me } = useAuth();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const items = menuNavForRole(me?.org_role, me?.is_super_admin);

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
            const active = pathname === item.href || pathname.startsWith(item.href + "/");
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                role="menuitem"
                data-tour={item.tour}
                onClick={() => setOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors",
                  active ? "bg-accent text-accent-foreground" : "text-foreground hover:bg-muted",
                )}
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
