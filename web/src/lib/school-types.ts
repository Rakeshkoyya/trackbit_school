// TrackBit School domain types â€” mirror app/schemas/{academics,students,fees}.py.

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
  /** Periods this event eats, e.g. [1,2,3]. null = the whole day (V2-P7). */
  blocks_periods: number[] | null;
  notes: string | null;
}

export interface CalendarEventInput {
  academic_year_id: string;
  type: CalendarEventType;
  title: string;
  start_date: string;
  end_date: string;
  affects_teaching?: boolean;
  blocks_periods?: number[] | null;
}

export interface ExamPortion {
  id: string;
  exam_event_id: string;
  class_subject_id: string;
  upto_topic_id: string;
}

/** short (won't fit) | tight (manageable) | fits (perfect) | surplus (spare days)
 *  | no_portion | unallocated */
export type ExamFitVerdict = "short" | "tight" | "fits" | "surplus" | "no_portion" | "unallocated";

export interface ExamFitSubject {
  class_subject_id: string;
  subject_name: string;
  verdict: ExamFitVerdict;
  required_periods: number;
  capacity_periods: number;
  unsized_topics: number;
}

export interface ExamFitExam {
  exam_event_id: string;
  title: string;
  start_date: string;
  end_date: string;
  days_to_exam: number;
  gap_start: string;
  gap_end: string;
  teaching_days_in_gap: number;
  subjects: ExamFitSubject[];
}

export interface ExamFit {
  class_id: string;
  exams: ExamFitExam[];
}

// â”€â”€ computed week/day schedule (V2-P12) â€” never stored â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export interface DaySlot {
  period_no: number;
  class_subject_id: string;
  subject_name: string;
  teacher_name: string | null;
  topic_id: string | null;
  topic_title: string | null;
  unit_title: string | null;
  /** actual = logged Â· planned = projected from remaining syllabus Â· blocked Â· past */
  state: "actual" | "planned" | "blocked" | "past";
}

export interface DaySchedule {
  date: string;
  weekday: number;
  blocked: boolean;
  slots: DaySlot[];
}

export interface WeekSchedule {
  class_id: string;
  class_label: string;
  week_start: string;
  periods_per_day: number;
  days: DaySchedule[];
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
  /** null = not sized yet, so not scheduled. Distinct from 1. */
  est_periods: number | null;
  position: number;
}

export interface SyllabusUnit {
  id: string;
  title: string;
  position: number;
  /** null = not scoped to a term (whole-year chapter). */
  term_id: string | null;
  topics: SyllabusTopic[];
}

export interface PlanEntry {
  topic_id: string;
  topic_title: string;
  unit_title: string;
  week_start: string;
}

/** One planning window. term_id === null is the untermed bucket. */
export interface PlanTerm {
  term_id: string | null;
  name: string;
  start_date: string;
  end_date: string;
  topic_count: number;
  unestimated_topics: number;
  approved: boolean;
}

export interface Plan {
  class_subject_id: string;
  status: "draft" | "partial" | "approved" | "none";
  approved_at: string | null;
  total_est_periods: number;
  unestimated_topics: number;
  terms: PlanTerm[];
  entries: PlanEntry[];
}

export interface Forecast {
  class_subject_id: string;
  subject_name: string;
  class_label: string;
  /** `unplanned` = chapters unsized; `unallocated` = 0 periods/week on the class. */
  status: "green" | "amber" | "red" | "none" | "unplanned" | "unallocated";
  total_topics: number;
  baseline_finish: string | null;
  projected_finish: string | null;
  weeks_behind: number;
  unestimated_topics: number;
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
  period_id: string | null;
  status: "held" | "not_held";
  opened: boolean;
  closed: boolean;
  attendance_marked: boolean;
  roster_count: number;
  present_count: number | null;
  absent_count: number | null;
  late_count: number | null;
  homework_set: boolean;
}

export interface MyDay {
  date: string;
  classes: MyDayClass[];
  periods: MyDayPeriod[];
  homework_pending: HomeworkPending[];
}

// â”€â”€ timetable (V2-P1, SPRD2 Â§5.3) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

export interface TimetableGenerateIssue {
  class_label: string;
  subject_name: string;
  detail: string;
}

