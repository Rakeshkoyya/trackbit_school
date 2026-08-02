// Parent portal API + types (mirrors app/schemas/parent.py — the curated,
// parent-safe shapes; bands/observations/skills never exist here).

import { api } from "@/lib/api-client";
import type { Session } from "@/lib/types";

export interface ParentChild {
  student_id: string;
  full_name: string;
  class_label: string | null;
  admission_no: string;
}

export interface ParentMe {
  name: string;
  phone: string | null;
  username: string | null;
  email: string | null;
  has_password: boolean;
  org_name: string;
  children: ParentChild[];
}

export interface ParentTaughtItem {
  subject_name: string;
  topic: string;
}

/** V1-5 vocabulary (core/homework_verdict.py). `carried` = absent when it was
 *  set, `waived` = the teacher let it go, `not_checked` = the teacher has not
 *  gone through it. None of the three is the child failing to do something, and
 *  no parent surface may colour them as if it were (D-35). */
export type HomeworkStatus =
  | "done" | "not_done" | "partial" | "late" | "carried" | "waived" | "not_checked";

export interface ParentHomeworkItem {
  subject_name: string;
  text: string;
  status: HomeworkStatus;
  due_date: string | null;
  personal: boolean;
}

export interface ParentHomeworkDay {
  date: string;
  items: ParentHomeworkItem[];
  done: number;
  not_done: number;
  partial: number;
  /** V1-5 (`S-99`): done, but after the deadline. Counted as done and reported
   *  BESIDE completion — never folded into it, never rendered as a miss. */
  late: number;
  /** `D-34`/`D-35`: absent when it was set. Pending, never a miss — and it
   *  leaves the denominator entirely, exactly as `not_checked` does. */
  carried: number;
  /** The TEACHER's gap, never the child's. Never coloured as a miss (HW-1). */
  not_checked: number;
}

export interface ParentSessionItem {
  session_name: string;
  kind: string;
  status: string;
  homework_done: boolean | null;
  log_note: string | null;
}

export type DayStatus =
  | "no_school" | "not_marked" | "present" | "partial" | "absent"
  /** V1-3 (Q-03): present in the morning, absent after lunch — its own state. */
  | "left_after_lunch";

/** One school day of the month strip (V1-3, S-11) — a DAILY status only. */
export interface ParentMonthDay {
  date: string;
  status: DayStatus;
}

export interface ParentToday {
  date: string;
  status: DayStatus;
  marked_periods: number;
  absent_periods: number;
  late_periods: number;
  /** S-11: this month's school days, so the parent sees the pattern. */
  month: ParentMonthDay[];
  present_days: number;
  marked_days: number;
  /** D-02: the reason the school recorded, as one plain sentence. */
  absence_reason: string | null;
  /** S-25: the school's number for the "tell the school why" link. */
  school_phone: string | null;
  taught: ParentTaughtItem[];
  homework: ParentHomeworkItem[];
  sessions: ParentSessionItem[];
  /** The last day with homework, and how it went — the first thing a parent asks. */
  yesterday: ParentHomeworkDay | null;
  /** Set and not finished: what's still to do. */
  pending: ParentHomeworkItem[];
  /** `S-94`: work whose deadline has passed, split OUT of "still to do" — the
   *  two were one list, so missed work sat beside upcoming work looking as if
   *  it could still be handed in. Carries no red: it is a fact, and the child
   *  may well have finished it since. */
  missed: ParentHomeworkItem[];
  /** V1-10 (`D-66`/`Q-69`): the fee reminder — **one line**, and only when
   *  something is actually due. A family that has paid sees no money message at
   *  all. Never red, never the word defaulter: a reminder, not a demand. */
  fee: ParentFeeLine | null;
}

export interface ParentFeeLine {
  amount_due: number;
  due_date: string | null;
  paid_so_far: number;
  /** Pre-composed on the server, so every surface says it the same way. */
  line: string;
  school_phone: string | null;
}

export interface ParentAttendance {
  marked_periods: number;
  present: number;
  absent: number;
  late: number;
  pct: number | null;
}

export interface ParentTopic {
  topic_id: string;
  title: string;
  status: "done" | "in_progress" | "pending";
  taught_on: string | null;
  student_attendance: "present" | "absent" | "late" | null;
}

export interface ParentChapter {
  unit_id: string;
  title: string;
  topics_total: number;
  /** Fully covered only — an in-progress topic is its own count (V1-0d). */
  topics_taught: number;
  topics_in_progress: number;
  topics_missed: number;
  topics: ParentTopic[];
}

