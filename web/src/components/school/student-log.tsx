"use client";

// The class teacher's own log about a child (founder, 2026-08-05).
//
// Every other thing on this page is a byproduct of doing the work (P5):
// attendance is a tap, coverage is a lesson log, a band is a test. This is the
// one deliberate exception and it is the homeroom's own — the thing she noticed
// that no capture surface has a field for.
//
// Three rules the UI has to hold up:
//   · **append-only** (law 3). There is no edit and no delete, because what a
//     teacher thought in September is part of the record when November
//     disagrees. The composer says so rather than leaving the absence of an edit
//     button to be read as an oversight.
//   · **staff-only.** It never reaches a parent surface — `parent_portal.py` is
//     an allowlist built field by field, so this stays out by construction.
//   · **one author.** A subject teacher already has the deep log for what
//     happens in her lesson; `can_write` comes from the server and is false for
//     everyone but the class teacher and an admin.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Lock, NotebookPen } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { StudentNoteKind } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const KINDS: { key: StudentNoteKind; label: string }[] = [
  { key: "general", label: "General" },
  { key: "wellbeing", label: "Wellbeing" },
  { key: "behaviour", label: "Behaviour" },
  { key: "achievement", label: "Achievement" },
  { key: "parent_contact", label: "Spoke to family" },
  { key: "concern", label: "Concern" },
];

const KIND_LABEL: Record<string, string> = Object.fromEntries(
  KINDS.map((k) => [k.key, k.label]));

export function StudentLog({ studentId }: { studentId: string }) {
  const qc = useQueryClient();
  const [kind, setKind] = useState<StudentNoteKind>("general");
  const [note, setNote] = useState("");

  const { data } = useQuery({
    queryKey: ["student-notes", studentId],
    queryFn: () => schoolApi.studentNotes(studentId),
  });

  const add = useMutation({
    mutationFn: () => schoolApi.addStudentNote(studentId, { kind, note: note.trim() }),
    onSuccess: (res) => {
      qc.setQueryData(["student-notes", studentId], res);
      qc.invalidateQueries({ queryKey: ["my-class", "students"] });
      setNote("");
      setKind("general");
      toast.success("Added to the log");
    },
    onError: (e) => showApiError(e, "Could not add that"),
  });

  if (!data) return null;

  return (
    <section className="mt-5 overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
        <NotebookPen className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          Class teacher&rsquo;s log
        </span>
        <span className="ml-auto inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          <Lock className="h-3 w-3" /> staff only
        </span>
      </header>

      {data.can_write ? (
        <div className="border-b border-border px-4 py-3">
          <div className="mb-2 flex flex-wrap gap-1.5">
            {KINDS.map((k) => (
              <button key={k.key} type="button" onClick={() => setKind(k.key)}
                className={cn("rounded-full border px-2.5 py-1 text-xs",
                  kind === k.key
                    ? "border-primary bg-primary/10 font-medium" : "border-border")}>
                {k.label}
              </button>
            ))}
          </div>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            maxLength={4000}
            placeholder="What did you notice? — the thing no other screen has a field for."
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
          />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={!note.trim() || add.isPending}
              onClick={() => add.mutate()}>
              {add.isPending ? "Adding…" : "Add to the log"}
            </Button>
            {/* Said plainly, so the missing edit button reads as a decision
                rather than as something not built yet. */}
            <span className="text-[11px] text-muted-foreground">
              Entries can&rsquo;t be edited or deleted — a correction is a new entry.
            </span>
          </div>
        </div>
      ) : null}

      {data.rows.length === 0 ? (
        <p className="px-4 py-5 text-center text-sm text-muted-foreground">
          {data.can_write
            ? "Nothing in the log yet."
            : "Nothing in the log yet. Only this child's class teacher can add to it."}
        </p>
      ) : (
        <ul>
          {data.rows.map((r) => (
            <li key={r.id} className="border-t border-border/60 px-4 py-3 first:border-t-0">
              <div className="flex items-start gap-2.5">
                <Avatar name={r.author_name ?? "?"} className="h-6 w-6 text-[10px]" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="text-[13px] font-medium">
                      {r.author_name ?? "A former colleague"}
                    </span>
                    <span className="rounded-full border border-border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide text-muted-foreground">
                      {KIND_LABEL[r.kind] ?? r.kind}
                    </span>
                    <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                      {new Date(r.created_at).toLocaleDateString(undefined,
                        { day: "numeric", month: "short", year: "numeric" })}
                    </span>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap text-[13px] leading-snug">
                    {r.note}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
