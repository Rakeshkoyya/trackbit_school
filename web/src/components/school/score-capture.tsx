"use client";

/**
 * Photo score capture (SC-2) — snap → glance → confirm.
 *
 * `CaptureReview` is the human-confirm surface (§8): the roster on the left,
 * the AI-read score prefilled where the deterministic matcher was confident,
 * fuzzy matches flagged amber, unread rows assignable by hand. Nothing reaches
 * `assessment_scores` until Confirm. Photos stay attached as evidence (P5).
 *
 * `useStartCapture` bundles create-capture (and optionally create-cycle first)
 * so the scores tab and the My Day period page share one flow.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, CheckCircle2, ImagePlus, Loader2, ScanLine, Trash2 } from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { Capture, CaptureParsedRow } from "@/lib/school-types";

const PARSE_ERROR_TEXT: Record<string, string> = {
  ai_off: "AI is not configured — type the scores below; the photos stay attached as evidence.",
  unreadable_page: "A page could not be read — retake the photo or type the scores below.",
};

type Edit = { score: string; max: string; from?: CaptureParsedRow };

export function CaptureReview({ captureId, onDone }: { captureId: string; onDone: () => void }) {
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const [uploading, setUploading] = useState(false);
  const { data: cap } = useQuery({ queryKey: ["capture", captureId], queryFn: () => schoolApi.capture(captureId) });

  // The parse result prefills the grid; `edits` holds only the human's overrides,
  // so a re-parse refreshes untouched cells without clobbering typed ones.
  const prefill = useMemo(() => {
    const map: Record<string, Edit> = {};
    for (const r of cap?.parsed_rows ?? []) {
      if (r.student_id) map[r.student_id] = { score: String(r.score), max: String(r.max_score ?? 100), from: r };
    }
    return map;
  }, [cap?.parsed_rows]);
  const valueOf = (sid: string): Edit | undefined => edits[sid] ?? prefill[sid];

  const refresh = (c: Capture) => qc.setQueryData(["capture", captureId], c);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      let latest: Capture | undefined;
      for (const f of Array.from(files)) latest = await schoolApi.uploadCapturePage(captureId, f);
      if (latest) refresh(latest);
    } catch (e) {
      showApiError(e, "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const parse = useMutation({
    mutationFn: () => schoolApi.parseCapture(captureId),
    onSuccess: (c) => { refresh(c); if (c.status === "parsed") toast.success("Photos read — review the scores"); },
    onError: (e) => showApiError(e, "Could not read the photos"),
  });
  const confirm = useMutation({
    mutationFn: () => schoolApi.confirmCapture(captureId, (cap?.roster ?? [])
      .map((s) => ({ student_id: s.student_id, v: valueOf(s.student_id) }))
      .filter((r): r is { student_id: string; v: Edit } =>
        !!r.v && r.v.score.trim() !== "" && !Number.isNaN(Number(r.v.score)))
      .map(({ student_id, v }) => ({ student_id, score: Number(v.score), max_score: Number(v.max) || 100 }))),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["grid"] });
      qc.invalidateQueries({ queryKey: ["captures"] });
      toast.success("Scores saved");
      onDone();
    },
    onError: (e) => showApiError(e, "Could not confirm"),
  });
  const discard = useMutation({
    mutationFn: () => schoolApi.discardCapture(captureId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["captures"] }); onDone(); },
    onError: (e) => showApiError(e, "Could not discard"),
  });

  if (!cap) return <p className="py-8 text-center text-sm text-muted-foreground"><Loader2 className="mx-auto mb-2 h-5 w-5 animate-spin" /></p>;

  const filled = cap.roster.filter((s) => (valueOf(s.student_id)?.score ?? "").trim() !== "").length;
  const matchedIds = new Set(cap.roster.filter((s) => valueOf(s.student_id)).map((s) => s.student_id));
  const unmatched = (cap.parsed_rows ?? []).filter((r) => !r.student_id);

  return (
    <div className="space-y-3">
      {/* pages strip + actions */}
      <div className="flex flex-wrap items-center gap-2">
        {cap.pages.map((p) => (
          <a key={p.id} href={p.url} target="_blank" rel="noreferrer"
            className="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-md border border-border bg-muted/40">
            {p.content_type.startsWith("image/")
              // eslint-disable-next-line @next/next/no-img-element
              ? <img src={p.url} alt={`Page ${p.page_no}`} className="h-full w-full object-cover" />
              : <span className="text-xs text-muted-foreground">PDF {p.page_no}</span>}
          </a>
        ))}
        <input ref={fileRef} type="file" accept="image/*,application/pdf" multiple hidden
          onChange={(e) => upload(e.target.files)} />
        <Button size="sm" variant="outline" disabled={uploading} onClick={() => fileRef.current?.click()}>
          {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImagePlus className="h-4 w-4" />}
          {cap.pages.length ? "Add page" : "Add photos"}
        </Button>
        {cap.pages.length > 0 && cap.status === "uploaded" ? (
          <Button size="sm" disabled={parse.isPending} onClick={() => parse.mutate()}>
            {parse.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanLine className="h-4 w-4" />}
            Read photos
          </Button>
        ) : null}
        {cap.status === "parsed" ? <Badge tone="success"><CheckCircle2 className="h-3 w-3" /> read</Badge> : null}
      </div>

      {cap.parse_error ? (
        <p className="rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          {PARSE_ERROR_TEXT[cap.parse_error] ?? cap.parse_error}
        </p>
      ) : null}

      {/* unmatched transcriptions → assign by hand */}
      {unmatched.length > 0 ? (
        <div className="rounded-lg border border-[color:var(--warning,#8a6d1a)]/40 bg-[color:var(--warning,#8a6d1a)]/5 p-3">
          <p className="mb-2 text-xs font-medium">Read from the photo but not matched — pick who each row belongs to:</p>
          <div className="space-y-1.5">
            {unmatched.map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="min-w-0 flex-1 truncate">“{r.name_text}” · {r.score}{r.max_score ? `/${r.max_score}` : ""}</span>
                <select className="rounded-md border border-border bg-card px-1.5 py-1 text-sm" value=""
                  onChange={(e) => {
                    if (!e.target.value) return;
                    setEdits((p) => ({ ...p, [e.target.value]: { score: String(r.score), max: String(r.max_score ?? 100), from: r } }));
                  }}>
                  <option value="">assign…</option>
                  {(r.candidates.length ? r.candidates : cap.roster.map((s) => ({ student_id: s.student_id, full_name: s.full_name })))
                    .filter((c) => !matchedIds.has(c.student_id))
                    .map((c) => <option key={c.student_id} value={c.student_id}>{c.full_name}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* the review grid: full roster, prefilled where matched */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
            <tr><th className="px-3 py-2">Student</th><th className="px-2 py-2">Score</th><th className="px-2 py-2">Out of</th><th className="px-2 py-2" /></tr>
          </thead>
          <tbody>
            {cap.roster.map((s) => {
              const e = valueOf(s.student_id);
              return (
                <tr key={s.student_id} className="border-t border-border">
                  <td className="whitespace-nowrap px-3 py-1.5 font-medium">{s.full_name}</td>
                  <td className="px-2 py-1">
                    <input type="number" className="w-16 rounded border border-border bg-card px-1.5 py-1 text-sm"
                      value={e?.score ?? ""}
                      onChange={(ev) => setEdits((p) => ({ ...p, [s.student_id]: { ...(p[s.student_id] ?? prefill[s.student_id]), score: ev.target.value, max: (p[s.student_id] ?? prefill[s.student_id])?.max ?? "100" } }))} />
                  </td>
                  <td className="px-2 py-1">
                    <input type="number" className="w-14 rounded border border-border bg-card px-1.5 py-1 text-sm"
                      value={e?.max ?? "100"}
                      onChange={(ev) => setEdits((p) => ({ ...p, [s.student_id]: { ...(p[s.student_id] ?? prefill[s.student_id]), score: (p[s.student_id] ?? prefill[s.student_id])?.score ?? "", max: ev.target.value } }))} />
                  </td>
                  <td className="px-2 py-1 text-xs text-muted-foreground">
                    {e?.from?.confidence === "fuzzy" ? <Badge tone="warning">read as “{e.from.name_text}”</Badge>
                      : e?.from?.confidence ? <span className="text-[color:var(--success,#234a37)]">✓ photo</span>
                      : e?.score ? "manual" : ""}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="flex items-center gap-2">
        <Button disabled={confirm.isPending || filled === 0} onClick={() => confirm.mutate()}>
          {confirm.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
          Confirm {filled}/{cap.roster.length} scores
        </Button>
        <Button variant="outline" disabled={discard.isPending} onClick={() => discard.mutate()}>
          <Trash2 className="h-4 w-4" /> Discard
        </Button>
      </div>
    </div>
  );
}

/** Create a capture (optionally creating its daily-test cycle first) and hand back the id. */
export function useStartCapture(onStarted: (captureId: string) => void) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: {
      cycle?: { type: string; name: string; date: string; class_id?: string; subject_id?: string };
      cycle_id?: string;
      class_id: string;
      subject_id?: string;
      skill_area_id?: string;
    }) => {
      const cycleId = v.cycle_id ?? (await schoolApi.createCycle(v.cycle!)).id;
      return schoolApi.createCapture({
        cycle_id: cycleId, class_id: v.class_id,
        subject_id: v.subject_id, skill_area_id: v.skill_area_id });
    },
    onSuccess: (cap) => {
      qc.invalidateQueries({ queryKey: ["cycles"] });
      qc.invalidateQueries({ queryKey: ["captures"] });
      onStarted(cap.id);
    },
    onError: (e) => showApiError(e, "Could not start the capture"),
  });
}

export const CaptureIcon = Camera;
