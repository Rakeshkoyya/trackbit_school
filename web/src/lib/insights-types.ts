// DASH3 — the admin operating board. Mirrors app/schemas/insights.py.
//
// Kept in its own module rather than appended to school-types.ts: this is one
// coherent feature with ~40 types, and the seven dashboard tabs are the only
// things that import it.
//
// Two distinctions ride through every type here, and no screen may collapse
// either of them:
//   * "not captured" is not "captured as zero" — an unmarked period is not a
//     period with nobody present, and unchecked homework is not homework nobody
//     did.
//   * unplanned / unallocated / unestimated are STATES, never a RAG colour.
//     Painting them green is exactly the regression V2-P11 fixed.

import type { AttendancePulse, HomeworkOverview } from "@/lib/school-types";

// ── M1 attendance ────────────────────────────────────────────────────────────

/** free = nothing scheduled · pending = scheduled, unmarked · marked ·
 *  not_held = the teacher said the class did not happen (captured, not missing) ·
 *  not_expected = scheduled, but the org's attendance mode doesn't mark this
 *  period (V1-3, D-01) — neutral, out of the denominator. */
export type CaptureState = "free" | "pending" | "marked" | "not_held" | "not_expected";

export interface CaptureCell {
  period_no: number;
  state: CaptureState;
  class_subject_id: string | null;
  subject_name: string | null;
  absent: number;
  late: number;
}

export interface CaptureRow {
  class_id: string;
  class_label: string;
  roster: number;
  cells: CaptureCell[];
  marked: number;
  expected: number;
}

export interface PeriodCaptureGrid {
  date: string;
  periods_per_day: number;
  period_times: { period_no: number; start: string; end: string }[];
  rows: CaptureRow[];
  marked: number;
  expected: number;
  /** V1-3 (D-01): what the denominator means — state it beside the count. */
  mode: "every_period" | "first_period" | "twice_daily";
}

export interface StaffAbsentee {
  member_id: string;
  name: string;
  role: string;
  on_leave: boolean;
  reason: string | null;
  periods_due: number;
  periods_covered: number;
}

export interface StaffPresence {
  date: string;
  /** False = nobody has taken staff attendance yet. Information, not a failure —
   *  must never render red. */
  marked: boolean;
  total: number;
  present: number;
  absent: number;
  on_leave: number;
  absentees: StaffAbsentee[];
}

export interface AttendanceBoard {
  date: string;
  students: AttendancePulse;
  capture: PeriodCaptureGrid;
  staff: StaffPresence;
  streak_count: number;
}

export interface AbsenceStreak {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  class_id: string | null;
  class_label: string | null;
  streak: number;
  last_present: string | null;
  days_partial: number;
  guardian_count: number;
  class_teacher_member_id: string | null;
  class_teacher_name: string | null;
  reminded_today: boolean;
  followup_assigned_today: boolean;
}

export interface StreakBoard {
  as_of: string;
  min_days: number;
  window_days: number;
  rows: AbsenceStreak[];
}

// ── V1-3: the attendance tab as questions (S-08, D-02/D-86) ─────────────────
/** `status` answers "has anybody dealt with this?" (D-86): unexplained = red,
 *  explained = amber. Computed server-side (S-22) — the UI only paints. */
export interface CallRow extends AbsenceStreak {
  status: "explained" | "unexplained";
  reason_code: string | null;
  reason_note: string | null;
}

export interface DriftRow {
  student_id: string;
  full_name: string;
  roll_no: string | null;
  class_label: string | null;
  present_days: number;
  marked_days: number;
  pct: number;
}

export interface LateRow {
  student_id: string;
  full_name: string;
  class_label: string | null;
  late_days: number;
  window_days: number;
}

export interface LeftRow {
  student_id: string;
  full_name: string;
  class_label: string | null;
}

export interface CallBoard {
  date: string;
  roster_considered: number;
  present_today: number;
  min_attendance_pct: number;
  mode: "every_period" | "first_period" | "twice_daily";
  needs_call: CallRow[];
  drifting: DriftRow[];
  chronic_late: LateRow[];
  left_after_lunch: LeftRow[];
}

// ── S-62 · reach: who the school's own alerts did not get to (V1-11) ─────────

