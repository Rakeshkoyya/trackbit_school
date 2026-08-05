"use client";

/**
 * Plan → Syllabus (SY-1) — the whole school's chapters, as one table.
 *
 * Replaces the one-class, one-subject editor. That editor is not gone: it is
 * what "Edit chapters" opens, because adding and deleting chapters is a setup
 * act while the table is a reading surface. Mixing them put a delete button on
 * the row an admin scans every morning.
 *
 * The same page serves a teacher — the SERVER decides she sees her own subjects
 * (a block, not a filter), so there is nothing here to switch on.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Settings2 } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BoardSkeleton } from "@/components/insights/shared";
import {
  ClassSelect,
  SubjectSelect,
  SyllabusEditor,
  useClassSubjectPick,
} from "@/components/school/plan-shared";
import { SyllabusTable } from "@/components/school/syllabus-table";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

/** The chapter editor, kept whole but moved off the reading surface. */
function EditChapters({ open, onOpenChange, yearId, canEdit, onChanged }: {
  open: boolean; onOpenChange: (v: boolean) => void;
  yearId: string | null; canEdit: boolean; onChanged: () => void;
}) {
  const { classes, classId, setClassId, subjects, csId, setCsId } =
    useClassSubjectPick(yearId);
  // All the year's terms, not just those that already have chapters — a new
  // chapter has to be assignable to an empty term.
  const { data: terms = [] } = useQuery({
    queryKey: ["terms", yearId], queryFn: () => schoolApi.terms(yearId!), enabled: !!yearId,
  });
  return (
    <Modal open={open} onOpenChange={(v) => { if (!v) onChanged(); onOpenChange(v); }}
      title="Edit chapters"
      description="Add, size or remove chapters for one class-subject.">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <ClassSelect classes={classes} classId={classId} onChange={setClassId} />
        <SubjectSelect subjects={subjects} csId={csId} onChange={setCsId} />
      </div>
      {csId ? (
        <SyllabusEditor csId={csId} canEdit={canEdit} terms={terms} />
      ) : (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          No subjects on this class yet — add classes and subjects in Setup.
        </p>
      )}
    </Modal>
  );
}

function SyllabusInner() {
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";
  const { yearId } = useYear();
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [term, setTerm] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["syllabus-board", yearId, term],
    queryFn: () => schoolApi.syllabusBoard({
      yearId: yearId ?? undefined, termId: term || undefined,
    }),
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["syllabus-board"] });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Syllabus"
          subtitle="Every chapter, where it stands and when it was taught" />
        <div className="flex flex-wrap items-center gap-2">
          <YearSwitcher />
          {data && data.terms.length > 1 ? (
            <select value={term} onChange={(e) => setTerm(e.target.value)}
              aria-label="Term"
              className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm">
              <option value="">All terms</option>
              {data.terms.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          ) : null}
          {isAdmin ? (
            <button type="button" onClick={() => setEditing(true)}
              className="inline-flex h-8 items-center gap-1.5 rounded-full border border-border bg-card px-3 text-xs font-medium transition-colors hover:bg-muted">
              <Settings2 className="h-3.5 w-3.5" /> Edit chapters
            </button>
          ) : null}
        </div>
      </div>

      {isLoading || !data ? <BoardSkeleton /> : (
        <>
          {/* Lead with a sentence, not a number (rule 3). */}
          <p className="mb-4 text-base font-medium">{data.headline}</p>
          {/* Difficulty and remarks are writable by whoever may edit the
              chapter — the server narrows that to her own subjects, so a
              teacher annotating her own chapter is not an admin act. */}
          <SyllabusTable board={data} canEdit onChanged={refresh} />
        </>
      )}

      <EditChapters open={editing} onOpenChange={setEditing} yearId={yearId}
        canEdit={isAdmin} onChanged={refresh} />
    </div>
  );
}

export default function SyllabusPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <SyllabusInner />
    </AuthGuard>
  );
}
