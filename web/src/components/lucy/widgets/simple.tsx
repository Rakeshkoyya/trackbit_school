"use client";

// Lucy's non-chart widgets. Status colors (green/amber/red) always ship with
// their label text — state is never color-alone. All content is data from the
// server-materialized payload; the markdown widget is the one model-prose
// surface and is rendered as escaped React nodes, never raw HTML.

import { useState } from "react";

import { AlertTriangle, CheckCircle2, ChevronRight, CircleAlert, Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type {
  AlertListData,
  DrilldownData,
  MarkdownData,
  ProgressData,
  RagBoardData,
  ReportCardData,
  RosterGridData,
  StatGroupData,
  StudentCardData,
  TimelineData,
} from "@/lib/lucy-types";

type Tone = "neutral" | "success" | "warning" | "danger" | "primary" | "outline";

const STATUS_TONE: Record<string, Tone> = {
  green: "success", amber: "warning", red: "danger",
  present: "success", late: "warning", absent: "danger",
  done: "success", pending: "warning", overdue: "danger",
};

function toneFor(status: string): Tone {
  return STATUS_TONE[status.toLowerCase()] ?? "neutral";
}

function fmt(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(1);
  }
  return String(value);
}

// --- stat_group ---------------------------------------------------------------

export function StatGroup({ data }: { data: StatGroupData }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {data.items.map((it) => (
        <div key={it.label} className="rounded-lg border border-border bg-muted/20 px-3 py-2">
          <p className="truncate text-xs text-muted-foreground">{it.label}</p>
          <p className={`text-lg font-semibold tabular-nums ${
            it.tone === "danger" ? "text-danger"
              : it.tone === "warning" ? "text-warning"
                : it.tone === "success" ? "text-success" : ""}`}>
            {fmt(it.value)}
          </p>
          {it.sub !== null && it.sub !== undefined ? (
            <p className="truncate text-xs text-muted-foreground">{fmt(it.sub)}</p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

// --- rag_board ------------------------------------------------------------------

export function RagBoard({ data }: { data: RagBoardData }) {
  return (
    <ul className="space-y-1.5">
      {data.items.map((it, i) => (
        <li key={i} className="flex items-center gap-2 rounded-lg border border-border px-3 py-2">
          <Badge tone={toneFor(it.status)}>{it.status}</Badge>
          <span className="min-w-0 flex-1 truncate text-sm font-medium">{it.label}</span>
          {it.detail ? (
            <span className="hidden truncate text-xs text-muted-foreground sm:block">{it.detail}</span>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

// --- roster_grid ------------------------------------------------------------------

export function RosterGrid({ data }: { data: RosterGridData }) {
  const s = data.summary;
  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
        {s.marked === false ? <Badge tone="outline">not marked yet</Badge> : null}
        <Badge tone="success">{s.present_count ?? 0} present</Badge>
        <Badge tone="danger">{s.absent_count ?? 0} absent</Badge>
        <Badge tone="warning">{s.late_count ?? 0} late</Badge>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {data.students.map((st, i) => (
          <span key={i}
            className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs ${
              st.status === "absent"
                ? "border-danger/40 bg-danger/10 text-danger"
                : st.status === "late"
                  ? "border-warning/40 bg-warning-soft text-warning"
                  : "border-border bg-muted/20"}`}>
            {st.roll_no ? <span className="text-muted-foreground">{st.roll_no}.</span> : null}
            {st.name}
            {st.status === "late" && st.late_minutes
              ? <span className="text-muted-foreground">+{st.late_minutes}m</span> : null}
          </span>
        ))}
      </div>
    </div>
  );
}

// --- drilldown ---------------------------------------------------------------------

export function DrilldownWidget({ data }: { data: DrilldownData }) {
  const [open, setOpen] = useState<Record<number, boolean>>({});
  return (
    <ul className="space-y-1.5">
      {data.groups.map((g, i) => (
        <li key={i} className="rounded-lg border border-border">
          <button type="button"
            className="flex w-full items-center gap-2 px-3 py-2 text-left"
            onClick={() => setOpen((o) => ({ ...o, [i]: !o[i] }))}>
            <ChevronRight
              className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
                open[i] ? "rotate-90" : ""}`} />
            <span className="min-w-0 flex-1 truncate text-sm font-medium">{g.label}</span>
            {g.stats.map((s) => (
              <span key={s.label} className="shrink-0 text-xs text-muted-foreground">
                {s.label}: <span className="font-medium text-foreground">{fmt(s.value)}</span>
              </span>
            ))}
            {g.children.length ? (
              <span className="shrink-0 text-xs text-muted-foreground">
                {g.children.length}
              </span>
            ) : null}
          </button>
          {open[i] && g.children.length ? (
            <ul className="space-y-1 border-t border-border px-3 py-2">
              {g.children.map((c, j) => (
                <li key={j} className="flex items-center gap-2 text-sm">
                  {c.status ? <Badge tone={toneFor(c.status)}>{c.status}</Badge> : null}
                  <span className="min-w-0 flex-1 truncate">{c.label}</span>
                  {c.detail ? (
                    <span className="truncate text-xs text-muted-foreground">{c.detail}</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

// --- timeline ----------------------------------------------------------------------

export function TimelineWidget({ data }: { data: TimelineData }) {
  return (
    <ul className="space-y-0">
      {data.entries.map((e, i) => (
        <li key={i} className="relative flex gap-3 pb-3 last:pb-0">
          <div className="flex w-14 shrink-0 flex-col items-end pt-0.5">
            <span className="text-xs tabular-nums text-muted-foreground">{e.time ?? ""}</span>
          </div>
          <div className="relative flex flex-col items-center">
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-primary/60" />
            {i < data.entries.length - 1 ? (
              <span className="w-px flex-1 bg-border" />
            ) : null}
          </div>
          <div className="min-w-0 flex-1 pb-1">
            <p className="text-sm font-medium">
              {e.title}
              {e.status ? <Badge tone={toneFor(e.status)} className="ml-2">{e.status}</Badge> : null}
            </p>
            {e.detail ? <p className="text-xs text-muted-foreground">{e.detail}</p> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

// --- report_card ------------------------------------------------------------------

function HighlightList({ items, icon, tone }: {
  items: string[]; icon: React.ReactNode; tone: string;
}) {
  if (!items.length) return null;
  return (
    <ul className="space-y-1">
      {items.map((t, i) => (
        <li key={i} className={`flex items-start gap-1.5 text-sm ${tone}`}>
          <span className="mt-0.5 shrink-0">{icon}</span>
          <span>{t}</span>
        </li>
      ))}
    </ul>
  );
}

export function ReportCard({ data }: { data: ReportCardData }) {
  return (
    <div className="space-y-3">
      <HighlightList items={data.risks} tone="text-danger"
        icon={<AlertTriangle className="h-3.5 w-3.5" />} />
      <HighlightList items={data.ambiguities} tone="text-warning"
        icon={<CircleAlert className="h-3.5 w-3.5" />} />
      <HighlightList items={data.wins} tone="text-success"
        icon={<CheckCircle2 className="h-3.5 w-3.5" />} />
      {data.sections.map((sec) => (
        <div key={sec.heading}>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {sec.heading}
          </p>
          <ul className="space-y-0.5">
            {sec.lines.map((line, i) => (
              <li key={i} className="text-sm">{line}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

// --- student_card -----------------------------------------------------------------

export function StudentCard({ data }: { data: StudentCardData }) {
  return (
    <div>
      <p className="text-base font-semibold">{data.title}</p>
      {data.subtitle ? <p className="text-sm text-muted-foreground">{data.subtitle}</p> : null}
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
        {data.fields.map((f) => (
          <div key={f.label}>
            <dt className="text-xs text-muted-foreground">{f.label}</dt>
            <dd className="text-sm font-medium">{fmt(f.value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

// --- alert_list --------------------------------------------------------------------

export function AlertList({ data }: { data: AlertListData }) {
  return (
    <ul className="space-y-1.5">
      {data.alerts.map((a, i) => (
        <li key={i} className="flex items-start gap-2 rounded-lg border border-border px-3 py-2">
          {a.severity === "red" || a.severity === "danger"
            ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
            : a.severity === "amber" || a.severity === "warning"
              ? <CircleAlert className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
              : <Info className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />}
          <div className="min-w-0">
            <p className="text-sm font-medium">{a.title}</p>
            {a.detail ? <p className="text-xs text-muted-foreground">{a.detail}</p> : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

// --- progress ----------------------------------------------------------------------

export function ProgressList({ data }: { data: ProgressData }) {
  return (
    <ul className="space-y-2">
      {data.items.map((it, i) => (
        <li key={i}>
          <div className="mb-0.5 flex items-baseline justify-between gap-2 text-sm">
            <span className="min-w-0 truncate font-medium">{it.label}</span>
            <span className="shrink-0 tabular-nums text-xs text-muted-foreground">
              {it.pct === null ? "—" : `${Math.round(it.pct)}%`}
              {it.detail ? ` · ${it.detail}` : ""}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary/70 transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(0, it.pct ?? 0))}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

// --- markdown (model prose — escaped, minimal formatting, no raw HTML) ---------------

function inline(text: string, key: number): React.ReactNode {
  // **bold** and `code` only; everything else stays literal text.
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
  return (
    <span key={key}>
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**")
          ? <strong key={i}>{p.slice(2, -2)}</strong>
          : p.startsWith("`") && p.endsWith("`")
            ? <code key={i} className="rounded bg-muted px-1 text-[0.85em]">{p.slice(1, -1)}</code>
            : p)}
    </span>
  );
}

export function MarkdownWidget({ data }: { data: MarkdownData }) {
  const blocks = (data.md ?? "").split(/\n{2,}/);
  return (
    <div className="space-y-2 text-sm">
      {blocks.map((block, bi) => {
        const lines = block.split("\n").filter((l) => l.trim());
        if (!lines.length) return null;
        if (lines.every((l) => /^\s*[-*]\s+/.test(l))) {
          return (
            <ul key={bi} className="list-disc space-y-0.5 pl-5">
              {lines.map((l, i) => <li key={i}>{inline(l.replace(/^\s*[-*]\s+/, ""), i)}</li>)}
            </ul>
          );
        }
        if (/^#{1,3}\s+/.test(lines[0])) {
          return (
            <p key={bi} className="pt-1 text-sm font-semibold">
              {inline(lines[0].replace(/^#{1,3}\s+/, ""), 0)}
            </p>
          );
        }
        return <p key={bi}>{lines.map((l, i) => inline(l + (i < lines.length - 1 ? " " : ""), i))}</p>;
      })}
    </div>
  );
}
