"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { OrgDashboard } from "@/components/reports/org-dashboard";

export default function DashboardPage() {
  return (
    <AuthGuard requireRole="admin">
      <OrgDashboard />
    </AuthGuard>
  );
}
