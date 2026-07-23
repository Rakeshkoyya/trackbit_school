// Sample data for every School UI Kit component (GA §3.4). This is the
// gallery's ground truth: each entry mirrors what the backend shaper of that
// type materializes, so the gallery breaks when a data contract drifts.

import type {
  AlertListData,
  AreaChartData,
  ChartData,
  DonutData,
  DrilldownData,
  MarkdownData,
  MeterData,
  ProgressData,
  RadarData,
  RagBoardData,
  ReportCardData,
  RosterGridData,
  StatGroupData,
  StudentCardData,
  TableData,
  TimelineData,
  WidgetType,
} from "@/lib/lucy-types";

export interface GallerySample {
  type: WidgetType;
  title: string;
  summary: string;
  data: unknown;
}

const table: TableData = {
  columns: [
    { key: "name", label: "Student", kind: "text" },
    { key: "cls", label: "Class", kind: "badge" },
    { key: "pct", label: "Attendance", kind: "pct" },
    { key: "avg", label: "Avg score", kind: "number" },
  ],
  rows: [
    { name: "Asha Reddy", cls: "6-A", pct: 96.2, avg: 78 },
    { name: "Bharat Kumar", cls: "6-A", pct: 88.4, avg: 64 },
    { name: "Chetan Rao", cls: "6-B", pct: 74.1, avg: 51 },
  ],
};

const statGroup: StatGroupData = {
  items: [
    { label: "Present today", value: 412, sub: "of 428", tone: "success" },
    { label: "Absent", value: 14, tone: "danger" },
    { label: "Late", value: 2, tone: "warning" },
    { label: "Periods logged", value: "38/42", tone: "neutral" },
  ],
};

const barChart: ChartData = {
  x_key: "x",
  series: [{ key: "attendance", label: "Attendance %" }, { key: "homework", label: "Homework %" }],
  rows: [
    { x: "6-A", attendance: 96, homework: 88 },
    { x: "6-B", attendance: 89, homework: 72 },
    { x: "7-A", attendance: 93, homework: 91 },
    { x: "8-A", attendance: 85, homework: 66 },
  ],
};

const lineChart: ChartData = {
  x_key: "x",
  series: [{ key: "maths", label: "Maths" }, { key: "science", label: "Science" }],
  rows: [
    { x: "Unit 1", maths: 62, science: 71 },
    { x: "Mid-term", maths: 66, science: 68 },
    { x: "Unit 2", maths: 71, science: 74 },
    { x: "Term 1", maths: 75, science: 70 },
  ],
};

const areaChart: AreaChartData = {
  label: "attendance",
  unit: "%",
  rows: [
    { x: "Mon", v: 94 }, { x: "Tue", v: 96 }, { x: "Wed", v: 91 },
    { x: "Thu", v: 88 }, { x: "Fri", v: 95 }, { x: "Sat", v: 97 },
  ],
};

const donut: DonutData = {
  slices: [
    { label: "On track", value: 9 },
    { label: "Slipping", value: 3 },
    { label: "Behind", value: 2 },
  ],
};

const meter: MeterData = {
  label: "Fee collection",
  value: 72.5,
  sub: "₹4,32,000 of ₹5,96,000",
  unit: "%",
};

const radar: RadarData = {
  series: [{ key: "student", label: "Asha" }, { key: "cls", label: "Class avg" }],
  rows: [
    { x: "Reading", student: 78, cls: 64 },
    { x: "Writing", student: 61, cls: 66 },
    { x: "Reasoning", student: 84, cls: 62 },
    { x: "Numeracy", student: 70, cls: 68 },
    { x: "Recall", student: 66, cls: 71 },
  ],
};

const ragBoard: RagBoardData = {
  items: [
    { label: "Maths — 6-A", status: "green", detail: "on baseline" },
    { label: "Science — 6-A", status: "amber", detail: "1.5 weeks behind" },
    { label: "English — 6-B", status: "red", detail: "3 weeks behind" },
  ],
};

const rosterGrid: RosterGridData = {
  summary: { class_label: "6-A", period_no: 3, date: "2026-07-24", marked: true,
    present_count: 26, absent_count: 2, late_count: 1 },
  students: [
    { name: "Asha Reddy", roll_no: "1", status: "present" },
    { name: "Bharat Kumar", roll_no: "2", status: "absent" },
    { name: "Chetan Rao", roll_no: "3", status: "late", late_minutes: 10 },
    { name: "Divya Nair", roll_no: "4", status: "present" },
    { name: "Esha Patel", roll_no: "5", status: "present" },
  ],
};

