"use client";

// My time → My month (`D-78`, teacher side). Her own record, and only hers.
//
// Stated as a requirement rather than a feature in the module notes: *a teacher
// must be able to see her own attendance record.* If the number is ever
// disputed, the evidence has to be visible to the person disputing it.

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { AuthGuard } from "@/components/auth/auth-guard";
import { StaffMonthSummary } from "@/components/staff/month-summary";
import { buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";

export default function MyMonthPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="[&>header]:mb-0">
          <PageHeader title="My month"
            subtitle="Days you worked out of the month's working days, and your leave balance." />
        </div>
        {/* V1-16 — the same argument as this page's own: the record of where
            your time went should be readable by the person whose time it was. */}
        <Link href="/staff/member/me"
          className={buttonVariants({ variant: "outline", size: "sm" })}>
          Where my time went <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </div>
      <StaffMonthSummary mine />
    </AuthGuard>
  );
}
