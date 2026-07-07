"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/contexts/auth-context";
import type { OrgRole } from "@/lib/types";
import { landingForRole } from "@/components/layout/nav-items";

function FullScreenSpinner() {
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

/** Gate authenticated areas; redirect to login when there's no session.
 *  `requireRole` locks to one role; `allow` accepts any role in the list. */
export function AuthGuard({
  children,
  requireRole,
  allow,
}: {
  children: React.ReactNode;
  requireRole?: OrgRole;
  allow?: OrgRole[];
}) {
  const { me, loading, mustSetPassword } = useAuth();
  const router = useRouter();

  const denied = (r: OrgRole) =>
    (requireRole && r !== requireRole) || (allow && !allow.includes(r));

  useEffect(() => {
    if (loading) return;
    if (!me) {
      router.replace("/auth/login");
    } else if (mustSetPassword) {
      router.replace("/auth/set-password");
    } else if (denied(me.org_role)) {
      router.replace(landingForRole(me.org_role));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, me, mustSetPassword, requireRole, allow, router]);

  if (loading || !me || mustSetPassword || denied(me.org_role)) {
    return <FullScreenSpinner />;
  }
  return <>{children}</>;
}
