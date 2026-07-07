"use client";

import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { setTheme, useTheme } from "@/lib/theme";

/**
 * Light/dark toggle for the topbar. The current state comes from the shared
 * theme store (see lib/theme.ts); clicking flips and persists it.
 */
export function ThemeToggle() {
  const theme = useTheme();
  const next = theme === "dark" ? "light" : "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(next)}
      aria-label={`Switch to ${next} mode`}
      title={`Switch to ${next} mode`}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
