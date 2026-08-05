"use client";

// The class picker every My Class tab shares (founder, 2026-08-05).
//
// A class teacher usually owns exactly one homeroom, so the picker collapses to
// a heading and gets out of the way. An admin browsing the area — and the rare
// teacher with two sections — gets pills. The choice is held in the URL
// (`?class=`) rather than in component state so that moving between tabs keeps
// the class you were looking at; a picker that reset on every tab change would
// make the area unusable for exactly the people who need the picker.

import { useQuery } from "@tanstack/react-query";
import { Users } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";

import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import type { MyClassSummary } from "@/lib/school-types";
import { cn } from "@/lib/utils";

export function MyClassShell({
  title, subtitle, children,
}: {
  title: (klass: MyClassSummary) => string;
  subtitle?: (klass: MyClassSummary) => string;
  children: (klass: MyClassSummary) => React.ReactNode;
}) {
  const router = useRouter();
  const params = useSearchParams();
  const picked = params.get("class");
  const { data, isLoading } = useQuery({
    queryKey: ["my-classes"],
    queryFn: schoolApi.myClasses,
  });

  if (isLoading) return <PageLoading label="Loading your class…" />;

  const classes = data?.classes ?? [];
  if (classes.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="No class assigned to you"
        body="A class teacher owns one class and section. Ask your admin to set yours in Staff → People — pick your name, then Class teacher."
      />
    );
  }
  const active = classes.find((c) => c.class_id === picked) ?? classes[0];

  return (
    <div>
      <PageHeader title={title(active)} subtitle={subtitle?.(active)} />
      {classes.length > 1 ? (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {classes.map((c) => (
            <button key={c.class_id} type="button"
              onClick={() => {
                const next = new URLSearchParams(params.toString());
                next.set("class", c.class_id);
                router.replace(`?${next.toString()}`, { scroll: false });
              }}
              className={cn(
                "rounded-full border px-3 py-1 text-sm",
                c.class_id === active.class_id
                  ? "border-primary bg-primary/10 font-medium" : "border-border",
              )}>
              {c.class_label}
              <span className="ml-1.5 font-mono text-[11px] text-muted-foreground">
                {c.roster}
              </span>
            </button>
          ))}
        </div>
      ) : null}
      {children(active)}
    </div>
  );
}
