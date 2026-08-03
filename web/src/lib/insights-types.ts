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
  /** The day this row describes, and — for approved leave — the whole span it
   *  covers. Cover is arranged for the absence, not for one day of it. */
  date: string | null;
  leave_start: string | null;
  leave_end: string | null;
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
  /** V1-14: the primary guardian, named and dialable — the row's whole purpose
   *  is the call, and "2 guardians on file" is not a phone number. */
  guardian_name: string | null;
  guardian_phone: string | null;
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

  // ── V1-15 ──────────────────────────────────────────────────────────────────
  /** The two halves of the weighted figure. 1.5 topics is 1 finished + 1
   *  half-done, or 3 half-done — never reconstruct it, render these. */
  taught_full: number;
  taught_partial: number;
  /** Where the plan said this would be by today. `expected_pct` shares
   *  `coverage_pct`'s denominator, `expected_syllabus_pct` shares
   *  `syllabus_pct`'s — a marker is only ever drawn against the figure it was
   *  divided by. Both server-divided (S-51). */
  expected_pct: number | null;
  expected_syllabus_pct: number | null;
  /** Days the projection runs past its own baseline; `overruns_year` = past the
   *  end of the academic year, which is the only lateness a parent notices. */
  overrun_days: number | null;
  overruns_year: boolean;
  /** Why it is behind (S-41). Absent on a row that is not behind. */
  cause: SyllabusCause | null;
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

  // ── V1-15 ──────────────────────────────────────────────────────────────────
  due_topics: number;
  taught_due: number;
  behind_topics: number;
  taught_full: number;
  taught_partial: number;
  /** total − full − partial, carried so no component subtracts a weighted
   *  figure from a count of topics by accident. */
  untaught_topics: number;
  periods_not_held: number;
  /** The plan marker on each denominator — draw the one matching your arc. */
  expected_pct: number | null;
  expected_syllabus_pct: number | null;
  /** Server-decided, because three surfaces draw these nodes and a tone each
   *  worked out for itself would be three verdicts about one teacher. */
  tone: Tone;
  /** The tone in words. A colour alone never carries a verdict here. */
  pace_caption: string | null;
  /** The teacher pivot's denominators — "62% covered" needs "across 3 classes". */
  classes: number;
  subjects: number;
}

export type SyllabusCause = "not_logged" | "periods_lost" | "never_sized" | "slower";

/** S-41 counted. Four rows always, zeroes included — the proportions between
 *  them are the finding, and a tally that drops empty rows can't show one. */
export interface CauseTally {
  key: SyllabusCause;
  label: string;
  detail: string;
  count: number;
  behind_topics: number;
}

export interface TermOption {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  /** Decided against the school's clock, not the browser's. */
  is_current: boolean;
}

/** The overview's syllabus block — the same roll-up the tab renders, minus what
 *  only the tab has room for. Its own read so the term switch re-fetches one
 *  module rather than all seven. */
