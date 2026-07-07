"use client";

import { useYear } from "@/contexts/year-context";

/** Compact academic-year picker for page headers (fees + academic list views). */
export function YearSwitcher() {
  const { years, yearId, setYearId } = useYear();
  if (!years.length) return null;
  return (
    <select
      aria-label="Academic year"
      value={yearId ?? ""}
      onChange={(e) => setYearId(e.target.value)}
      className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm font-medium"
    >
      {years.map((y) => (
        <option key={y.id} value={y.id}>
          {y.label}
          {y.is_active ? " (current)" : ""}
        </option>
      ))}
    </select>
  );
}
