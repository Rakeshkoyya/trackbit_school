"use client";

/**
 * Plan → Syllabus → Exam mapping (SY-2).
 *
 * Same two rows as the Syllabus tab — class, then subject — because a portion
 * is per class-subject and the person setting one has just come from editing
 * that subject's chapters. Making her re-orient to a different navigation
 * between two halves of the same job was the old screen's real cost; the wall
 * of chips was only the visible half.
 *
 * The toggle picks which way round the same fact is drawn:
 *
 *   **By chapter** — a row per chapter, and beside it the exams that examine
 *     it. This is the view for *"chapter 4 slipped; which paper loses it?"*
 *   **By exam** — a collapsible table per exam, showing its portion. This is
 *     the view for *"what is in the half-yearly?"*, and it is the one that gets
 *     read out to a class.
 *
 * Both write the same `ExamPortion`, so there is no order of operations to get
 * wrong and no second place for a portion to be recorded.
 */

import { List, Table2 } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  ClassSubjectPicker,
  useClassSubject,
} from "@/components/school/class-subject-picker";
import {
  ExamSyllabusMap,
  type ExamMapView,
} from "@/components/school/exam-syllabus-map";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { cn } from "@/lib/utils";

function ViewToggle({ view, onChange }: {
  view: ExamMapView; onChange: (v: ExamMapView) => void;
}) {
  const tabs: { id: ExamMapView; label: string; icon: typeof List }[] = [
    { id: "chapter", label: "By chapter", icon: List },
    { id: "exam", label: "By exam", icon: Table2 },
  ];
  return (
    <div className="inline-flex rounded-full border border-border bg-card p-0.5">
      {tabs.map((t) => (
        <button key={t.id} type="button" onClick={() => onChange(t.id)}
          aria-pressed={view === t.id}
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors",
            view === t.id
              ? "bg-primary text-primary-foreground"
              : "text-muted-foreground hover:text-foreground")}>
          <t.icon className="h-3.5 w-3.5" /> {t.label}
        </button>
      ))}
    </div>
  );
}

function ExamMapInner() {
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";
  const { yearId } = useYear();
  const [view, setView] = useState<ExamMapView>("exam");

  // A teacher sees only classes she teaches in — the same `?mine=true` the
  // syllabus grid uses, and the same rule the board applies server-side.
  const pick = useClassSubject(yearId, { mine: !isAdmin });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Exam mapping"
          subtitle="Which chapters each exam examines — and whether they fit before it" />
        <div className="flex flex-wrap items-center gap-2">
          <ViewToggle view={view} onChange={setView} />
          <YearSwitcher />
        </div>
      </div>

      {/* Adding a class or a subject from here is the same act as adding one on
          the Syllabus tab, so the same control is offered rather than sending
          her back a tab to do it. */}
      <ClassSubjectPicker pick={pick} yearId={yearId} canAdd={!!isAdmin} />

      {pick.loading && !pick.classId ? (
        <PageLoading label="Loading classes…" />
      ) : !pick.classId ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          {isAdmin ? "No classes to map yet — add one above."
            : "You are not assigned to any class yet."}
        </p>
      ) : (
        <ExamSyllabusMap classId={pick.classId} csId={pick.csId} view={view}
          canEdit={!!isAdmin} />
      )}
    </div>
  );
}

export default function ExamMapPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ExamMapInner />
    </AuthGuard>
  );
}