/** Whole-school deterministic generation (POST /timetable/generate). */
export interface TimetableGenerate {
  academic_year_id: string;
  classes: number;
  cells: {
    class_id: string;
    class_label: string;
    weekday: number;
    period_no: number;
    class_subject_id: string;
    subject_name: string;
  }[];
  unplaced: TimetableGenerateIssue[];
  skipped: TimetableGenerateIssue[];
  applied: boolean;
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
export type SessionKind = "study" | "homework" | "activity";

export interface SessionSummary {
  id: string;
  name: string;
  weekdays: number[];
  time: string | null;
  end_time: string | null;
  kind: SessionKind;
  hostellers_only: boolean;
  active: boolean;
  roster_count: number;
  class_labels: string[];
  teacher_name: string | null;
  owner_member_id: string | null;
}

export interface SessionDetail extends SessionSummary {
  students: { student_id: string; full_name: string; roll_no: string | null; explicit: boolean }[];
  class_ids: string[];
}

// Write shape for create/update (HS).
export interface SessionWrite {
  name: string;
  weekdays: number[];
  time?: string | null;
  end_time?: string | null;
  kind?: SessionKind;
  student_ids?: string[];
  class_ids?: string[];
  hostellers_only?: boolean;
  owner_member_id?: string | null;
}

export type AttendanceStatus = "present" | "late" | "absent";

// â”€â”€ per-period attendance (V2-P2, SPRD2 Â§5.4) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Exception statuses only â€” "present" is derived (roster minus exceptions).
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

// â”€â”€ daily checks / recommendations (V2-P3, SPRD2 Â§5.5) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

// â”€â”€ daily report + student timeline (V2-P4, SPRD2 Â§5.6/Â§5.7) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export interface ReportSection {
  heading: string;
  lines: string[];
}

export interface ReportHighlights {
  risks: string[];
  ambiguities: string[];
  wins: string[];
}

export interface DailyReport {
  id: string;
  for_date: string;
  generated_at: string;
  status: string;
  content_md: string;
  highlights: ReportHighlights;
  sections: ReportSection[];
}

export interface TimelinePeriod {
  period_no: number;
  class_subject_id: string;
  subject_name: string | null;
  topic: string | null;
  attendance: "present" | "late" | "absent" | "unmarked";
  late_minutes: number | null;
  checks_flagged: string[];
  homework: string[];
  gap: boolean;
}

export interface TimelineSession {
  session_name: string;
  kind: SessionKind;
  status: string;
  homework_done: boolean | null;
  log_note: string | null;
}

export interface StudentTimeline {
  student_id: string;
  full_name: string;
  class_label: string | null;
  date: string;
  periods: TimelinePeriod[];
  sessions: TimelineSession[];
}

// â”€â”€ setup wizard + plan generation (V2-P5, SPRD2 Â§5.1/Â§5.2) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export interface WizardProgress {
  has_year: boolean;
  terms: number;
  has_timings: boolean;
  classes: number;
  subjects: number;
  class_subjects: number;
  syllabus_topics: number;
  teachers: number;
  students: number;
  timetable_slots: number;
  plans_total: number;
  plans_approved: number;
  calendar_events: number;
  exams: number;
  exam_portions: number;
  /** Capture gaps that would make the generated plan wrong (shown on the last step). */
  gaps: string[];
}

export interface WizardState {
  steps: WizardStep[];
  current_step: number;
  total_steps: number;
  status: string;
  payload: Record<string, unknown>;
  progress: WizardProgress;
}

export interface PlanViolation {
  code: "capacity" | "coverage" | "ordering" | "teacher_load" | "exam_coverage" | "unsized";
  message: string;
}

export interface PlanGenerateResult {
  fits: boolean;
  violations: PlanViolation[];
  plan: Plan;
}

export interface PlanComment {
  id: string;
  class_subject_id: string;
  topic_id: string | null;
  author_name: string | null;
  text: string;
  status: string;
  created_at: string;
}

export interface MeetingRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  class_label: string | null;
  status: AttendanceStatus | null;
  late_minutes: number | null;
  homework_done: boolean | null;
  log_count: number;
  log_note: string | null;
  media_count: number;
}

export interface SessionMediaItem {
  id: string;
  kind: "photo" | "video";
  url: string;
  content_type: string;
  caption: string | null;
  student_id: string | null;
  created_at: string;
}

// ── per-student session capture (HS-2) ───────────────────────────────────────
export interface StudentLogEntry {
  section: string;
  note: string;
}

export interface SessionStudentCard {
  meeting_id: string;
  date: string;
  session_id: string;
  session_name: string;
  kind: SessionKind;
  student_id: string;
  full_name: string;
  roll_no: string | null;
  class_label: string | null;
  status: AttendanceStatus | null;
  late_minutes: number | null;
  homework_done: boolean | null;
  homework: HomeworkBoardItem[];
  logs: StudentLogEntry[];
  media: SessionMediaItem[];
}

export interface MediaPresign {
  key: string;
  upload_url: string | null;
}

