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

/** `not_checked` means the teacher hasn't gone through it yet. It is a gap in
 *  the record, never a mark against the child — the UI must say so plainly. */
export type HomeworkStatus = "done" | "not_done" | "partial" | "not_checked";

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
}

export interface ParentReportSubject {
  subject_name: string;
  teacher_name: string | null;
  attendance: ParentAttendance;
  chapters: ParentChapter[];
  homework_assigned: number;
  homework_personal: number;
  scores: ParentScore[];
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

export interface RequestOtpResult {
  message: string;
  channel: "whatsapp" | "sms" | "stub";
  debug_code: string | null;
}

export const parentApi = {
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
};
