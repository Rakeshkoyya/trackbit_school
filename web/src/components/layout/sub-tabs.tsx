"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

import { cn } from "@/lib/utils";

export type SubTab = { label: string; href: string };

/**
 * Route-based tab bar for a consolidated IA area (Tasks · Plan · Students ·
 * Setup — SPRD2 §3). The first tab is the area root and matches exactly; the
 * rest also match their nested routes. Rendered by each area's layout so every
 * tab page shares one header.
 */
export function SubTabs({ tabs }: { tabs: SubTab[] }) {
  const pathname = usePathname();
  const rootHref = tabs[0]?.href;
  const activeRef = useRef<HTMLAnchorElement>(null);

  // Keep the current tab visible on a narrow, horizontally-scrolling bar so a
  // trailing tab (e.g. "Timetable") is never clipped off-screen.
  useEffect(() => {
    activeRef.current?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [pathname]);

  return (
    <div className="mb-5 flex gap-1 overflow-x-auto border-b border-border">
      {tabs.map((t) => {
        const active =
          t.href === rootHref ? pathname === t.href : pathname === t.href || pathname.startsWith(t.href + "/");
        return (
          <Link
            key={t.href}
            href={t.href}
            ref={active ? activeRef : undefined}
            className={cn(
              "whitespace-nowrap border-b-2 px-3.5 py-2.5 text-sm font-medium transition-colors",
              active
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {t.label}
          </Link>
        );
      })}
    </div>
  );
}
