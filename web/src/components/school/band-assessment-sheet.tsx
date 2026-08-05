"use client";

/**
 * Recording an assessment (founder 2026-08-05) — the roster, one input each.
 *
 * **Deliberately not capture-by-exception**, and that is not a lapse. P1v2's
 * budget rule is about *daily* capture across a whole class, where asking a
 * teacher to touch forty names for three facts is the mis-design. This is six
 * children she owns and the number for each one IS the point — the same
 * reasoning that lets `file_bands` touch every row of a class.
 *
 * The input follows the metric she chose, because these are three different
 * kinds of statement and one control cannot mean all three:
 *
 *   marks    a number, always beside the total it is out of
 *   rating   a **slider**, because an ordinal judgement should feel like moving
 *            a position and not like typing a score
 *   other    a word
 *
 * Three rules kept from the modules this borrows from:
 *
 *   · **Not evaluated is a word.** A child she hasn't got to renders as "not
 *     evaluated", never as a zero, and clearing an input puts him back there —
 *     which is why the save is a full replace and an empty row is a legitimate
 *     answer rather than a failed one.
 *   · **The average carries its denominator** and comes from the server, so this
 *     screen and the feed row above it can never quote different figures.
 *   · **No score for the teacher** (`S-170`) — nothing here rates how much of
 *     her roster she has got through.
 *
 * The per-child log button writes `student_notes` — the same log his class
 * teacher writes, with a pointer to this assessment. Not a note field on the
 * result row: a year later someone wants everything anyone noticed in one
 * scroll.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquarePlus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { BandChip } from "@/components/school/band-chip";
import { StudentLogDialog } from "@/components/school/student-log-dialog";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { AssessmentResultRow, BandAssessmentSheet as Sheet } from "@/lib/school-types";
import { cn } from "@/lib/utils";

type Draft = { marks: string; rating: string; verdict: string };

/** What is on the server for this child. The edit state is an **overlay** on
 *  top of this rather than a copy of it, seeded in an effect — which is both
 *  the house rule (no setState inside an effect) and the correct model: a
 *  re-fetch cannot silently drop a number she has typed but not saved. */
function serverDraft(r: AssessmentResultRow): Draft {
  return {
    marks: r.marks == null ? "" : String(r.marks),
    rating: r.rating == null ? "" : String(r.rating),
    verdict: r.verdict ?? "",
  };
}

function Row({
  row, sheet, draft, onChange, onLog,
}: {
  row: AssessmentResultRow;
  sheet: Sheet;
  draft: Draft;
  onChange: (d: Draft) => void;
  onLog: () => void;
}) {
  const a = sheet.assessment;
  const ratingMax = a.rating_max ?? 5;
  const rating = draft.rating === "" ? null : Number(draft.rating);

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-t border-border px-3 py-2.5 first:border-t-0 sm:grid-cols-[minmax(0,1fr)_minmax(0,220px)_auto]">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{row.full_name}</p>
        <p className="mt-0.5 flex items-center gap-1.5 text-xs text-muted-foreground">
          {row.roll_no ? <span>roll {row.roll_no}</span> : null}
          {/* Only when he HAS one — an unbanded child on a support sheet is not
              the place to say "not assessed" a second time. */}
          {row.tier ? <BandChip tier={row.tier} /> : null}
          {!row.evaluated ? <span>not evaluated</span> : null}
        </p>
      </div>

      <div className="col-span-2 sm:col-span-1">
        {a.metric === "marks" ? (
          <div className="flex items-center gap-2">
            <input
              type="number"
              inputMode="decimal"
              min={0}
              max={a.max_marks ?? undefined}
              value={draft.marks}
              onChange={(e) => onChange({ ...draft, marks: e.target.value })}
              placeholder="—"
              className="w-20 rounded-md border border-border bg-card px-2 py-1.5 text-right font-mono text-sm tabular-nums"
            />
            {/* The denominator is on screen beside every entry, not in a
                heading she has scrolled past. */}
            <span className="font-mono text-xs text-muted-foreground">
              of {a.max_marks ?? "—"}
            </span>
          </div>
        ) : a.metric === "rating" ? (
          <div className="flex items-center gap-2">
            <input
              type="range"
              min={0}
              max={ratingMax}
              step={1}
              value={rating ?? 0}
              onChange={(e) => onChange({ ...draft, rating: e.target.value })}
              className="h-1.5 min-w-0 flex-1 cursor-pointer accent-[color:var(--band-b)]"
              aria-label={`Rating for ${row.full_name}`}
            />
            <span className="w-14 shrink-0 text-right font-mono text-xs tabular-nums">
              {rating == null ? (
                <span className="text-muted-foreground">—</span>
              ) : (
                <>
                  {rating}
                  <span className="text-muted-foreground">/{ratingMax}</span>
                </>
              )}
            </span>
            {/* A slider cannot express "I haven't got to him", so the way back
                to not-evaluated has to be its own control. */}
            <button
              type="button"
              onClick={() => onChange({ ...draft, rating: "" })}
              disabled={rating == null}
              className="shrink-0 text-[11px] text-muted-foreground underline disabled:opacity-40"
            >
              clear
            </button>
          </div>
        ) : (
          <input
            value={draft.verdict}
            onChange={(e) => onChange({ ...draft, verdict: e.target.value })}
            placeholder="read it on his own"
            className="w-full rounded-md border border-border bg-card px-2 py-1.5 text-sm"
          />
        )}
      </div>

      <Button
        size="sm"
        variant="ghost"
        onClick={onLog}
        title="Add to his log"
        className="shrink-0"
      >
        <MessageSquarePlus className="h-4 w-4" />
        {row.notes ? (
          <span className="font-mono text-[11px] tabular-nums">{row.notes}</span>
        ) : null}
      </Button>
    </div>
  );
}

