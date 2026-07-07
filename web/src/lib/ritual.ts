import type { History, Home } from "@/lib/types";

const AFFIRMATIONS = [
  "Nothing is waiting on you.",
  "That's the lot — rest easy.",
  "Clean slate. Enjoy the quiet.",
  "All clear. See you tomorrow.",
];

/**
 * One contextual line for the "done for today" ritual (plan §3.2).
 * The streak line shows ONLY when an active all-clear run >= 2 — never as a
 * lost/broken streak. There is no shame state anywhere.
 */
export function ritualLine(home: Home, hist: History | undefined, firstEver: boolean): string {
  if (firstEver) return "That's how it works. See you tomorrow 👋";
  if (hist) {
    if (hist.current_run >= 2) {
      return `That's ${hist.current_run} days in a row finishing everything.`;
    }
    if (hist.this_week_count >= 3 && hist.this_week_count >= hist.personal_best) {
      return `${hist.this_week_count} tasks this week — your best week yet.`;
    }
  }
  // Stable choice per cleared day so it doesn't flicker on re-render.
  const seed = home.done_today + (home.date_label.length || 0);
  return AFFIRMATIONS[seed % AFFIRMATIONS.length];
}
