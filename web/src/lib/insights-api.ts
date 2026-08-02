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
  CallBoard,
  ReachBoard,
  ExamsBoard,
  HomeworkBoard,
  OverviewBoard,
  StaffBoard,
  StaffImpact,
  Substitution,
  SyllabusBoard,
  SyllabusCheckpoint,
  SyllabusScope,
  TaskBoard,
} from "@/lib/insights-types";

// V1-7 reuses this — one query-string builder, not a second one in events-api.
export const qs = (params: Record<string, string | number | undefined | null>) => {
  const p = Object.entries(params).filter(([, v]) => v != null && v !== "");
  return p.length ? "?" + p.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&") : "";
};

export const insightsApi = {
  /** The overview: a block per module + the rail of what is waiting. */
  overview: (yearId?: string) =>
    api.get<OverviewBoard>(`/insights/overview${qs({ year_id: yearId })}`),

  attendance: (yearId?: string) =>
    api.get<AttendanceBoard>(`/insights/attendance${qs({ year_id: yearId })}`),
  /** V1-3 (S-08): needs-a-call (D-86 coloured) · drifting · chronic late ·
   *  left after lunch. */
  attendanceCalls: (yearId?: string) =>
    api.get<CallBoard>(`/insights/attendance/calls${qs({ year_id: yearId })}`),
  /** V1-11 (`S-62`): the families the school's own alerts did not reach.
   *  Removing WhatsApp did not remove the reach problem — it made it visible. */
  attendanceReach: (onDate?: string) =>
    api.get<ReachBoard>(`/insights/attendance/reach${qs({ on_date: onDate })}`),

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

  /** `type` filters on the school's own word for the exam type (`D-55`);
   *  `scale` on minor/major. Nothing in the payload is pooled across the two. */
  exams: (p: { yearId?: string; type?: string; scale?: string } = {}) =>
    api.get<ExamsBoard>(`/insights/exams${qs({ year_id: p.yearId, type: p.type, scale: p.scale })}`),

  // ── the action rail ────────────────────────────────────────────────────────
  /** Every rail button. The server appends a `followup_actions` row and refuses
   *  to fire the same action twice in one day — `already_done` says so. */
  action: (kind: ActionKind, body: ActionIn) =>
    api.post<ActionResult>(`/insights/actions/${kind}`, body),
  substitutions: (onDate?: string) =>
    api.get<Substitution[]>(`/insights/substitutions${qs({ on_date: onDate })}`),
  cancelSubstitution: (id: string) =>
    api.post<Substitution>(`/insights/substitutions/${id}/cancel`),
};
