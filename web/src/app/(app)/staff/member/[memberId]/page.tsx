"use client";

// One member of staff's record (V1-16). Reached by tapping a name on the
// day-book, on the overview's staff block, or on the week table.
//
// Both roles are allowed, and the SERVER decides what that means: an admin reads
// anyone in their school, a teacher reads only themselves and gets a 403 on a
// colleague. A person whose time is being written down must be able to read what
// was written — the same rule `/staff/month` has held since V1-4, and the reason
// the endpoint is `require_academic` rather than `require_admin`.

import { use } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { StaffRecordView } from "@/components/staff/record-view";

export default function StaffMemberPage({
  params,
}: {
  params: Promise<{ memberId: string }>;
}) {
  const { memberId } = use(params);
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <StaffRecordView memberId={memberId} />
    </AuthGuard>
  );
}