export interface SyllabusPulse {
  as_of: string;
  academic_year_id: string | null;
  term_id: string | null;
  term_label: string | null;
  headline: string;
  school: SyllabusNode | null;
  classes: SyllabusNode[];
  subjects: SyllabusNode[];
  terms: TermOption[];
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
  /** V1-15 — S-41 rolled up, plus the switcher's terms and the year's end date
   *  (which is what makes a projected finish *late* rather than merely later). */
  causes: CauseTally[];
  terms: TermOption[];
  year_end_date: string | null;
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

// ─────────────────────────────────────────────────────────────────────────────
// V1-14 — the presence panorama: three rings, three named blocks, one month
// ─────────────────────────────────────────────────────────────────────────────

/** One of the three rings. `marked=false` means nobody has taken it — `pct` is
 *  null and the ring is drawn neutral with its caption, never at 0% and never
 *  red. Those are opposite facts and must not share a colour. */
export interface PresenceRing {
  key: "students" | "teachers" | "admins";
  label: string;
  marked: boolean;
  present: number;
  absent: number;
  total: number;
  pct: number | null;
  caption: string;
  tone: Tone;
  href: string;
}

/** The verbs the action rail already implements, plus two the UI resolves
 *  locally (a sheet, a screen) rather than firing straight at the server. */
export type PresenceAction =
  | "remind_guardian"
  | "assign_followup"
  | "record_reason"
  | "arrange_cover"
  | "reassign_work";

export interface PresenceRow {
  id: string;
  name: string;
  subtitle: string;
  tone: Tone;
  href: string | null;
  actions: PresenceAction[];
  /** Already fired today — the rail refusing to pester, rendered as a state. */
  done: PresenceAction[];
  badge: string | null;
}

/** At or under `inline_limit` the people are NAMED with their buttons; above it
 *  the block is one sentence and a link. The threshold is decided server-side
 *  so every surface obeys the same rule. */
export interface PresenceGroup {
  key: "students" | "teachers" | "admins";
  label: string;
  headline: string;
  tone: Tone;
  count: number;
  inline_limit: number;
  inline: boolean;
  rows: PresenceRow[];
  href: string;
  action_label: string;
  note: string | null;
  note_href: string | null;
}

export interface PresenceBoard {
  /** The last day the school actually RAN — not necessarily today. */
  date: string;
  is_today: boolean;
  rings: PresenceRing[];
  groups: PresenceGroup[];
  headline: string;
  /** The roll, summed server-side over the cohorts that were actually MARKED —
   *  `roll_caption` says which. A total that quietly swept in an unmarked
   *  cohort would be the exact lie three denominators exist to prevent. */
  in_building: number;
  roll: number;
  away: number;
  roll_caption: string;
}

export interface PresenceDay {
  date: string;
  marked: boolean;
  present: number;
  absent: number;
  total: number;
  pct: number | null;
}

export interface ClassMonthCell {
  date: string;
  state: "marked" | "unmarked" | "closed";
  absent: number;
  roster: number;
  pct: number | null;
}

export interface ClassMonthRow {
  class_id: string;
  class_label: string;
  roster: number;
  cells: ClassMonthCell[];
  marked_days: number;
  absent_days: number;
  pct: number | null;
  tone: Tone;
}

export interface AbsenceProfile {
  student_id: string;
  full_name: string;
  class_id: string | null;
  class_label: string | null;
  roll_no: string | null;
  days_absent: number;
  marked_days: number;
  pct: number | null;
  current_streak: number;
  absent_today: boolean;
  status: "explained" | "unexplained";
  reason_code: string | null;
  reason_note: string | null;
  guardian_name: string | null;
  guardian_phone: string | null;
  class_teacher_name: string | null;
  reminded_today: boolean;
  followup_assigned_today: boolean;
  /** The row read aloud, composed server-side so the table, the overview and
   *  Lucy cannot describe the same child differently. */
  summary: string;
  tone: Tone;
}

export interface PresenceAnomaly {
  key: string;
  title: string;
  detail: string;
  tone: Tone;
  href: string | null;
}

export interface AdminWorkRow {
  member_id: string;
  user_id: string;
  name: string;
  present: boolean;
  on_leave: boolean;
  reason: string | null;
  open_tasks: number;
  overdue: number;
  critical_overdue: number;
  due_today: number;
  rows: TaskRedRow[];
  tone: Tone;
  summary: string;
}

export interface PresenceMonth {
  date: string;
  window_days: number;
  from_date: string;
  to_date: string;
  dates: string[];
  students: PresenceDay[];
  teachers: PresenceDay[];
  admins: PresenceDay[];
  classes: ClassMonthRow[];
  profiles: AbsenceProfile[];
  staff_absent: StaffAbsentee[];
  admin_work: AdminWorkRow[];
  anomalies: PresenceAnomaly[];
  admin_options: PresenceRow[];
  headline: string;
}

// ── V1-16 · the day-book ─────────────────────────────────────────────────────
// The whole staff's day as one grid, and the person's record you reach by
// tapping a name. Every colour is resolved server-side (`core/work_types.py`),
// so the grid, the ring and the settings swatch cannot each have their own idea
// of what "Exam work" looks like.

/** A column. `label` is set only on breaks. */
export interface DaybookPeriod {
  period_no: number;
  start: string;
  end: string;
  label: string | null;
}

/** `closed` = a period nobody was asked to work (a holiday, a non-school day, a
 *  locked period). It is NOT free: it leaves every denominator, and it is the
 *  difference between "the school was shut" and "nobody worked". */
export type DaybookKind =
  | "class" | "cover" | "work" | "free" | "away" | "closed";

export interface DaybookCell {
  period_no: number;
  kind: DaybookKind;
  label: string | null;
  detail: string | null;
  work_type: string | null;
  /** A category hex, `"slate"`, or the structural tokens `"teaching"`/`"free"`. */
  color: string;
}

export interface DaybookRow {
  member_id: string;
  name: string;
  role: string;
  cells: DaybookCell[];
  teaching: number;
  cover: number;
  work: number;
  free: number;
  away_reason: string | null;
  summary: string;
  teaches: boolean;
}

export interface DaybookSlice {
  key: string;
  label: string;
  periods: number;
  color: string;
}

export interface Daybook {
  date: string;
  is_today: boolean;
  weekday: number;
  is_working_day: boolean;
  closed_reason: string | null;
  locked_periods: number[];
  periods: DaybookPeriod[];
  breaks: DaybookPeriod[];
  rows: DaybookRow[];
  /** Set only by the glimpse, where rows are trimmed. */
  rows_total: number | null;
  slots_total: number;
  slots_teaching: number;
  slots_work: number;
  slots_free: number;
  slots_away: number;
  occupied_pct: number | null;
  slices: DaybookSlice[];
  headline: string;
}

export interface RecordDaySlot {
  period_no: number;
  start: string;
  end: string;
  kind: DaybookKind;
  label: string | null;
  detail: string | null;
  work_type: string | null;
  color: string;
}

export type RecordDayState = "working" | "off" | "holiday" | "leave" | "future";

export interface RecordMonthDay {
  date: string;
  weekday: number;
  state: RecordDayState;
  label: string | null;
  teaching: number;
  cover: number;
  work: number;
  free: number;
  busy: number;
}

export interface RecordPoint {
  date: string;
  teaching: number;
  work: number;
}

export interface StaffRecord {
  member_id: string;
  name: string;
  role: string;
  month: string;
  start_date: string;
  end_date: string;
  date: string;
  is_today: boolean;

  today: RecordDaySlot[];
  today_breaks: DaybookPeriod[];
  today_summary: string;
  away_reason: string | null;
  evening_labels: string[];

  days: RecordMonthDay[];
  series: RecordPoint[];
  slices: DaybookSlice[];
  teaching_periods: number;
  cover_periods: number;
  work_periods: number;
  evening_sessions: number;
  busiest_day: string | null;
  busiest_periods: number;

  working_days: number;
  days_marked: number;
  days_not_marked: number;
  days_present: number;
  days_absent: number;
  half_days: number;
  lates: number;
  leave_days: number;
  leave_remaining: number;

  headline: string;
  where_time_went: string[];
  highlights: string[];
  watch: string[];
  summary: string;
  summary_source: "computed" | "ai";
}
