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
}

export interface CreateSchoolPayload {
  org_name: string;
  timezone: string;
  admin_name: string;
  admin_email: string;
  admin_password: string;
}

export interface CreateSchoolResult {
  org: PlatformOrg;
  admin_email: string;
  admin_name: string;
}

export const platformApi = {
  orgs: () => api.get<PlatformOrg[]>("/platform/orgs"),
  createSchool: (payload: CreateSchoolPayload) =>
    api.post<CreateSchoolResult>("/platform/orgs", payload),
  enterOrg: (orgId: string) => api.post<Session>(`/platform/orgs/${orgId}/enter`),
};