export interface ParentScore {
  cycle_name: string;
  date: string;
  score: number;
  max_score: number;
  /** V1-8 (`D-55`): the school's own word for the exam type. */
  type_label: string | null;
  /** `S-114`: minor and major are NEVER pooled. A 5-mark slip test and an
   *  80-mark term exam are not two points on one line. */
  scale: string;
}

export interface ParentReportSubject {
  subject_name: string;
  teacher_name: string | null;
  attendance: ParentAttendance;
  chapters: ParentChapter[];
  homework_assigned: number;
  homework_personal: number;
  scores: ParentScore[];
  /** V1-6 (S-51/S-54): computed server-side against the WHOLE syllabus — the
   *  only denominator that cannot fall when next term's chapters are sized.
   *  Never sum the chapters in the browser again. */
  coverage_taught: number;
  coverage_total: number;
  coverage_pct: number | null;
  /** S-48 — what the class is actually on, which is what a parent can ask about. */
  latest_chapter: string | null;
  latest_topic: string | null;
  latest_taught_on: string | null;
}

export interface ParentReport {
  student_id: string;
  full_name: string;
  class_label: string | null;
  attendance: ParentAttendance;
  subjects: ParentReportSubject[];
  strengths: string[];
  growth_areas: string[];
}

// ── D-13 · the login, one step per screen ──────────────────────────────────
export interface ParentClassOption {
  class_id: string;
  name: string;
  section: string | null;
  label: string | null;
}

export interface SchoolLookup {
  org_id: string;
  school_name: string;
  school_phone: string | null;
  classes: ParentClassOption[];
}

export interface ParentChildMatch {
  student_id: string;
  full_name: string;
}

// ── D-08/D-14 · the notifications archive ──────────────────────────────────
export interface ParentNotification {
  id: string;
  kind: string;
  title: string;
  body: string;
  url: string | null;
  student_id: string;
  student_name: string;
  created_at: string;
  read: boolean;
}

export interface ParentNotifications {
  items: ParentNotification[];
  unread: number;
}

// ── Q-56 · the school calendar ─────────────────────────────────────────────
export interface ParentCalendarItem {
  date: string;
  end_date: string | null;
  title: string;
  kind: string;
  /** The answer to "is school open on Monday?". The title is the reason. */
  closed: boolean;
  detail: string | null;
}

export interface ParentCalendar {
  items: ParentCalendarItem[];
}

export interface RequestOtpResult {
  message: string;
  channel: "whatsapp" | "sms" | "stub";
  debug_code: string | null;
}

export const parentApi = {
  // `D-13` the front door: code → class → section → child → date of birth.
  lookupSchool: (code: string) =>
    api.post<SchoolLookup>("/parent/auth/school", { code }, false),
  findChild: (orgId: string, classId: string, query: string) =>
    api.post<ParentChildMatch[]>(
      "/parent/auth/find-child", { org_id: orgId, class_id: classId, query }, false),
  verifyDob: (studentId: string, dateOfBirth: string) =>
    api.post<Session>(
      "/parent/auth/verify-dob", { student_id: studentId, date_of_birth: dateOfBirth }, false),
  // `Q-25` (b): each child proved once, then the switcher works unchanged.
  addChild: (studentId: string, dateOfBirth: string) =>
    api.post<{ student_id: string; full_name: string }>(
      "/parent/children/add", { student_id: studentId, date_of_birth: dateOfBirth }),
  // `Q-29` the recovery door, kept for the family whose child has no DOB on file.
  requestOtp: (phone: string) =>
    api.post<RequestOtpResult>("/parent/auth/request-otp", { phone }, false),
  verifyOtp: (phone: string, code: string) =>
    api.post<Session>("/parent/auth/verify-otp", { phone, code }, false),
  setCredentials: (body: { username?: string; email?: string; password: string }) =>
    api.post<{ message: string }>("/parent/auth/credentials", body),
  me: () => api.get<ParentMe>("/parent/me"),
  today: (studentId: string) =>
    api.get<ParentToday>(`/parent/children/${studentId}/today`),
  report: (studentId: string) =>
    api.get<ParentReport>(`/parent/children/${studentId}/report`),
  calendar: (studentId: string) =>
    api.get<ParentCalendar>(`/parent/children/${studentId}/calendar`),
  notifications: () => api.get<ParentNotifications>("/parent/notifications"),
  markNotificationsRead: () =>
    api.post<{ message: string }>("/parent/notifications/read", {}),
};
