"use client";

/**
 * "Set an assessment" (founder 2026-08-05).
 *
 * Six fields, and the order is the order she thinks in: which class · what it is
 * called · what they have to do · why (her own note) · **how she will judge it**
 * · and who it is for.
 *
 * The metric is the decision that shapes the evaluation screen, so it is chosen
 * here and not there — marks give a number input, a rating gives a slider, and
 * `other` gives a word. Its consequence is stated under the picker rather than
 * discovered on the next screen.
 *
 * **Everyone vs. the ones she picks** is not a convenience. "Everyone" keeps the
 * roster COMPUTED (HS-1's rule), so a child assigned to her next week is on this
 * assessment without anyone remembering to edit it; picking names freezes the
 * set, which is right for "just these two are re-doing it" and wrong for a
 * standing weekly check. The sentence under the toggle says which she is getting.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { AssessmentMetric } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const METRICS: { key: AssessmentMetric; label: string; hint: string }[] = [
  { key: "marks", label: "Marks", hint: "A number out of a total you set." },
  { key: "rating", label: "Rating", hint: "A slider — your own judgement, 1 to 5." },
  { key: "other", label: "A word", hint: "No number: “read it”, “still guessing”." },
];

const field =
  "mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm";

export function BandAssessmentCreate({
  open, onOpenChange, onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated?: (id: string) => void;
}) {
  const qc = useQueryClient();
  const [classId, setClassId] = useState("");
  const [name, setName] = useState("");
  const [instructions, setInstructions] = useState("");
  const [description, setDescription] = useState("");
  const [metric, setMetric] = useState<AssessmentMetric>("marks");
  const [maxMarks, setMaxMarks] = useState("10");
  const [ratingMax, setRatingMax] = useState("5");
  const [dueDate, setDueDate] = useState("");
  const [coversAll, setCoversAll] = useState(true);
  const [picked, setPicked] = useState<string[]>([]);

  // Her own children, so the class list and the student list are both the
  // programme's — never the whole school's roster.
  const { data: mine } = useQuery({
    queryKey: ["band-my-students", "all"],
    queryFn: () => schoolApi.myBandStudents(),
    enabled: open,
  });
  const inClass = (mine?.rows ?? []).filter((r) => r.class_id === classId);
  // One entry per child: ownership is per subject, so the same child can hold
  // two rows on her list and must not appear twice in a picker.
  const students = [...new Map(inClass.map((r) => [r.student_id, r])).values()];

  const create = useMutation({
    mutationFn: () =>
      schoolApi.createBandAssessment({
        class_id: classId,
        name: name.trim(),
        instructions: instructions.trim() || null,
        description: description.trim() || null,
        metric,
        max_marks: metric === "marks" ? Number(maxMarks) : null,
        rating_max: metric === "rating" ? Number(ratingMax) : null,
        due_date: dueDate || null,
        covers_all: coversAll,
        student_ids: coversAll ? [] : picked,
      }),
    onSuccess: (row) => {
      qc.invalidateQueries({ queryKey: ["band-assessments"] });
      toast.success("Set — record how they do when you have marked it");
      onOpenChange(false);
      setName("");
      setInstructions("");
      setDescription("");
      setPicked([]);
      onCreated?.(row.id);
    },
    onError: (e) => showApiError(e, "Could not set the assessment"),
  });

  const ready =
    classId && name.trim() && (coversAll || picked.length > 0) &&
    (metric !== "marks" || Number(maxMarks) > 0);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title="Set an assessment"
      description="For the support children you own in one class. Staff only — nothing here reaches a parent."
      size="md"
    >
      <div className="space-y-3 px-5 py-4">
        <div>
          <Label htmlFor="a-class">Class</Label>
          <select
            id="a-class"
            value={classId}
            onChange={(e) => {
              setClassId(e.target.value);
              setPicked([]);
            }}
            className={field}
          >
            <option value="">Pick a class…</option>
            {(mine?.classes ?? []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.label} — {c.count} child{c.count === 1 ? "" : "ren"}
              </option>
            ))}
          </select>
          {mine && !mine.classes.length ? (
            // Blocked with a sentence, never an empty form she fills in and
            // then cannot save (`S-46`).
            <p className="mt-1 text-xs text-muted-foreground">
              You have no support children yet, so there is nobody to assess.
            </p>
          ) : null}
        </div>

        <div>
          <Label htmlFor="a-name">What is it called</Label>
          <input
            id="a-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Reading aloud — week 3"
            className={field}
          />
        </div>

        <div>
          <Label htmlFor="a-instr">What they need to do</Label>
          <textarea
            id="a-instr"
            rows={2}
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
            placeholder="read page 24 aloud, then answer the three questions"
            className={field}
          />
        </div>

        <div>
          <Label htmlFor="a-desc">Your note about it (optional)</Label>
          <textarea
            id="a-desc"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="same passage as week 1, to see whether the fluency work held"
            className={field}
          />
        </div>

        <div>
          <Label>How you will judge it</Label>
          <div className="mt-1 grid grid-cols-3 gap-1.5">
            {METRICS.map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => setMetric(m.key)}
                className={cn(
                  "rounded-md border px-2 py-2 text-xs transition-colors",
                  metric === m.key
                    ? "border-primary bg-primary/10 font-medium text-primary"
                    : "border-border hover:bg-muted/50",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
          {/* The consequence, said here rather than discovered on the next
              screen. */}
          <p className="mt-1 text-xs text-muted-foreground">
            {METRICS.find((m) => m.key === metric)?.hint}
          </p>
        </div>

        {metric === "marks" ? (
          <div>
            <Label htmlFor="a-total">Out of</Label>
            <input
              id="a-total"
              type="number"
              min={1}
              value={maxMarks}
              onChange={(e) => setMaxMarks(e.target.value)}
              className={field}
            />
            {/* Every figure carries its denominator (ux §3) — which is only
                possible if she gives one. */}
            <p className="mt-1 text-xs text-muted-foreground">
              Every mark is shown with this, so “12” is never on screen alone.
            </p>
          </div>
        ) : null}

        {metric === "rating" ? (
          <div>
            <Label htmlFor="a-rmax">Rating runs to</Label>
            <select
              id="a-rmax"
              value={ratingMax}
              onChange={(e) => setRatingMax(e.target.value)}
              className={field}
            >
              {[3, 4, 5, 6, 10].map((n) => (
                <option key={n} value={n}>
                  1 to {n}
                </option>
              ))}
            </select>
          </div>
        ) : null}

        <div>
          <Label htmlFor="a-due">Due (optional)</Label>
          <input
            id="a-due"
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className={field}
          />
        </div>

        <div>
          <Label>Who it is for</Label>
          <div className="mt-1 grid grid-cols-2 gap-1.5">
            <button
              type="button"
              onClick={() => setCoversAll(true)}
              className={cn(
                "rounded-md border px-2 py-2 text-xs transition-colors",
                coversAll
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-border hover:bg-muted/50",
              )}
            >
              All my students
            </button>
            <button
              type="button"
              onClick={() => setCoversAll(false)}
              className={cn(
                "rounded-md border px-2 py-2 text-xs transition-colors",
                !coversAll
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-border hover:bg-muted/50",
              )}
            >
              Just the ones I pick
            </button>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {coversAll
              ? "Stays up to date — a child assigned to you next week is on it, and one who moves on drops off."
              : "A fixed list. Right for “these two are re-doing it”, wrong for a standing weekly check."}
          </p>
        </div>

        {!coversAll ? (
          <div className="rounded-lg border border-border">
            {classId && students.length ? (
              students.map((s) => (
                <label
                  key={s.student_id}
                  className="flex cursor-pointer items-center gap-2 border-t border-border px-3 py-2 text-sm first:border-t-0"
                >
                  <input
                    type="checkbox"
                    checked={picked.includes(s.student_id)}
                    onChange={(e) =>
                      setPicked((p) =>
                        e.target.checked
                          ? [...p, s.student_id]
                          : p.filter((x) => x !== s.student_id),
                      )
                    }
                  />
                  <span className="min-w-0 flex-1">{s.full_name}</span>
                  {s.tier ? (
                    <span
                      className="rounded-md px-1.5 py-0.5 font-mono text-[11px] font-semibold text-white"
                      style={{ background: `var(--band-${s.tier.toLowerCase()})` }}
                    >
                      {s.tier}
                    </span>
                  ) : null}
                </label>
              ))
            ) : (
              <p className="px-3 py-3 text-sm text-muted-foreground">
                {classId
                  ? "Nobody assigned to you in that class."
                  : "Pick a class first."}
              </p>
            )}
          </div>
        ) : null}

        <Button
          className="w-full"
          disabled={!ready || create.isPending}
          onClick={() => create.mutate()}
        >
          Set it
        </Button>
      </div>
    </Modal>
  );
}
