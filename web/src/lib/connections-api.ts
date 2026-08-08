/**
 * Agent connections — the Settings screen that lets a school connect Claude.
 *
 * Two credential shapes live behind this, and the screen shows both because
 * different clients need different things:
 *  - an **OAuth client** (Client ID + Secret) for claude.ai, Desktop and mobile,
 *    which run the authorization-code flow and will not take a bare token;
 *  - a **connector token** (`tbk_…`) for Claude Code and Cursor, which send a
 *    static Authorization header.
 */
import { api } from "@/lib/api-client";

export type OAuthClient = {
  id: string;
  name: string;
  client_id: string;
  scopes: string[];
  mode: "read" | "read_write";
  redirect_uris: string[];
  confidential: boolean;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
};

export type OAuthClientCreated = {
  client: OAuthClient;
  /** Shown exactly once. Not stored anywhere it can be read back. */
  client_secret: string | null;
};

export type ApiTokenRow = {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  mode: "read" | "read_write";
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  last_used_ip: string | null;
  revoked_at: string | null;
};

export type ApiTokenCreated = { token: ApiTokenRow; secret: string };

export type ConsentSummary = {
  client_name: string;
  org_name: string;
  member_name: string;
  mode: "read" | "read_write";
  scopes: string[];
  tool_count: number;
  domains: string[];
  writes: string[];
};

export type ConsentGrant = {
  client_id: string;
  redirect_uri: string;
  code_challenge: string;
  code_challenge_method: string;
  scope?: string | null;
  state?: string | null;
  resource?: string | null;
  issuer?: string | null;
};

/** The selectable toolsets, in the order the backend declares them. */
export const TOOLSETS = [
  { name: "students", label: "Students", hint: "Directory, growth, timeline, report cards" },
  { name: "attendance", label: "Attendance", hint: "The register and absence reasons" },
  { name: "capture", label: "Daily capture", hint: "My day, lesson logs, homework, checks" },
  { name: "planning", label: "Planning", hint: "Syllabus, plans, forecast, timetable" },
  { name: "exams", label: "Exams", hint: "Cycles, scores, trends and analysis" },
  { name: "bands", label: "Support bands", hint: "A/B/C tiers — staff-only, never shown to parents" },
  { name: "staff", label: "Staff", hint: "Directory, leave, timesheets, substitutions" },
  { name: "tasks", label: "Tasks", hint: "Boards, tasks and recurring templates" },
  { name: "insights", label: "Insights", hint: "The admin dashboards and daily report" },
  { name: "sessions", label: "Sessions", hint: "Hostel and activity sessions" },
  // `pending` = the toolset exists but none of its tools are built yet, so
  // ticking it grants a real but currently empty permission. Say so rather than
  // offering it as though it already does something.
  {
    name: "events",
    label: "Events",
    hint: "Observances and what's on — no tools built yet",
    pending: true,
  },
  { name: "fees", label: "Fees", hint: "Collection and structures — admin only" },
] as const;

/** `core` is always granted and cannot be switched off, so it isn't a checkbox. */
export const ALWAYS_ON_TOOLSET = "core";

/** Who may create a connection. `off` is the default for a new school. */
export type AgentAccess = "off" | "admins" | "all_staff";

export const connectionsApi = {
  /** Only the one field this screen owns; the settings payload is much larger. */
  agentAccess: () =>
    api.get<{ agent_access: AgentAccess }>("/org/settings").then((s) => s.agent_access),
  setAgentAccess: (agent_access: AgentAccess) =>
    api.patch<{ agent_access: AgentAccess }>("/org/settings", { agent_access }),

  listClients: () => api.get<OAuthClient[]>("/org/oauth-clients"),
  createClient: (body: {
    name: string;
    scopes: string[];
    mode: "read" | "read_write";
    confidential?: boolean;
  }) => api.post<OAuthClientCreated>("/org/oauth-clients", body),
  revokeClient: (id: string) => api.del<OAuthClient>(`/org/oauth-clients/${id}`),

  listTokens: () => api.get<ApiTokenRow[]>("/org/api-tokens"),
  createToken: (body: {
    name: string;
    scopes: string[];
    mode: "read" | "read_write";
    expires_days?: number | null;
  }) => api.post<ApiTokenCreated>("/org/api-tokens", body),
  revokeToken: (id: string) => api.del<ApiTokenRow>(`/org/api-tokens/${id}`),

  consentSummary: (clientId: string, scope?: string | null) =>
    api.get<ConsentSummary>(
      `/org/oauth-consent?client_id=${encodeURIComponent(clientId)}` +
        (scope ? `&scope=${encodeURIComponent(scope)}` : ""),
    ),
  grantConsent: (body: ConsentGrant) =>
    api.post<{ redirect_to: string }>("/org/oauth-consent", body),
};

/**
 * The origin the API is served from — what the user pastes into Claude.
 *
 * Derived from the configured API base rather than hardcoded, because it is
 * `http://localhost:8000` in development and `https://api.trackbit.in` in
 * production, and the value has to match the server's own idea of itself or the
 * OAuth audience check will refuse the token.
 */
export function serverOrigin(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
  try {
    return new URL(base).origin;
  } catch {
    return base.replace(/\/api\/v1\/?$/, "");
  }
}

export function mcpUrl(): string {
  return `${serverOrigin()}/mcp`;
}
