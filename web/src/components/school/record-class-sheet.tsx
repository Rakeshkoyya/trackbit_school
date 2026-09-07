"use client";

/**
 * FB-1a — record a class the timetable did not schedule.
 *
 * The grid is the norm, not the whole truth. A teacher's day is legitimately
 * empty during an exam window, on a Saturday extra class, when she is covering
 * a room the grid still gives to somebody else, or when the class has no grid
 * at all. Before this she had nowhere to put the lesson she had just taught —
 * so it went unrecorded, and the school's syllabus board read 3% while the
 * teaching had actually happened.
 *
 * Three taps: class, subject, period. Everything after that is the ORDINARY
 * period card — same register, same lesson log, same homework, same history.
 * This is a way IN to that card, never a second way of recording a class; if
 * the (class, period) already has a record she lands on it rather than making
 * a duplicate, because the route is keyed on class + period + date.
 *
 * The picker is built from `/periods/recordable`, which is filtered by the same
 * rule the card's guard enforces. Offering a class the card would then refuse
 * is the "Loading roster… forever" bug wearing a different hat.
 */

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";
import { schoolApi } from "@/lib/school-api";
import type { RecordableClass } from "@/lib/school-types";
import { cn } from "@/lib/utils";

function Choice({
  selected, onClick, children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1.5 text-sm transition-colors",
        selected
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card hover:bg-muted",
      )}
    >
      {children}
    </button>
  );
}

function Step({ n, label, children }: { n: number; label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-2 text-xs font-medium text-muted-foreground">
        {n}. {label}
      </p>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
  );
}

export function RecordClassSheet({
  open, onOpenChange,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const router = useRouter();
  const [classPick, setClassPick] = useState("");
  const [csPick, setCsPick] = useState("");
  const [periodNo, setPeriodNo] = useState<number | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["recordable"],
    queryFn: () => schoolApi.recordable(),
    enabled: open,
  });

  // Everything below is DERIVED, not stored. Two things fall out of that for
  // free, and both were bugs when this was written with effects:
  //   · one class, or one subject, is not a decision — it is preselected
  //     without an effect writing state back during render (P1v2: three taps
  //     is the budget, and this is where two of them are free);
  //   · a subject only counts while it belongs to the class currently picked,
  //     so changing class cannot carry 5-A's English into 7-B and 400 the card
  //     on a class-subject that is somebody else's room.
  const classId =
    classPick || (data?.classes.length === 1 ? data.classes[0].class_id : "");
  const klass: RecordableClass | undefined =
    data?.classes.find((c) => c.class_id === classId);
  const csId =
    (klass?.subjects.some((s) => s.class_subject_id === csPick) ? csPick : "") ||
    (klass?.subjects.length === 1 ? klass.subjects[0].class_subject_id : "");

  const ready = classId !== "" && periodNo !== null;

  const go = () => {
    if (!ready) return;
    const q = csId ? `?cs=${csId}` : "";
    onOpenChange(false);
    router.push(`/my-day/period/${classId}/${periodNo}${q}`);
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Record a class">
      <div className="space-y-5">
        <p className="text-sm text-muted-foreground">
          For a class your timetable doesn&apos;t have today — an extra class, a
          swap, a room you covered. It records exactly like any other period.
        </p>

        {error ? (
          <p className="text-sm text-destructive">
            Couldn&apos;t load your classes. Close this and try again.
          </p>
        ) : isLoading || !data ? (
          <p className="text-sm text-muted-foreground">Loading your classes…</p>
        ) : data.classes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            You don&apos;t have any classes yet. Ask your admin to assign your
            subjects, or to make you a class teacher.
          </p>
        ) : (
          <>
            <Step n={1} label="Class">
              {data.classes.map((c) => (
                <Choice key={c.class_id} selected={c.class_id === classId}
                  onClick={() => setClassPick(c.class_id)}>
                  {c.class_label}
                </Choice>
              ))}
            </Step>

            {klass ? (
              <Step n={2} label="Subject">
                {klass.subjects.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    You take none of this class&apos;s subjects — you can still
                    take its register.
                  </p>
                ) : (
                  klass.subjects.map((s) => (
                    <Choice key={s.class_subject_id} selected={s.class_subject_id === csId}
                      onClick={() => setCsPick(s.class_subject_id)}>
                      {s.subject_name}
                    </Choice>
                  ))
                )}
              </Step>
            ) : null}

            {klass ? (
              <Step n={3} label="Period">
                {data.periods.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    This school hasn&apos;t set a bell schedule yet, so there are
                    no periods to choose. Ask your admin to add one.
                  </p>
                ) : (
                  data.periods.map((p) => (
                    <Choice key={p.period_no} selected={p.period_no === periodNo}
                      onClick={() => setPeriodNo(p.period_no)}>
                      {/* The clock when the school set one, the number when it
                          didn't — never an empty-looking row. */}
                      {data.has_timings && p.start
                        ? `${p.start}–${p.end ?? ""}`
                        : `Period ${p.period_no}`}
                    </Choice>
                  ))
                )}
              </Step>
            ) : null}

            <div className="flex justify-end gap-2 pt-1">
              <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
              <Button onClick={go} disabled={!ready}>Open the class</Button>
            </div>
          </>
        )}
      </div>
    </Sheet>
  );
}
