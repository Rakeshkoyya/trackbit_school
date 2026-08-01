"use client";

// Plan → My subjects (V1-6, `S-46`).
//
// Arrives asking: *"Where am I in my own subjects, and what's next?"*
// Leaves having: decided what to teach this week, or knowing she needs to
// catch up.
//
// The rest of the Plan area is admin-shaped — pick a year, pick a class, pick a
// subject, then look at one plan — so a teacher with six class-subjects picked
// her way to each one, every time. Five to eight rows is **a list, not a
// selector**, and that is the whole idea.
//
// `D-15`: her own subjects only, blocked rather than merely defaulted. The
// server scopes on `teacher_member_id`, so no other teacher's row is ever
// loaded; there is nothing for this screen to filter.

import { useQuery } from "@tanstack/react-query";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BoardSkeleton } from "@/components/insights/shared";
import { SubjectPaceList } from "@/components/school/subject-pace-list";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function MySubjectsInner() {
  const { yearId } = useYear();
  const { data, isLoading } = useQuery({
    queryKey: ["planner", "my-subjects", yearId],
    queryFn: () => schoolApi.mySubjects(yearId ?? undefined),
  });

  if (isLoading || !data) {
    return <><PageHeader title="My subjects" subtitle="Where you are, and what to teach next." /><BoardSkeleton /></>;
  }

  return (
    <div>
      <PageHeader title="My subjects" subtitle="Where you are, and what to teach next." />
      {/* Lead with a sentence, not a number (rule 3). */}
      <p className="mb-4 text-base font-medium">{data.headline}</p>
      <SubjectPaceList
        rows={data.rows}
        emptyText="You are not assigned to any class-subject yet. Ask the office to add you to one." />
    </div>
  );
}

export default function MySubjectsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MySubjectsInner />
    </AuthGuard>
  );
}
