"use client";

// Lucy's interactive table widget — the StudentTable language generalized to
// arbitrary columns from the widget's column meta: client-side search, optional
// group-by over any text column, and sort over any column. All operations run
// on the materialized rows; nothing refetches.

import { ChevronDown, ChevronUp, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Dropdown } from "@/components/school/student-table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import type { TableData } from "@/lib/lucy-types";

const GROUP_COLORS = ["#5b74e8", "#1f9a5f", "#b0762a", "#c2447e", "#2b93b3", "#8a5fd4"];

function cellText(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(1);
  return String(value);
}

function Cell({ value, kind }: { value: unknown; kind: string }) {
  if (value === null || value === undefined) {
    return <span className="text-muted-foreground">—</span>;
  }
  if (kind === "pct") {
    const n = Number(value);
    if (!Number.isNaN(n)) {
      const tone = n >= 75 ? "success" : n >= 40 ? "warning" : "danger";
      return <Badge tone={tone}>{Number.isInteger(n) ? n : n.toFixed(1)}%</Badge>;
    }
  }
  if (kind === "badge") {
    const v = String(value).toLowerCase();
    const tone = ["green", "present", "done", "paid", "approved", "true"].includes(v)
      ? "success"
      : ["amber", "late", "partial", "pending"].includes(v)
        ? "warning"
        : ["red", "absent", "overdue", "failed"].includes(v)
          ? "danger"
          : "neutral";
    return <Badge tone={tone}>{String(value)}</Badge>;
  }
  if (kind === "number") return <span className="tabular-nums">{cellText(value)}</span>;
  return <span>{cellText(value)}</span>;
}

export function LucyTable({ data }: { data: TableData }) {
  const { columns, rows } = data;
  const [q, setQ] = useState("");
  const [groupBy, setGroupBy] = useState<string>("none");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);

  const groupable = columns.filter((c) => c.kind === "text" || c.kind === "badge");

  const visible = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let out = needle
      ? rows.filter((r) =>
          columns.some((c) => cellText(r[c.key]).toLowerCase().includes(needle)))
      : [...rows];
    if (sort) {
      out = out.sort((a, b) => {
        const av = a[sort.key];
        const bv = b[sort.key];
        if (av === bv) return 0;
        if (av === null || av === undefined) return 1;
        if (bv === null || bv === undefined) return -1;
        if (typeof av === "number" && typeof bv === "number") {
          return (av - bv) * sort.dir;
        }
        return String(av).localeCompare(String(bv), undefined, { numeric: true }) * sort.dir;
      });
    }
    return out;
  }, [rows, columns, q, sort]);

  const groups = useMemo(() => {
    if (groupBy === "none") return [["", visible] as [string, typeof visible]];
    const map = new Map<string, typeof visible>();
    for (const r of visible) {
      const k = cellText(r[groupBy]);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(r);
    }
    return [...map.entries()].sort(([a], [b]) =>
      a.localeCompare(b, undefined, { numeric: true }));
  }, [visible, groupBy]);

  const onHeaderClick = (key: string) =>
    setSort((s) => (s?.key === key ? (s.dir === 1 ? { key, dir: -1 } : null) : { key, dir: 1 }));

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1 basis-32">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="h-8 pl-8 text-sm" placeholder="Search…" value={q}
            onChange={(e) => setQ(e.target.value)} />
        </div>
        {groupable.length > 0 ? (
          <Dropdown label="Group by" value={groupBy}
            options={[["none", "None"], ...groupable.map((c) => [c.key, c.label] as [string, string])]}
            onChange={setGroupBy} />
        ) : null}
      </div>

      {visible.length === 0 ? (
        <p className="px-2 py-4 text-center text-sm text-muted-foreground">No rows match.</p>
      ) : (
        <div className="space-y-3">
          {groups.map(([label, groupRows], gi) => (
            <div key={label || "all"} className="overflow-x-auto rounded-lg border border-border">
              {groupBy !== "none" ? (
                <div className="flex items-center gap-2 border-b border-border bg-muted/30 px-3 py-1.5">
                  <span className="h-3.5 w-1 rounded-full"
                    style={{ background: GROUP_COLORS[gi % GROUP_COLORS.length] }} />
                  <p className="text-xs font-semibold">{label}</p>
                  <span className="text-xs text-muted-foreground">{groupRows.length}</span>
                </div>
              ) : null}
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/20 text-left">
                    {columns.map((c) => (
                      <th key={c.key} className="whitespace-nowrap px-3 py-2 font-medium">
                        <button type="button" onClick={() => onHeaderClick(c.key)}
                          className="inline-flex items-center gap-1 text-muted-foreground hover:text-foreground">
                          {c.label}
                          {sort?.key === c.key
                            ? sort.dir === 1
                              ? <ChevronUp className="h-3 w-3" />
                              : <ChevronDown className="h-3 w-3" />
                            : null}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {groupRows.map((r, i) => (
                    <tr key={i} className="border-b border-border last:border-b-0 hover:bg-muted/30">
                      {columns.map((c) => (
                        <td key={c.key} className="whitespace-nowrap px-3 py-1.5">
                          <Cell value={r[c.key]} kind={c.kind} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
