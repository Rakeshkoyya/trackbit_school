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

export interface DemoRequest extends Required<Omit<DemoRequestPayload, "source">> {
  id: string;
  source: string;
  status: "new" | "contacted" | "scheduled" | "won" | "lost";
  created_at: string;
}

export const marketingApi = {
  // `false` = send no bearer token: this endpoint is public by design.
  bookDemo: (payload: DemoRequestPayload) =>
    api.post<DemoRequestAck>("/marketing/demo-requests", payload, false),
  demoRequests: () => api.get<DemoRequest[]>("/marketing/demo-requests"),
};
