"use client";

import { useSyncExternalStore } from "react";

/**
 * Shared light/dark theme store. The `.dark` class on <html> is the source of
 * truth; it's set pre-hydration by the inline script in layout.tsx (system
 * preference unless the user chose before) and flipped here by setTheme().
 *
 * We read it via useSyncExternalStore (stable server snapshot → no hydration
 * mismatch) instead of useState+effect — the project lints
 * `react-hooks/set-state-in-effect` as an error.
 */
export const THEME_STORAGE_KEY = "trackbit_theme";
export type Theme = "light" | "dark";

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("tb-theme", onChange);
  return () => window.removeEventListener("tb-theme", onChange);
}

function getSnapshot(): Theme {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}

function getServerSnapshot(): Theme {
  return "light";
}

export function useTheme(): Theme {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}

export function setTheme(theme: Theme) {
  applyTheme(theme);
  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    /* storage unavailable (private mode) — theme still applies for this session */
  }
  window.dispatchEvent(new Event("tb-theme"));
}
