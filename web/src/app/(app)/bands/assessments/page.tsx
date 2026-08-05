"use client";

/**
 * ABC bands → Assessments (founder 2026-08-05).
 *
 * The third thing the programme needed and did not have. She could give work
 * (per-student homework) and write a weekly check-in; what she could not do was
 * **set a check and record how each child did on it**, which is the only way
 * "did the last three weeks move anybody?" gets an answer that is not memory.
 *
 * Not exams: `assessment_cycles` is the school's academic record and moves a
 * child's band under `D-76`. Nothing recorded here reaches his standing, his
 * report card, or his band.
 */

import { BandAssessments } from "@/components/school/band-assessments";
import { PageHeader } from "@/components/ui/page-header";

export default function BandsAssessmentsPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Assessments"
        subtitle="The checks you have set for your support children, and how each of them did."
      />
      <div className="mt-4">
        <BandAssessments />
      </div>
    </div>
  );
}