export interface ReachRow {
  student_id: string;
  student_name: string;
  guardian_name: string;
  /** The whole point of the row is the call, so the number rides along. */
  phone: string | null;
  kind: string;
  title: string;
  /** The sentence a human reads ("hasn't signed in to the app yet"). */
  reason: string;
  reason_code: "no_login" | "no_device" | "push_failed";
  created_at: string;
}

export interface ReachBoard {
  date: string;
  messages_sent: number;
  delivered: number;
  unreachable: number;
  /** Kept apart from `unreachable`: a family that asked not to be messaged is
   *  not a delivery failure, and must never join a list the office is told to
   *  clear. */
  opted_out: number;
  summary: string;
  rows: ReachRow[];
}

// ── cover for an absent teacher ──────────────────────────────────────────────

export interface SubstituteCandidate {
  member_id: string;
  name: string;
  reason: string;
  rank: number;
  teaches_subject_elsewhere: boolean;
  teaches_this_class: boolean;
  teaching_periods_today: number;
  /** S-74 — what she recorded for that period. Shown, never a block. */
  work_label: string | null;
  /** D-29/S-79(a) — this cover can be a real lesson, not a study period. */
  can_teach_next_topic: boolean;
  /** D-29/S-79(b) — she is behind in her own subjects. A warning, never a block. */
  behind_note: string | null;
}

export interface ImpactPeriod {
  period_no: number;
  start: string | null;
  end: string | null;
  class_id: string;
  class_label: string;
  class_subject_id: string;
  subject_name: string | null;
  substitution_id: string | null;
  covered_by_member_id: string | null;
  covered_by_name: string | null;
  /** D-29 — what the class gains: the next planned topic nobody has logged. */
  next_topic: string | null;
  candidates: SubstituteCandidate[];
}

export interface ImpactTask {
  task_id: string;
  title: string;
  board_name: string | null;
  due_at: string | null;
  is_critical: boolean;
  days_overdue: number;
}

export interface StaffImpact {
  member_id: string;
  name: string;
  role: string;
  date: string;
  on_leave: boolean;
  reason: string | null;
  periods: ImpactPeriod[];
  tasks: ImpactTask[];
}

// ── M2 syllabus ──────────────────────────────────────────────────────────────

export interface SyllabusRow {
  class_subject_id: string;
  class_id: string;
  class_label: string;
  subject_id: string | null;
  subject_name: string;
  teacher_member_id: string | null;
  teacher_name: string | null;
  status: string;
  total_topics: number;
  planned_topics: number;
  taught_topics: number;
  coverage_pct: number | null;
  weeks_behind: number;
  baseline_finish: string | null;
  projected_finish: string | null;
  unestimated_topics: number;
  current_term_unplanned: boolean;
  logged_periods: number;

  // ── V1-6 ───────────────────────────────────────────────────────────────────
  /** Coverage of the WHOLE syllabus — the denominator that can only grow (S-54).
   *  `coverage_pct` above is coverage of the PLAN. Both are shown, side by side,
   *  because they answer different questions (S-51). */
  syllabus_pct: number | null;
  syllabus_taught: number;
  /** Pace a person can check by hand: topics whose planned week has arrived,
   *  and how many are still untaught (S-45). */
  due_topics: number;
  taught_due: number;
  behind_topics: number;
  /** Why it is behind (S-41). Absent on a row that is not behind. */
  cause: "not_logged" | "periods_lost" | "never_sized" | "slower" | null;
  cause_detail: string | null;
  periods_not_held: number;
  next_topic_title: string | null;
  next_chapter_title: string | null;
  /** D-16/S-60 — set while a catch-up request is open; `catchup_outcome` fills
   *  in when the meeting happened. The row clears on the OUTCOME, not the press. */
  catchup_task_id: string | null;
  catchup_requested_on: string | null;
  catchup_outcome: string | null;
}

export interface SyllabusTrendPoint {
  week_start: string;
  actual: number;
  baseline: number;
}

export interface SectionCompareRow {
  class_subject_id: string;
  class_label: string;
  teacher_name: string | null;
  status: string;
  coverage_pct: number | null;
  taught_topics: number;
  planned_topics: number;
  behind_topics: number;
}

export interface SectionCompare {
  grade: string;
  subject_name: string;
  spread_pct: number | null;
  rows: SectionCompareRow[];
}

