"use client";

/**
 * `/support` — the owner's list, kept at its own URL.
 *
 * The list itself is `SupportListView`, shared with ABC bands → My students
 * (founder 2026-08-04). Two doors, one screen: a teacher who lives in the Support
 * nav item keeps her muscle memory, and one who arrives through the programme's
 * own area finds it where she expects. Every `/support/[id]` link in the product
 * still resolves here.
 */

import { AuthGuard } from "@/components/auth/auth-guard";
import { SupportListView } from "@/components/school/support-list-view";
import { PageHeader } from "@/components/ui/page-header";

export default function SupportPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <div className="mx-auto max-w-3xl">
        <PageHeader
          title="My support students"
          subtitle="Staff-only — a support tier never reaches a parent"
        />
        <div className="mt-4">
          <SupportListView />
        </div>
      </div>
    </AuthGuard>
  );
}
