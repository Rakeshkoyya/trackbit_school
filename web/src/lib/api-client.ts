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
    // `super(message)` coerces with String(), so a non-string here becomes the
    // literal "[object Object]" and every toast downstream shows it. `parse()`
    // below is careful, but this is the chokepoint every ApiError passes
    // through, so the guarantee "an ApiError's message is readable text" is
    // enforced once, structurally, rather than trusted at each construction.
    super(typeof message === "string" && message.trim() ? message : "Something went wrong.");
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

/**
 * Turn whatever a failing response put in `detail` into a sentence.
 *
 * The backend's own errors are the structured envelope `{ error: { code,
 * message } }`, and `message` there is always a string. But FastAPI answers a
 * request whose BODY fails Pydantic validation before any of our code runs, and
 * that 422 has a different shape: `detail` is an ARRAY of objects
 * (`[{ loc, msg, type }]`). Handing that to `new ApiError(...)` gave `Error` a
 * non-string, which it coerced with `String()` — so every toast for a 422 read
 * exactly **"[object Object]"**, naming neither the field nor the problem.
 *
 * That is the error the founder hit saving a lesson detail and then could not
 * reproduce. It needs a malformed payload, so it surfaces only when some *other*
 * defect sends one — a `class_subject_id` that came through undefined for a
 * class with no subject mapped, an empty required field — which is exactly why
 * it looked intermittent. The trigger is worth fixing wherever it is found; a
 * validation error a person cannot read is a bug on its own, because it hides
 * the one clue that would have identified the trigger.
 *
 * Strings pass through, a Pydantic list becomes "field: message", and anything
 * else falls back rather than stringifying an object.
 */
function readDetail(detail: unknown): string | null {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((d) => {
        if (typeof d === "string") return d;
        if (!d || typeof d !== "object") return null;
        const { loc, msg } = d as { loc?: unknown; msg?: unknown };
        if (typeof msg !== "string") return null;
        // Drop the leading "body"/"query" frame — it names our transport, not
        // anything the person in front of the form can act on.
        const field = Array.isArray(loc)
          ? loc
            .filter((x) => typeof x === "string" && x !== "body" && x !== "query")
            .join(".")
          : "";
        return field ? `${field}: ${msg}` : msg;
      })
      .filter((x): x is string => !!x);
    if (parts.length) return parts.join(" \u00b7 ");
  }
  return null;
}

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  // A gateway 502/504 answers with HTML, not JSON. Letting JSON.parse throw here
  // raised a SyntaxError that was NOT an ApiError, so every caller's
  // `showApiError` fell through to its generic fallback and the status was lost.
  // Parse defensively and let the status carry the meaning instead.
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }
  if (!res.ok) {
    const body = (data ?? {}) as {
      error?: { code?: string; message?: string; details?: Record<string, unknown> };
      detail?: unknown;
    };
    const err = body.error;
    const message =
      (typeof err?.message === "string" && err.message ? err.message : null)
      ?? readDetail(body.detail)
      ?? (res.status >= 500
        ? "The server had a problem. Please try again."
        : "Something went wrong.");
    throw new ApiError(res.status, err?.code ?? "error", message, err?.details ?? {});
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

/** Authenticated file download → browser save dialog. Plain links can't carry
 *  the bearer token, so fetch → blob → a temporary anchor click. */
export async function apiDownload(path: string, filename: string): Promise<void> {
  let res = await raw(path, { method: "GET" });
  if (res.status === 401 && tokenStore.refresh) {
    if (await tryRefresh()) res = await raw(path, { method: "GET" });
  }
  if (!res.ok) {
    await parse(res); // throws the structured ApiError
    return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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
  download: (path: string, filename: string) => apiDownload(path, filename),
};
