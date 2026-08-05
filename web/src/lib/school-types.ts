// TrackBit School domain types â€” mirror app/schemas/{academics,students,fees}.py.

export interface AcademicYear {
  id: string;
  label: string;
  start_date: string;
  end_date: string;
  /** Mid-year adoption: when TrackBit started recording (null = start_date).
   *  Before this date = no-data, never a warning. */
  tracking_start_date: string | null;
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
  /** Ended before the school adopted TrackBit — never planned, never warned. */
  pre_tracking: boolean;
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
  /** `unplanned` = NOTHING scheduled yet; `unallocated` = 0 periods/week.
   *  A partially planned subject gets a real RAG over its planned portion,
   *  with `unestimated_topics` as info (chapters still to be sized). */
  status: "green" | "amber" | "red" | "none" | "unplanned" | "unallocated";
  total_topics: number;
  baseline_finish: string | null;
  projected_finish: string | null;
  weeks_behind: number;
  unestimated_topics: number;
  planned_topics: number;
  /** The term running today has chapters but none scheduled. */
  current_term_unplanned: boolean;
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
  /** V1-3 (D-01): false when the org's mode doesn't take attendance this
   *  period — the card stays, only the attendance ask moves.
   *
   *  DYNAMIC in a once-per-day school (founder, 2026-08-05): true on every
   *  period until the day's register is taken, then only on the one holding it.
   *  Read it together with `day_attendance_taken`. */
  marks_attendance: boolean;
  /** Once-per-day schools only (null elsewhere): has this class's day been
   *  captured? Separates "not asked because it is done" from "not asked because
   *  this period never marks" — two different things to tell a teacher. */
  day_attendance_taken: boolean | null;
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
  // D-41/D-43: rail follow-ups (last 3 working days) ∪ due today, capped at 5.
  tasks: import("./types").Task[];
  // "n older tasks →" — the window is never silent (D-43).
  older_task_count: number;
  // V1-7 (S-145): the school locked today, or some of its periods. Those period
  // cards are GONE from `periods` rather than sitting there unlogged — leaving
  // them would invent work on a holiday and make the capture rate lie.
  day_closed: boolean;
  locked_periods: number[];
  lock_reason: string | null;
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
  /** One register a day: the sheet hides its period picker, because choosing a
   *  period is a question with no meaning when the register is the day's. */
  once_per_day?: boolean;
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
  /** 2-3 sentence headline the dashboard leads with (AI-written when a key is
   * configured, deterministic otherwise — `summary_source` says which). */
  summary: string;
  summary_source: string;
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
  homework: TimelineHomework[];
  gap: boolean;
}

/** One homework as it applies to THIS student (HW-1). */
export interface TimelineHomework {
  assignment_id: string;
  text: string;
  status: HomeworkStatus;
  due_date: string | null;
  personal: boolean;
}

export interface TimelineSession {
  session_name: string;
  kind: SessionKind;
  status: string;
  homework_done: boolean | null;
  log_note: string | null;
}

/** D-46: a follow-up raised about this student — staff-only, never projected
 *  to the parent portal. */
export interface TimelineFollowup {
  task_id: string;
  title: string;
  status: string;
  assignee_name: string | null;
  outcome: string | null;
}