export interface Meeting {
  id: string;
  session_id: string;
  date: string;
  kind: SessionKind;
  evidence_url: string | null;
  roster: MeetingRow[];
  media: SessionMediaItem[];
}

// ── homework board (HS) ──────────────────────────────────────────────────────
export interface HomeworkBoardItem {
  assignment_id: string;
  subject: string;
  text: string;
  assigned_on: string;
  due_date: string | null;
  personal: boolean;
}

export interface HomeworkBoardRow {
  student_id: string;
  full_name: string;
  class_label: string | null;
  homework_done: boolean | null;
  items: HomeworkBoardItem[];
}

export interface HomeworkBoard {
  meeting_id: string;
  date: string;
  rows: HomeworkBoardRow[];
}

export interface SessionRecord {
  session_id: string;
  meeting_id: string;
  session_name: string;
  date: string;
  kind: SessionKind;
  media_count: number;
  present: number;
  late: number;
  absent: number;
  homework_done: number;
  total: number;
  evidence_url: string | null;
}

// â”€â”€ director dashboard (M4) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

// â”€â”€ assessments & bands (M3) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export interface SkillArea { id: string; name: string; position: number }

export type CycleType =
  | "diagnostic" | "unit_test" | "term_exam" | "daily_test"
  | "chapter_test" | "class_test" | "slip_test" | "objective" | "band_test";
export interface Cycle {
  id: string;
  term_id: string;
  type: CycleType;
  name: string;
  date: string;
  class_id: string | null;
  subject_id: string | null;
  topic: string | null;
  total_marks: number | null;
  student_ids: string[] | null;
}

// ── exams (SC-5) — the scores screen's exam-first surface ────────────────────
export interface ExamSummary {
  id: string;
  type: CycleType;
  name: string;
  date: string;
  class_id: string | null;
  class_label: string | null;
  subject_id: string | null;
  subject_name: string | null;
  topic: string | null;
  total_marks: number | null;
  few_students: boolean;
  roster_count: number;
  scored_count: number;
  avg_pct: number | null;
  verified: boolean;
  created_by_name: string | null;
  page_count: number;
  /** Org-wide / diagnostic cycles open in the score grid, not the exam page. */
  grid_only: boolean;
}

export interface ExamRosterRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  score: number | null;
  max_score: number | null;
}

export interface ExamDetail {
  id: string;
  type: CycleType;
  name: string;
  date: string;
  class_id: string;
  class_label: string;
  subject_id: string;
  subject_name: string;
  topic: string | null;
  total_marks: number | null;
  student_ids: string[] | null;
  verified: boolean;
  avg_pct: number | null;
  rows: ExamRosterRow[];
  pages: CapturePage[];
}

export interface ExamSaveBody {
  cycle_id?: string;
  class_id: string;
  subject_id: string;
  type: string;
  name: string;
  date: string;
  topic?: string | null;
  total_marks: number;
  student_ids?: string[] | null;
  capture_id?: string | null;
  rows: { student_id: string; score: number; max_score?: number | null }[];
}

export interface BandConfig { a_min: number; b_min: number }
export interface BandCategorizeResult {
  applied: number;
  counts: Record<string, number>; // A/B/C/no_score
}

// ── photo score capture (SC-2) ───────────────────────────────────────────────
export interface CapturePage { id: string; page_no: number; url: string; content_type: string }
export interface CaptureParsedRow {
  name_text: string;
  roll_text: string | null;
  score: number;
  max_score: number | null;
  student_id: string | null;
  confidence: "roll" | "exact" | "fuzzy" | null;
  candidates: { student_id: string; full_name: string }[];
}
export interface CaptureRosterRow { student_id: string; full_name: string; roll_no: string | null }
/** The AI-read exam header — a form prefill, never persisted as-is. */
export interface CaptureParsedMeta {
  title: string | null;
  subject_text: string | null;
  subject_id: string | null;
  total_marks: number | null;
  topic: string | null;
  date: string | null;
}
export interface Capture {
  id: string;
  cycle_id: string | null;
  class_id: string;
  subject_id: string | null;
  skill_area_id: string | null;
  status: "uploaded" | "parsed" | "confirmed" | "discarded";
  parse_error: string | null;
  pages: CapturePage[];
  parsed_rows: CaptureParsedRow[] | null;
  parsed_meta: CaptureParsedMeta | null;
  student_ids: string[] | null;
  roster: CaptureRosterRow[];
  created_at: string;
}
export interface CaptureSummary {
  id: string;
  cycle_id: string | null;
  class_id: string;
  subject_id: string | null;
  skill_area_id: string | null;
  status: string;
  page_count: number;
  created_at: string;
}

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

