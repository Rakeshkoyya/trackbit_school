"use client";

import { Loader2, LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { landingForRole } from "@/components/layout/nav-items";
import { SubTabs } from "@/components/layout/sub-tabs";
import { useAuth } from "@/contexts/auth-context";
import { cn } from "@/lib/utils";

import { ParentProvider, useParentPortal } from "./parent-context";

const TABS = [
  { label: "Today", href: "/parent" },
  { label: "Progress", href: "/parent/progress" },
  { label: "Report", href: "/parent/report" },
  { label: "Profile", href: "/parent/profile" },
];

function ChildSwitcher() {
  const { me, child, setChildId } = useParentPortal();
  if (!me || me.children.length <= 1) return null;
  return (
    <div className="flex gap-1.5 overflow-x-auto pb-1">
      {me.children.map((c) => (
        <button
          key={c.student_id}
          onClick={() => setChildId(c.student_id)}
          className={cn(
            "whitespace-nowrap rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            c.student_id === child?.student_id
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-card text-muted-foreground hover:text-foreground",
          )}
        >
          {c.full_name.split(" ")[0]}
          {c.class_label ? ` · ${c.class_label}` : ""}
        </button>
      ))}
    </div>
  );
}

function PortalShell({ children }: { children: React.ReactNode }) {
  const { me } = useParentPortal();
  const { logout } = useAuth();
  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-xl flex-col px-4 pb-[calc(2.5rem+env(safe-area-inset-bottom))] pt-4">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {me?.org_name ?? " "}
          </p>
          <h1 className="truncate text-lg font-semibold tracking-tight">
            {me ? `Hello, ${me.name.split(" ")[0]}` : " "}
          </h1>
        </div>
        <button
          onClick={logout}
          className="mt-1 rounded-md p-2 text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Sign out"
        >
          <LogOut className="h-4 w-4" />
        </button>
      </header>
      <ChildSwitcher />
      <SubTabs tabs={TABS} />
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}

/** Gate: only a parent session may enter; others bounce to their own landing. */
export default function ParentPortalLayout({ children }: { children: React.ReactNode }) {
  const { me, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!me) router.replace("/parent/login");
    else if (me.org_role !== "parent") router.replace(landingForRole(me.org_role, me.is_super_admin));
  }, [loading, me, router]);

  if (loading || !me || me.org_role !== "parent") {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  return (
    <ParentProvider>
      <PortalShell>{children}</PortalShell>
    </ParentProvider>
  );
}
