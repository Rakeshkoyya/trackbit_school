"use client";

import { useQuery } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState } from "react";

import { schoolApi } from "@/lib/school-api";
import type { AcademicYear } from "@/lib/school-types";

interface YearState {
  years: AcademicYear[];
  yearId: string | null; // currently selected
  setYearId: (id: string) => void;
  loading: boolean;
}

const YearContext = createContext<YearState | null>(null);
const LS_KEY = "trackbit.year";

/** Global academic-year switcher state (SPRD §6.3 header). Scopes fee + academic
 *  list views. Defaults to the org's active year; the choice is persisted. */
export function YearProvider({ children }: { children: React.ReactNode }) {
  const { data: years = [], isLoading } = useQuery({
    queryKey: ["academic-years"],
    queryFn: schoolApi.years,
    staleTime: 60_000,
  });
  // The user's explicit choice; null means "fall back to stored/active/first".
  const [override, setOverride] = useState<string | null>(null);

  // Derive the effective year (no setState-in-effect): override → stored → active → first.
  const yearId = useMemo<string | null>(() => {
    if (!years.length) return null;
    if (override && years.some((y) => y.id === override)) return override;
    const stored = typeof window !== "undefined" ? localStorage.getItem(LS_KEY) : null;
    if (stored && years.some((y) => y.id === stored)) return stored;
    return (years.find((y) => y.is_active) ?? years[0]).id;
  }, [override, years]);

  const setYearId = useCallback((id: string) => {
    setOverride(id);
    if (typeof window !== "undefined") localStorage.setItem(LS_KEY, id);
  }, []);

  const value = useMemo<YearState>(
    () => ({ years, yearId, setYearId, loading: isLoading }),
    [years, yearId, setYearId, isLoading],
  );
  return <YearContext.Provider value={value}>{children}</YearContext.Provider>;
}

export function useYear() {
  const ctx = useContext(YearContext);
  if (!ctx) throw new Error("useYear must be used within <YearProvider>");
  return ctx;
}
