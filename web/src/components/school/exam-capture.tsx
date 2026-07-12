"use client";

/**
 * ExamCapture (SC-5) — the one form that records a test's results.
 *
 * Drop photos/PDFs of the evaluated papers FIRST and the parse prefills the
 * exam fields (title, subject, total marks, topic) and every matched student's
 * mark — or skip the photos and type everything. A review step shows the whole
 * exam read-only before anything persists (§8), and the same component reopens
 * a saved exam for editing (examId set). Photos stay filed as evidence (P5).
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft, CheckCircle2, ClipboardCheck, FileUp, Loader2, Pencil,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { Capture, CycleType, ExamDetail } from "@/lib/school-types";

export const EXAM_TYPE_LABEL: Record<string, string> = {
  chapter_test: "Chapter-end test",
  class_test: "Class test",
  slip_test: "Slip test",
  objective: "Objective",
  unit_test: "Unit test",
  term_exam: "Term exam",
  daily_test: "Daily test",
  band_test: "Band test",
  diagnostic: "Diagnostic",
};
const PICKABLE_TYPES = ["chapter_test", "class_test", "slip_test", "objective",
  "unit_test", "term_exam", "daily_test"];

const PARSE_ERROR_TEXT: Record<string, string> = {
  ai_off: "AI is not configured — the photos stay attached as evidence; fill the form below.",
  unreadable_page: "A page could not be read — retake the photo or fill the form below.",
};

const today = () => new Date().toISOString().slice(0, 10);

type RosterStudent = { student_id: string; full_name: string; roll_no: string | null };

export function ExamCapture({ classId, studentIds, examId, fixedType, onSaved }: {
  classId: string;
  /** Few-students test: only these students sat it. Omit = whole class. */
  studentIds?: string[];
  /** Set = reopen this saved exam for editing. */
  examId?: string;
  /** Pins the type (the Bands page records band tests). */
  fixedType?: CycleType;
  onSaved?: (exam: ExamDetail) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [seeded, setSeeded] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState<string>(fixedType ?? "chapter_test");
  const [date, setDate] = useState(today());
  const [subjectId, setSubjectId] = useState("");
  const [topic, setTopic] = useState("");
  const [total, setTotal] = useState("100");
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [photoFill, setPhotoFill] = useState<Record<string, string>>({});
  const [captureId, setCaptureId] = useState<string | null>(null);
  const [cap, setCap] = useState<Capture | null>(null);
  const [uploading, setUploading] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  const { data: subjects = [] } = useQuery({ queryKey: ["subjects"], queryFn: schoolApi.subjects });
  const { data: allStudents = [] } = useQuery({
    queryKey: ["students", classId],
    queryFn: () => schoolApi.students({ class_id: classId }),
    enabled: !examId,
  });
  const { data: exam } = useQuery({
    queryKey: ["exam", examId], queryFn: () => schoolApi.exam(examId!), enabled: !!examId,
  });

  // Edit mode: seed the form from the saved exam exactly once.
  if (examId && exam && !seeded) {
    setSeeded(true);
    setName(exam.name);
    setType(exam.type);
    setDate(exam.date);
    setSubjectId(exam.subject_id);
    setTopic(exam.topic ?? "");
    setTotal(String(exam.total_marks ?? 100));
    setPhotoFill(Object.fromEntries(
      exam.rows.filter((r) => r.score != null).map((r) => [r.student_id, String(r.score)])));
  }

  const roster: RosterStudent[] = useMemo(() => {
    if (examId) {
      return (exam?.rows ?? []).map((r) => ({
        student_id: r.student_id, full_name: r.full_name, roll_no: r.roll_no }));
    }
    const active = allStudents.filter((s) => s.status === "active");
    const subset = studentIds?.length ? active.filter((s) => studentIds.includes(s.id)) : active;
    return subset.map((s) => ({ student_id: s.id, full_name: s.full_name, roll_no: s.roll_no }));
  }, [examId, exam?.rows, allStudents, studentIds]);

  const effSubject = subjects.some((s) => s.id === subjectId) ? subjectId : (subjects[0]?.id ?? "");
  const markOf = (sid: string) => edits[sid] ?? photoFill[sid] ?? "";

  // ── photos → draft capture → parse → prefill ───────────────────────────────
  const applyParsed = (c: Capture) => {
    setCap(c);
    const m = c.parsed_meta;
    if (m) {
      if (m.title && !name.trim()) setName(m.title);
      if (m.subject_id) setSubjectId(m.subject_id);
      if (m.total_marks && (total === "100" || !total)) setTotal(String(m.total_marks));
      if (m.topic && !topic.trim()) setTopic(m.topic);
      if (m.date && /^\d{4}-\d{2}-\d{2}$/.test(m.date)) setDate(m.date);
    }
    const fill: Record<string, string> = {};
    for (const r of c.parsed_rows ?? []) {
      if (r.student_id) fill[r.student_id] = String(r.score);
    }
    if (Object.keys(fill).length) setPhotoFill((p) => ({ ...p, ...fill }));
  };

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      let capId = captureId;
      if (!capId) {
        const created = await schoolApi.createCapture({
          class_id: classId, student_ids: studentIds?.length ? studentIds : undefined });
        capId = created.id;
        setCaptureId(created.id);
      }
      for (const f of Array.from(files)) await schoolApi.uploadCapturePage(capId, f);
      const parsed = await schoolApi.parseCapture(capId);
      applyParsed(parsed);
      if (parsed.status === "parsed") toast.success("Papers read — check the prefilled form");
    } catch (e) {
      showApiError(e, "Could not read the papers");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  // ── save ───────────────────────────────────────────────────────────────────
  const rows = roster
    .map((s) => ({ student_id: s.student_id, raw: markOf(s.student_id) }))
    .filter((r) => r.raw.trim() !== "" && !Number.isNaN(Number(r.raw)))
    .map((r) => ({ student_id: r.student_id, score: Number(r.raw) }));
  const totalNum = Number(total) || 0;
  const avg = rows.length && totalNum
    ? Math.round(rows.reduce((a, r) => a + r.score, 0) / (rows.length * totalNum) * 1000) / 10
    : null;
  const ready = name.trim() && date && effSubject && totalNum > 0 && rows.length > 0;

  const save = useMutation({
    mutationFn: () => schoolApi.saveExam({
      cycle_id: examId, class_id: classId, subject_id: effSubject,
      type, name: name.trim(), date, topic: topic.trim() || null,
      total_marks: totalNum,
      student_ids: examId ? (exam?.student_ids ?? undefined)
        : (studentIds?.length ? studentIds : undefined),
      capture_id: captureId ?? undefined, rows }),
    onSuccess: (d) => { toast.success(examId ? "Exam updated" : "Exam saved"); onSaved?.(d); },
    onError: (e) => showApiError(e, "Could not save the exam"),
  });

  const overMax = rows.some((r) => r.score > totalNum);
  const pages = [...(exam?.pages ?? []), ...(cap?.pages ?? [])];
  const matchedIds = new Set(Object.keys(photoFill).concat(Object.keys(edits)));
  const unmatched = (cap?.parsed_rows ?? []).filter((r) => !r.student_id);

  // ── review step: the whole exam read-only before it persists (§8) ──────────
  if (reviewing) {
    return (
      <div className="space-y-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <ClipboardCheck className="h-4 w-4" /> Review before saving
            </h2>
            <Badge tone="neutral">{EXAM_TYPE_LABEL[type] ?? type}</Badge>
          </div>
          <p className="text-base font-semibold">{name}</p>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {subjects.find((s) => s.id === effSubject)?.name} · {date}
            {topic.trim() ? ` · ${topic}` : ""} · out of {total}
          </p>
          <div className="mt-3 flex items-center gap-3 text-sm">
            <Badge tone="success">{rows.length}/{roster.length} marks</Badge>
            {avg != null ? <span className="text-muted-foreground">class average {avg}%</span> : null}
          </div>
        </div>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
              <tr><th className="px-3 py-2">Student</th><th className="px-2 py-2">Marks</th><th className="px-2 py-2">%</th></tr>
            </thead>
            <tbody>
              {roster.map((s) => {
                const raw = markOf(s.student_id);
                const n = raw.trim() === "" ? null : Number(raw);
                return (
                  <tr key={s.student_id} className="border-t border-border">
                    <td className="whitespace-nowrap px-3 py-1.5 font-medium">{s.full_name}</td>
                    <td className="px-2 py-1.5">{n == null ? <span className="text-xs text-muted-foreground">—</span> : `${n}/${total}`}</td>
                    <td className="px-2 py-1.5 text-xs text-muted-foreground">
                      {n != null && totalNum ? `${Math.round(n / totalNum * 1000) / 10}%` : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => setReviewing(false)}>
            <ArrowLeft className="h-4 w-4" /> Back to edit
          </Button>
          <Button disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
            {examId ? "Save changes" : "Save exam"}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* 1 · drop the evaluated papers (optional, prefills everything below) */}
      <div className="rounded-xl border border-dashed border-border bg-card p-4">
        <input ref={fileRef} type="file" accept="image/*,application/pdf" multiple hidden
          onChange={(e) => upload(e.target.files)} />
        <button type="button" className="flex w-full items-center gap-3 text-left"
          onClick={() => fileRef.current?.click()} disabled={uploading}>
          <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-muted text-muted-foreground">
            {uploading ? <Loader2 className="h-5 w-5 animate-spin" /> : <FileUp className="h-5 w-5" />}
          </span>
          <span>
            <span className="block text-sm font-semibold">
              {pages.length ? "Add more pages" : "Drop photos or a PDF of the evaluated papers"}
            </span>
            <span className="block text-xs text-muted-foreground">
              The exam details and each student&apos;s marks are read and prefilled — you review everything before saving.
            </span>
          </span>
        </button>
        {pages.length > 0 ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {pages.map((p) => (
              <a key={p.id} href={p.url} target="_blank" rel="noreferrer"
                className="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-md border border-border bg-muted/40">
                {p.content_type.startsWith("image/")
                  // eslint-disable-next-line @next/next/no-img-element
                  ? <img src={p.url} alt={`Page ${p.page_no}`} className="h-full w-full object-cover" />
                  : <span className="text-xs text-muted-foreground">PDF {p.page_no}</span>}
              </a>
            ))}
            {cap?.status === "parsed" ? <Badge tone="success"><CheckCircle2 className="h-3 w-3" /> read</Badge> : null}
          </div>
        ) : null}
        {cap?.parse_error ? (
          <p className="mt-2 rounded-md border border-border bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            {PARSE_ERROR_TEXT[cap.parse_error] ?? cap.parse_error}
          </p>
        ) : null}
      </div>

      {/* 2 · the exam itself */}
      <div className="grid gap-3 rounded-xl border border-border bg-card p-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Label>Test title</Label>
          <Input placeholder="Ch 3 Fractions — chapter test" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        {fixedType ? null : (
          <div>
            <Label>Type</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={type} onChange={(e) => setType(e.target.value)}>
              {PICKABLE_TYPES.map((t) => <option key={t} value={t}>{EXAM_TYPE_LABEL[t]}</option>)}
            </select>
          </div>
        )}
        <div>
          <Label>Date</Label>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div>
          <Label>Subject</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
            value={effSubject} onChange={(e) => setSubjectId(e.target.value)}>
            {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div>
          <Label>Total marks</Label>
          <Input type="number" min={1} value={total} onChange={(e) => setTotal(e.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <Label>Topic / chapter (optional)</Label>
          <Input placeholder="Fractions" value={topic} onChange={(e) => setTopic(e.target.value)} />
        </div>
      </div>

      {/* read from the photo but not matched to a student — assign by hand */}
      {unmatched.length > 0 ? (
        <div className="rounded-lg border border-[color:var(--warning,#8a6d1a)]/40 bg-[color:var(--warning,#8a6d1a)]/5 p-3">
          <p className="mb-2 text-xs font-medium">Read from the papers but not matched — pick who each row belongs to:</p>
          <div className="space-y-1.5">
            {unmatched.map((r, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <span className="min-w-0 flex-1 truncate">&ldquo;{r.name_text}&rdquo; · {r.score}{r.max_score ? `/${r.max_score}` : ""}</span>
                <select className="rounded-md border border-border bg-card px-1.5 py-1 text-sm" value=""
                  onChange={(e) => {
                    if (!e.target.value) return;
                    setEdits((p) => ({ ...p, [e.target.value]: String(r.score) }));
                  }}>
                  <option value="">assign…</option>
                  {roster.filter((s) => !matchedIds.has(s.student_id))
                    .map((s) => <option key={s.student_id} value={s.student_id}>{s.full_name}</option>)}
                </select>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* 3 · marks per student */}
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
            <tr><th className="px-3 py-2">Student</th><th className="px-2 py-2">Marks / {total || "?"}</th><th className="px-2 py-2" /></tr>
          </thead>
          <tbody>
            {roster.map((s) => {
              const val = markOf(s.student_id);
              const fromPhoto = !(s.student_id in edits) && s.student_id in photoFill && !examId;
              return (
                <tr key={s.student_id} className="border-t border-border">
                  <td className="whitespace-nowrap px-3 py-1.5 font-medium">
                    {s.full_name}
                    {s.roll_no ? <span className="ml-1.5 text-xs text-muted-foreground">#{s.roll_no}</span> : null}
                  </td>
                  <td className="px-2 py-1">
                    <input type="number" className="w-20 rounded border border-border bg-card px-1.5 py-1 text-sm"
                      value={val} placeholder="—"
                      onChange={(e) => setEdits((p) => ({ ...p, [s.student_id]: e.target.value }))} />
                  </td>
                  <td className="px-2 py-1 text-xs">
                    {fromPhoto ? <span className="text-[color:var(--success,#234a37)]">✓ photo</span>
                      : val && totalNum && Number(val) > totalNum ? <Badge tone="danger">over total</Badge> : null}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {roster.length === 0 ? (
        <p className="text-sm text-muted-foreground">No active students to mark.</p>
      ) : null}

      <div className="flex items-center gap-2">
        <Button disabled={!ready || overMax} onClick={() => setReviewing(true)}>
          <Pencil className="h-4 w-4" /> Review {rows.length}/{roster.length} marks
        </Button>
        {!ready ? (
          <p className="text-xs text-muted-foreground">
            {!name.trim() ? "Give the test a title." : !rows.length ? "Enter at least one mark." : ""}
          </p>
        ) : overMax ? <p className="text-xs text-muted-foreground">A mark is over the total.</p> : null}
      </div>
    </div>
  );
}
