// Platform (super-admin) API — the layer above orgs. Only reachable when the
// signed-in user has is_super_admin; everyone else gets a 403.

import { api } from "@/lib/api-client";
import type { Session } from "@/lib/types";

export interface PlatformOrg {
  id: string;
  name: string;
  timezone: string;
  plan: "free" | "pro";
  created_at: string;
  member_count: number;
  student_count: number;
  class_count: number;
  active_year: string | null;
  last_active_at: string | null;
  // V1-2: the parent-login code (S-57) + handover state (§6 ⑤).
  school_code: string | null;
  handed_over_at: string | null;
}

export interface CreateSchoolPayload {
  org_name: string;
  timezone: string;
  // V1-2 §6 ①: state + board scope the observance catalogue (D-61).
  address?: string | null;
  state?: string | null;
  board?: string | null;
  admin_name: string;
  admin_email: string;
  admin_password: string;
}

export interface CreateSchoolResult {
  org: PlatformOrg;
  admin_email: string;
  admin_name: string;
  school_code: string | null;
}

// ── the readiness report (V1-2, §6 ⑤) ──────────────────────────────────────
export interface ReadinessCheck {
  key: string;
  title: string;
  status: "ok" | "warn";
  summary: string;
  count: number | null;
  total: number | null;
  link: string | null;
  items: string[];
}

export interface Readiness {
  org_id: string;
  org_name: string;
  school_code: string | null;
  ready_count: number;
  total: number;
  handed_over_at: string | null;
  checks: ReadinessCheck[];
}

export const platformApi = {
  orgs: () => api.get<PlatformOrg[]>("/platform/orgs"),
  createSchool: (payload: CreateSchoolPayload) =>
    api.post<CreateSchoolResult>("/platform/orgs", payload),
  enterOrg: (orgId: string) => api.post<Session>(`/platform/orgs/${orgId}/enter`),
  readiness: (orgId: string) => api.get<Readiness>(`/platform/orgs/${orgId}/readiness`),
  markHandedOver: (orgId: string) =>
    api.post<Readiness>(`/platform/orgs/${orgId}/handover`),
};
