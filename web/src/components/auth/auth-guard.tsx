"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Loader2 } from "lucide-react";

import { useAuth } from "@/contexts/auth-context";
import type { OrgRole } from "@/lib/types";

function FullScreenSpinner() {
  return (
    <div className="flex min-h-dvh items-center justify-center">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

/** Gate authenticated areas; redirect to login when there's no session. */
export function AuthGuard({
  children,
  requireRole,
}: {
  children: React.ReactNode;
  requireRole?: OrgRole;
}) {
  const { me, loading, mustSetPassword } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    if (!me) {
      router.replace("/auth/login");
    } else if (mustSetPassword) {
      router.replace("/auth/set-password");
    } else if (requireRole && me.org_role !== requireRole) {
      router.replace("/home");
    }
  }, [loading, me, mustSetPassword, requireRole, router]);

  if (loading || !me || mustSetPassword || (requireRole && me.org_role !== requireRole)) {
    return <FullScreenSpinner />;
  }
  return <>{children}</>;
}
