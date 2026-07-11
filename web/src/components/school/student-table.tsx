"use client";

// Grouped student table (HS-2) — the boards-table language applied to students:
// a toolbar of dropdown pills + search, then one card per group with a colored
// header and count. Reused full-size on the Students directory and as the mini
// roster table on the session page.

import { ChevronDown, Search, Users } from "lucide-react";
import { useState } from "react";

import { Input } from "@/components/ui/input";

export function Dropdown({ label, value, options, onChange }: {
  label: string;
  value: string;
  options: [string, string][];
  onChange: (v: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const current = options.find(([v]) => v === value)?.[1] ?? value;
  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md border border-border bg-card px-2.5 py-1.5 text-sm hover:bg-muted">
        <span className="text-muted-foreground">{label}:</span>
        <span className="font-medium">{current}</span>
        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute left-0 top-full z-50 mt-1 min-w-[10rem] rounded-lg border border-border bg-card p-1 shadow-lg">
            {options.map(([v, lbl]) => (
              <button key={v} type="button" onClick={() => { onChange(v); setOpen(false); }}
                className={`block w-full rounded-md px-2.5 py-1.5 text-left text-sm hover:bg-muted ${v === value ? "font-medium" : ""}`}>
                {lbl}
              </button>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

export interface StudentRowData {
  id: string;
  name: string;
  roll_no?: string | null;
  class_label?: string | null;
  category?: string | null;
  /** Extra text matched by search (admission no, guardian, …). */
  search_extra?: string | null;
}

export type StudentGroupBy = "class" | "category" | "none";

const GROUP_COLORS = ["#6b7fd7", "#3f8f6b", "#c98a3d", "#b05f8a", "#5b9aa9", "#8a6bbf"];

export function StudentTable<T extends StudentRowData>({
  rows, groupBy, filters, right, onRowClick, searchPlaceholder = "Search students…",
}: {
  rows: T[];
  /** Fixed group-by, or offer the picker when omitted. */
  groupBy?: StudentGroupBy;
  /** Extra filter pills rendered next to the group-by. */
  filters?: React.ReactNode;
  /** Right side of each row (badges, checkboxes, …). */
  right?: (row: T) => React.ReactNode;
  onRowClick?: (row: T) => void;
  searchPlaceholder?: string;
}) {
  const [q, setQ] = useState("");
  const [grouping, setGrouping] = useState<StudentGroupBy>(groupBy ?? "class");

  const needle = q.trim().toLowerCase();
  const visible = needle
    ? rows.filter((r) =>
        r.name.toLowerCase().includes(needle)
        || (r.roll_no ?? "").toLowerCase().includes(needle)
        || (r.class_label ?? "").toLowerCase().includes(needle)
        || (r.search_extra ?? "").toLowerCase().includes(needle))
    : rows;

  const keyOf = (r: T) =>
    grouping === "class" ? (r.class_label ?? "No class")
      : grouping === "category" ? (r.category ?? "No category")
        : "";
  const groups = new Map<string, T[]>();
  for (const r of visible) {
    const k = grouping === "none" ? "" : keyOf(r);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(r);
  }
  const ordered = [...groups.entries()].sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1 basis-40">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="h-9 pl-8" placeholder={searchPlaceholder} value={q}
            onChange={(e) => setQ(e.target.value)} />
        </div>
        {groupBy === undefined ? (
          <Dropdown label="Group by" value={grouping}
            options={[["class", "Class"], ["category", "Category"], ["none", "None"]]}
            onChange={(v) => setGrouping(v as StudentGroupBy)} />
        ) : null}
        {filters}
      </div>

      {visible.length === 0 ? (
        <p className="rounded-xl border border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
          No students match.
        </p>
      ) : (
        <div className="space-y-4">
          {ordered.map(([label, groupRows], gi) => (
            <div key={label || "all"} className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
              {grouping !== "none" ? (
                <div className="flex items-center gap-2 border-b border-border px-3 py-2">
                  <span className="h-4 w-1 rounded-full" style={{ background: GROUP_COLORS[gi % GROUP_COLORS.length] }} />
                  <p className="text-sm font-semibold">{label}</p>
                  <span className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Users className="h-3 w-3" /> {groupRows.length}
                  </span>
                </div>
              ) : null}
              {groupRows.map((r) => (
                <div key={r.id}
                  role={onRowClick ? "button" : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  onClick={() => onRowClick?.(r)}
                  onKeyDown={(e) => { if (onRowClick && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); onRowClick(r); } }}
                  className={`flex items-center gap-3 border-b border-border px-3 py-2.5 last:border-b-0 ${onRowClick ? "cursor-pointer transition-colors hover:bg-muted/40 active:bg-muted/60" : ""}`}>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">
                      {r.roll_no ? <span className="mr-1 text-xs text-muted-foreground">{r.roll_no}.</span> : null}
                      {r.name}
                    </p>
                  </div>
                  {right ? <div className="flex shrink-0 items-center gap-1.5">{right(r)}</div> : null}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
