"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { EnquiriesScreen } from "@/components/school/enquiries-screen";

export default function EnquiriesPage() {
  return (
    <AuthGuard requireSuperAdmin>
      <EnquiriesScreen />
    </AuthGuard>
  );
}
