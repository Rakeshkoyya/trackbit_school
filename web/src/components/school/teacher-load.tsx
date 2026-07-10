"use client";

/**
 * Teaching load, counted off the live timetable grid (V2-P10).
 *
 * NOT from `class_subjects.periods_per_week` — that's what the admin *intended*.
 * This is what the grid actually commits each teacher to. A teacher at 40 periods
 * across six classes is the kind of thing nobody notices until she burns out or a
 * clash surfaces, and until now it wasn't visible anywhere in the product.
 */

import { useQuery } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { schoolApi } from "@/lib/school-api";

/** Rough Indian-school norms: ~30/wk is full, ~36+ is heavy. */
function tone(periods: number): "neutral" | "success" | "warning" | "danger" {
  if (periods === 0) return "neutral";
  if (periods >= 36) return "danger";
  if (periods >= 30) return "warning";
  return "success";
}

export function TeacherLoad() {
  const { data } = useQuery({ queryKey: ["teacher-load"], queryFn: schoolApi.teacherLoad });
  if (!data?.length) return null;

  const max = Math.max(...data.map((t) => t.periods_per_week), 1);

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex items-baseline justify-between border-b border-border px-4 py-2.5">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Teaching load
        </h2>
        <span className="text-[11px] text-muted-foreground">periods per week, from the timetable</span>
      </div>
      <ul className="divide-y divide-border">
        {data.map((t) => (
          <li key={t.member_id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
            <span className="w-40 shrink-0 truncate font-medium">{t.name}</span>
            <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${(t.periods_per_week / max) * 100}%` }}
              />
            </div>
            <span className="w-28 shrink-0 text-right text-xs text-muted-foreground">
              {t.classes} class{t.classes === 1 ? "" : "es"} · {t.subjects} subj
            </span>
            <Badge tone={tone(t.periods_per_week)} className="w-16 justify-center tabular-nums">
              {t.periods_per_week}/wk
            </Badge>
          </li>
        ))}
      </ul>
      {data.some((t) => t.periods_per_week === 0) ? (
        <p className="border-t border-border px-4 py-2 text-[11px] text-muted-foreground">
          A teacher on 0 periods is either new, or assigned to subjects that aren&apos;t on the
          timetable yet.
        </p>
      ) : null}
    </div>
  );
}
