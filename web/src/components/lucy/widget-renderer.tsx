"use client";

// One switch from widget type → component. Charts are a single next/dynamic
// chunk so Recharts loads only when a chart widget actually renders.

import dynamic from "next/dynamic";

import {
  AlertList,
  MarkdownWidget,
  ProgressList,
  RagBoard,
  ReportCard,
  RosterGrid,
  StatGroup,
  StudentCard,
  TimelineWidget,
} from "@/components/lucy/widgets/simple";
import { LucyTable } from "@/components/lucy/widgets/lucy-table";
import type {
  AlertListData,
  ChartData,
  DonutData,
  MarkdownData,
  ProgressData,
  RagBoardData,
  ReportCardData,
  RosterGridData,
  StatGroupData,
  StudentCardData,
  TableData,
  TimelineData,
  WidgetType,
} from "@/lib/lucy-types";

const chartLoading = () => (
  <div className="h-56 w-full animate-pulse rounded-lg bg-muted" />
);
const BarChartW = dynamic(
  () => import("@/components/lucy/widgets/charts").then((m) => m.LucyBarChart),
  { ssr: false, loading: chartLoading });
const LineChartW = dynamic(
  () => import("@/components/lucy/widgets/charts").then((m) => m.LucyLineChart),
  { ssr: false, loading: chartLoading });
const DonutW = dynamic(
  () => import("@/components/lucy/widgets/charts").then((m) => m.LucyDonut),
  { ssr: false, loading: chartLoading });

export function WidgetBody({ type, data }: { type: WidgetType; data: unknown }) {
  switch (type) {
    case "table": return <LucyTable data={data as TableData} />;
    case "stat_group": return <StatGroup data={data as StatGroupData} />;
    case "bar_chart": return <BarChartW data={data as ChartData} />;
    case "line_chart": return <LineChartW data={data as ChartData} />;
    case "donut": return <DonutW data={data as DonutData} />;
    case "rag_board": return <RagBoard data={data as RagBoardData} />;
    case "roster_grid": return <RosterGrid data={data as RosterGridData} />;
    case "timeline": return <TimelineWidget data={data as TimelineData} />;
    case "report_card": return <ReportCard data={data as ReportCardData} />;
    case "student_card": return <StudentCard data={data as StudentCardData} />;
    case "alert_list": return <AlertList data={data as AlertListData} />;
    case "progress": return <ProgressList data={data as ProgressData} />;
    case "markdown": return <MarkdownWidget data={data as MarkdownData} />;
    default:
      // Unknown/newer spec version — degrade to the raw payload, never crash.
      return (
        <pre className="overflow-x-auto rounded-lg bg-muted p-2 text-xs">
          {JSON.stringify(data, null, 2)}
        </pre>
      );
  }
}
