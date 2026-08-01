"use client";

// My time → My month (`D-78`, teacher side). Her own record, and only hers.
//
// Stated as a requirement rather than a feature in the module notes: *a teacher
// must be able to see her own attendance record.* If the number is ever
// disputed, the evidence has to be visible to the person disputing it.

import { AuthGuard } from "@/components/auth/auth-guard";
import { StaffMonthSummary } from "@/components/staff/month-summary";
import { PageHeader } from "@/components/ui/page-header";

export default function MyMonthPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <PageHeader title="My month"
        subtitle="Days you worked out of the month's working days, and your leave balance." />
      <StaffMonthSummary mine />
    </AuthGuard>
  );
}
