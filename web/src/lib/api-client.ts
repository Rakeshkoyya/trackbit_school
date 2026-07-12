/**
 * Thin API client for the TrackBit backend.
 * - Stores access/refresh tokens in localStorage.
 * - Attaches the bearer token, transparently refreshes once on 401, retries.
 * - Surfaces the backend's structured error envelope { error: { code, message } }.
 */

// Normalize the configured base URL so a stray trailing or duplicated slash in
// the env value (e.g. ".../:8000//api/v1") can't produce "//api/v1" and 404.
// Strip trailing slashes, then collapse runs of slashes except in the scheme.
const RAW_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const API_BASE = RAW_API_BASE.replace(/\/+$/, "").replace(
  /(https?:\/\/)|\/{2,}/g,
  (_match, scheme) => scheme ?? "/",
);

const ACCESS_KEY = "trackbit_access";
const REFRESH_KEY = "trackbit_refresh";

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;
  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export const tokenStore = {
  get access() {
    return typeof window === "undefined" ? null : localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return typeof window === "undefined" ? null : localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

type Options = {
  method?: string;
  body?: unknown;
  auth?: boolean; // attach bearer token (default true)
};

async function raw(path: string, opts: Options, accessOverride?: string): Promise<Response> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = accessOverride ?? tokenStore.access;
  if (opts.auth !== false && token) headers["Authorization"] = `Bearer ${token}`;

  return fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
}

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const err = data?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "error",
      err?.message ?? data?.detail ?? "Something went wrong.",
      err?.details ?? {},
    );
  }
  return data as T;
}

// Single-flight refresh. Refresh tokens are single-use/rotating on the backend
// (services/auth.py: the presented token is marked used and a new pair issued),
// so concurrent 401s must NOT each call /auth/refresh — the first would rotate
// the token and the rest would 401 on the now-spent token and clear the session,
// logging the user out. Sharing one in-flight promise spends the token exactly
// once; every caller awaits the same result and then retries with the new token.
let refreshInFlight: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  const refresh = tokenStore.refresh;
  if (!refresh) return false;
  const res = await raw("/auth/refresh", {
    method: "POST",
    body: { refresh_token: refresh },
    auth: false,
  });
  if (!res.ok) {
    tokenStore.clear();
    return false;
  }
  const data = await res.json();
  tokenStore.set(data.access_token, data.refresh_token);
  return true;
}

// Exported for the SSE client (lib/sse.ts), which streams with raw fetch and
// needs the same single-flight refresh-then-retry on 401.
export async function tryRefresh(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = performRefresh().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

export { API_BASE };

export async function apiFetch<T>(path: string, opts: Options = {}): Promise<T> {
  let res = await raw(path, opts);
  if (res.status === 401 && opts.auth !== false && tokenStore.refresh) {
    if (await tryRefresh()) {
      res = await raw(path, opts);
    }
  }
  return parse<T>(res);
}

async function rawUpload(path: string, form: FormData, accessOverride?: string): Promise<Response> {
  // No Content-Type header: the browser sets the multipart boundary.
  const headers: Record<string, string> = {};
  const token = accessOverride ?? tokenStore.access;
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, { method: "POST", headers, body: form });
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  let res = await rawUpload(path, form);
  if (res.status === 401 && tokenStore.refresh) {
    if (await tryRefresh()) res = await rawUpload(path, form);
  }
  return parse<T>(res);
}

export const api = {
  get: <T>(path: string, auth = true) => apiFetch<T>(path, { method: "GET", auth }),
  post: <T>(path: string, body?: unknown, auth = true) =>
    apiFetch<T>(path, { method: "POST", body, auth }),
  put: <T>(path: string, body?: unknown, auth = true) =>
    apiFetch<T>(path, { method: "PUT", body, auth }),
  patch: <T>(path: string, body?: unknown, auth = true) =>
    apiFetch<T>(path, { method: "PATCH", body, auth }),
  del: <T>(path: string, auth = true) => apiFetch<T>(path, { method: "DELETE", auth }),
  upload: <T>(path: string, form: FormData) => apiUpload<T>(path, form),
};