export interface StudentTimeline {
  student_id: string;
  full_name: string;
  class_label: string | null;
  date: string;
  periods: TimelinePeriod[];
  sessions: TimelineSession[];
  followups: TimelineFollowup[];
  /** THE day status (V1-0d) — computed once server-side; render, never re-derive. */
  day_status: "present" | "partial" | "absent" | "not_marked" | "no_school";
  marked_periods: number;
  absent_periods: number;
  late_periods: number;
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
  /** `staff` (SF-1) resolves on its own screen rather than becoming a task. */
  type: "pace" | "compliance" | "homework" | "staff";
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

export interface AttendanceDay {
  date: string;
  periods_marked: number;
  roster: number;          // student-periods covered by those marked periods
  absent: number;
  late: number;
  present_pct: number | null;
}

export interface AttendanceClassToday {
  class_label: string;
  periods_marked: number;
  periods_expected: number;
  absent: number;
  late: number;
  present_pct: number | null;
}

export interface AttendancePulse {
  window_days: number;
  today: AttendanceDay | null;
  days: AttendanceDay[];   // oldest → newest, marked days only
  classes_today: AttendanceClassToday[];
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
  attendance: AttendancePulse;
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

// ── exams (SC-5 + V1-8) — the scores screen's exam-first surface ─────────────
/** V1-8 `S-114`: the two buckets that are NEVER added together. Trajectory is
 *  read from `minor`, standing from `major`. There is no third value and no
 *  blended figure anywhere in the client. */
export type ExamScale = "minor" | "major";

/** V1-8 `D-55`: the school's own word for a kind of exam — *CET*, *pre-board*.
 *  `system_type` is what the code branches on and is never rendered. */
export interface ExamType {
  id: string;
  name: string;
  system_type: CycleType;
  scale: ExamScale;
  position: number;
  active: boolean;
  exams: number;
}

/** V1-8 `S-118`: a percentage that cannot be shown without its denominator.
 *  Render `sentence` — it already carries "across 5 of the 9 tests". */
export interface ScaleFigure {
  scale: ExamScale;
  label: string;
  purpose: string;
  avg_pct: number | null;
  tests_taken: number;
  tests_held: number;
  sentence: string;
}

export interface QuestionMark { q: string; score: number; max: number | null }

export interface ExamSummary {
  id: string;
  type: CycleType;
  exam_type_id: string | null;
  exam_type_name: string | null;
  /** The school's word, falling back to the system kind's label. Display this. */
  type_label: string;
  scale: ExamScale;
  locked: boolean;
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
  /** V1-8: read off the marked script; absent for a hand-typed exam. */
  question_marks: QuestionMark[] | null;
  /** `S-119`: this child's own paper, one tap away. */
  paper_url: string | null;
  /** `S-116`: the per-question marks don't sum to the total written on the
   *  paper. About the TEACHER's paper — never a claim about the child. */
  sum_mismatch: number | null;
}

export interface ExamLockRow {
  action: "lock" | "unlock";
  reason: string | null;
  by_name: string | null;
  at: string;
}

export interface ExamDetail {
  id: string;
  type: CycleType;
  exam_type_id: string | null;
  exam_type_name: string | null;
  type_label: string;
  scale: ExamScale;
  exam_event_id: string | null;
  exam_event_name: string | null;
  locked: boolean;
  locked_at: string | null;
  locked_by_name: string | null;
  lock_history: ExamLockRow[];
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
  exam_type_id?: string | null;
  exam_event_id?: string | null;
  rows: {
    student_id: string;
    score: number;
    max_score?: number | null;
    question_marks?: QuestionMark[] | null;
    /** V1-8 `S-119`: files this photographed script against this child, on
     *  save — i.e. once a human has confirmed the grid, never at parse time. */
    page_id?: string | null;
  }[];
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
  /** V1-8: null on an unreadable page — kept as a row for the teacher to map
   *  by hand (`D-80` step 5), never discarded. */
  score: number | null;
  max_score: number | null;
  student_id: string | null;
  confidence: "roll" | "exact" | "fuzzy" | null;
  candidates: { student_id: string; full_name: string }[];
  page_no: number | null;
  page_id: string | null;
  unreadable: boolean;
  question_marks: QuestionMark[] | null;
  sum_mismatch: number | null;
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
  /** V1-8 `D-80`: `scripts` = a photo per student's marked paper (the primary
   *  exam flow); `register` = one page listing many students (SC-1). */
  mode: "register" | "scripts";
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
  /** Set by the year-wide read (V1-2, S-77). */
  class_label?: string | null;
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
  /** V1-2 (D-13): the parent's portal password; null = parent cannot log in. */
  date_of_birth: string | null;
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
  /** V1-2 (D-13): DOB values that would not parse — reported, never guessed. */
  unresolved: { row: number; field: string; value: string; student: string; reason: string }[];
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
  /** V1-6 (S-51): weighted — a partly-covered topic is half, everywhere. */
  topics_taught: number;
  /** Computed server-side against the whole syllabus. Do not divide in the browser. */
  coverage_pct: number | null;
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

export interface PeriodDayEvent {
  id: string;
  title: string;
  type: "holiday" | "exam_block" | "event" | "celebration";
  affects_teaching: boolean;
  blocks_periods: number[] | null;
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
  /** V1-7 (S-147): the reason POINTS AT the approved event, so "what did Diwali
   *  cost us in periods?" is a query rather than forty spellings of free text. */
  not_held_event_id: string | null;
  /** The approved events running on this date — the picker behind "not held,
   *  because". Empty on an ordinary day, and she types instead. */
  day_events: PeriodDayEvent[];
  /** V1-7 (S-145/S-146): the ADMIN locked this period school-wide, so the
   *  teacher is never asked. Recording her own block too would subtract the
   *  period from capacity twice. */
  locked: boolean;
  lock_reason: string | null;
  opened: boolean;
  closed: boolean;
  attendance_marked: boolean;
  /** V1-3 (D-01/Q-02a): the mode may not mark this period; topic/homework/
   *  checks are unaffected. Dynamic in a once-per-day school — see
   *  `day_attendance_taken`. */
  marks_attendance: boolean;
  day_attendance_taken: boolean | null;
  roster: AttendanceRosterRow[];
  roster_count: number;
  present_count: number | null;
  absent_count: number | null;
  late_count: number | null;
  plan: PeriodPlan;
  homework: PeriodHomework[];
}

// ── My Class — the class teacher's area (V1-3, D-03) ────────────────────────
export interface MyClassSummary {
  class_id: string;
  class_label: string;
  roster: number;
  is_mine: boolean;
}

export interface MyClassList {
  classes: MyClassSummary[];
}

/** THE day status, computed server-side (`classify_marked_day`) — paint it,
 *  never re-derive it. `not_marked` is a gap in the record: neutral, never red. */
export type DayCellStatus =
  | "present" | "partial" | "absent" | "left_after_lunch" | "not_marked" | "no_school";

export interface RegisterCell {
  date: string;
  status: DayCellStatus;
  late: boolean;
  /** A reason on the exception, or a covering informed-absence note (D-86). */
  has_reason: boolean;
}

export interface RegisterRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  cells: RegisterCell[];
  present_days: number;
  marked_days: number;
}

/** One column's total — the figure a paper register carries in its bottom
 *  margin. `pct`/`marked` are null/false on a day nobody marked: the one number
 *  this grid must never invent is a day it has no record of. */
export interface RegisterDayTally {
  date: string;
  marked: boolean;
  present: number;
  absent: number;
  counted: number;
  pct: number | null;
}

export interface ClassRegister {
  class_id: string;
  class_label: string;
  month: string;
  mode: "every_period" | "first_period" | "twice_daily";
  /** A once-per-day school's register is one column per DAY, so the grid needs
   *  no period dimension and the capture sheet shows no period picker. */
  once_per_day: boolean;
  days: string[];
  school_days: number;
  rows: RegisterRow[];
  day_totals: RegisterDayTally[];
  marked_days: number;
  pct: number | null;
  headline: string;
}

// ── absence reasons + informed absence (V1-3, D-02/S-24) ────────────────────
export interface AbsenceNote {
  id: string;
  student_id: string;
  from_date: string;
  to_date: string;
  reason_code: string | null;
  note: string | null;
  source: "parent_call" | "office" | "teacher";
  created_by_name: string | null;
  created_at: string | null;
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
  /** Fully covered only — an in-progress topic is its own count (V1-0d). */
  topics_taught: number;
  topics_in_progress: number;
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
  /** V1-8: a slip test and a term exam are different questions — never one
   *  series through both (`S-114`). */
  cycle_id: string | null;
  type: CycleType | null;
  type_label: string | null;
  scale: ExamScale;
  paper_url: string | null;
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
  /** The two never-pooled averages, each carrying its denominator (`S-118`). */
  score_figures: ScaleFigure[];
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
  /** V1-7 (S-133): the full date belongs on the student's OWN record. Shared
   *  surfaces get the day only — never the age, never a DOB on a class list. */
  date_of_birth: string | null;
  band: string | null;
  band_history: GrowthBandEntry[];
  attendance: GrowthAttendance;
  subjects: GrowthSubject[];
  skills: GrowthSkill[];
  growth_areas: string[];
  /** The mirror of `growth_areas` — what this student is visibly good at. */
  strengths: string[];
}

// ── SF-1: staff attendance, timesheet, leave ─────────────────────────────────

/** V1-4 (D-04). `late` is PRESENT — a flag to be seen, never a deduction (S-19). */
export type StaffDayStatus = "present" | "absent" | "half_day" | "late";

export interface StaffRosterRow {
  member_id: string;
  name: string;
  role: string;
  /** Derived — true unless an absence row exists. `late` is still present. */
  present: boolean;
  status: StaffDayStatus;
  /** Which half a half_day was away — what tells the cover board which periods. */
  portion: "am" | "pm" | null;
  /** An approved leave covers this date, so the sheet opens them unticked. */
  on_leave: boolean;
  leave_reason: string | null;
  note: string | null;
}

export interface StaffAttendance {
  date: string;
  /** False = nobody has taken attendance yet, which is not the same as a full house. */
  marked: boolean;
  marked_at: string | null;
  marked_by: string | null;
  roster: StaffRosterRow[];
  total: number;
  present_count: number;
  absent_count: number;
  half_day_count: number;
  late_count: number;
  /** Days-present value of the day, half-days as 0.5 — what the month sums. */
  present_days: number;
}

export interface StaffMark {
  member_id: string;
  status: "absent" | "half_day" | "late";
  portion?: "am" | "pm" | null;
  note?: string | null;
}

/** D-78 — days worked out of working days. **No money on this row, ever.** */
export interface StaffMonthRow {
  member_id: string;
  name: string;
  role: string;
  working_days: number;
  days_marked: number;
  /** S-34: a day nobody marked is its own count, never an absence. */
  days_not_marked: number;
  days_present: number;
  days_absent: number;
  half_days: number;
  lates: number;
  leave_days: number;
  leave_remaining: number;
}

export interface StaffMonth {
  month: string;
  start_date: string;
  /** Clamped to today — a month in progress is not a month of absentees. */
  end_date: string;
  working_days: number;
  days_marked: number;
  rows: StaffMonthRow[];
}

/** 'class' = the timetable owns it (locked) · 'cover' = a live substitution
 *  (locked, Q-37) · 'work' = recorded · 'free' = open · 'away' = absent or on
 *  approved leave that day (S-72 — never rendered as free). */
export type TimesheetSlotKind = "class" | "cover" | "work" | "free" | "away";

export interface TimesheetSlot {
  period_no: number;
  start: string;
  end: string;
  kind: TimesheetSlotKind;
  class_label: string | null;
  subject_name: string | null;
  work_type: string | null;
  work_label: string | null;
  note: string | null;
  /** S-75 — what she usually records here. The picker opens on it and writes
   *  nothing; no row exists that a human did not put there. */
  suggested_work_type: string | null;
  suggested_work_label: string | null;
}

export interface TimesheetBreak {
  after_period_no: number;
  label: string;
  start: string;
  end: string;
}

export interface TimesheetDay {
  date: string;
  weekday: number;
  is_working_day: boolean;
  slots: TimesheetSlot[];
  teaching_count: number;
  work_count: number;
  free_count: number;
  cover_count: number;
  breaks: TimesheetBreak[];
  /** S-68 — hostel blocks she runs, reported beside the periods, never in them. */
  evening_labels: string[];
}

/** D-18/S-64 — month = shape, week = edit, day = do. One cell per DAY. */
export type TimesheetDayState = "working" | "off" | "holiday" | "leave" | "away" | "future";

export interface TimesheetMonthDay {
  date: string;
  weekday: number;
  state: TimesheetDayState;
  teaching: number;
  work: number;
  cover: number;
  free: number;
  label: string | null;
}

export interface TimesheetMonth {
  member_id: string;
  member_name: string;
  month: string;
  start_date: string;
  end_date: string;
  days: TimesheetMonthDay[];
  teaching_periods: number;
  work_periods: number;
  covered_periods: number;
  evening_sessions: number;
}

export interface TimesheetWeek {
  member_id: string;
  member_name: string;
  week_start: string;
  days: TimesheetDay[];
  teaching_periods: number;
  work_periods: number;
  free_periods: number;
  covered_periods: number;
  /** S-68 — evenings she runs this week. Beside the periods, never added in. */
  evening_sessions: number;
  /** org-day rows only: why this person is away today (S-72). */
  away_reason: string | null;
}

export interface WorkType {
  key: string;
  label: string;
}

export interface LeavePolicy {
  leaves_per_year: number;
  leaves_per_month: number;
}

export interface LeaveBalance {
  member_id: string;
  academic_year_id: string | null;
  allowed_per_year: number;
  allowed_per_month: number;
  approved_days: number;
  pending_days: number;
  remaining: number;
}

export type LeaveStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface LeaveEvent {
  action: string;
  actor_name: string | null;
  note: string | null;
  created_at: string;
}

export interface LeaveRequest {
  id: string;
  member_id: string;
  member_name: string;
  start_date: string;
  end_date: string;
  /** 0.5 for a half-day (D-04). */
  days: number;
  is_half_day: boolean;
  portion: "am" | "pm" | null;
  reason: string;
  status: LeaveStatus;
  created_at: string;
  /** Policy breaches. Advisory — the request still reaches the admin. */
  warnings: string[];
  events: LeaveEvent[];
  /** D-27 — the working days this approved leave still needs cover for. */
  cover_dates: string[];
}

export interface LeaveList {
  requests: LeaveRequest[];
  pending_count: number;
  policy: LeavePolicy;
}

// ── HW-1: per-student homework capture + analytics ───────────────────────────

/** The V1-5 vocabulary — mirrors `core/homework_verdict.py`. Import that table
 *  mentally before touching any of it:
 *    done/late  worth 1 · partial worth 0.5 · not_done worth 0 — all graded
 *    carried    absent when it was set. NOT a miss, NOT in the denominator (D-34)
 *    waived     the teacher let it go, so the yellow can clear (S-98)
 *    not_checked  the TEACHER has not gone through it — a gap in the record,
 *                 never a mark against the student. No surface may render it as
 *                 a miss, parent-facing ones included. */
export type HomeworkStatus =
  | "done" | "not_done" | "partial" | "late" | "carried" | "waived" | "not_checked";

/** What the teacher may set on the sheet. `done` is the absence of a row. */
export type HomeworkVerdict = "done" | "not_done" | "partial" | "late" | "carried" | "waived";

export interface HomeworkSheetRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  status: HomeworkVerdict;
  note: string | null;
  /** S-85: absent the day it was set. **Shown, never preselected** — a friend
   *  may have passed it on, and a hard exclusion cannot be overridden. */
  absent_when_set: boolean;
  /** S-97: items still carried from while they were away. */
  carried_pending: number;
  /** S-89: the streak, at the moment she is holding the child's book — the
   *  cheapest intervention point in the product. */
  miss_streak: number;
}

// ── V1-5: the teacher's homework screen (D-36 / S-100 / S-101) ──────────────

export interface HomeworkQueueItem {
  assignment_id: string;
  class_subject_id: string;
  class_label: string;
  subject_name: string | null;
  date: string;
  due_date: string | null;
  text: string;
  /** Set = a personal homework, so its roster is one child. */
  student_id: string | null;
  student_name: string | null;
  checked: boolean;
  checked_at: string | null;
  /** Deadline passed with nothing gone through. A fact about the RECORD. */
  overdue: boolean;
  days_waiting: number;
  missed: number;
  carried: number;
}

export interface HomeworkQueue {
  from_date: string;
  to_date: string;
  items: HomeworkQueueItem[];
  /** S-100 — the number on the button. Without it the screen is optional. */
  to_check: number;
  overdue: number;
}

export interface HomeworkLoadCell {
  class_id: string;
  class_label: string;
  date: string;
  subjects: number;
  assignments: number;
}

/** D-37: admin and CLASS TEACHER only — never a subject teacher, and never a cap. */
export interface HomeworkLoad {
  from_date: string;
  to_date: string;
  cells: HomeworkLoadCell[];
  busiest_class_label: string | null;
  busiest_date: string | null;
  busiest_subjects: number;
}

export interface HomeworkSheet {
  assignment_id: string;
  class_label: string;
  subject_name: string | null;
  text: string;
  date: string;
  due_date: string | null;
  /** False = never checked, which is NOT the same as everyone having done it. */
  checked: boolean;
  checked_at: string | null;
  checked_by: string | null;
  student_id: string | null;
  roster: HomeworkSheetRow[];
  done_count: number;
  not_done_count: number;
  partial_count: number;
}

/** V1-17 — set → checked → done, and all three in ONE unit.
 *
 *  Every figure here counts *student-homeworks*: one per student a homework was
 *  given to. That is what makes the stages nest (`given ⊇ checked ⊇ graded`) and
 *  the two gaps readable as lengths. They are two different problems and never
 *  the same colour:
 *
 *  - `given − checked` — nobody has gone through it. HW-1's rule: the teacher's
 *    gap, never a child's. Drawn as the no-record texture, never a zero, never
 *    red.
 *  - `graded − done_weighted` — the work that was not done. The only one of the
 *    two that may carry a judgement.
 *
 *  `carried` and `waived` sit between them: checked, but out of the denominator
 *  entirely (D-34/S-98), so they are reported and never silently absorbed. */
export interface HomeworkFunnel {
  given: number;
  checked: number;
  graded: number;
  done: number;
  late: number;
  partial: number;
  not_done: number;
  carried: number;
  waived: number;
  /** done + late + 0.5·partial — the numerator `completion` divides. Carried so
   *  no screen re-derives it and gets `partial` wrong on the way. */
  done_weighted: number;
  assignments: number;
  class_subjects: number;
  /** checked / given. Named apart from `completion` because they are different
   *  denominators, and reading one as the other is the whole defect. */
  check_rate: number | null;
  /** done_weighted / graded. Never over `given`. */
  completion: number | null;
}

/** One class × one subject. The two bar charts each collapsed a whole axis, so
 *  "6-B is low" and "Hindi is low" could not resolve into "6-B Hindi is where it
 *  happens". `completion === null` means nothing here was checked — a state,
 *  drawn as the no-record texture, never a 0%. */
export interface HomeworkMatrixCell {
  class_key: string;
  subject_key: string;
  assigned: number;
  checked: number;
  given: number;
  graded: number;
  completion: number | null;
  /** Decided server-side: three surfaces render these cells, and a tone each
   *  worked out for itself would be three verdicts about one teacher. */
  tone: "neutral" | "green" | "amber" | "red";
}

/** One bucket of the series — a day, or a week once the range is long.
 *
 *  Accumulated inside the same server-side pass as the funnel, so it goes
 *  through `core/homework_verdict` like every other figure. It used to be a
 *  second walk with its own arithmetic: `late` dropped from the numerator,
 *  `carried`/`waived` left in the denominator, the absent→carried rewrite never
 *  run — so the chart read lower than the sentence above it. */
export interface HomeworkDay {
  date: string;
  /** Server-formatted. A week bucket is not a date, and the client has no way
   *  to know which it got. */
  label: string;
  days: number;
  assigned: number;
  checked: number;
  given: number;
  /** Of those, graded — the completion denominator. */
  expected: number;
  /** done + late: whole students who did the work. */
  done: number;
  partial: number;
  not_done: number;
  not_checked: number;
  completion: number | null;
}

export interface HomeworkScopeRow {
  key: string;
  id: string | null;
  assigned: number;
  checked: number;
  students_expected: number;
  /** The funnel's first two stages at this scope, so a row can be drawn on the
   *  same track as the school figure. */
  students_set: number;
  students_checked: number;
  done: number;
  not_done: number;
  partial: number;
  /** V1-5: `late` is inside `completion` (it IS done — S-99) and reported
   *  beside it; `carried` and `waived` are outside the denominator entirely
   *  (D-34/S-98). `waived` was missing from this row until V1-17, so waived
   *  work was invisible here while the student history reported it. */
  late: number;
  carried: number;
  waived: number;
  completion: number | null;
  check_rate: number | null;
}

export interface TeacherCheckingRow {
  member_id: string | null;
  teacher_name: string;
  assigned: number;
  checked: number;
  unchecked_overdue: number;
  check_rate: number | null;
  last_checked_at: string | null;
}

export interface StudentHomeworkRow {
  student_id: string;
  full_name: string;
  class_label: string;
  roll_no: string | null;
  assigned: number;
  done: number;
  not_done: number;
  partial: number;
  late: number;
  carried: number;
  completion: number | null;
  streak: number;
  /** Misses in the earlier half of the window minus the recent half. Its own
   *  field since V1-17: the delta used to be written over `streak`, so a row
   *  claimed a miss streak it did not have and the screen printed "N fewer
   *  misses" out of a field named for the opposite thing. */
  improvement: number;
  subjects: string[];
  teachers: string[];
}

export interface HomeworkOverview {
  window_days: number;
  from_date: string;
  to_date: string;
  /** These two count SETS of homework, not students — the teacher checking
   *  table is denominated in sets ("she set 9 and went through 4"). Anything
   *  comparing set → checked → done reads `funnel`. */
  assigned: number;
  checked: number;
  check_rate: number | null;
  overall_completion: number | null;
  late: number;
  carried: number;
  funnel: HomeworkFunnel;
  daily: HomeworkDay[];
  matrix: HomeworkMatrixCell[];
  /** The matrix axes, ordered by the server so every renderer draws the same
   *  grid and an empty pair is a hole rather than a missing column. */
  matrix_classes: string[];
  matrix_subjects: string[];
  by_class: HomeworkScopeRow[];
  by_subject: HomeworkScopeRow[];
  teachers: TeacherCheckingRow[];
  needs_attention: StudentHomeworkRow[];
  perfect: StudentHomeworkRow[];
  most_improved: StudentHomeworkRow[];
  /** D-85's two derived admin signals. Different problems, different rows, and
   *  neither writes anything into a child's record: `delayed_teachers` is a
   *  backlog (counted only past the deadline, at the org's own
   *  `homework_gap_days`), `rough_classes` is a class that WAS checked and
   *  largely didn't do it. */
  delayed_teachers: TeacherCheckingRow[];
  rough_classes: RoughClassRow[];
}

export interface RoughClassRow {
  assignment_id: string;
  class_label: string;
  subject_name: string | null;
  date: string;
  text: string;
  missed: number;
  students_expected: number;
  teacher_name: string | null;
}

export interface StudentHomeworkItem {
  assignment_id: string;
  date: string;
  due_date: string | null;
  subject_name: string | null;
  class_label: string | null;
  text: string;
  personal: boolean;
  status: HomeworkStatus;
  note: string | null;
}

export interface StudentHomeworkHistory {
  student_id: string;
  full_name: string;
  class_label: string | null;
  window_days: number;
  assigned: number;
  done: number;
  not_done: number;
  partial: number;
  /** V1-5: `late` counts as DONE inside `completion` and is reported beside it
   *  (S-99). `carried`/`waived` are outside the denominator entirely (D-34/S-98)
   *  and `not_checked` is the teacher's gap — never the child's miss. */
  late: number;
  carried: number;
  waived: number;
  not_checked: number;
  completion: number | null;
  streak: number;
  items: StudentHomeworkItem[];
}

// ── V1-6: the teacher's own syllabus (S-46, D-15) ───────────────────────────
export interface SubjectPaceRow {
  class_subject_id: string;
  class_id: string;
  class_label: string;
  subject_id: string | null;
  subject_name: string;
  /** Already through the shared classifier — `unknown` means nobody logged
   *  anything, and must never render as a pace colour (S-42). */
  status: string;
  taught_topics: number;
  planned_topics: number;
  total_topics: number;
  coverage_pct: number | null;
  syllabus_pct: number | null;
  due_topics: number;
  behind_topics: number;
  weeks_behind: number;
  unestimated_topics: number;
  logged_periods: number;
  /** The reason she opened the screen at all (S-46). */
  next_topic_title: string | null;
  next_chapter_title: string | null;
  last_taught_on: string | null;
  /** Class-teacher view only (D-15) — never a rank, never school-wide. */
  teacher_name: string | null;
  cause: string | null;
  cause_detail: string | null;
}

export interface MySubjects {
  academic_year_id: string | null;
  as_of: string;
  headline: string;
  rows: SubjectPaceRow[];
}

export interface ClassSyllabus {
  class_id: string;
  class_label: string;
  as_of: string;
  headline: string;
  rows: SubjectPaceRow[];
}


// ── V1-8 · the exam Report tab (`D-80`) ──────────────────────────────────────
export interface ExamReportRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  score: number | null;
  max_score: number | null;
  pct: number | null;
}

