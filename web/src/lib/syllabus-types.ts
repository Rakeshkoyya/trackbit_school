// The syllabus board (SY-1) — mirrors `app/schemas/syllabus_board.py`.
//
// Every figure on these rows is decided server-side, including the words
// (`status`) and the dates (`planned_start` from a plan week). The browser
// renders; it does not compute coverage. That is `S-51`'s rule, and it is here
// because two of the five places "syllabus covered" used to be computed were
// `.reduce()` calls in React.

export type ChapterStatus =
  | "not_scheduled"
  | "not_started"
  | "in_progress"
  | "completed";

export type Difficulty = "easy" | "moderate" | "hard";

export interface SyllabusTopicRow {
  id: string;
  title: string;
  position: number;
  est_periods: number | null;
  status: ChapterStatus;
  coverage: "full" | "partial" | null;
  planned_start: string | null;
  planned_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  logs: number;
}

export interface SyllabusChapterRow {
  unit_id: string;
  class_subject_id: string;
  title: string;
  position: number;
  term_id: string | null;
  term_name: string | null;
  difficulty: Difficulty | null;
  remarks: string | null;
  /** The school decided this chapter is out of scope this year. The one STORED
   *  field on a row of derived ones: it forces `status` to `not_scheduled` and
   *  takes the chapter out of every coverage numerator and denominator. The
   *  topic counts stay real, so the table can show what is being excluded. */
  not_planned: boolean;
  est_periods: number | null;
  topics_total: number;
  unsized_topics: number;
  has_topic_detail: boolean;
  planned_start: string | null;
  planned_end: string | null;
  /** What was locked at approval. Differs from `planned_*` exactly when
   *  somebody rescheduled — which is why both are on the row. */
  baseline_start: string | null;
  baseline_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  status: ChapterStatus;
  completion_pct: number | null;
  /** V1-15's pace marker at chapter scale: how much of this chapter's own
   *  planned window has gone by, in teaching days. What makes the completion
   *  figure readable — 40% is fine in week one and alarming in the last week. */
  expected_pct: number | null;
  taught_full: number;
  taught_partial: number;
  overdue: boolean;
  finish_drift_days: number | null;
  topics: SyllabusTopicRow[];
}

export interface SyllabusSubjectGroup {
  class_subject_id: string;
  class_id: string;
  class_label: string;
  subject_id: string;
  subject_name: string;
  teacher_name: string | null;
  periods_per_week: number;
  plan_status: string;
  pace: string;
  coverage_pct: number | null;
  chapters: SyllabusChapterRow[];
}

export interface SyllabusClassGroup {
  class_id: string;
  label: string;
  subjects: SyllabusSubjectGroup[];
}

export interface SyllabusTermOut {
  id: string;
  name: string;
  start_date: string;
  end_date: string;
  pre_tracking: boolean;
}

export interface SyllabusBoard {
  academic_year_id: string | null;
  as_of: string;
  scope: "school" | "mine";
  headline: string;
  terms: SyllabusTermOut[];
  classes: SyllabusClassGroup[];
  chapters_total: number;
  completed: number;
  in_progress: number;
  not_started: number;
  not_scheduled: number;
  overdue: number;
}

// ── writes ───────────────────────────────────────────────────────────────────
export interface ChapterPatch {
  title?: string;
  /** "unset" clears it — a partial update can never blank a column by omission. */
  difficulty?: Difficulty | "unset";
  remarks?: string;
  /** true = out of scope this year, false = back in. Omitted leaves it alone. */
  not_planned?: boolean;
  term_id?: string;
  clear_term?: boolean;
}

export interface RescheduleViolation {
  unit_id: string | null;
  code: "too_short" | "overlaps" | "outside_year" | "unsized" | "past_exam";
  message: string;
}

export interface RescheduleResult {
  fits: boolean;
  violations: RescheduleViolation[];
  chapters: SyllabusChapterRow[];
}

// ── the reschedule dialog's read ─────────────────────────────────────────────
export interface TimelineChapter {
  unit_id: string;
  title: string;
  position: number;
  est_periods: number | null;
  planned_start: string | null;
  planned_end: string | null;
  actual_start: string | null;
  actual_end: string | null;
  status: ChapterStatus;
  difficulty: Difficulty | null;
  locked: boolean;
}

export interface TimelineMarker {
  kind: "exam" | "term_start" | "term_end" | "today";
  label: string;
  date: string;
  end_date: string | null;
}

export interface PlanTimeline {
  class_subject_id: string;
  class_label: string;
  subject_name: string;
  window_start: string;
  window_end: string;
  periods_per_week: number;
  locked: boolean;
  lock_reason: string | null;
  chapters: TimelineChapter[];
  markers: TimelineMarker[];
}

// ── exam ↔ syllabus mapping ──────────────────────────────────────────────────
export interface ExamMapChapter {
  unit_id: string;
  title: string;
  position: number;
  est_periods: number | null;
  term_id: string | null;
  selected: boolean;
  covered_earlier: boolean;
  status: ChapterStatus;
  planned_end: string | null;
}

export interface ExamMapSubject {
  class_subject_id: string;
  subject_name: string;
  source: "none" | "chapters" | "legacy_prefix";
  verdict: "short" | "tight" | "fits" | "surplus" | "no_portion" | "unallocated";
  required_periods: number;
  capacity_periods: number;
  unsized_topics: number;
  chapters: ExamMapChapter[];
}

export interface ExamMapExam {
  exam_event_id: string;
  title: string;
  start_date: string;
  end_date: string;
  days_to_exam: number;
  teaching_days_in_gap: number;
  subjects: ExamMapSubject[];
}

export interface ExamMap {
  class_id: string;
  class_label: string;
  headline: string;
  exams: ExamMapExam[];
}
