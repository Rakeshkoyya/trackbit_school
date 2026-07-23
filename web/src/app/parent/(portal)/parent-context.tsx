"use client";

import { useQuery } from "@tanstack/react-query";
import { createContext, useContext, useState } from "react";

import { parentApi, type ParentChild, type ParentMe } from "@/lib/parent-api";

interface ParentState {
  me: ParentMe | null;
  child: ParentChild | null; // the selected child (siblings switch here)
  setChildId: (id: string) => void;
}

const ParentContext = createContext<ParentState | null>(null);
const STORAGE_KEY = "trackbit_parent_child";

export function ParentProvider({ children }: { children: React.ReactNode }) {
  const { data: me } = useQuery({ queryKey: ["parent", "me"], queryFn: parentApi.me });
  // Seed from the last-viewed child; the selection is DERIVED against the
  // loaded children list, so a stale/foreign id just falls back to the first.
  const [childId, setChildIdState] = useState<string | null>(() =>
    typeof window === "undefined" ? null : localStorage.getItem(STORAGE_KEY),
  );

  const setChildId = (id: string) => {
    localStorage.setItem(STORAGE_KEY, id);
    setChildIdState(id);
  };

  const child =
    me?.children.find((c) => c.student_id === childId) ?? me?.children[0] ?? null;

  return (
    <ParentContext.Provider value={{ me: me ?? null, child, setChildId }}>
      {children}
    </ParentContext.Provider>
  );
}

export function useParentPortal() {
  const ctx = useContext(ParentContext);
  if (!ctx) throw new Error("useParentPortal must be used within <ParentProvider>");
  return ctx;
}
