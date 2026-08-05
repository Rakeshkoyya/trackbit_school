"use client";

/**
 * Plan → Syllabus → Exam mapping (SY-1).
 *
 * One class at a time, because a portion is per class-subject and a school-wide
 * grid of ticks would be a wall nobody could decide anything in. The class
 * picker is the only control above the board.
 */

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ExamSyllabusMap } from "@/components/school/exam-syllabus-map";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function ExamMapInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const { yearId } = useYear();
  const [picked, setPicked] = useState("");

  // A teacher sees only classes she teaches in — `?mine=true` has existed on
  // this endpoint all along and is the same rule the board applies.
  const { data: classes = [], isLoading } = useQuery({
    queryKey: ["classes", yearId, canEdit ? "all" : "mine"],
    queryFn: () => schoolApi.classes(yearId!, canEdit ? undefined : true),
    enabled: !!yearId,
  });
  const classId = classes.some((c) => c.id === picked) ? picked : (classes[0]?.id ?? "");

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Exam mapping"
          subtitle="Which chapters each exam examines — and whether they fit before it" />
        <div className="flex flex-wrap items-center gap-2">
          <YearSwitcher />
          {classes.length ? (
            <select value={classId} onChange={(e) => setPicked(e.target.value)}
              aria-label="Class"
              className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm">
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}{c.section ? `-${c.section}` : ""}
                </option>
              ))}
            </select>
          ) : null}
        </div>
      </div>

      {isLoading ? (
        <PageLoading label="Loading classes…" />
      ) : !classId ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No classes to map yet. Add them in Setup.
        </p>
      ) : (
        <ExamSyllabusMap classId={classId} canEdit={canEdit} />
      )}
    </div>
  );
}

export default function ExamMapPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ExamMapInner />
    </AuthGuard>
  );
}
