"use client";

import { useQuery } from "@tanstack/react-query";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassWeekGrid } from "@/components/school/class-week-grid";
import { ClassSelect, forecastLabel, PlanView, RAG, SubjectSelect, useClassSubjectPick, weekLabel } from "@/components/school/plan-shared";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function WeekPlanInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const { yearId } = useYear();
  const { classes, classId, setClassId, subjects, csId, setCsId } = useClassSubjectPick(yearId);
  const { data: forecast = [] } = useQuery({ queryKey: ["forecast", classId], queryFn: () => schoolApi.forecast(classId), enabled: !!classId });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <PageHeader title="Week plan" subtitle="Week-by-week plan and pace forecast" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <ClassSelect classes={classes} classId={classId} onChange={setClassId} />
        </div>
      </div>

      {classId ? (
        <div className="mb-6">
          <ClassWeekGrid classId={classId} />
        </div>
      ) : null}

      <h2 className="mb-2 text-sm font-semibold">Pace forecast</h2>
      <div className="mb-6 space-y-2">
        {forecast.length === 0 ? <p className="text-sm text-muted-foreground">No subjects on this class yet.</p> : null}
        {forecast.map((f) => (
          <div key={f.class_subject_id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{f.subject_name}</p>
              <p className="text-xs text-muted-foreground">
                {f.status === "unplanned"
                  ? "no finish date — size the remaining chapters to forecast"
                  : f.status === "unallocated"
                  ? "no periods/week set for this subject — fix the class allocation"
                  : <>
                      {f.baseline_finish ? `baseline ${weekLabel(f.baseline_finish)}` : "no plan"}
                      {f.projected_finish && f.weeks_behind > 0 ? ` · projected ${weekLabel(f.projected_finish)} (${f.weeks_behind}w behind)` : ""}
                    </>}
              </p>
            </div>
            <Badge tone={RAG[f.status]}>{forecastLabel(f.status, f.unestimated_topics)}</Badge>
          </div>
        ))}
      </div>

      {csId ? (
        <>
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-semibold">Subject</h2>
            <SubjectSelect subjects={subjects} csId={csId} onChange={setCsId} />
          </div>
          <PlanView csId={csId} canEdit={canEdit} canApprove={canEdit} />
        </>
      ) : null}
    </div>
  );
}

export default function WeekPlanPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <WeekPlanInner />
    </AuthGuard>
  );
}
