"use client";

/**
 * ExamCapture (SC-5 → V1-8 `D-80`) — the one form that records a test's results.
 *
 * **Photo-first, per student.** The teacher marks a stack of papers at her desk,
 * photographs each one, and the model reads the identity, the total and the
 * marks she wrote beside each question. `score_match` — deterministic, on the
 * server — decides *who* each paper belongs to; a hallucinated name can never
 * write a score. She then adjusts in the grid, and nothing persists until she
 * saves (§8).
 *
 * Three rules the shape of this screen exists to keep:
 *
 * 1. **Manual entry is first class, never a degraded fallback.** Skip the
 *    photos entirely and type; the form is identical.
 * 2. **A page we cannot read must never become a page we discard** (`D-80`
 *    step 5). An unreadable photo comes back as its own row, with the picture,
 *    and the teacher attaches the student and the marks by hand.
 * 3. **The exam type is the school's own word** (`D-55`) and it carries the
 *    `scale`, so she picks *one* thing — not a type and then minor/major.
 *
 * A locked exam (`D-53`) is the record: this form refuses to edit one, and says
 * who to ask.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle, ArrowLeft, CheckCircle2, ClipboardCheck, FileUp, Loader2, Lock, Pencil,
} from "lucide-react";
import { useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { showApiError } from "@/lib/errors";
import { todayKey } from "@/lib/format";
import { schoolApi } from "@/lib/school-api";
import type {
  Capture, CaptureParsedRow, CycleType, ExamDetail, QuestionMark,
} from "@/lib/school-types";

/** The fallback labels for the system kinds — used only where a school has not
 *  named its own exam types yet. Never in place of one that exists (`D-55`). */
export const EXAM_TYPE_LABEL: Record<string, string> = {
  chapter_test: "Chapter test",
  class_test: "Class test",
  slip_test: "Slip test",
  objective: "Objective test",
  unit_test: "Unit test",
  term_exam: "Term exam",
  daily_test: "Daily test",
  band_test: "Band test",
  diagnostic: "Diagnostic",
};

const PARSE_ERROR_TEXT: Record<string, string> = {
  ai_off: "AI is not configured — the photos stay attached as evidence; fill the form below.",
  unreadable_page: "None of the pages could be read — attach each one to a student below, or type the marks in.",
};

// Local, never UTC: an exam captured before 05:30 IST would otherwise be
// dated yesterday (see `dayKey` in lib/format).
const today = () => todayKey();

type RosterStudent = { student_id: string; full_name: string; roll_no: string | null };

