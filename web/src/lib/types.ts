// Shapes mirrored from the backend Pydantic schemas.

// SPRD v2 §2 — two staff roles: admin (runs the school) · teacher (all staff).
// "parent" is NOT a membership: it's the guardian-login session role (parent
// portal, founder decision 2026-07-23) and never appears in Members.
export type OrgRole = "admin" | "teacher" | "parent";

// Assignable STAFF roles + their plain-school-language labels (SPRD §6.1 voice).
export const ORG_ROLES: OrgRole[] = ["admin", "teacher"];
export const ROLE_LABELS: Record<OrgRole, string> = {
  admin: "Admin",
  teacher: "Teacher",
  parent: "Parent",
};

export interface User {
  id: string;
  name: string;
  email: string | null;
  username: string | null;
  phone: string | null;
}

/** The four package tiers, cheapest first (`D-106`). Cumulative: `max`
 *  includes everything in `pro`, which includes everything in `free`.
 *  Never branch on this in a component — ask for a FEATURE instead, so the
 *  browser never carries a second copy of `core/features.py`'s tier map. */
export type PlanTier = "free" | "pro" | "max" | "ultra";

export interface Org {
  id: string;
  name: string;
  timezone: string;
  plan: PlanTier;
  /** Every feature this school's package includes, computed server-side from
   *  `core/features.py`. Read it through `useFeature()` — never branch on
   *  `plan` in a component, or the tier map ends up living in two places. */
  features: string[];
  /** Set once TrackBit has handed the school over. From then on the school's
   *  structure — year, terms, classes, subjects, who teaches what, syllabus,
   *  timetable — is changed by us, not by the school (SETUP-REDESIGN-PLAN §6).
   *  The setup screens read this to go read-only. */
  handed_over_at: string | null;
}

// One org the signed-in user can switch into (includes the current one).
export interface OrgSummary {
  id: string;
  name: string;
  plan: PlanTier;
  org_role: OrgRole;
}

export interface Session {
  access_token: string;
  refresh_token: string;
  token_type: string;
  org_role: OrgRole;
  must_set_password: boolean;
  // Platform operator (the TrackBit dev): sees /platform, creates schools.
  is_super_admin: boolean;
  user: User;
  org: Org;
  orgs: OrgSummary[];
}