// ── class analysis (SC-4) ────────────────────────────────────────────────────
export interface AnalysisCyclePoint {
  cycle_id: string;
  name: string;
  date: string;
  type: string;
  avg_pct: number | null;
  subjects: { subject_id: string; name: string; avg_pct: number | null }[];
}
export interface AnalysisMover {
  student_id: string;
  full_name: string;
  latest_pct: number;
  prev_pct: number;
  delta: number;
}
export interface ClassAnalysis {
  class_id: string;
  band_counts: Record<string, number>;
  cycles: AnalysisCyclePoint[];
  movers: AnalysisMover[];
  histogram: { bucket: string; count: number }[];
  latest_cycle_name: string | null;
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

export interface AllocationRow {
  class_subject_id: string;
  subject_name: string;
  teacher_name: string | null;
  periods_per_week: number;
  /** Î£ est_periods of this subject's sized syllabus topics. */
  syllabus_periods: number;
  /** Proportional share of capacity by syllabus size â€” a proposal, never applied. */
  suggested: number;
}

export interface ClassAllocation {
  class_id: string;
  class_label: string;
  /** working weekdays Ã— periods/day. */
  capacity: number;
  allocated: number;
  rows: AllocationRow[];
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

/** The roster importer shares the one ingest envelope (see AnalyzeResult) â€” same
 *  gap-question flow as staff and syllabus. It used to return only the first four
 *  fields, which crashed the import panel when it read `.length` on the rest. */
export type RosterAnalyze = AnalyzeResult;

export interface RosterCommitResult {
  created: number;
  skipped: number;
  errors: { row: number; reason: string }[];
}

// â”€â”€ fees â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


// â”€â”€ document ingestion (V2-P7, SPRD2 Â§5.1) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
/** A gap a deterministic validator found; the model only phrased the question. */
export interface GapQuestion {
  field: string;
  label: string;
  question: string;
  options: string[];
  skippable: boolean;
  source: string;
}

export interface AnalyzeResult {
  columns: string[];
  mapping: Record<string, string>;
  rows: Record<string, unknown>[];
  row_count: number;
  unmapped_columns: string[];
  missing_required: string[];
  low_confidence: string[];
  questions: GapQuestion[];
  source: string;
}

export interface StaffCommitResult {
  created: { name: string; username: string; password: string; user_id: string }[];
  created_count: number;
  skipped: number;
  assigned: number;
  errors: { row?: number; reason?: string }[];
  /** Assignment hints we refused to guess at. */
  unresolved: { teacher: string; tokens: string[] }[];
}

export interface SyllabusTopicDraft {
  title: string;
  /** null when the document didn't state a number â€” imported unsized, not as 1. */
  est_periods: number | null;
}

export interface SyllabusUnitDraft {
  title: string;
  /** Term name as written in the sheet; resolved to a term on commit. */
  term?: string | null;
  topics: SyllabusTopicDraft[];
}

export interface SyllabusAnalyzeResult extends AnalyzeResult {
  mode: "grid" | "text";
  units: SyllabusUnitDraft[];
  unit_count: number;
  topic_count: number;
}

export interface SyllabusCommitResult {
  units_created: number;
  topics_created: number;
  replaced: boolean;
  unsized_topics: number;
  /** Term names in the sheet that matched no term of this class's academic year. */
  unresolved_terms: string[];
}

export interface TopicProgressRow {
  topic_id: string;
  topic_title: string;
  unit_title: string;
  /** null = not sized yet, so the chapter is not scheduled. */
  est_periods: number | null;
  status: "done" | "in_progress" | "pending";
}

export interface WizardStep {
  key: string;
  title: string;
  index: number;
  complete: boolean;
}

// â”€â”€ post-setup read models (V2-P10) â€” derived on read, never cached â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export interface YearFacts {
  academic_year_id: string;
  label: string;
  start_date: string;
  end_date: string;
  periods_per_day: number;
  terms: number;
  exams: number;
  exam_portions: number;
  /** Exams nobody mapped to a syllabus portion: configured but inert. */
  exams_without_portions: number;
}

/** `unplanned`/`unallocated` are not RAG colours: unsized chapters or 0 periods/week
 * mean no finish date exists. */
export type Rag = "green" | "none" | "amber" | "red" | "unplanned" | "unallocated";

export interface ClassRow {
  class_id: string;
  label: string;
  students: number;
  subjects: number;
  subjects_without_teacher: number;
  subjects_without_syllabus: number;
  timetable_slots: number;
  plans_approved: number;
  plans_total: number;
  worst_forecast: Rag;
}

export interface SchoolOverview {
  year: YearFacts;
  teachers: number;
  students: number;
  classes: ClassRow[];
}

export interface SubjectRow {
  class_subject_id: string;
  subject_name: string;
  teacher_member_id: string | null;
  teacher_name: string | null;
  periods_per_week: number;
  timetabled_periods: number;
  /** The entered budget and the grid disagree â€” every plan date is off. */
  periods_mismatch: boolean;
  chapters: number;
  topics: number;
  est_periods: number;
  topics_taught: number;
  plan_status: "none" | "draft" | "partial" | "approved";
  plan_approved_at: string | null;
  forecast: Rag;
  weeks_behind: number | null;
  baseline_finish: string | null;
  projected_finish: string | null;
}

export interface ClassOverview {
  class_id: string;
  label: string;
  academic_year_id: string;
  year_label: string;
  students: number;
  class_teacher_name: string | null;
  subjects: SubjectRow[];
}

export interface TeacherLoadRow {
  member_id: string;
  name: string;
  periods_per_week: number;
  classes: number;
  subjects: number;
}

// â”€â”€ period detail page (V2-P6 card) â€” the teacher's per-class capture surface â”€
/** One topic actually taught this period — a period can hold several, and the
 *  same topic can continue across days (partial → full). */
export interface PeriodLog {
  id: string;
  topic_id: string | null;
  topic_title: string | null;
  coverage: string;
  note: string | null;
}

export interface PeriodPlan {
  planned_topic_id: string | null;
  planned_topic_title: string | null;
  planned_unit_title: string | null;
  logged_topic_id: string | null;
  logged_coverage: string | null;
  logged: PeriodLog[];
  progress: TopicProgressRow[];
}

export interface PeriodHomework {
  id: string;
  text: string;
  /** Set when this is a per-student addition rather than class-wide. */
  student_id: string | null;
  due_date: string | null;
}

export interface PeriodCard {
  class_id: string;
  class_label: string;
  period_no: number;
  date: string;
  class_subject_id: string | null;
  subject_name: string | null;
  period_id: string | null;
  status: "held" | "not_held";
  not_held_reason: string | null;
  opened: boolean;
  closed: boolean;
  attendance_marked: boolean;
  roster: AttendanceRosterRow[];
  roster_count: number;
  present_count: number | null;
  absent_count: number | null;
  late_count: number | null;
  plan: PeriodPlan;
  homework: PeriodHomework[];
}

// â”€â”€ deep log â€” optional lesson observations (exception-only, P1v2) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export interface ObservationStudent {
  student_id: string;
  full_name: string;
  rating: "excellent" | "needs_work";
  note: string | null;
}

