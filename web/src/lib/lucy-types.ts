// Lucy — types mirrored from api/app/schemas/lucy.py and the widget envelopes
// materialized in api/app/services/lucy/widgets.py (spec_version 1).

export type WidgetType =
  | "table"
  | "stat_group"
  | "bar_chart"
  | "line_chart"
  | "donut"
  | "rag_board"
  | "roster_grid"
  | "timeline"
  | "report_card"
  | "student_card"
  | "alert_list"
  | "progress"
  | "markdown"
  | "confirm_action";

export interface TableColumn {
  key: string;
  label: string;
  kind: "text" | "number" | "pct" | "badge" | "date";
}

// Per-type widget data shapes (what `data` holds for each WidgetType).
export interface TableData { columns: TableColumn[]; rows: Record<string, unknown>[] }
export interface StatGroupData {
  items: { label: string; value: unknown; sub?: unknown; tone?: string }[];
}
export interface ChartData {
  x_key: string;
  series: { key: string; label: string }[];
  rows: Record<string, unknown>[];
}
export interface DonutData { slices: { label: string; value: number }[] }
export interface RagBoardData {
  items: { label: string; status: string; detail?: string | null }[];
}
export interface RosterGridData {
  summary: {
    class_label?: string; period_no?: number; date?: string; marked?: boolean;
    present_count?: number; absent_count?: number; late_count?: number;
  };
  students: { name: string; roll_no?: string | null; status: string; late_minutes?: number | null }[];
}
export interface TimelineData {
  entries: { time?: string | null; title: string; detail?: string | null; status?: string | null }[];
}
export interface ReportCardData {
  for_date?: string; status?: string;
  risks: string[]; ambiguities: string[]; wins: string[];
  sections: { heading: string; lines: string[] }[];
}
export interface StudentCardData {
  title: string; subtitle?: string | null;
  fields: { label: string; value: unknown }[];
}
export interface AlertListData {
  alerts: { title: string; detail?: string | null; severity: string }[];
}
export interface ProgressData {
  items: { label: string; pct: number | null; detail?: string | null }[];
}
export interface MarkdownData { md: string }

export interface LucyWidget {
  id: string;
  conversation_id: string;
  message_id: string;
  type: WidgetType;
  title: string;
  spec_version: number;
  data: unknown;
  config: Record<string, unknown>;
  source_tool: string | null;
  pinned: boolean;
  pinned_at: string | null;
  refreshed_at: string | null;
  created_at: string;
}

export interface PendingAction {
  id: string;
  conversation_id: string;
  message_id: string | null;
  tool: string;
  summary: string;
  params: Record<string, unknown>;
  status: "proposed" | "executed" | "failed" | "cancelled" | "expired";
  result: Record<string, unknown> | null;
  error: string | null;
  expires_at: string;
  created_at: string;
}

export interface LucyMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  widgets: LucyWidget[];
  actions: PendingAction[];
}

export interface LucyConversation {
  id: string;
  title: string | null;
  created_at: string;
  updated_at: string;
}

export interface LucyConversationDetail extends LucyConversation {
  messages: LucyMessage[];
}

export interface LucyMeta {
  ai_configured: boolean;
  suggested_prompts: string[];
}

// SSE events from POST /lucy/conversations/{id}/messages.
export type LucyStreamEvent =
  | { event: "status"; data: { stage: string; label: string } }
  | { event: "tool"; data: { name: string; state: "started" | "finished" | "error"; label: string } }
  | { event: "text"; data: { delta: string } }
  | { event: "widget"; data: StreamWidget }
  | { event: "action"; data: StreamAction }
  | { event: "error"; data: { code: string; message: string } }
  | { event: "done"; data: { conversation_id: string; message_id: string | null } };

// A widget as it arrives on the stream (before persistence adds row fields).
export interface StreamWidget {
  id: string;
  spec_version: number;
  type: WidgetType;
  title: string;
  data: unknown;
  config: Record<string, unknown>;
  source_tool: string | null;
  pinned: boolean;
}

export interface StreamAction {
  id: string;
  tool: string;
  summary: string;
  params_preview: { label: string; value: string }[];
  status: string;
  expires_at: string;
}
