"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { FeatureGate } from "@/components/plan/upgrade";
import { FEATURES } from "@/lib/features";
import { cn } from "@/lib/utils";

/**
 * The fee desk (FE-1).
 *
 * Fees is a Pro feature (`D-106`). The gate sits on the AREA rather than each
 * page so every sub-route — the board, the structure grid, the student table, a
 * family's ledger — is covered by one decision.
 *
 * ⚠️ SY-2's lesson applies directly here: *Plan → Exams was blank because it was
 * a Pro feature with no gate — a 402, not missing data.* Any new fee route must
 * live under this layout, or it renders an empty screen to a Free school instead
 * of the upgrade card.
 *
 * This composes with the fee fence and does not replace it: every fee route is
 * admin-only whatever the school's plan is, enforced server-side.
 *
 * The three tabs are in **frequency order**, which is the reverse of setup
 * order. An admin sets a year up once, right to left; she reads the board every
 * morning. Landing her on the thing she opens daily is worth more than
 * rehearsing the sequence she followed in April — and the Dashboard's empty
 * state points at Structure for the school that has not started yet.
 */
const TABS = [
  { href: "/fees", label: "Dashboard" },
  { href: "/fees/students", label: "Students" },
  { href: "/fees/structure", label: "Structure" },
];

export default function FeesLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <FeatureGate feature={FEATURES.feesCollection}>
      <div>
        <h1 className="mb-3 text-2xl font-semibold tracking-tight">Fees</h1>
        <nav className="mb-6 flex gap-1 border-b border-border" aria-label="Fees">
          {TABS.map((tab) => {
            // `/fees` would otherwise match every sub-route, so the root tab
            // needs an exact test while the others match their subtree.
            const active =
              tab.href === "/fees"
                ? pathname === "/fees"
                : pathname.startsWith(tab.href);
            return (
              <Link
                key={tab.href}
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "-mb-px border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                  active
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )}
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>
        {children}
      </div>
    </FeatureGate>
  );
}
