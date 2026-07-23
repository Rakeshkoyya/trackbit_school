"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";
import { bottomNavForRole } from "./nav-items";

/** Mobile bottom tab bar — hidden on lg+ where the sidebar takes over. */
export function BottomTabs() {
  const pathname = usePathname();
  const { me } = useAuth();
  // Four thumb-reachable primaries; everything else lives in the top hamburger
  // (MobileMenu) and the account menu (avatar popover).
  const items = bottomNavForRole(me?.org_role);

  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden">
      <ul className="mx-auto flex max-w-md items-stretch justify-around">
        {items.map((item) => {
          const active = pathname === item.href || pathname.startsWith(item.href + "/");
          const Icon = item.icon;
          return (
            <li key={item.href} className="flex-1">
              <Link
                href={item.href}
                data-tour={item.tour}
                className={cn(
                  "flex flex-col items-center gap-1 py-2.5 text-xs font-medium transition-colors",
                  active ? "text-primary" : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="h-5 w-5" strokeWidth={active ? 2.4 : 1.8} />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
