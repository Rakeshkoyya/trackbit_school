import { api } from "@/lib/api-client";
import type { Me, Session } from "@/lib/types";

export interface RegisterOrgPayload {
  org_name: string;
  name: string;
  email: string;
  password: string;
  timezone: string;
}

export const authApi = {
  registerOrg: (payload: RegisterOrgPayload) =>
    api.post<Session>("/auth/register-org", payload, false),
  login: (identifier: string, password: string) =>
    api.post<Session>("/auth/login", { identifier, password }, false),
  verifyToken: (token: string) => api.post<Session>("/auth/verify", { token }, false),
  setPassword: (password: string, name?: string) =>
    api.post<{ message: string }>("/auth/set-password", { password, name: name || null }),
  /** V1-7 (D-56): staff DOB is self-entered here and NEVER imported. Passing
   *  `dob` (including null, to clear it) sets it; omitting it leaves it alone. */
  updateProfile: (name: string, dob?: string | null) =>
    api.patch<Me>("/auth/me", dob === undefined
      ? { name }
      : { name, date_of_birth: dob, set_date_of_birth: true }),
  changePassword: (current_password: string, new_password: string) =>
    api.post<{ message: string }>("/auth/change-password", { current_password, new_password }),
  forgotPassword: (email: string) =>
    api.post<{ message: string }>("/auth/forgot-password", { email }, false),
  resetPassword: (token: string, password: string) =>
    api.post<Session>("/auth/reset-password", { token, password }, false),
  me: () => api.get<Me>("/auth/me"),
  switchOrg: (orgId: string) => api.post<Session>("/auth/switch-org", { org_id: orgId }),
  createOrg: (org_name: string, timezone: string) =>
    api.post<Session>("/auth/orgs", { org_name, timezone }),
};
