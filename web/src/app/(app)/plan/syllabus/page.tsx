"use client";

/**
 * Plan → Syllabus (SY-2) — navigate by class, then subject; edit the sheet.
 *
 * SY-1 made this one table of the whole school, groupable and filterable. That
 * answers *"which chapters are late?"* well and answers *"let me work on 7-B
 * Science"* badly — and the second is what a school opens this page to do every
 * day. It kept its spreadsheet.
 *
 * So the page leads with the two rows the founder asked for — classes, then
 * that class's subjects, each with an Add at the right — and the picked subject
 * opens as a **grid whose every cell is live**. The whole-school board is not
 * gone; it is the second view, because "which chapters are late across the
 * school" is still a real question and it is an admin's, once a week.
 *
 * **One page for both roles.** A teacher gets the identical component: the
 * SERVER scopes her — `?mine=true` on the class list, and the board is a block,
 * not a filter, so another teacher's subject is never loaded and then dropped.
 * Her Add buttons are absent because she is not an admin; her grid is fully
 * editable because the subject is hers, which is a question the service asks
 * (`assert_can_edit_class_subject`), not one this screen guesses at.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutGrid, Table2 } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BoardSkeleton } from "@/components/insights/shared";
import {
  ClassSubjectPicker,
  useClassSubject,
} from "@/components/school/class-subject-picker";
import { SyllabusGrid } from "@/components/school/syllabus-grid";
import { SyllabusTable } from "@/components/school/syllabus-table";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { appApi } from "@/lib/app-api";
import { schoolApi } from "@/lib/school-api";
import { cn } from "@/lib/utils";

type View = "subject" | "school";

function ViewToggle({ view, onChange }: {
  view: View; onChange: (v: View) => void;
}) {
  const tabs: { id: View; label: string; icon: typeof Table2 }[] = [
    { id: "subject", label: "By subject", icon: Table2 },
    { id: "school", label: "Whole school", icon: LayoutGrid },
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

function SyllabusInner() {
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";
  const { yearId, years } = useYear();
  const qc = useQueryClient();
  const [view, setView] = useState<View>("subject");
  const [term, setTerm] = useState("");

  const pick = useClassSubject(yearId, { mine: !isAdmin });
  const year = years.find((y) => y.id === yearId);

  // Names for the mentor caption on each subject chip. Admin-only: `/org/members`
  // is not a teacher's to read, and her own chips do not need it — she knows
  // whose subjects they are.
  const { data: members } = useQuery({
    queryKey: ["members"], queryFn: appApi.members, enabled: isAdmin,
  });
  const teacherFor = new Map(
    (members?.members ?? [])
      .filter((mm) => mm.member_id)
      .map((mm) => [mm.member_id!, mm.name] as const));

  // Two reads, deliberately separate. The grid asks for ONE class-subject so a
  // school with forty of them does not pace all forty to draw fourteen rows;
  // the whole-school view asks for the board it has always asked for.
  const { data: one, isLoading: oneLoading } = useQuery({
    queryKey: ["syllabus-board", yearId, "cs", pick.csId, term],
    queryFn: () => schoolApi.syllabusBoard({
      yearId: yearId ?? undefined, classSubjectId: pick.csId,
      termId: term || undefined,
    }),
    enabled: view === "subject" && !!pick.csId,
  });

  const { data: all, isLoading: allLoading } = useQuery({
    queryKey: ["syllabus-board", yearId, "all", term],
    queryFn: () => schoolApi.syllabusBoard({
      yearId: yearId ?? undefined, termId: term || undefined,
    }),
    enabled: view === "school",
  });

  const refresh = () => qc.invalidateQueries({ queryKey: ["syllabus-board"] });
  const board = view === "subject" ? one : all;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Syllabus"
          subtitle="Every chapter, where it stands and when it was taught" />
        <div className="flex flex-wrap items-center gap-2">
          <ViewToggle view={view} onChange={setView} />
          <YearSwitcher />
          {board && board.terms.length > 1 ? (
            <select value={term} onChange={(e) => setTerm(e.target.value)}
              aria-label="Term"
              className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm">
              <option value="">All terms</option>
              {board.terms.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          ) : null}
        </div>
      </div>

      {view === "subject" ? (
        <>
          <ClassSubjectPicker pick={pick} yearId={yearId} canAdd={!!isAdmin}
            teacherFor={teacherFor} />

          {!pick.csId ? (
            <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
              {pick.loading ? "Loading classes…"
                : isAdmin
                  ? "Pick a class and a subject above — or add one."
                  : "You have no subjects on this class."}
            </p>
          ) : oneLoading || !one ? (
            <BoardSkeleton />
          ) : (
            <>
              {/* Lead with a sentence, not a number (ux rule 3). */}
              <p className="mb-3 text-base font-medium">{one.headline}</p>
              <SyllabusGrid csId={pick.csId} board={one} canEdit onChanged={refresh}
                yearStart={year?.start_date} yearEnd={year?.end_date} />
            </>
          )}
        </>
      ) : allLoading || !all ? (
        <BoardSkeleton />
      ) : (
        <>
          <p className="mb-4 text-base font-medium">{all.headline}</p>
          {/* The SY-1 board, unchanged. Difficulty, remarks and scope are
              writable by whoever may edit the chapter — the server narrows that
              to her own subjects, so a teacher annotating her own chapter here
              is not an admin act. */}
          <SyllabusTable board={all} canEdit onChanged={refresh} />
        </>
      )}
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