export function ExamCapture({ classId, studentIds, examId, fixedType,
  fixedSubjectId, examEventId, defaultName, onSaved }: {
  classId: string;
  /** Few-students test: only these students sat it. Omit = whole class. */
  studentIds?: string[];
  /** Set = reopen this saved exam for editing. */
  examId?: string;
  /** Pins the type (the Bands page records band tests). */
  fixedType?: CycleType;
  /** Pins the subject and hides the picker. Plan → Exams opens capture from a
   *  class × subject CELL, so the subject is already decided — and a teacher
   *  may only enter her own subject, which a dropdown of all of them invites
   *  her to try and the server then refuses. */
  fixedSubjectId?: string;
  /** `S-115` — files this paper under a declared main exam. The link has
   *  existed on the cycle since V1-8 and nothing ever populated it. */
  examEventId?: string;
  /** Seeds the title, so a term paper is not typed thirty times. */
  defaultName?: string;
  onSaved?: (exam: ExamDetail) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [seeded, setSeeded] = useState(false);
  const [name, setName] = useState(defaultName ?? "");
  const [type, setType] = useState<string>(fixedType ?? "chapter_test");
  const [examTypeId, setExamTypeId] = useState<string>("");
  const [date, setDate] = useState(today());
  const [subjectId, setSubjectId] = useState(fixedSubjectId ?? "");
  const [topic, setTopic] = useState("");
  const [total, setTotal] = useState("100");
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [photoFill, setPhotoFill] = useState<Record<string, string>>({});
  // student → what the model read off their script, kept so it saves with the
  // mark (§4's reconciliation: no new capture surface, no extra taps).
  const [qmarks, setQmarks] = useState<Record<string, QuestionMark[]>>({});
  const [pageOf, setPageOf] = useState<Record<string, string>>({});   // student → page
  const [captureId, setCaptureId] = useState<string | null>(null);
  const [cap, setCap] = useState<Capture | null>(null);
  const [uploading, setUploading] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  const { data: subjects = [] } = useQuery({ queryKey: ["subjects"], queryFn: schoolApi.subjects });
  const { data: examTypes = [] } = useQuery({
    queryKey: ["exam-types"], queryFn: () => schoolApi.examTypes(),
  });
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
    setExamTypeId(exam.exam_type_id ?? "");
    setDate(exam.date);
    setSubjectId(exam.subject_id);
    setTopic(exam.topic ?? "");
    setTotal(String(exam.total_marks ?? 100));
    setPhotoFill(Object.fromEntries(
      exam.rows.filter((r) => r.score != null).map((r) => [r.student_id, String(r.score)])));
    setQmarks(Object.fromEntries(exam.rows
      .filter((r) => r.question_marks?.length)
      .map((r) => [r.student_id, r.question_marks!])));
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

  // A pinned subject wins outright — never falls back to subjects[0], which
  // would silently record the paper against the wrong subject.
  const effSubject = fixedSubjectId
    ?? (subjects.some((s) => s.id === subjectId) ? subjectId : (subjects[0]?.id ?? ""));
  const markOf = (sid: string) => edits[sid] ?? photoFill[sid] ?? "";
  const pickable = fixedType
    ? examTypes.filter((t) => t.system_type === fixedType)
    : examTypes.filter((t) => t.system_type !== "diagnostic" && t.system_type !== "band_test");
  const pickedType = examTypes.find((t) => t.id === examTypeId);

  // ── photos → draft capture → parse → prefill ───────────────────────────────
  const applyParsed = (c: Capture) => {
    setCap(c);
    const m = c.parsed_meta;
    if (m) {
      if (m.title && !name.trim()) setName(m.title);
      // Never let a parsed header move a pinned subject.
      if (m.subject_id && !fixedSubjectId) setSubjectId(m.subject_id);
      if (m.total_marks && (total === "100" || !total)) setTotal(String(m.total_marks));
      if (m.topic && !topic.trim()) setTopic(m.topic);
      if (m.date && /^\d{4}-\d{2}-\d{2}$/.test(m.date)) setDate(m.date);
    }
    const fill: Record<string, string> = {};
    const qs: Record<string, QuestionMark[]> = {};
    const pages: Record<string, string> = {};
    for (const r of c.parsed_rows ?? []) {
      if (!r.student_id || r.score == null) continue;
      fill[r.student_id] = String(r.score);
      if (r.question_marks?.length) qs[r.student_id] = r.question_marks;
      if (r.page_id) pages[r.student_id] = r.page_id;
    }
    if (Object.keys(fill).length) setPhotoFill((p) => ({ ...p, ...fill }));
    if (Object.keys(qs).length) setQmarks((p) => ({ ...p, ...qs }));
    if (Object.keys(pages).length) setPageOf((p) => ({ ...p, ...pages }));
  };

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      let capId = captureId;
      if (!capId) {
        const created = await schoolApi.createCapture({
          class_id: classId,
          // `D-80`: one page per student's marked script is the primary flow.
          mode: "scripts",
          student_ids: studentIds?.length ? studentIds : undefined });
        capId = created.id;
        setCaptureId(created.id);
      }
      for (const f of Array.from(files)) await schoolApi.uploadCapturePage(capId, f);
      const parsed = await schoolApi.parseCapture(capId);
      applyParsed(parsed);
      if (parsed.status === "parsed" && !parsed.parse_error) {
        toast.success("Papers read — check the prefilled marks");
      }
    } catch (e) {
      showApiError(e, "Could not read the papers");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  /** A page attached to a student by hand — the `D-80` step-5 path. */
  const attach = (row: CaptureParsedRow, studentId: string) => {
    if (!studentId) return;
    setEdits((p) => ({ ...p, [studentId]: row.score != null ? String(row.score) : (p[studentId] ?? "") }));
    if (row.question_marks?.length) setQmarks((p) => ({ ...p, [studentId]: row.question_marks! }));
    if (row.page_id) setPageOf((p) => ({ ...p, [studentId]: row.page_id! }));
  };

  // ── save ───────────────────────────────────────────────────────────────────
  const rows = roster
    .map((s) => ({ student_id: s.student_id, raw: markOf(s.student_id) }))
    .filter((r) => r.raw.trim() !== "" && !Number.isNaN(Number(r.raw)))
    .map((r) => ({
      student_id: r.student_id, score: Number(r.raw),
      question_marks: qmarks[r.student_id] ?? null,
      page_id: pageOf[r.student_id] ?? null,
    }));
  const totalNum = Number(total) || 0;
  const avg = rows.length && totalNum
    ? Math.round(rows.reduce((a, r) => a + r.score, 0) / (rows.length * totalNum) * 1000) / 10
    : null;
  const ready = name.trim() && date && effSubject && totalNum > 0 && rows.length > 0;

  const save = useMutation({
    mutationFn: () => schoolApi.saveExam({
      cycle_id: examId, class_id: classId, subject_id: effSubject,
      type: pickedType?.system_type ?? type, exam_type_id: examTypeId || null,
      name: name.trim(), date, topic: topic.trim() || null,
      total_marks: totalNum, exam_event_id: examEventId ?? null,
      student_ids: examId ? (exam?.student_ids ?? undefined)
        : (studentIds?.length ? studentIds : undefined),
      capture_id: captureId ?? undefined, rows }),
    onSuccess: (d) => { toast.success(examId ? "Exam updated" : "Exam saved"); onSaved?.(d); },
    onError: (e) => showApiError(e, "Could not save the exam"),
  });

  const overMax = rows.some((r) => r.score > totalNum);
  const pages = [...(exam?.pages ?? []), ...(cap?.pages ?? [])];
  const pageUrl = (id: string | null) => pages.find((p) => p.id === id)?.url ?? null;
  const claimed = new Set(Object.keys(photoFill).concat(Object.keys(edits)));
  // Every row the human still has to place: unmatched transcriptions AND the
  // pages nothing could be read from. Both are the same job, so they are one
  // list — and a page that was already attached drops out of it.
  const toPlace = (cap?.parsed_rows ?? []).filter(
    (r) => !r.student_id && !(r.page_id && Object.values(pageOf).includes(r.page_id)));

  // `D-53`: a locked exam is the record. Say who can reopen it, and stop.
  if (examId && exam?.locked) {
    return (
      <div className="space-y-4">
        <div className="flex items-start gap-3 rounded-xl border border-border bg-muted/30 p-4">
          <Lock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
          <div>
            <p className="text-sm font-semibold">These marks are locked.</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Locked by {exam.locked_by_name ?? "a teacher"}
              {exam.locked_at ? ` on ${exam.locked_at.slice(0, 10)}` : ""}. An admin can unlock
              it with a reason — the reason is kept, and the marks are not silently replaced.
            </p>
          </div>
        </div>
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
              <tr><th className="px-3 py-2">Student</th><th className="px-2 py-2">Marks</th>
                <th className="px-2 py-2">Paper</th></tr>
            </thead>
            <tbody>
              {exam.rows.map((r) => (
                <tr key={r.student_id} className="border-t border-border">
                  <td className="whitespace-nowrap px-3 py-1.5 font-medium">{r.full_name}</td>
                  <td className="px-2 py-1.5">
                    {r.score == null ? <span className="text-xs text-muted-foreground">did not sit</span>
                      : `${r.score}/${r.max_score ?? total}`}
                  </td>
                  <td className="px-2 py-1.5 text-xs">
                    {r.paper_url
                      ? <a href={r.paper_url} target="_blank" rel="noreferrer" className="underline">see the paper</a>
                      : <span className="text-muted-foreground">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // ── review step: the whole exam read-only before it persists (§8) ──────────
  if (reviewing) {
    return (
      <div className="space-y-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold">
              <ClipboardCheck className="h-4 w-4" /> Review before saving
            </h2>
            <Badge tone="neutral">{pickedType?.name ?? EXAM_TYPE_LABEL[type] ?? type}</Badge>
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
              <tr><th className="px-3 py-2">Student</th><th className="px-2 py-2">Marks</th>
                <th className="px-2 py-2">%</th><th className="px-2 py-2">Paper</th></tr>
            </thead>
            <tbody>
              {roster.map((s) => {
                const raw = markOf(s.student_id);
                const n = raw.trim() === "" ? null : Number(raw);
                const url = pageUrl(pageOf[s.student_id] ?? null);
                return (
                  <tr key={s.student_id} className="border-t border-border">
                    <td className="whitespace-nowrap px-3 py-1.5 font-medium">{s.full_name}</td>
                    <td className="px-2 py-1.5">{n == null ? <span className="text-xs text-muted-foreground">—</span> : `${n}/${total}`}</td>
                    <td className="px-2 py-1.5 text-xs text-muted-foreground">
                      {n != null && totalNum ? `${Math.round(n / totalNum * 1000) / 10}%` : ""}
                    </td>
                    <td className="px-2 py-1.5 text-xs">
                      {url ? <a href={url} target="_blank" rel="noreferrer" className="underline">paper</a>
                        : <span className="text-muted-foreground">—</span>}
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
      {/* 1 · a photo per marked script (optional — typing is the same form) */}
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
              {pages.length ? "Add more papers" : "Photograph each marked paper"}
            </span>
            <span className="block text-xs text-muted-foreground">
              One photo per student. The name, the total and the marks beside each question are
              read for you — you check everything before it saves. Or just type the marks below.
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
                  ? <img src={p.url} alt={`Paper ${p.page_no}`} className="h-full w-full object-cover" />
                  : <span className="text-xs text-muted-foreground">PDF {p.page_no}</span>}
              </a>
            ))}
            {cap?.status === "parsed" && !cap.parse_error
              ? <Badge tone="success"><CheckCircle2 className="h-3 w-3" /> read</Badge> : null}
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
        {fixedType && pickable.length <= 1 ? null : (
          <div>
            <Label>Type</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={examTypeId}
              onChange={(e) => {
                setExamTypeId(e.target.value);
                const t = examTypes.find((x) => x.id === e.target.value);
                if (t) setType(t.system_type);
              }}>
              <option value="">Choose…</option>
              {pickable.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            {pickedType ? (
              <p className="mt-1 text-xs text-muted-foreground">
                Counted as {pickedType.scale === "major" ? "a major exam — these show standing"
                  : "a minor test — these show movement"}.
              </p>
            ) : null}
          </div>
        )}
        <div>
          <Label>Date</Label>
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </div>
        <div>
          <Label>Subject</Label>
          {fixedSubjectId ? (
            <p className="rounded-md border border-border bg-muted/40 px-2 py-2 text-sm">
              {subjects.find((s) => s.id === fixedSubjectId)?.name ?? "This subject"}
            </p>
          ) : (
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={effSubject} onChange={(e) => setSubjectId(e.target.value)}>
              {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          )}
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

      {/* Papers still to place: unmatched reads AND pages nothing could be read
          from. `D-80` step 5 — a page we cannot read is kept and mapped by hand. */}
      {toPlace.length > 0 ? (
        <div className="rounded-lg border border-[color:var(--warning,#8a6d1a)]/40 bg-[color:var(--warning,#8a6d1a)]/5 p-3">
          <p className="mb-2 text-xs font-medium">
            {toPlace.length} paper{toPlace.length === 1 ? "" : "s"} still to place — say whose each one is:
          </p>
          <div className="space-y-2">
            {toPlace.map((r, i) => {
              const url = pageUrl(r.page_id);
              return (
                <div key={r.page_id ?? i} className="flex items-center gap-2 text-sm">
                  {url ? (
                    <a href={url} target="_blank" rel="noreferrer"
                      className="h-10 w-10 shrink-0 overflow-hidden rounded border border-border">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={url} alt={`Paper ${r.page_no ?? ""}`} className="h-full w-full object-cover" />
                    </a>
                  ) : null}
                  <span className="min-w-0 flex-1 truncate">
                    {r.unreadable
                      ? <span className="text-muted-foreground">Could not be read — attach it and type the marks</span>
                      : <>&ldquo;{r.name_text}&rdquo;{r.score != null ? ` · ${r.score}${r.max_score ? `/${r.max_score}` : ""}` : ""}</>}
                  </span>
                  <select className="rounded-md border border-border bg-card px-1.5 py-1 text-sm" value=""
                    onChange={(e) => attach(r, e.target.value)}>
                    <option value="">assign…</option>
                    {roster.filter((s) => !claimed.has(s.student_id))
                      .map((s) => <option key={s.student_id} value={s.student_id}>{s.full_name}</option>)}
                  </select>
                </div>
              );
            })}
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
              const qs = qmarks[s.student_id];
              // `S-116`: the per-question marks don't add up to the total on the
              // paper. About the TEACHER's paper, never a claim about the child.
              const qSum = qs?.length ? qs.reduce((a, q) => a + q.score, 0) : null;
              const mismatch = qSum != null && val.trim() !== "" && Math.abs(qSum - Number(val)) > 0.01
                ? qSum : null;
              return (
                <tr key={s.student_id} className="border-t border-border">
                  <td className="whitespace-nowrap px-3 py-1.5 font-medium">
                    {s.full_name}
                    {s.roll_no ? <span className="ml-1.5 text-xs text-muted-foreground">#{s.roll_no}</span> : null}
                    {qs?.length ? (
                      <span className="ml-1.5 text-xs text-muted-foreground">
                        {qs.map((q) => `Q${q.q} ${q.score}`).join(" · ")}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-2 py-1">
                    <input type="number" className="w-20 rounded border border-border bg-card px-1.5 py-1 text-sm"
                      value={val} placeholder="—"
                      onChange={(e) => setEdits((p) => ({ ...p, [s.student_id]: e.target.value }))} />
                  </td>
                  <td className="px-2 py-1 text-xs">
                    {mismatch != null ? (
                      <span className="inline-flex items-center gap-1 text-[color:var(--warning,#8a6d1a)]">
                        <AlertTriangle className="h-3 w-3" /> questions add to {mismatch}
                      </span>
                    ) : fromPhoto ? <span className="text-[color:var(--success,#234a37)]">✓ photo</span>
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
