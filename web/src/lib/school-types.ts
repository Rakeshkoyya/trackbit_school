// TrackBit School domain types — mirror app/schemas/{academics,students,fees}.py.

export interface AcademicYear {
  id: string;
  label: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
}

export interface Term {
  id: string;
  academic_year_id: string;
  name: string;
  start_date: string;
  end_date: string;
}

export interface Subject {
  id: string;
  name: string;
}

export interface SchoolClass {
  id: string;
  academic_year_id: string;
  name: string;
  section: string | null;
  class_teacher_member_id: string | null;
}

export type CalendarEventType = "holiday" | "exam_block" | "event" | "celebration";

export interface CalendarEvent {
  id: string;
  academic_year_id: string;
  type: CalendarEventType;
  title: string;
  start_date: string;
  end_date: string;
  affects_teaching: boolean;
  notes: string | null;
}

export interface CalendarSummary {
  academic_year_id: string;
  start_date: string;
  end_date: string;
  working_weekdays: number[];
  teaching_days: number;
  events: CalendarEvent[];
}

export interface SyllabusTopic {
  id: string;
  title: string;
  est_periods: number;
  position: number;
}

export interface SyllabusUnit {
  id: string;
  title: string;
  position: number;
  topics: SyllabusTopic[];
}

export interface PlanEntry {
  topic_id: string;
  topic_title: string;
  unit_title: string;
  week_start: string;
}

export interface Plan {
  class_subject_id: string;
  status: "draft" | "approved" | "none";
  approved_at: string | null;
  total_est_periods: number;
  entries: PlanEntry[];
}

export interface Forecast {
  class_subject_id: string;
  subject_name: string;
  class_label: string;
  status: "green" | "amber" | "red" | "none";
  total_topics: number;
  baseline_finish: string | null;
  projected_finish: string | null;
  weeks_behind: number;
}

export interface MyDayClass {
  class_subject_id: string;
  class_label: string;
  subject_name: string;
  planned_topic: string | null;
  planned_topic_id: string | null;
  logged: boolean;
  homework_set: boolean;
}

export interface HomeworkPending {
  assignment_id: string;
  class_label: string;
  subject_name: string;
  text: string;
}

export interface MyDayPeriod {
  period_no: number;
  class_subject_id: string;
  class_id: string;
  class_label: string;
  subject_name: string | null;
  planned_topic: string | null;
  planned_topic_id: string | null;
  logged: boolean;
  attendance_marked: boolean;
  roster_count: number;
  present_count: number | null;
  absent_count: number | null;
  late_count: number | null;
}

export interface MyDay {
  date: string;
  classes: MyDayClass[];
  periods: MyDayPeriod[];
  homework_pending: HomeworkPending[];
}

// ── timetable (V2-P1, SPRD2 §5.3) ────────────────────────────────────────────
export interface TimetableSlot {
  id: string;
  class_id: string;
  weekday: number;
  period_no: number;
  class_subject_id: string;
  subject_name: string | null;
  teacher_member_id: string | null;
  teacher_name: string | null;
  effective_from: string;
  effective_to: string | null;
}

export interface TimetableClash {
  weekday: number;
  period_no: number;
  teacher_member_id: string;
  teacher_name: string | null;
  class_labels: string[];
}

export interface TimetableGrid {
  class_id: string;
  class_label: string;
  weekdays: number[];
  periods_per_day: number;
  slots: TimetableSlot[];
  clashes: TimetableClash[];
}

export interface TeacherSlot {
  weekday: number;
  period_no: number;
  class_id: string;
  class_label: string;
  subject_name: string | null;
  class_subject_id: string;
}

export interface TeacherWeek {
  member_id: string;
  weekdays: number[];
  periods_per_day: number;
  slots: TeacherSlot[];
}

export interface PeriodTime {
  start: string;
  end: string;
  kind: string;
}

export interface PeriodConfig {
  academic_year_id: string;
  periods_per_day: number;
  period_times: PeriodTime[];
}

export interface TimetableImportCell {
  weekday: number;
  period_no: number;
  class_subject_id: string | null;
  subject_name: string;
  confidence: number;
}