export interface SyllabusNode {
  key: string;
  id: string | null;
  label: string;
  sublabel: string | null;
  class_subjects: number;
  on_track: number;
  slipping: number;
  behind: number;
  unplanned: number;
  unallocated: number;
  /** Has a plan, but nobody has logged a lesson against it (S-42). Its own
   *  bucket: not on track, not behind — a third thing. */
  unknown: number;
  planned_topics: number;
  taught_topics: number;
  coverage_pct: number | null;
  total_topics: number;
  syllabus_pct: number | null;
  weeks_behind_max: number;
  unestimated_topics: number;
  logged_periods: number;
  /** False = below the minimum sample. Render "not enough data yet", never a rank. */
  rank_eligible: boolean;
  score: number | null;
  /** The sentence the ordering rests on — show THIS, never the raw score (S-45). */
  rank_reason: string | null;
}

export interface ExamCheckpointSubject {
  class_subject_id: string;
  class_label: string;
  subject_name: string;
  verdict: "short" | "tight" | "fits" | "surplus" | "no_portion" | "unallocated";
  required_periods: number;
  capacity_periods: number;
  unsized_topics: number;
}

export interface ExamCheckpoint {
  exam_event_id: string;
  title: string;
  start_date: string;
  end_date: string;
  days_to_exam: number;
  teaching_days_in_gap: number;
  short: number;
  tight: number;
  ok: number;
  subjects: ExamCheckpointSubject[];
}

export type SyllabusScope = "school" | "class" | "subject" | "teacher";
export type SyllabusCheckpoint = "year" | "term" | "exam";

export interface SyllabusBoard {
  scope: SyllabusScope;
  checkpoint: SyllabusCheckpoint;
  as_of: string;
  academic_year_id: string | null;
  term_id: string | null;
  term_label: string | null;
  school: SyllabusNode | null;
  nodes: SyllabusNode[];
  rows: SyllabusRow[];
  exams: ExamCheckpoint[];
  ahead: SyllabusNode[];
  needs_support: SyllabusNode[];
  min_class_subjects: number;
  min_logged_periods: number;
  /** S-50 — the nearest exam, computed on every load, whatever tab is selected. */
  next_exam: ExamCheckpoint | null;
  /** The sentence the page opens with (rule 3). */
  headline: string | null;
  trend: SyllabusTrendPoint[];
  sections: SectionCompare[];
}

// ── M3 staff ─────────────────────────────────────────────────────────────────

export interface NowPerson {
  member_id: string;
  name: string;
  role: string;
  class_label: string | null;
  subject_name: string | null;
  work_type: string | null;
  work_label: string | null;
  note: string | null;
  open_tasks: number;
  substituting: boolean;
  reason: string | null;
}

export type SchoolPhase = "before" | "period" | "break" | "after" | "unset" | "holiday";

export interface NowBoard {
  now: string;
  date: string;
  phase: SchoolPhase;
  period_no: number | null;
  period_start: string | null;
  period_end: string | null;
  teaching: NowPerson[];
  working: NowPerson[];
  free: NowPerson[];
  absent: NowPerson[];
  staff_marked: boolean;
}

export interface WorkBucket {
  key: string;
  label: string;
  periods: number;
}

export interface LoadStripCell {
  period_no: number;
  kind: "class" | "work" | "free" | "absent" | "substituting";
  label: string | null;
}

export interface TeacherLoad {
  member_id: string;
  name: string;
  role: string;
  teaching_periods: number;
  work_periods: number;
  free_periods: number;
  /** S-68 — hostel evenings she runs. Beside the periods, never added to them. */
  evening_sessions: number;
  delta_vs_mean: number;
  load_flag: "over" | "under" | "balanced";
  open_tasks: number;
  today: LoadStripCell[];
}

/** D-21/S-66 — the slack profile. `free` means "free **or** unrecorded", which
 *  the screen says once: D-23 decided an unfilled period is free, so there is
 *  no third state to draw. */
export interface SlackSlot {
  weekday: number;
  period_no: number;
  teaching: number;
  working: number;
  free: number;
}

export interface SlackProfile {
  week_start: string;
  /** People who teach at all — including office staff would fake wide-open slots. */
  teacher_count: number;
  periods_per_day: number;
  working_weekdays: number[];
  slots: SlackSlot[];
  best_weekday: number | null;
  best_period_no: number | null;
  best_free: number;
}