export interface ExamReportQuestion {
  q: string;
  attempted: number;
  avg_score: number | null;
  max: number | null;
  avg_pct: number | null;
}

export interface ExamReport {
  cycle_id: string;
  name: string;
  date: string;
  type_label: string;
  scale: ExamScale;
  scale_label: string;
  class_id: string;
  class_label: string;
  subject_id: string;
  subject_name: string;
  topic: string | null;
  total_marks: number | null;
  locked: boolean;
  summary: string;
  summary_source: string;
  roster: number;
  scored: number;
  avg_pct: number | null;
  participation: number | null;
  distribution: { label: string; count: number }[];
  rows: ExamReportRow[];
  /** Named rows against a STATED criterion (`gap_points`) — never a rank. */
  not_sat: ExamReportRow[];
  struggling: ExamReportRow[];
  strong: ExamReportRow[];
  gap_points: number;
  /** Empty for a hand-typed exam; `question_note` says why, as a word. */
  questions: ExamReportQuestion[];
  question_note: string | null;
  coverage_taught: number;
  coverage_total: number;
  coverage_pct: number | null;
  coverage_note: string | null;
  latest_topic: string | null;
  exam_event_name: string | null;
}

// ── V1-8 · the two report levels (`D-81`) ────────────────────────────────────
export interface ReportCardExam {
  cycle_id: string;
  name: string;
  type_label: string;
  scale: ExamScale;
  date: string;
  score: number;
  max_score: number;
  pct: number | null;
  locked: boolean;
  paper_url: string | null;
}

