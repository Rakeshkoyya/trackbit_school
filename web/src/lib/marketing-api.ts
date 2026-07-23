// Marketing API — the one public, unauthenticated call in the app. Posted from
// the landing page's demo form; the leads are read back by super-admins only.

import { api } from "@/lib/api-client";

export interface DemoRequestPayload {
  school_name: string;
  contact_name: string;
  email: string;
  phone: string;
  city?: string | null;
  student_count?: number | null;
  message?: string | null;
  source?: string;
}

export interface DemoRequestAck {
  id: string;
  received: boolean;
}

export const DEMO_STATUSES = ["new", "contacted", "scheduled", "won", "lost"] as const;
export type DemoStatus = (typeof DEMO_STATUSES)[number];

export interface DemoRequest extends Required<Omit<DemoRequestPayload, "source">> {
  id: string;
  source: string;
  status: DemoStatus;
  created_at: string;
  /** How much working history the lead has, without opening it. */
  note_count: number;
  last_activity_at: string | null;
}

/** One append-only history entry: a remark, a status move, or both. */
export interface DemoRequestNote {
  id: string;
  created_at: string;
  author_name: string | null;
  note: string | null;
  status_from: DemoStatus | null;
  status_to: DemoStatus | null;
}

export interface DemoRequestDetail extends DemoRequest {
  notes: DemoRequestNote[];
}

export interface DemoRequestUpdate {
  status?: DemoStatus;
  note?: string;
}

export const marketingApi = {
  // `false` = send no bearer token: this endpoint is public by design.
  bookDemo: (payload: DemoRequestPayload) =>
    api.post<DemoRequestAck>("/marketing/demo-requests", payload, false),
  demoRequests: () => api.get<DemoRequest[]>("/marketing/demo-requests"),
  demoRequest: (id: string) => api.get<DemoRequestDetail>(`/marketing/demo-requests/${id}`),
  addDemoRequestNote: (id: string, payload: DemoRequestUpdate) =>
    api.post<DemoRequestDetail>(`/marketing/demo-requests/${id}/notes`, payload),
};
