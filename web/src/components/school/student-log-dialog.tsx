"use client";

/**
 * The student log, in a dialog (founder 2026-08-05).
 *
 * **This is `student_notes` — the SAME log the class teacher writes**, not a
 * support-specific remark store. A year later the person asking "what happened
 * with Kabir" wants everything anybody noticed in one scroll; a second table
 * would put half of it somewhere nobody opens. What the support surfaces add is
 * a pointer — `assessment_id` — to what occasioned the note.
 *
 * Two doors, one component:
 *   · **at any time**, from a row of My students — the thing she noticed
 *     walking past him, which no capture surface has a field for
 *   · **against an assessment**, from the evaluation sheet — why the mark is
 *     what it is
 *
 * Append-only (law 3). There is no edit and no delete: what a teacher thought in
 * September is part of the record when November disagrees, and a log that can be
 * quietly rewritten is not a log. So the history is shown above the box — she is
 * writing into a record, and it should look like one.
 *
 * Staff-only (P4-adjacent): `services/parent_portal.py` is an allowlist built
 * field by field, so this never reaches a guardian by construction.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { StudentNoteKind } from "@/lib/school-types";

/** The fixed list, deliberately short: the value of the log is reading a year of
 *  it in one scroll, and forty spellings of "spoke to parent" is a diary. */
const KINDS: { key: StudentNoteKind; label: string }[] = [
  { key: "support", label: "Support" },
  { key: "general", label: "General" },
  { key: "behaviour", label: "Behaviour" },
  { key: "wellbeing", label: "Wellbeing" },
  { key: "achievement", label: "Achievement" },
  { key: "concern", label: "Concern" },
  { key: "parent_contact", label: "Spoke to a parent" },
];

export function StudentLogDialog({
  open,
  onOpenChange,
  studentId,
  studentName,
  /** Set from an evaluation sheet — the note is filed against that check. */
  assessmentId,
  assessmentName,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  studentId: string;
  studentName: string;
  assessmentId?: string;
  assessmentName?: string;
}) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [kind, setKind] = useState<StudentNoteKind>(
    assessmentId ? "assessment" : "support",
  );

  const { data } = useQuery({
    queryKey: ["student-notes", studentId],
    queryFn: () => schoolApi.studentNotes(studentId),
    enabled: open,
  });

  const add = useMutation({
    mutationFn: () =>
      schoolApi.addStudentNote(studentId, {
        kind,
        note: note.trim(),
        assessment_id: assessmentId ?? null,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["student-notes", studentId] });
      qc.invalidateQueries({ queryKey: ["band-my-students"] });
      qc.invalidateQueries({ queryKey: ["band-assessment-sheet"] });
      toast.success("Added to his log");
      setNote("");
    },
    onError: (e) => showApiError(e, "Could not add it"),
  });

  const rows = data?.rows ?? [];
  const canWrite = data?.can_write ?? false;

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={`Log — ${studentName}`}
      description={
        assessmentName
          ? `Filed against “${assessmentName}”. It joins his running log.`
          : "His running log. Staff only — it never reaches a parent."
      }
      size="md"
    >
      <div className="space-y-4 px-5 py-4">
        {canWrite ? (
          <div className="space-y-2">
            <div>
              <Label htmlFor="log-kind">What kind</Label>
              <select
                id="log-kind"
                value={kind}
                onChange={(e) => setKind(e.target.value as StudentNoteKind)}
                className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              >
                {assessmentId ? (
                  <option value="assessment">About this assessment</option>
                ) : null}
                {KINDS.map((k) => (
                  <option key={k.key} value={k.key}>
                    {k.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="log-note">What you noticed</Label>
              <textarea
                id="log-note"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="read the whole passage without stopping — first time"
                className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              />
            </div>
            <Button
              className="w-full"
              disabled={!note.trim() || add.isPending}
              onClick={() => add.mutate()}
            >
              Add to the log
            </Button>
            {/* Said plainly, before she writes rather than after. */}
            <p className="text-xs text-muted-foreground">
              Nothing here can be edited or removed later — a correction is a new entry.
            </p>
          </div>
        ) : (
          <p className="rounded-lg border border-border p-3 text-sm text-muted-foreground">
            You can read this log but not add to it — that is his class teacher&rsquo;s,
            an admin&rsquo;s, or his support owner&rsquo;s.
          </p>
        )}

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Earlier entries
          </h3>
          {rows.length ? (
            <ul className="mt-2 space-y-2">
              {rows.map((r) => (
                <li key={r.id} className="rounded-lg border border-border p-3">
                  <p className="text-sm leading-relaxed">{r.note}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {r.kind.replace("_", " ")}
                    {r.author_name ? ` · ${r.author_name}` : ""}
                    {" · "}
                    {new Date(r.created_at).toLocaleDateString()}
                  </p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">
              Nothing written yet. That is a gap in the record, not a statement about
              him.
            </p>
          )}
        </div>
      </div>
    </Modal>
  );
}
