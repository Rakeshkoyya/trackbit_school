"use client";

/**
 * The operator's setup screen (SETUP-REDESIGN-PLAN §5).
 *
 * One school, one workbook, one page: download the pack → the school fills it
 * in → review → import → hand over. It replaces the ten-step wizard, which
 * asked an admin to type a whole school into forms.
 *
 * Two rules the report rendering follows, both taken from the validator that
 * produces these findings:
 *
 *   * a NOTE is not a problem. An unsized chapter, an unplanned term and a
 *     subject with no teacher are states a school can legitimately hand over
 *     with — rendering them red would tell the operator to chase a school for
 *     something it is right not to know yet;
 *   * only a blocker blocks. The Import button is disabled on blockers alone.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  Info,
  Loader2,
  Upload,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { ApiError } from "@/lib/api-client";
import {
  type FindingSeverity,
  type PackCredential,
  type PackFinding,
  type PackImport,
  type PackReview,
  platformApi,
} from "@/lib/platform-api";
import { cn } from "@/lib/utils";

const SEVERITY: Record<FindingSeverity, {
  tone: "danger" | "warning" | "neutral";
  Icon: typeof AlertTriangle;
}> = {
  blocker: { tone: "danger", Icon: AlertTriangle },
  warning: { tone: "warning", Icon: AlertTriangle },
  note: { tone: "neutral", Icon: Info },
};

function Card({ step, title, subtitle, done, children }: {
  step: number;
  title: string;
  subtitle?: string;
  done?: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-5">
      <div className="mb-4 flex items-start gap-3">
        <span
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-semibold",
            done ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground",
          )}
        >
          {done ? <CheckCircle2 className="h-4 w-4" /> : step}
        </span>
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">{title}</h2>
          {subtitle ? (
            <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>
          ) : null}
        </div>
      </div>
      {children}
    </section>
  );
}

function Finding({ finding }: { finding: PackFinding }) {
  const { tone, Icon } = SEVERITY[finding.severity];
  return (
    <li className="flex gap-3 border-t border-border/60 py-3 first:border-t-0">
      <Icon
        className={cn(
          "mt-0.5 h-4 w-4 shrink-0",
          finding.severity === "blocker" ? "text-danger"
            : finding.severity === "warning" ? "text-warning"
              : "text-muted-foreground",
        )}
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm">{finding.message}</p>
        {finding.fix ? (
          <p className="mt-0.5 text-sm text-muted-foreground">{finding.fix}</p>
        ) : null}
      </div>
      <Badge tone={tone} className="shrink-0">
        {finding.sheet}
        {finding.row ? ` · row ${finding.row}` : ""}
      </Badge>
    </li>
  );
}

function Report({ review }: { review: PackReview }) {
  const counts = [
    { n: review.blockers, label: "must fix", tone: "danger" as const },
    { n: review.warnings, label: "worth checking", tone: "warning" as const },
    { n: review.notes, label: "for information", tone: "neutral" as const },
  ].filter((c) => c.n > 0);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {review.ready ? (
          <Badge tone="success">Ready to import</Badge>
        ) : (
          <Badge tone="danger">Not ready</Badge>
        )}
        <span className="text-sm text-muted-foreground">
          {review.total_rows} row{review.total_rows === 1 ? "" : "s"} read
        </span>
        {counts.map((c) => (
          <Badge key={c.label} tone={c.tone}>{c.n} {c.label}</Badge>
        ))}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[28rem] text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-muted-foreground">
              <th className="py-2 pr-3 font-medium">Sheet</th>
              <th className="py-2 pr-3 font-medium">Rows</th>
              <th className="py-2 font-medium">State</th>
            </tr>
          </thead>
          <tbody>
            {review.summaries.map((s) => (
              <tr key={s.key} className="border-t border-border/60">
                <td className="py-2 pr-3">{s.title}</td>
                {/* Not-sent is a word, never a zero: a sheet the school did not
                    send is a different fact from one it sent empty. */}
                <td className="py-2 pr-3 tabular-nums text-muted-foreground">
                  {s.present ? s.rows : "—"}
                </td>
                <td className="py-2">
                  {!s.present ? (
                    <span className="text-muted-foreground">not sent</span>
                  ) : s.blocked_rows ? (
                    <span className="text-danger">
                      {s.blocked_rows} row{s.blocked_rows === 1 ? "" : "s"} to fix
                    </span>
                  ) : (
                    <span className="text-muted-foreground">ok</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {review.findings.length ? (
        <ul className="rounded-lg border border-border p-3">
          {review.findings.map((f, i) => (
            <Finding key={`${f.rule}-${i}`} finding={f} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          Nothing to report — every sheet reads cleanly.
        </p>
      )}
    </div>
  );
}

function Credentials({ rows }: { rows: PackCredential[] }) {
  function copy() {
    const text = rows
      .map((c) => `${c.name}\t${c.username}\t${c.password}`)
      .join("\n");
    void navigator.clipboard.writeText(text);
    toast.success("Logins copied");
  }
  return (
    <div className="rounded-lg border border-warning/40 bg-warning-soft/40 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-sm font-medium">
          {rows.length} staff login{rows.length === 1 ? "" : "s"} — shown once
        </p>
        <Button variant="outline" size="sm" onClick={copy}>Copy all</Button>
      </div>
      <p className="mb-3 text-sm text-muted-foreground">
        Passwords are hashed on the way in and cannot be read back. Copy these
        now; a lost one is reset, never recovered.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[24rem] text-sm">
          <tbody>
            {rows.map((c) => (
              <tr key={c.username} className="border-t border-border/60">
                <td className="py-1.5 pr-3">{c.name}</td>
                <td className="py-1.5 pr-3 font-mono text-xs">{c.username}</td>
                <td className="py-1.5 font-mono text-xs">{c.password}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Outcome({ result }: { result: PackImport }) {
  const built = result.sheets.filter((s) => s.created || s.updated);
  const notes = result.sheets.flatMap((s) => s.notes.map((n) => ({ s, n })));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2">
        {built.map((s) => (
          <Badge key={s.key} tone="success">
            {s.title}: {s.created} new{s.updated ? ` · ${s.updated} updated` : ""}
          </Badge>
        ))}
      </div>
      {notes.length ? (
        <ul className="space-y-1 text-sm text-muted-foreground">
          {notes.map(({ s, n }, i) => (
            <li key={`${s.key}-${i}`}>· {n}</li>
          ))}
        </ul>
      ) : null}
      {result.credentials.length ? (
        <Credentials rows={result.credentials} />
      ) : null}
    </div>
  );
}

export function SetupPackScreen({ orgId }: { orgId: string }) {
  const router = useRouter();
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [review, setReview] = useState<PackReview | null>(null);
  const [result, setResult] = useState<PackImport | null>(null);
  const [replaceSyllabus, setReplaceSyllabus] = useState(false);

  const { data: orgs } = useQuery({
    queryKey: ["platform-orgs"],
    queryFn: platformApi.orgs,
  });
  const org = orgs?.find((o) => o.id === orgId);

  const { data: readiness } = useQuery({
    queryKey: ["readiness", orgId],
    queryFn: () => platformApi.readiness(orgId),
    enabled: Boolean(result?.imported),
  });

  const download = useMutation({
    mutationFn: () => platformApi.downloadSetupPack(orgId, org?.name ?? "School"),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Download failed"),
  });

  const welcome = useMutation({
    mutationFn: () =>
      platformApi.downloadWelcomeSheet(orgId, org?.name ?? "School"),
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Download failed"),
  });

  const runReview = useMutation({
    mutationFn: (f: File) => platformApi.reviewSetupPack(orgId, f),
    onSuccess: (r) => {
      setReview(r);
      setResult(null);
    },
    onError: (e) =>
      toast.error(e instanceof ApiError ? e.message : "Could not read that file"),
  });

  const runImport = useMutation({
    mutationFn: () => platformApi.importSetupPack(orgId, file!, replaceSyllabus),
    onSuccess: (r) => {
      setResult(r);
      setReview(r.review);
      if (r.imported) toast.success("The school is built");
      else toast.error("Nothing was imported — fix the blockers first");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Import failed"),
  });

  function pick(selected: File | null) {
    setFile(selected);
    setResult(null);
    setReview(null);
    if (selected) runReview.mutate(selected);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
      <PageHeader
        title={org ? `Set up ${org.name}` : "Set up school"}
        subtitle="One workbook carries the whole school. Send it, get it back, review it, import it."
      />

      <Card
        step={1}
        title="Send the school its pack"
        subtitle="Year and terms, classes, staff, who teaches what, the syllabus, students — and optionally the timetable, calendar and fees."
        done={Boolean(review)}
      >
        <Button onClick={() => download.mutate()} disabled={download.isPending}>
          {download.isPending
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <Download className="h-4 w-4" />}
          Download the blank pack
        </Button>
        <p className="mt-3 text-sm text-muted-foreground">
          It comes pre-filled with what you already typed when you created the
          school, and every column carries a note explaining what goes in it.
          A blank cell always means <em>not known yet</em> — the school should
          leave one rather than guess.
        </p>
      </Card>

      <Card
        step={2}
        title="Upload what they send back"
        subtitle="Nothing is written yet. Review as many times as you need."
        done={Boolean(review)}
      >
        <input
          ref={fileInput}
          type="file"
          accept=".xlsx"
          className="hidden"
          onChange={(e) => pick(e.target.files?.[0] ?? null)}
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="outline" onClick={() => fileInput.current?.click()}
            disabled={runReview.isPending}>
            {runReview.isPending
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <Upload className="h-4 w-4" />}
            Choose the filled pack
          </Button>
          {file ? (
            <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <FileSpreadsheet className="h-4 w-4" />
              {file.name}
            </span>
          ) : null}
        </div>
      </Card>

      {review ? (
        <Card
          step={3}
          title="What the pack says"
          subtitle="Only 'must fix' stops the import. The rest is the school telling you what it does not know yet."
          done={review.ready}
        >
          <Report review={review} />
        </Card>
      ) : null}

      {review ? (
        <Card
          step={4}
          title="Build the school"
          subtitle="Everything lands in one go, or nothing does."
          done={Boolean(result?.imported)}
        >
          {result?.imported ? (
            <Outcome result={result} />
          ) : (
            <div className="space-y-3">
              <label className="flex items-start gap-2 text-sm">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={replaceSyllabus}
                  onChange={(e) => setReplaceSyllabus(e.target.checked)}
                />
                <span>
                  Replace the existing syllabus
                  <span className="block text-muted-foreground">
                    Leave this off for a school that is adding a term. On, it
                    deletes chapters already in TrackBit for every class-subject
                    in the sheet — including any a teacher has logged against.
                  </span>
                </span>
              </label>
              <Button
                onClick={() => runImport.mutate()}
                disabled={!review.ready || runImport.isPending || !file}
              >
                {runImport.isPending
                  ? <Loader2 className="h-4 w-4 animate-spin" />
                  : null}
                Import everything
              </Button>
              {!review.ready ? (
                <p className="text-sm text-muted-foreground">
                  Send the sheet back to the school with the list above, then
                  upload it again.
                </p>
              ) : null}
            </div>
          )}
        </Card>
      ) : null}

      {result?.imported ? (
        <Card step={5} title="Hand it over"
          subtitle="Check the school reads correctly before you give out the password.">
          <div className="flex flex-wrap items-center gap-3">
            {readiness ? (
              <Badge tone={readiness.ready_count === readiness.total ? "success" : "warning"}>
                {readiness.ready_count} of {readiness.total} checks ready
              </Badge>
            ) : null}
            <Button onClick={() => welcome.mutate()} disabled={welcome.isPending}>
              {welcome.isPending
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Download className="h-4 w-4" />}
              Download the handover sheet
            </Button>
            <Button variant="outline" onClick={() => router.push("/platform")}>
              Readiness &amp; handover
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            Give the school the handover sheet — it carries the school code, both
            sign-in addresses and the line between what they change themselves
            and what they ask us for. It holds no passwords: those are hashed and
            cannot be read back, so hand them over when they are generated.
          </p>
        </Card>
      ) : null}
    </div>
  );
}
