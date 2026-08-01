"use client";

// My Class — the class teacher's area (V1-3, D-03). Her children: the month
// attendance grid, who needs a call, and the way into each child's page.

import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Section } from "@/components/insights/shared";
import { ClassRegister } from "@/components/school/class-register";
import { SubjectPaceList } from "@/components/school/subject-pace-list";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import { cn } from "@/lib/utils";

/**
 * `S-28` / `D-15` — her class's syllabus: **all** subjects, not just hers, with
 * the subject teacher named beside each one because she cannot act on it
 * otherwise and she is staff (`Q-20`).
 *
 * Scoped to her own class and nothing wider — there is no school-wide form of
 * this view, by design. The same honesty guard as the admin board rides along:
 * numbers beside the name, framed as needing support, **never a rank**. And no
 * pace figure from this block ever reaches a parent (`D-11`).
 */
function ClassSyllabusBlock({ classId }: { classId: string }) {
  const { data } = useQuery({
    queryKey: ["planner", "class-syllabus", classId],
    queryFn: () => schoolApi.classSyllabus(classId),
  });
  if (!data) return null;
  return (
    <Section title="My class's syllabus"
      hint="Every subject this class takes, and how far each has got. Where something is behind, the reason is beside it.">
      <p className="mb-3 text-sm font-medium">{data.headline}</p>
      <SubjectPaceList rows={data.rows} showTeacher
        emptyText="This class has no subjects set up yet." />
    </Section>
  );
}

/**
 * `D-37` / `S-87` — tonight's homework load for her class.
 *
 * Six teachers each made a reasonable decision and **no screen in any school
 * product adds them up**; she is the one person responsible for that child's
 * evening. Needs no new capture — it is `homework_assignments` grouped by class
 * and date.
 *
 * **Informational, never a cap.** A limit turns into "whose turn is it to set
 * homework", which is a worse problem than the one it solves. And `D-37` scopes
 * it deliberately: the admin and the CLASS teacher see it, a subject teacher
 * never does — the number exists for the staff room, not to make one teacher
 * feel they should have set less.
 */
function HomeworkLoadBlock({ classId }: { classId: string }) {
  const { data } = useQuery({
    queryKey: ["homework-load", classId],
    queryFn: () => schoolApi.homeworkLoad({ classId }),
  });
  if (!data || !data.cells.length) return null;
  const recent = data.cells.slice(-10);
  const busiest = Math.max(...recent.map((c) => c.subjects), 1);
  return (
    <Section title="Their evenings"
      hint="How many subjects set homework each day. A picture of the load nobody else sees — not a limit.">
      {data.busiest_date ? (
        <p className="mb-3 text-sm">
          Heaviest recently: <span className="font-medium">{data.busiest_subjects} subjects</span>
          {" "}on {new Date(`${data.busiest_date}T00:00:00`).toLocaleDateString("en-IN",
            { weekday: "long", day: "numeric", month: "short" })}.
        </p>
      ) : null}
      <div className="flex items-end gap-1.5">
        {recent.map((c) => (
          <div key={c.date} className="flex min-w-0 flex-1 flex-col items-center gap-1">
            <div className="flex h-16 w-full items-end">
              <div className="w-full rounded-t bg-primary/70"
                style={{ height: `${(c.subjects / busiest) * 100}%` }}
                title={`${c.subjects} subjects · ${c.assignments} assignments`} />
            </div>
            <span className="text-[10px] tabular-nums text-muted-foreground">{c.date.slice(8)}</span>
          </div>
        ))}
      </div>
    </Section>
  );
}

function MyClassInner() {
  const { data, isLoading } = useQuery({
    queryKey: ["my-classes"],
    queryFn: schoolApi.myClasses,
  });
  const [picked, setPicked] = useState<string | null>(null);

  if (isLoading) return <PageLoading label="Loading your class…" />;

  const classes = data?.classes ?? [];
  if (classes.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="No class assigned to you"
        body="A class teacher owns one class and section. Ask your admin to assign yours in Setup → Academics."
      />
    );
  }
  const active = classes.find((c) => c.class_id === picked) ?? classes[0];

  return (
    <div>
      <PageHeader
        title={`My Class · ${active.class_label}`}
        subtitle={`${active.roster} students — their month at a glance, and who to call today`}
      />

      {classes.length > 1 ? (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {classes.map((c) => (
            <button key={c.class_id} onClick={() => setPicked(c.class_id)}
              className={cn(
                "rounded-full border px-3 py-1 text-sm",
                c.class_id === active.class_id
                  ? "border-primary bg-primary/10 font-medium" : "border-border",
              )}>
              {c.class_label}
            </button>
          ))}
        </div>
      ) : null}

      <ClassRegister classId={active.class_id} />

      {/* Order is deliberate (screens/teacher.md): the people who need something
          today, then the record, then the class's academic position. */}
      <ClassSyllabusBlock classId={active.class_id} />
      <HomeworkLoadBlock classId={active.class_id} />
    </div>
  );
}

export default function MyClassPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyClassInner />
    </AuthGuard>
  );
}
