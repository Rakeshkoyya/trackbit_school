"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, Loader2, Moon, NotebookPen } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { parentApi, type DayStatus } from "@/lib/parent-api";

import { useParentPortal } from "./parent-context";

const STATUS_COPY: Record<DayStatus, { label: string; tone: "success" | "warning" | "danger" | "neutral"; hint?: string }> = {
  present: { label: "Present today", tone: "success" },
  partial: { label: "Missed some periods", tone: "warning" },
  absent: { label: "Absent today", tone: "danger" },
  not_marked: {
    label: "Attendance not marked yet",
    tone: "neutral",
    hint: "Teachers mark attendance during the day — check back later.",
  },
  no_school: { label: "No school periods today", tone: "neutral" },
};

function Section({ icon: Icon, title, children }: {
  icon: React.ElementType; title: string; children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4 text-muted-foreground" />
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function ParentTodayPage() {
  const { child } = useParentPortal();
  const { data, isLoading } = useQuery({
    queryKey: ["parent", "today", child?.student_id],
    queryFn: () => parentApi.today(child!.student_id),
    enabled: !!child,
  });

  if (!child || isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!data) return null;
  const status = STATUS_COPY[data.status];

  return (
    <div className="space-y-4">
      {/* Attendance — one calm daily line, never a per-period feed. */}
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs text-muted-foreground">{child.full_name}</p>
            <p className="mt-0.5 text-base font-semibold">{status.label}</p>
            {data.status === "partial" ? (
              <p className="mt-0.5 text-xs text-muted-foreground">
                Missed {data.absent_periods} of {data.marked_periods} marked periods.
              </p>
            ) : null}
            {data.late_periods > 0 ? (
              <p className="mt-0.5 text-xs text-muted-foreground">
                Arrived late to {data.late_periods} period{data.late_periods > 1 ? "s" : ""}.
              </p>
            ) : null}
            {status.hint ? (
              <p className="mt-0.5 text-xs text-muted-foreground">{status.hint}</p>
            ) : null}
          </div>
          <Badge tone={status.tone}>{data.date}</Badge>
        </div>
      </section>

      <Section icon={BookOpen} title="Taught today">
        {data.taught.length ? (
          <ul className="space-y-2">
            {data.taught.map((t, i) => (
              <li key={i} className="flex items-baseline gap-2 text-sm">
                <span className="w-24 shrink-0 text-xs font-medium text-muted-foreground">
                  {t.subject_name}
                </span>
                <span>{t.topic}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Nothing logged yet today.</p>
        )}
      </Section>

      <Section icon={NotebookPen} title="Homework tonight">
        {data.homework.length ? (
          <ul className="space-y-2">
            {data.homework.map((hw, i) => (
              <li key={i} className="flex items-baseline gap-2 text-sm">
                <span className="w-24 shrink-0 text-xs font-medium text-muted-foreground">
                  {hw.subject_name}
                </span>
                <span>{hw.text}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">No homework recorded today.</p>
        )}
      </Section>

      {data.sessions.length ? (
        <Section icon={Moon} title="Evening & activities">
          <ul className="space-y-2.5">
            {data.sessions.map((s, i) => (
              <li key={i} className="text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{s.session_name}</span>
                  <Badge tone={s.status === "absent" ? "danger" : s.status === "late" ? "warning" : "success"}>
                    {s.status}
                  </Badge>
                </div>
                {s.log_note ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">{s.log_note}</p>
                ) : null}
                {s.homework_done != null ? (
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Homework {s.homework_done ? "completed" : "not completed"}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </div>
  );
}
