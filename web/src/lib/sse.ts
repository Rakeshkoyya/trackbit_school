// fetch-based SSE client for Lucy's message stream.
//
// EventSource can't send an Authorization header, so we POST with fetch and
// read the body as a stream, splitting on the blank line between SSE frames.
// 401 gets the same single-flight refresh + one retry as the JSON client.

import { API_BASE, ApiError, tokenStore, tryRefresh } from "@/lib/api-client";

export interface SseEvent {
  event: string;
  data: unknown;
}

async function open(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  const token = tokenStore.access;
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
  });
}

/**
 * POST to an SSE endpoint and invoke `onEvent` per frame until the stream ends.
 * Throws ApiError for non-2xx responses (error envelope parsed when present).
 */
export async function fetchEventStream(
  path: string,
  body: unknown,
  onEvent: (ev: SseEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let res = await open(path, body, signal);
  if (res.status === 401 && tokenStore.refresh) {
    if (await tryRefresh()) res = await open(path, body, signal);
  }
  if (!res.ok || !res.body) {
    let code = "error";
    let message = "Something went wrong.";
    try {
      const data = await res.json();
      code = data?.error?.code ?? code;
      message = data?.error?.message ?? data?.detail ?? message;
    } catch {
      // non-JSON error body — keep the fallbacks
    }
    throw new ApiError(res.status, code, message);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = "";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      if (!event) continue;
      try {
        onEvent({ event, data: data ? JSON.parse(data) : null });
      } catch {
        // one malformed frame must not kill the whole stream
      }
    }
  }
}