export interface ObservationConcept {
  concept: string | null;
  students: ObservationStudent[];
}

export interface ObservationSection {
  section: string;
  period_id: string | null;
  concepts: ObservationConcept[];
}

export interface Observations {
  class_subject_id: string;
  date: string;
  sections: ObservationSection[];
}

// â”€â”€ student growth report (staff-only; teachers see their own students) â”€â”€â”€â”€â”€â”€
export interface GrowthAttendance {
  marked_periods: number;
  present: number;
  absent: number;
  late: number;
  pct: number | null;
}

export interface GrowthTopic {
  topic_id: string;
  title: string;
  status: "done" | "in_progress" | "pending";
  taught_on: string | null;
  student_attendance: "present" | "absent" | "late" | null;
}

export interface GrowthChapter {
  unit_id: string;
  title: string;
  topics_total: number;
  topics_taught: number;
  topics_missed: number;
  topics: GrowthTopic[];
}

export interface GrowthObservation {
  date: string;
  section: string;
  concept: string | null;
  rating: string;
  note: string | null;
}

export interface GrowthScore {
  cycle_name: string;
  date: string;
  score: number;
  max_score: number;
}

export interface GrowthSubject {
  class_subject_id: string;
  subject_name: string;
  teacher_name: string | null;
  attendance: GrowthAttendance;
  chapters: GrowthChapter[];
  homework_assigned: number;
  homework_personal: number;
  checks_flagged: number;
  observations: GrowthObservation[];
  scores: GrowthScore[];
}

export interface GrowthSkill {
  skill_area: string;
  score: number;
  max_score: number;
  cycle_name: string;
}

export interface GrowthBandEntry {
  tier: string;
  set_on: string;
  note: string | null;
}

export interface StudentGrowth {
  student_id: string;
  full_name: string;
  class_label: string | null;
  band: string | null;
  band_history: GrowthBandEntry[];
  attendance: GrowthAttendance;
  subjects: GrowthSubject[];
  skills: GrowthSkill[];
  growth_areas: string[];
}