export interface Me {
  org_role: OrgRole;
  must_set_password: boolean;
  is_super_admin: boolean;
  /** V1-3 (D-03): class teacher of at least one class — the nav shows
   *  "My Class" from this alone. */
  is_class_teacher: boolean;
  /** Takes at least one band-monitored subject (admins always). Gates the ABC
   * bands nav item — a teacher outside the programme never sees it. */
  has_band_scope: boolean;
  /** V1-7 (D-56): your own date of birth, self-entered on Account. Never shown
   *  on a class list (S-133) and never sent to a parent surface (Q-57). */
  date_of_birth: string | null;
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

/** D-46: what a task is about — a student or a member, resolved to a name. */
export interface TaskSubject {
  type: "student" | "member";
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
  subject?: TaskSubject | null; // D-46
  outcome?: string | null; // D-46: "what happened?" once completed
  asked_by?: string | null; // S-106: "Priya asked · this morning"
  asked_at?: string | null;
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
  member_id: string | null;
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
export interface OrgUsage {
  boards: number;
  members: number;
}

/** One timesheet category (V1-2, D-19): stable key, mutable label, retire
 *  never delete. `other` is always present and always active. */
export interface WorkCategory {
  key: string;
  label: string;
  active: boolean;
  /** V1-16 — the day-book cell colour, resolved server-side. One of the five
   *  validated hues in `core/work_types.CATEGORY_COLORS`, or `"slate"` for a
   *  category past the fifth (read by its label, not its colour). */
  color: string;
}

export type AttendanceMode = "every_period" | "first_period" | "twice_daily";

export interface OrgSettings {
  id: string;
  name: string;
  timezone: string;
  report_card_hour: number;
  plan: PlanTier;
  plan_status: "none" | "active" | "grace";
  plan_renews_at: string | null;
  // V1-2 — setup & onboarding
  school_code: string | null;
  address: string | null;
  state: string | null;
  board: string | null;
  /** V1-3 (S-25): the parent portal's "tell the school why" number. */
  phone: string | null;
  /** Whether parents may sign in at all. Set from the setup pack's School sheet;
   *  the guard is a live check on every parent request, so switching it off ends
   *  sessions already open rather than only blocking new ones. */
  parent_portal_enabled: boolean;
  attendance_mode: AttendanceMode;
  min_attendance_pct: number;
  homework_gap_days: number;
  /** V1-8 (`D-54`/`S-138`): keep the model-read-vs-teacher-corrected diff on
   *  locked exam captures. Default off, and asked for — no export path in v1. */
  training_data_opt_in: boolean;
  work_categories: WorkCategory[];
  /** Every feature this school's plan includes, computed server-side from
   *  `core/features.py`. The browser reads this list and never re-derives the
   *  tier map — one computation, many renderings. */
  features: string[];
  usage: OrgUsage;
}

// ---- Package tiers (D-106) ----
/** One tier, priced for THIS school. `monthly_paise` is `unit × students`,
 *  computed server-side — the wall renders the working, never a bare total. */
export interface TierQuote {
  plan: PlanTier;
  label: string;
  unit_paise_per_student: number;
  students: number;
  monthly_paise: number;
  features: string[];
  is_current: boolean;
  is_upgrade: boolean;
}

export interface PlanQuote {
  current_plan: PlanTier;
  students: number;
  currency: string;
  tiers: TierQuote[];
}

export interface UpgradeRequest {
  id: string;
  org_id: string;
  requested_plan: PlanTier;
  feature_id: string | null;
  message: string | null;
  status: "new" | "contacted" | "won" | "lost";
  created_at: string;
  requested_by_name: string | null;
  org_name?: string | null;
  current_plan?: PlanTier | null;
  students?: number | null;
  monthly_paise?: number | null;
}

/** A tier's list price. Operator-editable without a deploy (`D-106`). */
export interface PlanPrice {
  plan: PlanTier;
  amount_paise_per_student: number;
  currency: string;
  effective_from: string;
}

/** One plan assignment. Append-only — undo is a compensating row, never an
 *  edit. The amounts are SNAPSHOTS: a later list-price change never moves what
 *  this school was sold. */
export interface PlanChange {
  id: string;
  from_plan: PlanTier | null;
  to_plan: PlanTier;
  reason: string | null;
  student_count_at_change: number | null;
  unit_amount_snapshot: number | null;
  monthly_amount_snapshot: number | null;
  effective_from: string;
  expires_at: string | null;
  created_at: string;
  changed_by_name: string | null;
}

/** The operator's working note on a live negotiation. Platform-only — the
 *  school this is about can never read it. */
export interface UpgradeRequestNote {
  id: string;
  note: string | null;
  status_from: string | null;
  status_to: string | null;
  created_at: string;
  author_name: string | null;
}

export interface UpgradeRequestDetail {
  request: UpgradeRequest;
  notes: UpgradeRequestNote[];
}

export interface OrgPlan {
  quote: PlanQuote;
  open_request: UpgradeRequest | null;
  /** False for a teacher (`D-110`) — the wall then says "contact your admin"
   *  and offers no form, rather than a button that 403s. */
  can_request: boolean;
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
  plan: PlanTier;
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
  subject?: TaskSubject | null; // D-46
  outcome?: string | null; // D-46
  asked_by?: string | null; // S-106
  asked_at?: string | null;
  stale?: boolean; // D-45: open + untouched 3 weeks — grouped, never auto-closed
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
  /** D-44: done rows hidden by the 7-day window — the date filter reaches them. */
  hidden_done_count: number;
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