export interface ReportCardSubject {
  subject_id: string | null;
  subject_name: string | null;
  exams: ReportCardExam[];
  figures: ScaleFigure[];
}

/** Level 1 — numbers only. Never a band (P4): this is the surface most likely
 *  to be printed and handed to a family. */
export interface ReportCard {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  admission_no: string | null;
  class_label: string | null;
  as_of: string;
  subjects: ReportCardSubject[];
  figures: ScaleFigure[];
}

export interface ClassReportCard {
  class_id: string;
  class_label: string;
  as_of: string;
  columns: {
    cycle_id: string; name: string; type_label: string; scale: ExamScale;
    date: string; subject_id: string | null; subject_name: string | null;
    total_marks: number | null;
  }[];
  students: ReportCard[];
}

/** Level 2 — the narrative, over the same figures. */
export interface AnalysisSubject {
  subject_id: string | null;
  subject_name: string | null;
  teacher_name: string | null;
  figures: ScaleFigure[];
  coverage_taught: number;
  coverage_total: number;
  coverage_pct: number | null;
  attendance_pct: number | null;
  topics: { title: string; status: string; missed_while_absent: boolean }[];
  summary: string;
  summary_source: string;
}

export interface StudentAnalysis {
  student_id: string;
  full_name: string;
  class_label: string | null;
  as_of: string;
  attendance_pct: number | null;
  figures: ScaleFigure[];
  subjects: AnalysisSubject[];
  skills: { skill_area: string; score: number; max_score: number; pct: number | null }[];
  strengths: string[];
  growth_areas: string[];
  summary: string;
  summary_source: string;
}


