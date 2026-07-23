"use client";

import { AccountMenu } from "@/components/layout/account-menu";
import { MobileMenu } from "@/components/layout/mobile-menu";
import { NotificationsToggle } from "@/components/layout/notifications-toggle";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { useAuth } from "@/contexts/auth-context";

export function Topbar() {
  const { me } = useAuth();

  return (
    <header className="relative z-30 flex h-14 items-center justify-between border-b border-border bg-card/80 px-4 backdrop-blur lg:px-8">
      <div className="flex min-w-0 items-center gap-1.5">
        <MobileMenu />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{me?.org.name}</p>
          <p className="truncate text-xs text-muted-foreground">
            {me?.user.name}
            {me?.org_role === "admin" ? " · admin" : ""}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <NotificationsToggle />
        <AccountMenu />
      </div>
    </header>
  );
}
