"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { PlatformScreen } from "@/components/school/platform-screen";

export default function PlatformPage() {
  return (
    <AuthGuard requireSuperAdmin>
      <PlatformScreen />
    </AuthGuard>
  );
}