// ── V1-9 · the support programme (bands) ─────────────────────────────────────
export type BandTier = "A" | "B" | "C";

/** `S-166`: the letter never renders without its sentence. */
export interface BandDescriptor {
  id: string | null;
  subject_id: string;
  subject_name: string;
  tier: BandTier;
  text: string;
  /** The subject's own threshold (`D-74`). null on C — C is "below B". */
  min_pct: number | null;
}

export interface BandSubjectSetup {
  subject_id: string;
  subject_name: string;
  monitored: boolean;
  descriptors: BandDescriptor[];
}

export interface AssessRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  current_tier: BandTier | null;
  pct: number | null;
  /** null = did not sit it. **Not assessed is a word**, never a C. */
  suggested_tier: BandTier | null;
}

export interface BandClassBoard {
  class_id: string;
  class_label: string;
  subject_id: string;
  subject_name: string;
  term_id: string | null;
  a_min: number;
  b_min: number;
  cycle_id: string | null;
  cycle_name: string | null;
  descriptors: BandDescriptor[];
  rows: AssessRow[];
}

export interface BandMoveRow {
  student_id: string;
  full_name: string;
  from_tier: BandTier | null;
  to_tier: BandTier;
  pct: number;
  direction: "up" | "down" | "new";
}

/** The review step (`Q-81`) — shown before anything commits, because
 *  `student_bands` is append-only and a child slipping B → C is permanent. */
export interface BandPromotePreview {
  cycle_id: string;
  name: string;
  date: string;
  class_id: string | null;
  class_label: string | null;
  subject_id: string | null;
  subject_name: string | null;
  total_marks: number | null;
  locked: boolean;
  already_promoted: boolean;
  blocked: string | null;
  /** `S-184`: warn, never block. */
  warnings: string[];
  roster: number;
  sat: number;
  not_sat: number;
  unchanged: number;
  moves: BandMoveRow[];
  applied: number;
  descriptor: string | null;
}

export interface ProgrammeRow {
  student_id: string;
  full_name: string;
  class_label: string | null;
  /** `S-188`: never a row about a child without the subject on it. */
  subject_id: string;
  subject_name: string;
  since: string | null;
  owner_member_id: string | null;
  owner_name: string | null;
  intervention_id: string | null;
  last_checkin: string | null;
}

