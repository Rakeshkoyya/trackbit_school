"use client";

import { useQuery } from "@tanstack/react-query";

import { schoolApi } from "@/lib/school-api";

/** §5.7 — the student's day, period-by-period (computed join, no new tables). */
export function TimelineBlock({ studentId }: { studentId: string }) {
  const { data } = useQuery({
    queryKey: ["timeline", studentId],
    queryFn: () => schoolApi.studentTimeline(studentId),
  });
  if (!data) return null;
  const tone = (a: string) => a === "absent" ? "text-danger" : a === "late" ? "text-warning" : a === "present" ? "text-[#234a37]" : "text-muted-foreground";
  return (
    <div>
      <p className="mb-1 font-medium">Today’s timeline</p>
      {data.periods.length === 0 && data.sessions.length === 0 ? (
        <p className="text-muted-foreground">No timetable or sessions today.</p>
      ) : (
        <ul className="space-y-1">
          {data.periods.map((p) => (
            <li key={p.period_no} className={`flex items-center gap-2 ${p.gap ? "opacity-60" : ""}`}>
              <span className="w-6 shrink-0 text-xs font-semibold text-muted-foreground">P{p.period_no}</span>
              <span className="min-w-0 flex-1 truncate">
                {p.subject_name ?? "—"}{p.topic ? ` · ${p.topic}` : ""}
                {p.homework.length ? <span className="text-xs text-muted-foreground"> · hw</span> : null}
                {p.checks_flagged.length ? <span className="text-xs text-warning"> · flagged</span> : null}
              </span>
              <span className={`text-xs ${tone(p.attendance)}`}>{p.attendance}{p.late_minutes ? ` ${p.late_minutes}m` : ""}</span>
            </li>
          ))}
          {data.sessions.map((s, i) => (
            <li key={`sess-${i}`} className="flex items-center gap-2">
              <span className="w-6 shrink-0 text-xs font-semibold text-muted-foreground">◷</span>
              <span className="min-w-0 flex-1 truncate">
                {s.session_name}
                {s.log_note ? <span className="text-xs text-muted-foreground"> · {s.log_note}</span> : null}
                {s.homework_done ? <span className="text-xs text-muted-foreground"> · hw ✓</span> : null}
              </span>
              <span className={`text-xs ${tone(s.status)}`}>{s.status}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
