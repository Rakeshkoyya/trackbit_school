// Shapes mirrored from the backend Pydantic schemas.

// SPRD §3.2 — admin (Director) · coordinator · teacher · office.
export type OrgRole = "admin" | "coordinator" | "teacher" | "office";

// Assignable roles + their plain-school-language labels (SPRD §6.1 voice).
export const ORG_ROLES: OrgRole[] = ["admin", "coordinator", "teacher", "office"];
export const ROLE_LABELS: Record<OrgRole, string> = {
  admin: "Director",
  coordinator: "Coordinator",
  teacher: "Teacher",
  office: "Office",
};

export interface User {
  id: string;
  name: string;
  email: string | null;
  username: string | null;
  phone: string | null;
}

export interface Org {
  id: string;
  name: string;
  timezone: string;
  plan: "free" | "pro";
}

// One org the signed-in user can switch into (includes the current one).
export interface OrgSummary {
  id: string;
  name: string;
  plan: "free" | "pro";
  org_role: OrgRole;
}

export interface Session {
  access_token: string;
  refresh_token: string;
  token_type: string;
  org_role: OrgRole;
  must_set_password: boolean;
  user: User;
  org: Org;
  orgs: OrgSummary[];
}

export interface Me {
  org_role: OrgRole;
  must_set_password: boolean;
  user: User;
  org: Org;
  orgs: OrgSummary[];
}

// ---- Tasks / boards ----
export type TaskStatus = "open" | "done" | "missed" | "cancelled";

export interface Assignee {
  id: string;
  name: string;
}

export interface Task {
  id: string;
  board_id: string;
  board_name: string;
  title: string;
  description: string | null;
  category: string | null;
  priority: number;
  assignee: Assignee | null;
  due_at: string | null;
  all_day: boolean;
  status: TaskStatus;
  pass_count: number;
  is_critical: boolean;
  passed_by: string | null;
  created_at: string;
}

export interface TaskEvent {
  id: number;
  type: string;
  actor_name: string | null;
  at: string;
  text: string;
}

export interface TaskDetail extends Task {
  events: TaskEvent[];
  assignable: Assignee[];
  can_cancel: boolean;
}

export interface BoardListItem {
  id: string;
  name: string;
  visibility: "public" | "private";
  task_scope: "all" | "assigned";
  category: "tasks" | "checklist";
  done_today: number;
  total_today: number;
  done: number;
  total: number;
  is_owner: boolean;
}

export interface BoardsList {
  my_boards: BoardListItem[];
  other_public: BoardListItem[];
}

export interface BoardMember {
  user_id: string;
  name: string;
}

export interface Board {
  id: string;
  name: string;
  visibility: "public" | "private";
  task_scope: "all" | "assigned";
  category: "tasks" | "checklist";
  owner_id: string;
  archived: boolean;
  can_manage: boolean;
  members: BoardMember[];
  member_count: number;
}

export interface Home {
  greeting_name: string;
  date_label: string;
  done_today: number;
  total_today: number;
  overdue: Task[];
  older_overdue_count: number;
  due_today: Task[];
  anytime: Task[];
  claimable: Task[];
}

export interface CompleteResult {
  status: string;
  already_done: boolean;
  completed_by_name: string | null;
}

export interface Member {
  user_id: string;
  name: string;
  email: string | null;
  username: string | null;
  phone: string | null;
  role: OrgRole;
  status: string;
  last_active_at: string | null;
  has_email: boolean;
  has_phone: boolean;
  pending: boolean;
}

// ---- Members: bulk create + admin reset ----
// No name: bulk staff set their own name on first login (until then the display
// name defaults to the username server-side).
export interface BulkMemberInput {
  username: string;
  password: string;
  role: OrgRole;
}

export interface BulkMemberResult {
  name: string;
  username: string;
  role: OrgRole;
  ok: boolean;
  user_id: string | null;
  password: string | null;
  error: string | null;
}

export interface BulkMembersResult {
  results: BulkMemberResult[];
  created: number;
}

export interface UsernameCheck {
  username: string; // normalized form the server would store
  available: boolean;
  error: "username_taken" | "invalid_username" | null;
}

export interface AdminResetResult {
  mode: "link_sent" | "password_set";
  password: string | null;
}

// ---- Reports (S6 board report, S7 org dashboard) ----
export interface TrendPoint {
  date: string;
  done: number;
}

export interface MemberBar {
  user_id: string;
  name: string;
  done: number;
  total: number;
  on_time: number;
}