export interface TimetableImportAnalyze {
  class_id: string;
  source: string;
  cells: TimetableImportCell[];
  unmatched: string[];
}

export interface TimetableDraft {
  class_id: string;
  enabled: boolean;
  cells: TimetableImportCell[];
  clashes: TimetableClash[];
  unresolved: string[];
  message: string;
}

export interface ComplianceRow {
  class_subject_id: string;
  class_label: string;
  subject_name: string;
  teacher_name: string | null;
  logged: boolean;
}

export interface Compliance {
  date: string;
  logged_count: number;
  total: number;
  rows: ComplianceRow[];
}

// ── sessions (M2) ───────────────────────────────────────────────────────────
export interface SessionSummary {
  id: string;
  name: string;
  weekdays: number[];
  time: string | null;
  active: boolean;
  roster_count: number;
}

export interface SessionDetail extends SessionSummary {
  students: { student_id: string; full_name: string; roll_no: string | null }[];
}

export type AttendanceStatus = "present" | "late" | "absent";

// ── per-period attendance (V2-P2, SPRD2 §5.4) ────────────────────────────────
// Exception statuses only — "present" is derived (roster minus exceptions).
export type AttendanceException = "absent" | "late";

export interface AttendanceRosterRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  status: AttendanceException | null;
  late_minutes: number | null;
}

export interface AttendanceRoster {
  class_id: string;
  class_label: string;
  period_no: number;
  date: string;
  marked: boolean;
  roster: AttendanceRosterRow[];
  present_count: number;
  absent_count: number;
  late_count: number;
}

export interface AttendanceMarkResult {
  mark_id: string;
  class_id: string;
  period_no: number;
  date: string;
  roster_count: number;
  present_count: number;
  absent_count: number;
  late_count: number;
  alerted_count: number;
}

// ── daily checks / recommendations (V2-P3, SPRD2 §5.5) ───────────────────────
export interface CheckResult {
  student_id: string;
  full_name: string;
  status: "not_done" | "note";
  note: string | null;
}

export interface DailyCheck {
  id: string;
  description: string;
  source: string;
  band_scope: "all" | "A" | "B" | "C";
  student_id: string | null;
  student_name: string | null;
  confirmed: boolean;
  results: CheckResult[];
}

export interface Checks {
  class_subject_id: string;
  date: string;
  checks: DailyCheck[];
}

export interface MeetingRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  status: AttendanceStatus | null;
  late_minutes: number | null;
  homework_done: boolean | null;
}

export interface Meeting {
  id: string;
  session_id: string;
  date: string;
  evidence_url: string | null;
  roster: MeetingRow[];
}

export interface SessionRecord {
  session_id: string;
  meeting_id: string;
  session_name: string;
  date: string;
  present: number;
  late: number;
  absent: number;
  homework_done: number;
  total: number;
  evidence_url: string | null;
}

// ── director dashboard (M4) ─────────────────────────────────────────────────
export interface DashboardAlert {
  id: string;
  type: "pace" | "compliance" | "homework";
  severity: "amber" | "red";
  title: string;
  detail: string;
  class_id: string | null;
  class_subject_id: string | null;
}

export interface HomeworkClassHealth {
  class_label: string;
  assignments: number;
  completion: number | null;
}

export interface HomeworkHealth {
  window_days: number;
  overall_completion: number | null;
  classes: HomeworkClassHealth[];
}

export interface DashboardOverview {
  academic_year_id: string | null;
  rag_green: number;
  rag_amber: number;
  rag_red: number;
  rag: Forecast[];
  fees: FeeSummary | null;
  sessions: SessionRecord[];
  homework: HomeworkHealth;
  alerts: DashboardAlert[];
}

export interface Digest {
  text: string;
  issues: string[];
  wins: string[];
}

// ── assessments & bands (M3) ────────────────────────────────────────────────
export interface SkillArea { id: string; name: string; position: number }

export type CycleType = "diagnostic" | "unit_test" | "term_exam";
export interface Cycle { id: string; term_id: string; type: CycleType; name: string; date: string }

