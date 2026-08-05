"use client";

// Staff → People (founder, 2026-08-05). Admin-only: the directory joins the
// homeroom and class-subject assignments onto every membership, which is a
// school-wide read a teacher has no business making.

import { AuthGuard } from "@/components/auth/auth-guard";
import { StaffDirectoryTable } from "@/components/staff/staff-directory";
import { PageHeader } from "@/components/ui/page-header";

export default function StaffDirectoryPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <PageHeader
        title="People"
        subtitle="Everyone who works here, what they take, and whose class is whose. Tap a row to open their file."
      />
      <StaffDirectoryTable />
    </AuthGuard>
  );
}