export interface WorkloadWeek {
  week_start: string;
  date: string;
  working_weekdays: number[];
  periods_per_day: number;
  mean_teaching: number;
  teachers: TeacherLoad[];
  buckets: WorkBucket[];
  slack: SlackProfile | null;
}

export interface LeaveQueueRow {
  request_id: string;
  member_id: string;
  member_name: string;
  start_date: string;
  end_date: string;
  days: number;
  is_half_day: boolean;
  portion: "am" | "pm" | null;
  reason: string;
  /** Policy breaches. Advisory — SF-1 flags over-policy leave, never blocks it. */
  warnings: string[];
  created_at: string;
  cover_dates: string[];
}

/** S-81 — an approved future absence nobody has covered yet. Raised when the
 *  leave is approved, not on the morning it starts. */
export interface UpcomingCover {
  date: string;
  member_id: string;
  member_name: string;
  request_id: string | null;
  periods_due: number;
  periods_covered: number;
}

export interface LeavePulse {
  pending: number;
  on_leave_today: number;
  approved_days_this_month: number;
  allowed_per_year: number;
  allowed_per_month: number;
  queue: LeaveQueueRow[];
  upcoming: UpcomingCover[];
}

export interface StaffBoard {
  date: string;
  presence: StaffPresence;
  leave: LeavePulse;
  now: NowBoard;
  week: WorkloadWeek;
  uncovered_periods: number;
}

// ── M4 homework ──────────────────────────────────────────────────────────────

export interface HomeworkDay {
  date: string;
  assigned: number;
  checked: number;
  /** Student-assignments under CHECKED homework — the completion denominator.
   *  Unchecked homework is excluded, never counted as done or as missed. */
  expected: number;
  done: number;
  completion: number | null;
}

export interface HomeworkBoard {
  /** V1-12 §7: the sentence the tab opens with, composed server-side. */
  headline: string | null;
  overview: HomeworkOverview;
  daily: HomeworkDay[];
}

// ── M5 tasks + duties ────────────────────────────────────────────────────────

export interface TaskScopeRow {
  key: string;
  id: string | null;
  label: string;
  open: number;
  overdue: number;
  completed: number;
  completion: number | null;
}

export interface TaskRedRow {
  task_id: string;
  title: string;
  board_id: string;
  board_name: string;
  assignee_user_id: string | null;
  assignee_name: string | null;
  due_at: string | null;
  days_overdue: number;
  is_critical: boolean;
}

export interface TaskDayPoint {
  date: string;
  completed: number;
  created: number;
}

export interface DutyRow {
  member_id: string;
  name: string;
  due_periods: number;
  attendance_marked: number;
  logged: number;
  homework_set: number;
  checks_confirmed: number;
  completion: number | null;
}

export interface TaskBoard {
  /** V1-12 §7. */
  headline: string | null;
  date: string;
  window_days: number;
  open: number;
  overdue: number;
  completed_window: number;
  critical_overdue: number;
  unassigned: number;
  daily: TaskDayPoint[];
  by_board: TaskScopeRow[];
  by_assignee: TaskScopeRow[];
  red_rows: TaskRedRow[];
  duties: DutyRow[];
  duty_completion: number | null;
}

// ── M6 exams ─────────────────────────────────────────────────────────────────

export interface ExamRollup {
  cycle_id: string;
  name: string;
  type: string;
  /** V1-8: the school's own word for the type (`D-55`) — display this, not
   *  `type`, which is the code's kind. */
  type_label: string;
  scale: "minor" | "major";
  locked: boolean;
  date: string;
  class_id: string | null;
  class_label: string | null;
  subject_id: string | null;
  subject_name: string | null;
  avg_pct: number | null;
  scored: number;
  roster: number;
  participation: number | null;
}

export interface ScaleFigureRollup {
  scale: "minor" | "major";
  label: string;
  purpose: string;
  exams: number;
  scored: number;
  avg_pct: number | null;
}

export interface ExamScopeRow {
  key: string;
  id: string | null;
  label: string;
  exams: number;
  scored: number;
  /** V1-8 `S-114`: within the board's basis scale — NEVER blended across the
   *  two. The other bucket rides along beside it. */
  avg_pct: number | null;
  minor_pct: number | null;
  minor_exams: number;
  major_pct: number | null;
  major_exams: number;
}

