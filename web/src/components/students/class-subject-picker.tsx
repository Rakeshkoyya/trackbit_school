"use client";

/**
 * Pick a class, then a subject (founder, 2026-08-05).
 *
 * Two rows of buttons rather than two dropdowns: a school has ten-ish classes
 * and six-ish subjects, and on that scale a button row shows you what exists
 * while a `<select>` hides it behind a press. It is the same device
 * `/bands/manage` uses for the same reason, so the two screens read alike.
 *
 * `mine` is passed to `classes()` for a teacher, so the row is built from what
 * she may act on and **there is no such thing as a tab here that 403s** —
 * `/academics/classes?mine=true` returns the classes she teaches, and the
 * subject row under it is that class's own class-subjects.
 *
 * The first class and its first subject are selected on arrival. A picker that
 * starts empty makes a page look broken for the several seconds before anyone
 * realises they have to choose something.
 */

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";
import { cn } from "@/lib/utils";

const chip = (active: boolean) =>
  cn("whitespace-nowrap rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
    active
      ? "border-primary bg-primary text-primary-foreground"
      : "border-border text-muted-foreground hover:bg-muted hover:text-foreground");

export function ClassSubjectPicker({
  classId, subjectCsId, onChange,
}: {
  classId: string | null;
  subjectCsId: string | null;
  onChange: (next: { classId: string | null; subjectCsId: string | null }) => void;
}) {
  const { me } = useAuth();
  const { yearId } = useYear();
  const mine = me?.org_role !== "admin";

  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId, mine],
    queryFn: () => schoolApi.classes(yearId ?? undefined, mine),
    enabled: !!yearId,
  });
  const { data: subjects = [] } = useQuery({
    queryKey: ["class-subjects", classId],
    queryFn: () => schoolApi.classSubjects(classId!),
    enabled: !!classId,
  });
  // A teacher's OWN class-subjects (V1-6 `/planner/my-subjects`, scoped on
  // `teacher_member_id`). Used only to pick the landing subject: a teacher who
  // takes Maths in this class was landing on English, which she may read but
  // not write, so the page opened with no way to add to it and no explanation.
  // Reading every subject is still correct and unchanged — this reorders the
  // default, it does not narrow the row.
  const { data: mySubjects } = useQuery({
    queryKey: ["my-subjects", yearId],
    queryFn: () => schoolApi.mySubjects(yearId ?? undefined),
    enabled: !!yearId && mine,
  });
  const ownCsIds = new Set((mySubjects?.rows ?? []).map((r) => r.class_subject_id));

  // Land on something real. Re-runs when the class changes, which is what
  // clears a subject belonging to the class you just left.
  useEffect(() => {
    if (!classes.length) return;
    if (!classId || !classes.some((c) => c.id === classId)) {
      onChange({ classId: classes[0].id, subjectCsId: null });
    }
  }, [classes, classId, onChange]);

  useEffect(() => {
    if (!subjects.length) return;
    if (!subjectCsId || !subjects.some((s) => s.id === subjectCsId)) {
      const own = subjects.find((s) => ownCsIds.has(s.id));
      onChange({ classId: classId ?? null, subjectCsId: (own ?? subjects[0]).id });
    }
    // `ownCsIds` is rebuilt every render; the query key behind it is what
    // actually changes, so it is deliberately not a dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subjects, subjectCsId, classId, onChange, mySubjects]);

  if (!classes.length) {
    return (
      <p className="mb-4 text-sm text-muted-foreground">
        No classes are assigned to you yet.
      </p>
    );
  }

  return (
    <div className="mb-4 space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {classes.map((c) => (
          <button key={c.id} type="button" className={chip(c.id === classId)}
            onClick={() => onChange({ classId: c.id, subjectCsId: null })}>
            {c.name}{c.section ? `-${c.section}` : ""}
          </button>
        ))}
      </div>
      {classId ? (
        <div className="flex flex-wrap gap-1.5">
          {subjects.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              This class has no subjects set up yet.
            </p>
          ) : subjects.map((s) => (
            <button key={s.id} type="button" className={chip(s.id === subjectCsId)}
              onClick={() => onChange({ classId, subjectCsId: s.id })}>
              {s.subject_name ?? "—"}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