export interface ProgrammeGridCell {
  class_id: string;
  class_label: string | null;
  subject_id: string;
  subject_name: string;
  c_count: number;
  moved_up: number;
  slipped: number;
}

export interface ProgrammeBoard {
  term_id: string | null;
  term_name: string | null;
  subjects: string[];
  headline: string;
  moved_up: number;
  slipped: number;
  stuck: ProgrammeRow[];
  grid: ProgrammeGridCell[];
  not_assessed: string[];
}

/** What this member may band — and therefore whether the ABC Bands nav item
 * exists for them (founder 2026-08-04). */
export interface BandScopeClass {
  class_id: string;
  class_label: string;
  subjects: { id: string; label: string }[];
}

export interface BandScope {
  /** Any subject monitored in the school at all. */
  enabled: boolean;
  /** This member gets the area at all — `can_band` or `owns_students`. */
  has_scope: boolean;
  /** At least one monitored class-subject, so the banding tabs mean something. */
  can_band: boolean;
  /** At least one active support plan of their own. Kept apart from `can_band`:
   *  an owner who teaches none of the monitored subjects still needs My
   *  students, and would read an empty Manage-bands screen as a broken one. */
  owns_students: boolean;
  is_admin: boolean;
  classes: BandScopeClass[];
  subjects: { id: string; label: string }[];
}

/** One class, or one subject, tallied A/B/C.
 *
 * The unit is the **placement** (one child in one subject), never the child:
 * `D-75` retired the overall letter, so a boy who is A in Maths and C in Hindi
 * is in both columns. Only a subject row collapses back to children. */
export interface BandScopeRow {
  key: string;
  label: string;
  a: number;
  b: number;
  c: number;
  /** a + b + c — the denominator every percentage on this row is taken over. */
  assessed: number;
  /** How many placements could exist. `eligible - assessed` is the record's gap. */
  eligible: number;
  a_pct: number;
  b_pct: number;
  c_pct: number;
  not_assessed: number;
  students: number;
}

export interface BandDistribution {
  term_id: string | null;
  term_name: string | null;
  subjects: string[];
  /** `S-169`: movement leads, the distribution explains. */
  headline: string;
  moved_up: number;
  slipped: number;
  school: BandScopeRow;
  caption: string;
  by_class: BandScopeRow[];
  by_subject: BandScopeRow[];
}

export interface AllocationRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  class_id: string | null;
  class_label: string | null;
  subject_id: string;
  subject_name: string;
  tier: string;
  since: string | null;
  owner_member_id: string | null;
  owner_name: string | null;
  intervention_id: string | null;
  last_checkin: string | null;
  checkins: number;
  status: string;
}

export interface AllocationBoard {
  term_id: string | null;
  term_name: string | null;
  headline: string;
  rows: AllocationRow[];
  assigned: number;
  unassigned: number;
  classes: { id: string; label: string }[];
  subjects: { id: string; label: string }[];
}

/** Suggested, never restricted. `load` is capacity, never a score (`S-170`). */
export interface OwnerSuggestion {
  member_id: string;
  name: string;
  suggested: boolean;
  reason: string;
  load: number;
  current: boolean;
}

/** The written summary. `source` is "ai" only when a model actually answered;
 * with no key it is "computed" and the deterministic sentences render, so the
 * page is never blank and the reader can tell which they are looking at. */
export interface SupportSummary {
  source: string;
  summary: string;
  insights: string[];
  based_on: string[];
}

export interface SupportDayRow { date: string; kind: string; text: string }

export interface SupportStudentRow {
  intervention_id: string;
  student_id: string;
  full_name: string;
  class_label: string | null;
  subject_id: string | null;
  subject_name: string | null;
  tier: BandTier | null;
  since: string | null;
  checkins: number;
  last_checkin: string | null;
  weeks_since_checkin: number | null;
  checked_in_this_week: boolean;
  ready_to_retest: boolean;
  status: string;
}

export interface SupportList {
  as_of: string;
  week_start: string;
  headline: string;
  groups: { subject_name: string; rows: SupportStudentRow[] }[];
  moved_on: SupportStudentRow[];
}

export interface SupportCheckpoint {
  id: string;
  week_start: string;
  worked_on: string | null;
  what_changed: string | null;
  next_step: string | null;
  ready_to_retest: boolean;
  author_name: string | null;
  created_at: string;
}

export interface SupportChild {
  intervention_id: string;
  student_id: string;
  full_name: string;
  class_label: string | null;
  subject_id: string | null;
  subject_name: string | null;
  /** The (class, subject) an assignment given from this page is filed against.
   *  Support work reuses per-student homework rather than growing a second
   *  "did he do the work" store. Null when the class isn't taught this subject. */
  class_subject_id: string | null;
  tier: BandTier | null;
  since: string | null;
  source: string | null;
  owner_name: string | null;
  goal_text: string;
  exit_criterion: string | null;
  status: string;
  headline: string;
  descriptors: BandDescriptor[];
  /** `S-164`: his week as five other teachers already recorded it. */
  week: SupportDayRow[];
  week_start: string | null;
  checkpoints: SupportCheckpoint[];
  latest_pct: number | null;
  latest_test: string | null;
}

// ── the owner's own assessments (founder, 2026-08-05) ────────────────────────
// Not exams. `assessment_cycles` is the school's academic record — it carries a
// scale, verify-and-lock, and it moves a child's band. This is a support
// owner's own small check on the children she owns, and its figures never leave
// the programme. The arithmetic lives in `core/band_assessment.py`; the client
// renders what the server computed and never re-derives an average.
export type AssessmentMetric = "marks" | "rating" | "other";
export type AssessmentStatus = "pending" | "partial" | "evaluated";

export interface MyStudentRow {
  intervention_id: string;
  student_id: string;
  full_name: string;
  roll_no: string | null;
  class_id: string | null;
  class_label: string | null;
  subject_id: string | null;
  subject_name: string | null;
  tier: BandTier | null;
  /** `S-166`: the letter never renders without its sentence. */
  descriptor: string | null;
  since: string | null;
  checkins: number;
  last_checkin: string | null;
  weeks_since_checkin: number | null;
  checked_in_this_week: boolean;
  ready_to_retest: boolean;
  /** Per-student homework nobody has checked yet — the TEACHER's gap (HW-1).
   *  Never rendered as the child having failed to do it. */
  open_assignments: number;
  notes: number;
  status: string;
}

export interface MyStudentsBoard {
  headline: string;
  as_of: string;
  week_start: string;
  class_id: string | null;
  classes: { id: string; label: string; count: number }[];
  rows: MyStudentRow[];
  /** The unfiltered count, so an empty class filter reads differently from
   *  having no children at all. */
  total: number;
  moved_on: MyStudentRow[];
}

