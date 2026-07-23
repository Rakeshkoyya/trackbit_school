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

export interface ParentHomeworkItem {
  subject_name: string;
  text: string;
}

export interface ParentSessionItem {
  session_name: string;
  kind: string;
  status: string;
  homework_done: boolean | null;
  log_note: string | null;
}

export type DayStatus = "no_school" | "not_marked" | "present" | "partial" | "absent";

export interface ParentToday {
  date: string;
  status: DayStatus;
  marked_periods: number;
  absent_periods: number;
  late_periods: number;
  taught: ParentTaughtItem[];
  homework: ParentHomeworkItem[];
  sessions: ParentSessionItem[];
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
  topics_taught: number;
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
