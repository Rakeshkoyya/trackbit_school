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
  Daybook,
  ReachBoard,
  ExamsBoard,
  HomeworkBoard,
  OverviewBoard,
  PresenceBoard,
  PresenceMonth,
  StaffBoard,
  StaffImpact,
  StaffRecord,
  Substitution,
  SyllabusBoard,
  SyllabusPulse,
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

  // ── V1-14 presence ─────────────────────────────────────────────────────────
  /** The three rings and the three named blocks. Anchored on the last day the
   *  school actually ran, which the payload carries as `date`/`is_today`. */
  presence: (yearId?: string) =>
    api.get<PresenceBoard>(`/insights/presence${qs({ year_id: yearId })}`),
  /** The tab's whole visual + action layer in one read: the class × day grid,
   *  the three day-series, every student with an absence, the away staff, the
   *  admin desk and what stands out. */
  presenceMonth: (p: { yearId?: string; days?: number } = {}) =>
    api.get<PresenceMonth>(
      `/insights/presence/month${qs({ year_id: p.yearId, days: p.days })}`,
    ),

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

  /** The overview's syllabus block. Narrowable to a term without recomposing
   *  the other six modules — which is why it is not a field on `overview`. */
  syllabusPulse: (p: { yearId?: string; termId?: string } = {}) =>
    api.get<SyllabusPulse>(
      `/insights/syllabus/pulse${qs({ year_id: p.yearId, term_id: p.termId })}`,
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
  // ── V1-16 the day-book ─────────────────────────────────────────────────────
  /** The whole staff's day. `on` is any date — the board says what that date
   *  WAS, so a Sunday reads "the school was shut" rather than as an empty grid. */
  daybook: (onDate?: string, yearId?: string) =>
    api.get<Daybook>(`/insights/daybook${qs({ on: onDate, year_id: yearId })}`),
  /** The overview's block — the same computation, trimmed to what fits. */
  daybookGlimpse: (p: { onDate?: string; limit?: number } = {}) =>
    api.get<Daybook>(`/insights/daybook/glimpse${qs({ on: p.onDate, limit: p.limit })}`),
  /** One person's record. Admin reads anyone; a teacher only themselves.
   *  Pass `"me"` when the reader IS the subject — the session carries no
   *  membership id, so the server resolves it. */
  staffRecord: (memberId: string, p: { month?: string; onDate?: string } = {}) =>
    api.get<StaffRecord>(
      `/insights/staff/${memberId}/record${qs({ month: p.month, on: p.onDate })}`,
    ),

  substitutions: (onDate?: string) =>
    api.get<Substitution[]>(`/insights/substitutions${qs({ on_date: onDate })}`),
  cancelSubstitution: (id: string) =>
    api.post<Substitution>(`/insights/substitutions/${id}/cancel`),
};
