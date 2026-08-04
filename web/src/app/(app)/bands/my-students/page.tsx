"use client";

/**
 * ABC bands → My students (teacher).
 *
 * The same list as `/support`, inside the area that now owns the subject.
 * `SupportListView` is mounted in both places rather than written twice — the
 * house rule that keeps two screens about one thing from drifting apart.
 *
 * Clicking a child opens `/support/[id]`, which is where the weekly check-in and
 * his already-written week live. That page is not duplicated here: it is the one
 * screen the whole module lives or dies on, and a second copy of it is a second
 * place for the check-in to be half-implemented.
 */

import { SupportListView } from "@/components/school/support-list-view";
import { PageHeader } from "@/components/ui/page-header";

export default function BandsMyStudentsPage() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="My students"
        subtitle="The Band C children you own — click one to write this week's check-in."
      />
      <div className="mt-4">
        <SupportListView />
      </div>
    </div>
  );
}
