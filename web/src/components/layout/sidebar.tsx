"use client";

import { ChevronDown, Lock } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/contexts/auth-context";
import { useFeatures } from "@/lib/use-feature";
import { cn } from "@/lib/utils";
import { navForRole, type NavItem } from "./nav-items";

const isUnder = (pathname: string, href: string) =>
  pathname === href || pathname.startsWith(href + "/");

const rowClass = (active: boolean) =>
  cn("flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
    active ? "bg-accent text-accent-foreground"
      : "text-muted-foreground hover:bg-muted hover:text-foreground");

/** A nav item that opens into its two halves instead of navigating.
 *
 *  It starts open whenever you are already inside it, so the tab you are on is
 *  never hidden behind a press — a drawer that closes over your own location is
 *  how a person loses track of where they are. Closing it by hand while inside
 *  is still allowed; that is a deliberate act, not a default.
 */
function NavGroup({ item, pathname }: { item: NavItem; pathname: string }) {
  const inside = item.children!.some((c) => isUnder(pathname, c.href))
    || isUnder(pathname, item.href);
  const [open, setOpen] = useState(inside);
  const Icon = item.icon;
  const expanded = open || inside;

  return (
    <li>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setOpen(!expanded)}
        className={rowClass(inside)}
      >
        <Icon className="h-5 w-5" strokeWidth={inside ? 2.2 : 1.8} />
        {item.label}
        <ChevronDown
          className={cn("ml-auto h-4 w-4 transition-transform", expanded && "rotate-180")}
          aria-hidden
        />
      </button>
      {expanded ? (
        // Indented under the parent and tied to it by a hairline, so the two
        // read as one thing with two doors rather than four unrelated items.
        <ul className="ml-[1.4rem] mt-0.5 space-y-0.5 border-l border-border pl-2">
          {item.children!.map((child) => {
            const active = isUnder(pathname, child.href);
            const ChildIcon = child.icon;
            return (
              <li key={child.href}>
                <Link href={child.href} className={cn(rowClass(active), "py-1.5")}>
                  <ChildIcon className="h-4 w-4" strokeWidth={active ? 2.2 : 1.8} />
                  {child.label}
                </Link>
              </li>
            );
          })}
        </ul>
      ) : null}
    </li>
  );
}

/** A padlock on an item the school's package does not include (`D-106`).
 *
 *  The item is NOT hidden and the link still works — founder's rule: "we show
 *  everything on the screen like as it is now", and the block happens on
 *  arrival, where the wall can explain itself and quote a price. A hidden item
 *  teaches a school nothing about what it could buy. */
function NavLock() {
  return <Lock className="ml-auto h-3.5 w-3.5 shrink-0 opacity-60" aria-label="locked" />;
}

/** Desktop sidebar — visible on lg+. */
export function Sidebar() {
  const pathname = usePathname();
  const { me } = useAuth();
  const features = useFeatures();
  const items = navForRole(me?.org_role, me?.is_super_admin, me?.is_class_teacher, me?.has_band_scope);

  return (
    <aside className="hidden w-60 shrink-0 flex-col border-r border-border bg-card lg:flex">
      <div className="flex h-16 items-center gap-2 px-6">
        <span className="text-lg font-semibold tracking-tight text-primary">TrackBit</span>
      </div>
      <nav className="flex-1 px-3 py-2">
        <ul className="space-y-1">
          {items.map((item) => {
            if (item.children?.length) {
              return <NavGroup key={item.href} item={item} pathname={pathname} />;
            }
            const active = isUnder(pathname, item.href);
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  data-tour={item.tour}
                  className={rowClass(active)}
                >
                  <Icon className="h-5 w-5" strokeWidth={active ? 2.2 : 1.8} />
                  {item.label}
                  {item.feature && !features.has(item.feature) ? <NavLock /> : null}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </aside>
  );
}
