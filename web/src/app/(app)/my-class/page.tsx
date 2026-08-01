"use client";

// My Class — the class teacher's area (V1-3, D-03). Her children: the month
// attendance grid, who needs a call, and the way into each child's page.

import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassRegister } from "@/components/school/class-register";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import { cn } from "@/lib/utils";

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
