"use client";

// Staff → Month (`D-78`). Days worked out of the month's working days, leave
// used, leave left — for every member of staff. No money, by design.

import { AuthGuard } from "@/components/auth/auth-guard";
import { StaffMonthSummary } from "@/components/staff/month-summary";
import { PageHeader } from "@/components/ui/page-header";

export default function StaffMonthPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <PageHeader title="The month"
        subtitle="Days worked out of working days, leave used, leave left." />
      <StaffMonthSummary />
    </AuthGuard>
  );
}
