// Chart palette + shared shapes. Deliberately free of Recharts imports: pages
// and stat tiles read these constants, and pulling them from the chart module
// would drag the whole charting library into the main bundle.

// Validated with the dataviz six-checks against BOTH surfaces (#fcfcfb light,
// #21211b dark): lightness band, chroma floor, CVD separation, normal-vision
// floor, contrast. Do not eyeball edits to this list — re-run the validator.
export const SERIES_COLORS = [
  "#5b74e8", "#1f9a5f", "#b0762a", "#c2447e", "#2b93b3", "#8a5fd4",
];

// Reserved state colours for chart MARKS. These are `--chart-*`, not the
// `--success/--warning/--danger` text tokens: as adjacent arcs the text steps
// are too close to tell apart (see the note in globals.css). Theme-aware, never
// used as "series 4", and never shown without their label.
export const STATUS_COLOR = {
  green: "var(--chart-green)",
  amber: "var(--chart-amber)",
  red: "var(--chart-red)",
  neutral: "var(--color-muted-foreground)",
} as const;

export type ChartRow = Record<string, string | number | null>;
export type Series = { key: string; label: string; color?: string };
export type Slice = { label: string; value: number; color?: string };

/** Percent → the reserved status colour. One place, so "what counts as good"
 * is the same on the dashboard, the trends board and a report card. */
export function toneForPct(pct: number | null, { good = 75, fair = 50 } = {}): string {
  if (pct == null) return STATUS_COLOR.neutral;
  if (pct >= good) return STATUS_COLOR.green;
  if (pct >= fair) return STATUS_COLOR.amber;
  return STATUS_COLOR.red;
}
