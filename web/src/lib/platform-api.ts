// Platform (super-admin) API — the layer above orgs. Only reachable when the
// signed-in user has is_super_admin; everyone else gets a 403.

import { api } from "@/lib/api-client";
import type {
  PlanChange,
  PlanPrice,
  PlanTier,
  Session,
  UpgradeRequest,
  UpgradeRequestDetail,
} from "@/lib/types";

export interface PlatformOrg {
  id: string;
  name: string;
  timezone: string;
  plan: PlanTier;
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

// ── the setup pack (SETUP-REDESIGN-PLAN §5) ────────────────────────────────
// One workbook carries a whole school. The operator downloads it blank, the
// school fills it in, the operator reviews and imports. Only `import` writes.
export type FindingSeverity = "blocker" | "warning" | "note";

export interface PackFinding {
  sheet: string;
  severity: FindingSeverity;
  message: string;
  fix: string;
  /** 1-based row in the sheet the school must open. Null for whole-sheet findings. */
  row: number | null;
  rule: string;
}

export interface PackSheetSummary {
  key: string;
  title: string;
  present: boolean;
  rows: number;
  blocked_rows: number;
}

export interface PackReview {
  /** Ready to IMPORT. Readiness to hand over is a different question, answered
   *  by the readiness report after the data is in. */
  ready: boolean;
  findings: PackFinding[];
  summaries: PackSheetSummary[];
  blockers: number;
  warnings: number;
  notes: number;
  total_rows: number;
  missing_sheets: string[];
  extra_sheets: string[];
}

export interface PackSheetResult {
  key: string;
  title: string;
  created: number;
  updated: number;
  skipped: number;
  notes: string[];
}

/** A staff login, shown ONCE — the password is hashed on the way in. */
export interface PackCredential {
  user_id: string;
  name: string;
  username: string;
  password: string;
}

/** One editable row on the logins step. No password: the generated one is
 *  already unreadable by the time this list is fetched, and a blank field on
 *  the form means *leave the existing one alone*. */
export interface StaffLoginRow {
  user_id: string;
  name: string;
  username: string | null;
  org_role: string;
}

export interface StaffLoginsResult {
  saved: number;
  renamed: number;
  passwords_set: number;
  rows: StaffLoginRow[];
}

export interface UsernameCheck {
  username: string;
  available: boolean;
  reason: string | null;
}

export interface PackImport {
  imported: boolean;
  review: PackReview;
  sheets: PackSheetResult[];
  credentials: PackCredential[];
}

export const platformApi = {
  orgs: () => api.get<PlatformOrg[]>("/platform/orgs"),

  // ── package tiers (`D-106`) ───────────────────────────────────────────────
  // There is no payment gateway. The operator reads the queue, phones the
  // school, takes the money, and sets the plan by hand with `assignPlan`.
  prices: () => api.get<PlanPrice[]>("/platform/plans/prices"),
  /** Change a LIST price. Appends a row; schools already on a plan keep the
   *  rate they were sold, so this never repricess anyone retroactively. */
  setPrice: (body: { plan: string; amount_paise_per_student: number; note?: string | null }) =>
    api.post<PlanPrice>("/platform/plans/prices", body),
  expiringPlans: (days = 30) =>
    api.get<PlatformOrg[]>(`/platform/plans/expiring?days=${days}`),

  assignPlan: (
    orgId: string,
    body: { plan: string; reason?: string | null; expires_at?: string | null },
  ) => api.post<PlanChange>(`/platform/orgs/${orgId}/plan`, body),
  planHistory: (orgId: string) =>
    api.get<PlanChange[]>(`/platform/orgs/${orgId}/plan/history`),

  upgrades: (status?: string) =>
    api.get<UpgradeRequest[]>(`/platform/upgrades${status ? `?status=${status}` : ""}`),
  upgrade: (id: string) => api.get<UpgradeRequestDetail>(`/platform/upgrades/${id}`),
  /** Append a remark, a status move, or both. Never edits an earlier row.
   *  These notes are ours — the school can never read them. */
  addUpgradeNote: (id: string, body: { note?: string | null; status_to?: string | null }) =>
    api.post<UpgradeRequestDetail>(`/platform/upgrades/${id}/notes`, body),
  createSchool: (payload: CreateSchoolPayload) =>
    api.post<CreateSchoolResult>("/platform/orgs", payload),
  enterOrg: (orgId: string) => api.post<Session>(`/platform/orgs/${orgId}/enter`),
  readiness: (orgId: string) => api.get<Readiness>(`/platform/orgs/${orgId}/readiness`),
  markHandedOver: (orgId: string) =>
    api.post<Readiness>(`/platform/orgs/${orgId}/handover`),

  // ── the setup pack ───────────────────────────────────────────────────────
  downloadSetupPack: (orgId: string, schoolName: string) =>
    api.download(`/platform/orgs/${orgId}/setup/template`,
      `TrackBit-Setup-Pack-${schoolName.replace(/[^\w -]/g, "").trim()
        .replace(/\s+/g, "-") || "School"}.xlsx`),

  /** The handover sheet the school keeps: who signs in where, the school code,
   *  and what they change themselves versus what they ask us for. Carries no
   *  passwords — those are hashed and cannot be read back. */
  downloadWelcomeSheet: (orgId: string, schoolName: string) =>
    api.download(`/platform/orgs/${orgId}/setup/welcome`,
      `TrackBit-Welcome-${schoolName.replace(/[^\w -]/g, "").trim()
        .replace(/\s+/g, "-") || "School"}.xlsx`),

  /** Reads the filled pack and reports what is wrong. Writes NOTHING, so the
   *  operator can send it back to the school and try again as often as needed. */
  reviewSetupPack: (orgId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.upload<PackReview>(`/platform/orgs/${orgId}/setup/review`, form);
  },

  /** Builds the school, in one transaction. Refuses on any blocker and returns
   *  the report instead. `replaceSyllabus` is off by default: a later upload
   *  ADDS chapters rather than destroying ones already being taught. */
  importSetupPack: (orgId: string, file: File, replaceSyllabus = false) => {
    const form = new FormData();
    form.append("file", file);
    form.append("replace_syllabus", String(replaceSyllabus));
    return api.upload<PackImport>(`/platform/orgs/${orgId}/setup/import`, form);
  },

  // ── the staff logins, between import and handover ────────────────────────
  /** Every staff account the school has, with the username each signs in with.
   *  Read back from the server rather than replayed from the import response,
   *  so a page reload mid-edit does not lose the section. */
  staffLogins: (orgId: string) =>
    api.get<StaffLoginRow[]>(`/platform/orgs/${orgId}/setup/logins`),

  /** `users.username` is GLOBAL, so this spans every school. It answers rather
   *  than erroring — an unavailable name is a normal state of the form.
   *  `forUserId` excludes the person being edited, or their own username would
   *  read as taken and no unchanged row could ever be saved. */
  checkUsername: (username: string, forUserId?: string) =>
    api.get<UsernameCheck>(
      `/platform/username-check?username=${encodeURIComponent(username)}${
        forUserId ? `&for_user_id=${forUserId}` : ""}`),

  /** The whole batch or none of it: half the staff holding logins from a
   *  handover sheet that is now wrong is worse than a refusal. A blank password
   *  leaves the existing one alone. */
  saveStaffLogins: (
    orgId: string,
    logins: { user_id: string; username: string; password?: string | null }[],
  ) => api.post<StaffLoginsResult>(`/platform/orgs/${orgId}/setup/logins`, { logins }),
};
