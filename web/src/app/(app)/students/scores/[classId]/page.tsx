"use client";

/**
 * Record a test for one class (SC-5). Two modes:
 *  - Whole class: straight into the capture form (photos → prefill → review).
 *  - Few students: pick who actually sat the test first, then the same form
 *    scoped to that subset (retests, absentee catch-ups, special groups).
 */

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Users } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ExamCapture } from "@/components/school/exam-capture";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function StudentPicker({ classId, onNext }: { classId: string; onNext: (ids: string[]) => void }) {
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const { data: students = [] } = useQuery({
    queryKey: ["students", classId],
    queryFn: () => schoolApi.students({ class_id: classId }),
    select: (rows) => rows.filter((s) => s.status === "active"),
  });
  const toggle = (id: string) => setPicked((p) => {
    const next = new Set(p);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        Pick the students who sat this test — only they appear on the marks sheet.
      </p>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {students.map((s) => {
          const on = picked.has(s.id);
          return (
            <button key={s.id} type="button" onClick={() => toggle(s.id)}
              className={`flex items-center gap-2.5 rounded-lg border px-3 py-2 text-left text-sm transition-colors ${on ? "border-primary bg-primary/5" : "border-border bg-card hover:bg-muted/40"}`}>
              <span className={`grid h-4 w-4 shrink-0 place-items-center rounded border text-[10px] ${on ? "border-primary bg-primary text-primary-foreground" : "border-border"}`}>
                {on ? "✓" : ""}
              </span>
              <span className="min-w-0 flex-1 truncate font-medium">{s.full_name}</span>
              {s.roll_no ? <span className="text-xs text-muted-foreground">#{s.roll_no}</span> : null}
            </button>
          );
        })}
      </div>
      {students.length === 0 ? <p className="text-sm text-muted-foreground">No active students in this class.</p> : null}
      <Button disabled={picked.size === 0} onClick={() => onNext(Array.from(picked))}>
        Continue with {picked.size} student{picked.size === 1 ? "" : "s"} <ArrowRight className="h-4 w-4" />
      </Button>
    </div>
  );
}

function RecordTestInner() {
  const { classId } = useParams<{ classId: string }>();
  const router = useRouter();
  const { yearId } = useYear();
  const [tab, setTab] = useState<"class" | "few">("class");
  const [subset, setSubset] = useState<string[] | null>(null);

  const { data: classes = [] } = useQuery({ queryKey: ["classes", yearId], queryFn: () => schoolApi.classes(yearId!), enabled: !!yearId });
  const klass = classes.find((c) => c.id === classId);
  const label = klass ? `${klass.name}${klass.section ? `-${klass.section}` : ""}` : "";

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/students/scores" className="rounded-md border border-border bg-card p-2 hover:bg-muted/40">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <PageHeader title={label ? `Record a test · Class ${label}` : "Record a test"}
            subtitle="Drop the evaluated papers or type the marks — review, then save" />
        </div>
      </div>

      <div className="mb-4 flex items-center gap-1 rounded-lg border border-border bg-card p-1 text-sm font-medium w-fit">
        {([["class", "Whole class"], ["few", "Few students"]] as const).map(([key, text]) => (
          <button key={key} type="button"
            className={`rounded-md px-3.5 py-1.5 transition-colors ${tab === key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted/40"}`}
            onClick={() => { setTab(key); setSubset(null); }}>
            {text}
          </button>
        ))}
      </div>

      {tab === "class" ? (
        <ExamCapture classId={classId}
          onSaved={(exam) => router.push(`/students/scores/exam/${exam.id}`)} />
      ) : subset === null ? (
        <StudentPicker classId={classId} onNext={setSubset} />
      ) : (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <Badge tone="warning"><Users className="h-3 w-3" /> {subset.length} selected students</Badge>
            <Button size="sm" variant="outline" onClick={() => setSubset(null)}>Change selection</Button>
          </div>
          <ExamCapture classId={classId} studentIds={subset}
            onSaved={(exam) => router.push(`/students/scores/exam/${exam.id}`)} />
        </div>
      )}
    </div>
  );
}

export default function RecordTestPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <RecordTestInner />
    </AuthGuard>
  );
}
