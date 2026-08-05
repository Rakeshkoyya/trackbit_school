"use client";

/**
 * ABC bands → My students (teacher).
 *
 * Rewritten from the grouped card list (founder 2026-08-05): a class filter, a
 * table, and the two actions she opens this screen for — her assigned work for a
 * child, and her log about him — on the row rather than two navigations away.
 *
 * Clicking a child still opens `/support/[id]`, which is where the weekly
 * check-in and his already-written week live. That page is deliberately not
 * duplicated here: it is the one screen the whole module lives or dies on, and a
 * second copy of it is a second place for the check-in to be half-implemented.
 */

import { BandMyStudents } from "@/components/school/band-my-students";
import { PageHeader } from "@/components/ui/page-header";

export default function BandsMyStudentsPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="My students"
        subtitle="The children assigned to you — their work, their log, and this week's check-in."
      />
      <div className="mt-4">
        <BandMyStudents />
      </div>
    </div>
  );
}