export interface GridColumn { id: string; name: string; kind: "subject" | "skill" }
export interface GridCell { student_id: string; column_id: string; score: number; max_score: number }
export interface ScoreGrid {
  cycle_id: string;
  cycle_type: string;
  verified: boolean;
  columns: GridColumn[];
  students: { student_id: string; full_name: string }[];
  cells: GridCell[];
}

export interface BandRow {
  student_id: string;
  full_name: string;
  current_tier: string | null;
  suggested_tier: string | null;
  latest_pct: number | null;
}
export interface BandBoard { class_id: string; term_id: string | null; rows: BandRow[] }
export interface BandHistoryRow {
  id: string;
  tier: string;
  scope_skill_area_id: string | null;
  note: string | null;
  created_at: string;
}

export interface SkillProfileCycle { cycle_id: string; name: string; date: string; scores: Record<string, number> }
export interface SkillProfile { student_id: string; skills: string[]; cycles: SkillProfileCycle[] }

export interface SubjectTrend {
  subject_id: string;
  subject_name: string;
  points: { cycle_name: string; date: string; avg_pct: number }[];
  weak: boolean;
}

export interface InterventionItem { id: string; text: string; task_instance_id: string | null; done: boolean }
export interface Intervention {
  id: string;
  student_id: string;
  goal_text: string;
  target_tier: string;
  status: string;
  items: InterventionItem[];
}

export interface ClassSubject {
  id: string;
  class_id: string;
  subject_id: string;
  subject_name: string | null;
  teacher_member_id: string | null;
  periods_per_week: number;
}

export interface StudentCategory {
  id: string;
  name: string;
}

export interface Guardian {
  id: string;
  student_id: string;
  name: string;
  relation: string | null;
  phone: string;
  is_primary: boolean;
  notify_opt_out: boolean;
}

export interface StudentListItem {
  id: string;
  admission_no: string;
  full_name: string;
  class_id: string | null;
  roll_no: string | null;
  status: string;
  category_id: string | null;
}

export interface StudentDetail extends StudentListItem {
  class_label: string | null;
  category_name: string | null;
  guardians: Guardian[];
}

export interface RosterAnalyze {
  columns: string[];
  mapping: Record<string, string>;
  rows: Record<string, unknown>[];
  row_count: number;
}

export interface RosterCommitResult {
  created: number;
  skipped: number;
  errors: { row: number; reason: string }[];
}

// ── fees ──────────────────────────────────────────────────────────────────
export interface FeeTemplate {
  installment_number: number;
  label: string | null;
  amount: string;
  due_date: string | null;
}

export interface FeeStructure {
  id: string;
  class_name: string;
  category_id: string | null;
  category_name: string | null;
  academic_year_id: string;
  total_amount: string;
  num_installments: number;
  is_active: boolean;
  templates: FeeTemplate[];
}

export interface Installment {
  id: string;
  installment_number: number;
  label: string | null;
  amount: string;
  due_date: string | null;
  paid_amount: string;
  status: string;
  paid_date: string | null;
}

export interface StudentFeeListItem {
  id: string;
  student_id: string;
  student_name: string;
  class_label: string | null;
  category_name: string | null;
  academic_year_id: string;
  total_fee: string;
  discount: string;
  net_fee: string;
  opening_dues: string;
  paid: string;
  pending: string;
  status: string;
}

export interface StudentFeeDetail {
  id: string;
  student_id: string;
  student_name: string;
  class_label: string | null;
  category_name: string | null;
  academic_year_id: string;
  total_fee: string;
  discount: string;
  net_fee: string;
  opening_dues: string;
  total_payable: string;
  paid: string;
  balance: string;
  status: string;
  installments: Installment[];
}

export interface FeeTransaction {
  id: string;
  installment_id: string | null;
  amount: string;
  type: string;
  note: string | null;
  mode: string | null;
  receipt_number: string | null;
  created_at: string;
  created_by_name: string | null;
}

export interface FeeSummary {
  total_fee: string;
  collected_fee: string;
  pending_installments: number;
  overdue_amount: string;
}