export interface BandAssessmentRow {
  id: string;
  name: string;
  class_id: string;
  class_label: string;
  subject_id: string | null;
  subject_name: string | null;
  instructions: string | null;
  description: string | null;
  metric: AssessmentMetric;
  max_marks: number | null;
  rating_max: number | null;
  covers_all: boolean;
  given_on: string;
  due_date: string | null;
  author_name: string | null;
  /** `pending` is a state, never an empty score. */
  status: AssessmentStatus;
  roster: number;
  evaluated: number;
  not_evaluated: number;
  average: number | null;
  average_pct: number | null;
  /** The figure with its denominator, in this metric's own words. Render this
   *  rather than composing one from `average` — the server owns the wording. */
  caption: string;
}

export interface BandAssessmentList {
  headline: string;
  rows: BandAssessmentRow[];
  page: number;
  per_page: number;
  total: number;
  pages: number;
  classes: { id: string; label: string; count: number }[];
  open_count: number;
}

export interface AssessmentResultRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  class_label: string | null;
  tier: BandTier | null;
  marks: number | null;
  rating: number | null;
  verdict: string | null;
  note: string | null;
  /** Null means NOT EVALUATED. Render it as a word, never as a zero. */
  result_text: string | null;
  evaluated: boolean;
  notes: number;
}

export interface BandAssessmentSheet {
  assessment: BandAssessmentRow;
  rows: AssessmentResultRow[];
  can_record: boolean;
}

export interface StudentIntervention {
  id: string;
  student_id: string;
  subject_id: string | null;
  subject_name: string | null;
  owner_member_id: string | null;
  owner_name: string | null;
  goal_text: string;
  exit_criterion: string | null;
  target_tier: string;
  status: string;
  closed_at: string | null;
  outcome_note: string | null;
  items: { id: string; text: string; task_instance_id: string | null; done: boolean }[];
}


// ── V1-10 · the collection board ─────────────────────────────────────────────

/** The whole academic year, on one track.
 *
 *  The three figures the board leads with — `billed`, `due_by_today`,
 *  `collected` — share ONE denominator, which is why they are drawn as one arc
 *  against one marker rather than as three rings: three rings would draw the
 *  same track three times and the "billed" one would be a full circle saying
 *  nothing. And `collected` can EXCEED `due_by_today` when families pay in
 *  advance, which a marker can express and stacked arcs cannot. */
export interface YearCollection {
  billed: number;
  /** Of that, what the schedule has already asked for — paid or not. Not the
   *  same as `overdue`, which is only the unpaid part of it. */
  due_by_today: number;
  collected: number;
  pending: number;
  overdue: number;
  pct: number | null;
  /** due_by_today / billed — where the marker sits on the same track. */
  due_pct: number | null;
  /** max(0, due_by_today − collected). Zero when level or ahead: a school that
   *  collected early is not "minus ₹40,000 behind". */
  shortfall: number;
  tone: "neutral" | "green" | "amber" | "red";
}

export interface QuarterRow {
  label: string;
  start: string;
  end: string;
  billed: number;
  collected: number;
  pending: number;
  overdue: number;
  /** null when nothing was billed — a quarter with no instalments is **not**
   *  0% collected. */
  pct: number | null;
  /** The same pace pair at quarter scale: its own denominator, its own marker. */
  due_by_today: number;
  due_pct: number | null;
  shortfall: number;
  /** Server-decided. A quarter with nothing due yet is `neutral` and says so in
   *  a word — it has not been missed, and painting next January red every
   *  August is how a board stops being read. */
  tone: "neutral" | "green" | "amber" | "red";
  state: "past" | "current" | "future";
}

export interface ClassCollectionRow {
  class_id: string | null;
  class_label: string;
  /** `S-159`: both denominators. ₹1.4L is one big defaulter or fourteen small
   *  ones, and those need opposite actions. */
  families_pending: number;
  families_total: number;
  billed: number;
  collected: number;
  pending: number;
  overdue: number;
  pct: number | null;
}

export interface CollectionPoint { day: string; collected: number; previous: number | null }

export interface DefaulterRow {
  student_fee_id: string;
  student_id: string;
  student_name: string;
  class_label: string | null;
  overdue_amount: number;
  earliest_due_date: string | null;
  /** `S-157`: the person who owes is the person you ring. */
  guardian_name: string | null;
  guardian_phone: string | null;
  other_guardians: { name: string; phone: string }[];
  reminded_on: string | null;
  assigned_on: string | null;
  /** `S-161`: what the family SAID, not that a button was pressed. */
  last_said: string | null;
  last_said_on: string | null;
}

export interface CollectionBoard {
  as_of: string;
  academic_year_id: string | null;
  academic_year_label: string | null;
  quarter: string | null;
  headline: string;
  billed: number;
  collected: number;
  /** Three states, never summed (`S-163`): pending is a forecast, overdue is a
   *  phone call. There is no "outstanding" field on purpose. */
  pending: number;
  overdue: number;
  pct: number | null;
  /** The whole year, beside the picked quarter. The figures above are the
   *  PICKED QUARTER's — reading them as the year's is the mistake this field
   *  exists to remove. */
  year: YearCollection;
  quarters: QuarterRow[];
  curve: CollectionPoint[];
  by_class: ClassCollectionRow[];
  defaulters: DefaulterRow[];
  unscheduled_billed: number;
  unscheduled_note: string | null;
  /** `D-88`: dues from a previous year — their own line, never in the figures
   *  above, and never silently omitted either. */
  carried: { amount: number; families: number; note: string } | null;
}

export interface FeeNote {
  id: string;
  kind: string;
  said: string | null;
  promised_date: string | null;
  author_name: string | null;
  created_at: string;
}

export interface RemindResult {
  sent: number;
  skipped: string | null;
  message: string;
}

/** `D-83` — the one fee payload a teacher may receive: this student, inside
 *  this task. */
export interface FeeFollowupDetail {
  task_id: string;
  student_id: string;
  student_fee_id: string;
  student_name: string;
  class_label: string | null;
  pending_amount: number;
  due_date: string | null;
  paid_so_far: number;
  total_fee: number;
  guardian_name: string | null;
  guardian_phone: string | null;
  notes: FeeNote[];
}

// ── the staff directory (founder, 2026-08-05) ────────────────────────────────
// Setup → Members is an ACCOUNT screen (who can log in, invite state, reset a
// password). This is the people screen: who works here, whose homeroom is whose,
// and what everyone carries.
//
// `role_key` is DERIVED, never stored. `org_role` remains `admin | teacher` —
// the two-value column every guard in the app is built on — and the class
// teacher lives in exactly one place, `school_classes.class_teacher_member_id`.
// Writing "Class teacher" back is an assignment on the CLASS.

export interface ClassRef {
  class_id: string;
  class_label: string;
}

export interface StaffSubjectRef {
  class_subject_id: string;
  class_id: string;
  class_label: string;
  subject_id: string;
  subject_name: string;
  periods_per_week: number;
}

export type StaffRoleKey = "admin" | "class_teacher" | "teacher";