const drilldown: DrilldownData = {
  groups: [
    {
      label: "Maths",
      stats: [{ label: "Coverage", value: "64%" }, { label: "Missed", value: 3 }],
      children: [
        { label: "Algebra — linear equations", detail: "taught 12 Jul", status: "done" },
        { label: "Algebra — word problems", detail: "taught 15 Jul (absent)", status: "missed" },
        { label: "Geometry — angles", detail: "planned wk 8", status: "pending" },
      ],
    },
    {
      label: "Science",
      stats: [{ label: "Coverage", value: "81%" }, { label: "Missed", value: 0 }],
      children: [
        { label: "Light — reflection", detail: "taught 10 Jul", status: "done" },
        { label: "Light — refraction", detail: "taught 18 Jul", status: "done" },
      ],
    },
  ],
};

const timeline: TimelineData = {
  entries: [
    { time: "P1", title: "Maths — fractions revision", status: "present" },
    { time: "P2", title: "Science — light", detail: "homework assigned", status: "present" },
    { time: "P3", title: "English", detail: "absent this period", status: "absent" },
    { time: "P4", title: "Social — maps", status: "present" },
  ],
};

const reportCard: ReportCardData = {
  for_date: "2026-07-24",
  status: "draft",
  risks: ["8-A English is 3 weeks behind baseline", "Bharat Kumar absent 3 days running"],
  ambiguities: ["6-B P4 has attendance but no lesson log"],
  wins: ["100% homework completion in 7-A Maths"],
  sections: [
    { heading: "Attendance", lines: ["412 of 428 present (96.3%)", "2 classes unmarked at 4 pm"] },
    { heading: "Syllabus", lines: ["9 subjects green, 3 amber, 2 red"] },
  ],
};

const studentCard: StudentCardData = {
  title: "Asha Reddy",
  subtitle: "Class 6-A · Roll 1 · Hosteller",
  fields: [
    { label: "Attendance", value: "96.2%" },
    { label: "Latest test", value: "78% (Unit 2 Maths)" },
    { label: "Guardian", value: "R. Reddy (father)" },
  ],
};

const alertList: AlertListData = {
  alerts: [
    { title: "English 6-B is 3 weeks behind", detail: "red for 2 weeks", severity: "high" },
    { title: "Bharat Kumar — 3 absences in a row", detail: "guardian alerted", severity: "medium" },
    { title: "2 periods unlogged today", severity: "info" },
  ],
};

const progress: ProgressData = {
  items: [
    { label: "Ch 1 — Numbers", pct: 100 },
    { label: "Ch 2 — Fractions", pct: 60, detail: "3 of 5 topics" },
    { label: "Ch 3 — Geometry", pct: 0, detail: "starts wk 9" },
  ],
};

const markdown: MarkdownData = {
  md: "**Asha** is comfortably ahead in reasoning-heavy topics; the one soft spot is *written English*, where scores trail the class average by ~5 points.",
};

export const GALLERY: GallerySample[] = [
  { type: "table", title: "Table", summary: "Lists and detail rows", data: table },
  { type: "stat_group", title: "Stat group", summary: "Headline numbers", data: statGroup },
  { type: "bar_chart", title: "Bar chart", summary: "Comparison across categories", data: barChart },
  { type: "line_chart", title: "Line chart", summary: "Trend over time", data: lineChart },
  { type: "area_chart", title: "Area chart", summary: "One measure's shape over time", data: areaChart },
  { type: "donut", title: "Donut", summary: "Parts of a whole", data: donut },
  { type: "meter", title: "Meter", summary: "A single percentage", data: meter },
  { type: "radar", title: "Radar", summary: "Profile across skill areas", data: radar },
  { type: "rag_board", title: "RAG board", summary: "Green/amber/red status per item", data: ragBoard },
  { type: "roster_grid", title: "Roster grid", summary: "One class-period's attendance", data: rosterGrid },
  { type: "drilldown", title: "Drilldown", summary: "Two-level expandable groups", data: drilldown },
  { type: "timeline", title: "Timeline", summary: "A day, period by period", data: timeline },
  { type: "report_card", title: "Report card", summary: "The generated daily report", data: reportCard },
  { type: "student_card", title: "Student card", summary: "Identity + key facts", data: studentCard },
  { type: "alert_list", title: "Alert list", summary: "Prioritized warnings", data: alertList },
  { type: "progress", title: "Progress", summary: "Completion per item", data: progress },
  { type: "markdown", title: "Markdown", summary: "Model prose (escaped, never HTML)", data: markdown },
];