export function BandAssessmentSheetDialog({
  assessmentId, onClose,
}: {
  assessmentId: string;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  // Only what she has TOUCHED. Everything else reads straight off the server
  // row, so there is no seeding effect and no window in which the two disagree.
  const [edits, setEdits] = useState<Record<string, Draft>>({});
  const [logging, setLogging] = useState<AssessmentResultRow | null>(null);

  const { data } = useQuery({
    queryKey: ["band-assessment-sheet", assessmentId],
    queryFn: () => schoolApi.bandAssessmentSheet(assessmentId),
  });

  const draftFor = (r: AssessmentResultRow) => edits[r.student_id] ?? serverDraft(r);

  const save = useMutation({
    mutationFn: () =>
      schoolApi.recordBandAssessment(assessmentId, {
        results: (data?.rows ?? []).map((r) => {
          const d = draftFor(r);
          return {
            student_id: r.student_id,
            marks: d.marks === "" ? null : Number(d.marks),
            rating: d.rating === "" ? null : Number(d.rating),
            verdict: d.verdict.trim() || null,
          };
        }),
      }),
    onSuccess: (sheet) => {
      qc.setQueryData(["band-assessment-sheet", assessmentId], sheet);
      qc.invalidateQueries({ queryKey: ["band-assessments"] });
      setEdits({});
      toast.success("Recorded");
      onClose();
    },
    onError: (e) => showApiError(e, "Could not record it"),
  });

  const a = data?.assessment;

  return (
    <>
      <Modal
        open
        onOpenChange={(v) => !v && onClose()}
        title={a?.name ?? "Assessment"}
        description={
          a
            ? `${a.class_label}${a.subject_name ? ` · ${a.subject_name}` : ""} · ${a.given_on}`
            : undefined
        }
        size="lg"
      >
        {!data || !a ? (
          <p className="px-5 py-8 text-center text-sm text-muted-foreground">Loading…</p>
        ) : (
          <div className="px-5 py-4">
            {a.instructions ? (
              <p className="mb-3 rounded-lg border border-border bg-muted/30 p-3 text-sm leading-relaxed">
                {a.instructions}
              </p>
            ) : null}

            {/* The server's own sentence — the figure with its denominator, in
                this metric's words. Never recomposed here. */}
            <p className="mb-3 text-xs text-muted-foreground">{a.caption}</p>

            {data.rows.length ? (
              <div className="rounded-xl border border-border">
                {data.rows.map((r) => (
                  <Row
                    key={r.student_id}
                    row={r}
                    sheet={data}
                    draft={draftFor(r)}
                    onChange={(d) => setEdits((p) => ({ ...p, [r.student_id]: d }))}
                    onLog={() => setLogging(r)}
                  />
                ))}
              </div>
            ) : (
              <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
                Nobody is on this assessment right now — the children it was set for
                have all moved on.
              </p>
            )}

            <div className="mt-4 flex items-center justify-between gap-3">
              {/* Said plainly: this is a full replace, and an empty input is a
                  real answer rather than a mistake. */}
              <p className="text-xs text-muted-foreground">
                Leave a child blank and he stays <em>not evaluated</em> — never a zero.
              </p>
              <Button
                disabled={save.isPending || !data.rows.length}
                onClick={() => save.mutate()}
                className={cn("shrink-0")}
              >
                Record
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {logging && a ? (
        <StudentLogDialog
          open
          onOpenChange={(v) => !v && setLogging(null)}
          studentId={logging.student_id}
          studentName={logging.full_name}
          assessmentId={a.id}
          assessmentName={a.name}
        />
      ) : null}
    </>
  );
}
