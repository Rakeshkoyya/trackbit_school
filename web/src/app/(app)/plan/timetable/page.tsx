"use client";

import { CalendarRange } from "lucide-react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";

function TimetableInner() {
  return (
    <div>
      <div className="mb-4">
        <PageHeader title="Timetable" subtitle="Weekly period grid per class" />
      </div>
      <EmptyState
        icon={CalendarRange}
        title="Timetable is coming next"
        body="The period grid, photo/xlsx import and assisted draft land in V2-P1. My Day will render each teacher's day straight from it."
      />
    </div>
  );
}

export default function TimetablePage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <TimetableInner />
    </AuthGuard>
  );
}