export interface BoardReport {
  board_id: string;
  board_name: string;
  range: "today" | "week";
  total: number;
  done: number;
  completion_pct: number;
  on_time: number;
  on_time_pct: number;
  overdue: number;
  members: MemberBar[];
  trend: TrendPoint[];
}

export interface BoardSummary {
  board_id: string;
  name: string;
  total: number;
  done: number;
  completion_pct: number;
}

export interface HotspotMember {
  user_id: string;
  name: string;
  passes_received: number;
}

export interface HotTask {
  id: string;
  title: string;
  board_name: string;
  pass_count: number;
}

export interface OrgDashboard {
  range: "today" | "week";
  total: number;
  done: number;
  completion_pct: number;
  on_time: number;
  on_time_pct: number;
  overdue: number;
  members: MemberBar[];
  boards: BoardSummary[];
  hotspot_members: HotspotMember[];
  hotspot_tasks: HotTask[];
  orphaned_count: number;
}

export interface NudgeResult {
  sent: boolean;
  overdue_count: number;
  reason: string | null;
}

// ---- History / trophy room (S10, §3.3) ----
export type DotState = "all" | "partial" | "none";

export interface DayDot {
  date: string;
  state: DotState;
  done: number;
  total: number;
}

export interface WeekCount {
  week_start: string;
  count: number;
}

export interface CompletedItem {
  id: string;
  title: string;
  board_name: string;
  completed_at: string;
}

export interface History {
  dots: DayDot[];
  weekly: WeekCount[];
  this_week_count: number;
  personal_best: number;
  current_run: number;
  total_completed: number;
  completions: CompletedItem[];
}

// ---- Billing + settings (S9, P4) ----
export interface PlanLimits {
  boards: number | null;
  members: number | null;
  report_days: number;
  report_card: boolean;
  attachments: boolean;
  critical: boolean;
}

export interface OrgUsage {
  boards: number;
  members: number;
}

export interface OrgSettings {
  id: string;
  name: string;
  timezone: string;
  report_card_hour: number;
  plan: "free" | "pro";
  plan_status: "none" | "active" | "grace";
  plan_renews_at: string | null;
  limits: PlanLimits;
  usage: OrgUsage;
}

export interface Invoice {
  id: string;
  amount: number; // paise
  currency: string;
  status: string;
  paid_at: string | null;
  created_at: string;
}

export interface Billing {
  plan: "free" | "pro";
  plan_status: "none" | "active" | "grace";
  renews_at: string | null;
  grace_until: string | null;
  configured: boolean;
  key_id: string | null;
  amount: number;
  currency: string;
  invoices: Invoice[];
}

export interface Checkout {
  configured: boolean;
  subscription_id: string | null;
  key_id: string | null;
  short_url: string | null;
  message: string | null;
}

// ---- Attachments (S2, P4) ----
export interface Attachment {
  id: string;
  kind: "note" | "photo";
  content: string | null;
  file_url: string | null;
  uploaded_by_name: string;
  created_at: string;
}

export interface RecurrenceRule {
  freq: "daily" | "weekdays" | "weekly" | "monthly" | "custom";
  time?: string;
  days?: string[];
  day?: number;
  interval_days?: number;
}

export interface RecurringTemplate {
  id: string;
  board_id: string;
  board_name: string;
  title: string;
  description: string | null;
  category: string | null;
  priority: number;
  recurrence: RecurrenceRule;
  default_assignee: Assignee | null;
  active: boolean;
  is_critical: boolean;
  next_occurrences: string[];
  created_at: string;
}

// ---- Monday-style board table ----
export type BoardRowKind = "task" | "recurring";

export interface BoardRow {
  kind: BoardRowKind;
  id: string;
  title: string;
  description: string | null;
  category: string | null;
  priority: number;
  assignee: Assignee | null;
  due_at: string | null;
  all_day: boolean;
  status: TaskStatus | "scheduled";
  recurrence: RecurrenceRule | null;
  today_instance_id: string | null;
  occurs_today: boolean;
  pass_count: number;
  is_critical: boolean;
  passed_by: string | null;
  created_at: string;
}

export interface BoardGroup {
  name: string;
  color: string;
}

export interface BoardTable {
  rows: BoardRow[];
  categories: string[];
  groups: BoardGroup[];
}

export interface MyTaskRow extends BoardRow {
  board_id: string;
  board_name: string;
}

export interface MyTasks {
  rows: MyTaskRow[];
}

export interface RecurringDay {
  date: string;
  status: TaskStatus | "scheduled";
  instance_id: string | null;
  completed_by_name: string | null;
  due_at: string | null;
}

export interface RecurringHistory {
  template: RecurringTemplate;
  days: RecurringDay[];
  upcoming: string[];
}