/** Staff hold one of TWO org roles. Deliberately not `OrgRole`, which also
 *  carries "parent" — a parent is never a member of staff. */
export type StaffOrgRole = "admin" | "teacher";

export interface StaffRow {
  member_id: string;
  user_id: string;
  name: string;
  email: string | null;
  username: string | null;
  phone: string | null;
  date_of_birth: string | null;
  /** What is STORED. */
  org_role: StaffOrgRole;
  /** What is SHOWN — org role plus the homeroom assignment. */
  role_key: StaffRoleKey;
  role_label: string;
  status: string;
  pending: boolean;
  last_active_at: string | null;
  class_teacher_of: ClassRef[];
  classes: ClassRef[];
  subjects: StaffSubjectRef[];
  subject_count: number;
  periods_per_week: number;
}

export interface StaffDirectory {
  rows: StaffRow[];
  classes: ClassRef[];
  total: number;
  admins: number;
  teachers: number;
  class_teachers: number;
  classes_without_teacher: ClassRef[];
}

export interface StaffDetail {
  row: StaffRow;
  classes: ClassRef[];
  can_edit: boolean;
  is_last_admin: boolean;
}

export interface StaffUpdateIn {
  name?: string;
  email?: string;
  username?: string;
  phone?: string;
  date_of_birth?: string;
  clear_email?: boolean;
  clear_phone?: boolean;
  clear_date_of_birth?: boolean;
  org_role?: StaffOrgRole;
  /** FULL REPLACE. `[]` means "class teacher of nothing"; omit to leave alone. */
  class_teacher_of?: string[];
}


// ── My Class, expanded (founder, 2026-08-05) ─────────────────────────────────
//
// `SchoolTone` is the server's own verdict on a row. It is decided there and
// only there: three surfaces render these rows, and a tone each worked out for
// itself would be three opinions about one teacher on one morning (the V1-15
// precedent).
export type SchoolTone = "neutral" | "green" | "amber" | "red";

// The class teacher's whole desk. Every figure below is COMPUTED SERVER-SIDE by
// the service that already owns it (coverage, homework verdicts, bands, exams),
// so a component that re-derived one would be the drift V1-0 exists to remove.
//
// The rule that repeats through all of it: a denominator nobody has filled in is
// `null`, never 0. An unopened register and an empty classroom are opposite
// facts; an unchecked homework and a class that did nothing are opposite facts.

export interface MyClassAbsentee {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  status: string;
  streak: number;
  reason_code: string | null;
  reason_note: string | null;
  explained: boolean;
  guardian_name: string | null;
  guardian_phone: string | null;
  reminded_today: boolean;
  /** Explained absences are amber, never red (`D-86`) — somebody dealt with it. */
  tone: SchoolTone;
}

export interface MyClassAttendance {
  date: string;
  is_today: boolean;
  school_open: boolean;
  marked: boolean;
  /** The class's strength, populated whether or not anything is marked. */
  roster: number;
  present: number;
  absent: number;
  late: number;
  periods_marked: number;
  periods_scheduled: number;
  pct: number | null;
  month_pct: number | null;
  month_marked_days: number;
  month_school_days: number;
  absentees: MyClassAbsentee[];
  headline: string;
  tone: SchoolTone;
}

export interface MyClassHomework {
  from_date: string;
  to_date: string;
  /** Student-homeworks throughout, so `given ⊇ checked ⊇ graded` nests. */
  given: number;
  checked: number;
  graded: number;
  /** The TEACHER's gap. Never rendered as a child's miss, never in the %. */
  not_checked: number;
  done_weighted: number;
  /** `null` when nothing has been checked — never 0%. */
  completion_pct: number | null;
  late: number;
  carried: number;
  waived: number;
  missed: number;
  assignments: number;
  unchecked_assignments: number;
  headline: string;
  tone: SchoolTone;
}

export interface MyClassBandSubject {
  subject_id: string;
  subject_name: string;
  a: number;
  b: number;
  c: number;
  assessed: number;
  /** Its own number in its own word — never a tier, never a step on the ramp. */
  not_assessed: number;
}

export interface MyClassBands {
  subjects: MyClassBandSubject[];
  monitored: number;
  headline: string;
}

export interface MyClassExams {
  recent: ExamSummary[];
  headline: string;
}

export interface MyClassOverview {
  class_id: string;
  class_label: string;
  roster: number;
  as_of: string;
  headline: string;
  attendance: MyClassAttendance;
  homework: MyClassHomework;
  bands: MyClassBands;
  exams: MyClassExams;
  syllabus: ClassSyllabus | null;
}

export interface MyClassStudentRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  admission_no: string | null;
  category: string | null;
  attendance_pct: number | null;
  marked_days: number;
  days_absent: number;
  absent_today: boolean;
  homework_pct: number | null;
  homework_missed: number;
  homework_graded: number;
  /** "C · Hindi" (`S-186`) — the band with the subject that earned it. */
  band_chips: string[];
  latest_exam_pct: number | null;
  latest_exam_name: string | null;
  note_count: number;
  guardian_name: string | null;
  guardian_phone: string | null;
  tone: SchoolTone;
}

export interface MyClassStudents {
  class_id: string;
  class_label: string;
  from_date: string;
  to_date: string;
  rows: MyClassStudentRow[];
  headline: string;
}

export type StudentNoteKind =
  | "general" | "behaviour" | "wellbeing" | "achievement" | "parent_contact" | "concern"
  | "support" | "assessment";

export interface StudentNote {
  id: string;
  student_id: string;
  kind: StudentNoteKind;
  note: string;
  /** What occasioned it, when it came off a support assessment's sheet. */
  assessment_id: string | null;
  author_name: string | null;
  created_at: string;
}

export interface StudentNotes {
  student_id: string;
  full_name: string;
  /** The homeroom's own teacher, an admin, or the owner of his support plan. */
  can_write: boolean;
  rows: StudentNote[];
}

// ── the teacher's attendance board (founder, 2026-08-05) ─────────────────────
// Attendance used to be reachable only from a My Day period card, so the person
// covering for an absent class teacher had no door into it — which is exactly
// the case the school's rule exists for.

export interface MyAttendanceClass {
  class_id: string;
  class_label: string;
  roster: number;
  is_class_teacher: boolean;
  class_subject_id: string | null;
  subject_name: string | null;
  marked: boolean;
  marked_period_no: number | null;
  marked_by_name: string | null;
  marked_at: string | null;
  periods_marked: number;
  present: number;
  absent: number;
  late: number;
  pct: number | null;
  absentee_names: string[];
  can_mark: boolean;
  /** Would this be the day's opening register — the one that alerts guardians? */
  first_of_day: boolean;
  /** A suggestion for which period to open, never a restriction. */
  suggested_period_no: number;
  headline: string;
  tone: SchoolTone;
}

export interface MyAttendanceBoard {
  date: string;
  is_today: boolean;
  school_open: boolean;
  classes: MyAttendanceClass[];
  headline: string;
}
