// V1-7 — events & dates: the what's-on feed, the approval sheet, the catalogue.
//
// One feed shape for all three sources (a birthday, the school's own calendar
// row, an approved observance), because they are one computation with many
// renderings (ux §9). A surface that needs to tell them apart reads `source`.

import { api } from "@/lib/api-client";
import { qs } from "@/lib/insights-api";

export type FeedSource = "birthday" | "staff_birthday" | "calendar";
export type LockLevel = "closed" | "periods" | "open";
export type CalendarEventKind = "holiday" | "exam_block" | "event" | "celebration";

export interface FeedItem {
  source: FeedSource;
  on_date: string;
  /** Set only when the shown date differs from the real one — the vacation
   *  birthday rolled to the nearest working day (S-128). The copy must say so;
   *  quietly moving a child's birthday is worse than not showing it. */
  actual_date: string | null;
  title: string;
  detail: string | null;
  event_id: string | null;
  event_type: CalendarEventKind | null;
  affects_teaching: boolean | null;
  blocks_periods: number[] | null;
  student_id: string | null;
  member_id: string | null;
  class_label: string | null;
  days_away: number;
}

export interface WhatsOn {
  date: string;
  today: FeedItem[];
  upcoming: FeedItem[];
  /** S-124 — the figure with its denominator, so an empty card says how to
   *  fill it instead of looking broken. */
  dob_known: number;
  dob_total: number;
  pending_suggestions: number;
}

export interface Suggestion {
  id: string;
  key: string;
  name: string;
  date: string;
  end_date: string | null;
  kind: "holiday" | "festival" | "observance";
  tier: "major" | "minor";
  prep_days: number;
  tradition: string | null;
  /** S-150 — where this date came from. Rendered on the row: the admin
   *  approving it is the last human in the chain. */
  source: string;
  note: string | null;
  days_away: number;
  approved_count: number;
}

export interface ApprovePayload {
  title?: string | null;
  start_date: string;
  end_date?: string | null;
  lock: LockLevel;
  blocks_periods?: number[] | null;
  event_type?: CalendarEventKind;
  note?: string | null;
}

export interface CostMove {
  class_label: string;
  subject_name: string;
  from_status: string;
  to_status: string;
}

export interface LockCost {
  days_lost: number;
  periods_lost: number;
  working_days: number;
  already_blocked: number;
  moves: CostMove[];
  unaffected: number;
  sentence: string;
}

export interface Decision {
  id: string;
  observance_key: string;
  action: "approved" | "dismissed";
  calendar_event_id: string | null;
  note: string | null;
}

// ── the platform catalogue (super-admin) ──────────────────────────────────
export interface Observance {
  id: string;
  key: string;
  name: string;
  date: string;
  end_date: string | null;
  kind: "holiday" | "festival" | "observance";
  tier: "major" | "minor";
  prep_days: number;
  /** V1-19 — the set of states that observe this. null/empty = all India. */
  states: string[] | null;
  board: string | null;
  tradition: string | null;
  source: string;
  note: string | null;
  is_active: boolean;
  decided_count: number;
}

export type ObservancePayload = Omit<Observance, "id" | "decided_count"> & {
  key?: string;
};

export const eventsApi = {
  whatsOn: (p: { onDate?: string; horizon?: number } = {}) =>
    api.get<WhatsOn>(`/events/whats-on${qs({ on_date: p.onDate, horizon: p.horizon })}`),
  suggestions: (horizon?: number) =>
    api.get<Suggestion[]>(`/events/suggestions${qs({ horizon })}`),
  approve: (id: string, body: ApprovePayload) =>
    api.post<Decision>(`/events/suggestions/${id}/approve`, body),
  dismiss: (id: string, note?: string) =>
    api.post<Decision>(`/events/suggestions/${id}/dismiss`, { note: note ?? null }),
  /** S-143 — what this lock removes, asked before it is committed. */
  cost: (body: {
    academic_year_id: string;
    start_date: string;
    end_date?: string | null;
    lock: LockLevel;
    blocks_periods?: number[] | null;
  }) => api.post<LockCost>("/events/cost", body),

  catalogue: (p: { year?: number; state?: string; q?: string } = {}) =>
    api.get<Observance[]>(`/platform/observances${qs({ year: p.year, state: p.state, q: p.q })}`),
  createObservance: (body: Partial<ObservancePayload>) =>
    api.post<Observance>("/platform/observances", body),
  updateObservance: (id: string, body: Partial<ObservancePayload>) =>
    api.put<Observance>(`/platform/observances/${id}`, body),
  retireObservance: (id: string) => api.del<void>(`/platform/observances/${id}`),
  /** S-151 — a year from one source, upserted on (key, date), so re-running a
   *  corrected file FIXES every school rather than suggesting twice to all of
   *  them. The rows are parsed and reviewed in the browser first; this endpoint
   *  never sees anything a human has not looked at. */
  importObservances: (source: string, entries: Partial<ObservancePayload>[]) =>
    api.post<{ created: number; updated: number }>(
      "/platform/observances/bulk", { source, entries }),
};
