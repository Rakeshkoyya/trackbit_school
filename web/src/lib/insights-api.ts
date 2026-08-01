// DASH3 — the admin operating board's API surface (`/insights/*`).
//
// Separate from `school-api.ts` for the same reason its types are separate: one
// coherent feature, one import for the seven dashboard tabs. Every route here is
// admin-only server-side; the client never has to reason about that.

import { api } from "@/lib/api-client";
import type {
  ActionIn,
  ActionKind,
  ActionResult,
  AttendanceBoard,
  ExamsBoard,
  FollowupRow,
  HomeworkBoard,
  OverviewBoard,
  StaffBoard,
  StaffImpact,
  StreakBoard,
  Substitution,
  SyllabusBoard,
  SyllabusCheckpoint,
  SyllabusScope,
  TaskBoard,
} from "@/lib/insights-types";

const qs = (params: Record<string, string | number | undefined | null>) => {
  const p = Object.entries(params).filter(([, v]) => v != null && v !== "");
  return p.length ? "?" + p.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&") : "";
};

export const insightsApi = {
  /** The overview: a block per module + the rail of what is waiting. */
  overview: (yearId?: string) =>
    api.get<OverviewBoard>(`/insights/overview${qs({ year_id: yearId })}`),

  attendance: (yearId?: string) =>
    api.get<AttendanceBoard>(`/insights/attendance${qs({ year_id: yearId })}`),
  streaks: (p: { minDays?: number; yearId?: string } = {}) =>
    api.get<StreakBoard>(`/insights/attendance/streaks${qs({ min_days: p.minDays, year_id: p.yearId })}`),

  staff: (weekStart?: string) =>
    api.get<StaffBoard>(`/insights/staff${qs({ week_start: weekStart })}`),
  /** What one absent member's day breaks: periods + ranked substitutes + tasks. */
  staffImpact: (memberId: string, onDate?: string) =>
    api.get<StaffImpact>(`/insights/staff/${memberId}/impact${qs({ on_date: onDate })}`),

  syllabus: (p: {
    yearId?: string;
    scope?: SyllabusScope;
    checkpoint?: SyllabusCheckpoint;
    termId?: string;
  } = {}) =>
    api.get<SyllabusBoard>(
      `/insights/syllabus${qs({
        year_id: p.yearId, scope: p.scope, checkpoint: p.checkpoint, term_id: p.termId,
      })}`,
    ),

  homework: (windowDays?: number) =>
    api.get<HomeworkBoard>(`/insights/homework${qs({ window_days: windowDays })}`),

  tasks: (windowDays?: number) =>
    api.get<TaskBoard>(`/insights/tasks${qs({ window_days: windowDays })}`),

  exams: (p: { yearId?: string; type?: string } = {}) =>
    api.get<ExamsBoard>(`/insights/exams${qs({ year_id: p.yearId, type: p.type })}`),

  // ── the action rail ────────────────────────────────────────────────────────
  /** Every rail button. The server appends a `followup_actions` row and refuses
   *  to fire the same action twice in one day — `already_done` says so. */
  action: (kind: ActionKind, body: ActionIn) =>
    api.post<ActionResult>(`/insights/actions/${kind}`, body),
  actionHistory: (p: { subjectType?: string; subjectId?: string; limit?: number } = {}) =>
    api.get<FollowupRow[]>(
      `/insights/actions/history${qs({
        subject_type: p.subjectType, subject_id: p.subjectId, limit: p.limit,
      })}`,
    ),

  substitutions: (onDate?: string) =>
    api.get<Substitution[]>(`/insights/substitutions${qs({ on_date: onDate })}`),
  cancelSubstitution: (id: string) =>
    api.post<Substitution>(`/insights/substitutions/${id}/cancel`),
};
