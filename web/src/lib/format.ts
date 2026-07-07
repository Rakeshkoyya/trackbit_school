/** Lightweight date/time formatting in the user's locale. */

export function timeLabel(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

export function dayLabel(iso: string | null): string | null {
  if (!iso) return null;
  return new Date(iso).toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

export function relativeDue(iso: string | null): string {
  if (!iso) return "Anytime";
  const due = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = due - now;
  const dayMs = 86_400_000;
  if (diffMs < -dayMs) return `${Math.round(-diffMs / dayMs)}d overdue`;
  if (diffMs < 0) return "Overdue";
  const t = timeLabel(iso);
  return t ?? "Today";
}

const DAY_LABELS: Record<string, string> = {
  mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu", fri: "Fri", sat: "Sat", sun: "Sun",
};

export function recurrenceSummary(rule: {
  freq: string;
  time?: string;
  days?: string[];
  day?: number;
}): string {
  const at = rule.time ? ` at ${rule.time}` : "";
  switch (rule.freq) {
    case "daily":
      return `Every day${at}`;
    case "weekdays":
      return `Weekdays (Mon–Fri)${at}`;
    case "weekly":
      return `Weekly on ${(rule.days ?? []).map((d) => DAY_LABELS[d] ?? d).join(", ")}${at}`;
    case "monthly":
      return `Monthly on day ${rule.day}${at}`;
    default:
      return `Custom${at}`;
  }
}

/** Priority levels: 0=none, 1=low, 2=med, 3=high. Pills are self-contained
 *  (own bg + dark text) so they read in light and dark mode alike. */
export const PRIORITY = [
  { v: 0, label: "—", cls: "text-muted-foreground" },
  { v: 1, label: "Low", cls: "bg-[#B5D4F4] text-[#042C53]" },
  { v: 2, label: "Medium", cls: "bg-[#9FE1CB] text-[#04342C]" },
  { v: 3, label: "High", cls: "bg-[#CECBF6] text-[#26215C]" },
] as const;

export function priorityMeta(p: number) {
  return PRIORITY[p] ?? PRIORITY[0];
}

export const GROUP_PALETTE = [
  "#2f8f5b", "#185fa5", "#7f77dd", "#b5791f", "#d4537e", "#1d9e75", "#d85a30", "#534ab7",
];

/** Deterministic accent color for a group with no saved color (e.g. grouped by
 *  board/status), derived from its key. */
export function groupColor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i += 1) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return GROUP_PALETTE[h % GROUP_PALETTE.length];
}

export function eventTimeLabel(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" }) +
    " · " +
    d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}