export interface ExamTrendPoint {
  label: string;
  date: string;
  avg_pct: number;
}

export interface ExamTrend {
  key: string;
  label: string;
  points: ExamTrendPoint[];
}

export interface ExamBand {
  label: string;
  count: number;
}

export interface ExamsBoard {
  /** V1-12 §7 — names which scale its figure came from. */
  headline: string | null;
  as_of: string;
  academic_year_id: string | null;
  /** The school's own words for the types in scope (`D-55`). */
  types: string[];
  type_filter: string | null;
  exams: number;
  scored: number;
  /** V1-8 `S-114`: computed within `scale_basis` alone — there is no blended
   *  figure on this board. `standing` (major) and `trajectory` (minor) carry
   *  the two separately, so the screen can name which it is showing. */
  avg_pct: number | null;
  scale_filter: string | null;
  scale_basis: "minor" | "major";
  standing: ScaleFigureRollup | null;
  trajectory: ScaleFigureRollup | null;
  trend_scale: "minor" | "major";
  recent: ExamRollup[];
  by_class: ExamScopeRow[];
  by_subject: ExamScopeRow[];
  trends: ExamTrend[];
  distribution: ExamBand[];
}

// ── the action rail ──────────────────────────────────────────────────────────

export type ActionKind =
  | "guardian_reminded"
  | "followup_assigned"
  | "substitute_assigned"
  | "task_reassigned"
  | "task_extended"
  | "nudged"
  /** D-16 — a meeting request, not a directive. Clears on the OUTCOME. */
  | "catchup_requested";

export interface SubstitutionIn {
  date: string;
  class_id: string;
  period_no: number;
  class_subject_id: string;
  substitute_member_id: string;
  absent_member_id?: string | null;
  note?: string | null;
}

export interface Substitution {
  id: string;
  date: string;
  class_id: string;
  class_label: string | null;
  period_no: number;
  class_subject_id: string | null;
  subject_name: string | null;
  absent_member_id: string | null;
  absent_name: string | null;
  substitute_member_id: string;
  substitute_name: string | null;
  note: string | null;
  cancelled_at: string | null;
}

export interface ActionIn {
  student_id?: string;
  member_id?: string;
  user_id?: string;
  task_id?: string;
  board_id?: string;
  title?: string;
  message?: string;
  note?: string;
  due_at?: string;
  substitution?: SubstitutionIn;
  /** D-16 — the class-subject a catch-up plan is being asked about. */
  class_subject_id?: string;
}

export interface ActionResult {
  kind: string;
  ok: boolean;
  message: string;
  subject_type: string | null;
  subject_id: string | null;
  task_id: string | null;
  substitution: Substitution | null;
  /** True = the rail refused to fire twice today. Not an error. */
  already_done: boolean;
}

export interface FollowupRow {
  id: number;
  kind: string;
  subject_type: string;
  subject_id: string | null;
  actor_name: string | null;
  target_name: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}

// ── the overview ─────────────────────────────────────────────────────────────
// One block per module rather than one number per module: two or three figures
// that mean something together, plus the named specifics under them. The tab is
// still where the work happens — the overview only makes opening one a decision.

export type Tone = "neutral" | "green" | "amber" | "red";

export interface OverviewMetric {
  key: string;
  label: string;
  value: string;
  sub: string | null;
  tone: Tone;
  href: string | null;
  /** The trajectory behind the number. Never a second figure. */
  spark: (number | null)[];
}

/** A named specific. "3 uncovered periods" sends you looking; this doesn't. */
export interface OverviewNote {
  text: string;
  tone: Tone;
  href: string | null;
}

export interface OverviewSection {
  key: string;
  label: string;
  href: string;
  headline: string;
  tone: Tone;
  metrics: OverviewMetric[];
  notes: OverviewNote[];
}

/** Something waiting on the admin now, with the screen that clears it. Derived,
 *  so an empty rail is a real "nothing waiting". */
export interface QuickAction {
  key: string;
  label: string;
  detail: string;
  href: string;
  tone: Tone;
  count: number;
}

export interface OverviewBoard {
  date: string;
  phase: SchoolPhase;
  period_no: number | null;
  period_label: string | null;
  sections: OverviewSection[];
  actions: QuickAction[];
}
