"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

/**
 * The subjects taught in one class, and who teaches each.
 *
 * Shared by Setup → Academics and the setup wizard's staff step: a teacher account
 * with no class-subject is not yet teaching anything, so the two screens that
 * create teachers both need this, and it must not drift between them.
 *
 * Reassigning a teacher PATCHes the row. Deleting is the destructive path —
 * `class_subjects` cascades to syllabus_units, plans, plan_entries and timetable
 * slots — so it asks first, and the teacher dropdown offers "Unassigned" as the way
 * to take someone off a subject without taking the subject apart.
 */
export function ClassSubjectsPanel({ classId, canEdit }: { classId: string; canEdit: boolean }) {
  const qc = useQueryClient();
  const [subjectId, setSubjectId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [periods, setPeriods] = useState("5");

  const { data: rows = [] } = useQuery({
    queryKey: ["class-subjects", classId],
    queryFn: () => schoolApi.classSubjects(classId),
    enabled: !!classId,
  });
  const { data: subjects = [] } = useQuery({ queryKey: ["subjects"], queryFn: schoolApi.subjects });
  const { data: membersData } = useQuery({ queryKey: ["members"], queryFn: appApi.members });
  // Anyone with a membership can be put in front of a class — admins teach too.
  const staff = (membersData?.members ?? []).filter((m) => m.member_id);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["class-subjects", classId] });
    qc.invalidateQueries({ queryKey: ["forecast"] });
  };

  const add = useMutation({
    mutationFn: () =>
      schoolApi.addClassSubject({
        class_id: classId,
        subject_id: subjectId,
        teacher_member_id: teacherId || null,
        periods_per_week: Number(periods),
      }),
    onSuccess: () => {
      invalidate();
      setSubjectId("");
      setTeacherId("");
      toast.success("Subject added");
    },
    onError: (e) => showApiError(e, "Could not add"),
  });

  const reassign = useMutation({
    mutationFn: ({ id, memberId }: { id: string; memberId: string | null }) =>
      schoolApi.updateClassSubject(id, { teacher_member_id: memberId }),
    onSuccess: () => {
      invalidate();
      toast.success("Teacher updated");
    },
    onError: (e) => showApiError(e, "Could not reassign"),
  });

  const setPeriodsFor = useMutation({
    mutationFn: ({ id, n }: { id: string; n: number }) =>
      schoolApi.updateClassSubject(id, { periods_per_week: n }),
    onSuccess: invalidate,
    onError: (e) => showApiError(e, "Could not update periods"),
  });

  const del = useMutation({
    mutationFn: (id: string) => schoolApi.deleteClassSubject(id),
    onSuccess: () => {
      invalidate();
      toast.success("Subject removed");
    },
    onError: (e) => showApiError(e, "Could not remove"),
  });

  function confirmDelete(id: string, subject: string | null) {
    const ok = window.confirm(
      `Remove ${subject ?? "this subject"} from this class?\n\n` +
        `Its syllabus, plan and timetable slots go with it. To just take a teacher off, ` +
        `set the teacher to "Unassigned" instead.`,
    );
    if (ok) del.mutate(id);
  }

  const available = subjects.filter((s) => !rows.some((r) => r.subject_id === s.id));

  return (
    <div className="mt-2 rounded-md bg-muted/30 p-2">
      {rows.length === 0 ? (
        <p className="px-1 py-1 text-xs text-muted-foreground">
          No subjects yet — add one below so a teacher has something to teach.
        </p>
      ) : null}

      {rows.map((cs) => (
        <div key={cs.id} className="flex flex-wrap items-center gap-2 px-1 py-1 text-sm">
          <span className="min-w-24 flex-1 font-medium">{cs.subject_name}</span>

          {canEdit ? (
            <>
              <select
                aria-label={`Teacher for ${cs.subject_name}`}
                className={`rounded border bg-card px-1.5 py-1 text-xs ${
                  cs.teacher_member_id ? "border-border" : "border-warning text-warning"
                }`}
                value={cs.teacher_member_id ?? ""}
                onChange={(e) => reassign.mutate({ id: cs.id, memberId: e.target.value || null })}
              >
                <option value="">Unassigned</option>
                {staff.map((t) => (
                  <option key={t.member_id} value={t.member_id!}>
                    {t.name}
                  </option>
                ))}
              </select>
              <Input
                aria-label={`Periods per week for ${cs.subject_name}`}
                className="h-7 w-14 text-xs"
                type="number"
                min={0}
                max={60}
                defaultValue={cs.periods_per_week}
                onBlur={(e) => {
                  const n = Number(e.target.value);
                  if (n !== cs.periods_per_week && n >= 0) setPeriodsFor.mutate({ id: cs.id, n });
                }}
              />
              <span className="text-xs text-muted-foreground">p/wk</span>
              <button
                type="button"
                aria-label={`Remove ${cs.subject_name}`}
                onClick={() => confirmDelete(cs.id, cs.subject_name)}
                className="text-muted-foreground hover:text-danger"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </>
          ) : (
            <span className="text-xs text-muted-foreground">
              {cs.periods_per_week}p/wk
              {cs.teacher_member_id
                ? ` · ${staff.find((t) => t.member_id === cs.teacher_member_id)?.name ?? "teacher"}`
                : " · unassigned"}
            </span>
          )}
        </div>
      ))}

      {canEdit ? (
        <form
          className="mt-1 flex flex-wrap items-center gap-1.5"
          onSubmit={(e) => {
            e.preventDefault();
            if (subjectId) add.mutate();
          }}
        >
          <select
            aria-label="Subject to add"
            className="rounded border border-border bg-card px-1.5 py-1 text-sm"
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
          >
            <option value="">Subject…</option>
            {available.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <select
            aria-label="Teacher for the new subject"
            className="rounded border border-border bg-card px-1.5 py-1 text-sm"
            value={teacherId}
            onChange={(e) => setTeacherId(e.target.value)}
          >
            <option value="">Teacher…</option>
            {staff.map((t) => (
              <option key={t.member_id} value={t.member_id!}>
                {t.name}
              </option>
            ))}
          </select>
          <Input
            aria-label="Periods per week"
            className="h-8 w-14"
            type="number"
            min={0}
            max={60}
            value={periods}
            onChange={(e) => setPeriods(e.target.value)}
          />
          <Button size="sm" type="submit" disabled={add.isPending || !subjectId}>
            Add
          </Button>
          {available.length === 0 && subjects.length > 0 ? (
            <span className="text-xs text-muted-foreground">Every subject is already on this class.</span>
          ) : null}
        </form>
      ) : null}
    </div>
  );
}
