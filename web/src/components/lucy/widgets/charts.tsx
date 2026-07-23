"use client";

// Lucy's chart widgets — thin adapters over the ONE product chart kit
// (components/charts/school-charts), so a bar chart in a Lucy answer is the
// same mark as on the dashboard or a report card (GA §3.3: promote, don't
// fork). This module is loaded via next/dynamic by the widget renderer, and
// the Recharts chunk is shared with every other chart screen.

import {
  AbilityRadar,
  ColumnChart,
  Donut,
  Gauge,
  PulseArea,
  TrendLine,
} from "@/components/charts/school-charts";
import type { ChartRow } from "@/components/charts/palette";
import { toneForPct } from "@/components/charts/palette";
import type {
  AreaChartData,
  ChartData,
  DonutData,
  MeterData,
  RadarData,
} from "@/lib/lucy-types";

export function LucyBarChart({ data }: { data: ChartData }) {
  return <ColumnChart rows={data.rows as ChartRow[]} series={data.series} />;
}

export function LucyLineChart({ data }: { data: ChartData }) {
  return <TrendLine rows={data.rows as ChartRow[]} series={data.series} />;
}

export function LucyDonut({ data }: { data: DonutData }) {
  return <Donut slices={data.slices} />;
}

export function LucyMeter({ data }: { data: MeterData }) {
  return (
    <Gauge value={data.value} label={data.label} sub={data.sub ?? undefined}
      color={toneForPct(data.value)} />
  );
}

export function LucyRadar({ data }: { data: RadarData }) {
  return <AbilityRadar rows={data.rows as ChartRow[]} series={data.series} />;
}

export function LucyAreaChart({ data }: { data: AreaChartData }) {
  return (
    <PulseArea rows={data.rows as ChartRow[]} dataKey="v" label={data.label}
      yUnit={data.unit} />
  );
}
