"use client";

// The Lucy stream reducer: POST one message, fold the SSE events into local
// state the chat page renders live, then invalidate the conversation query so
// the persisted truth replaces the transient stream state.

import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import type { LucyStreamEvent, StreamAction, StreamWidget } from "@/lib/lucy-types";
import { fetchEventStream } from "@/lib/sse";

export interface LiveTurn {
  userContent: string;
  statusLabel: string | null;
  tools: { name: string; state: string; label: string }[];
  text: string;
  widgets: StreamWidget[];
  actions: StreamAction[];
  error: { code: string; message: string } | null;
}

const emptyTurn = (userContent: string): LiveTurn => ({
  userContent, statusLabel: null, tools: [], text: "",
  widgets: [], actions: [], error: null,
});

export function useLucyStream(conversationId: string) {
  const qc = useQueryClient();
  const [turn, setTurn] = useState<LiveTurn | null>(null);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const send = useCallback(async (content: string) => {
    if (!content.trim()) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setTurn(emptyTurn(content));
    setStreaming(true);
    try {
      await fetchEventStream(
        `/lucy/conversations/${conversationId}/messages`,
        { content },
        (raw) => {
          const ev = raw as LucyStreamEvent;
          setTurn((t) => {
            if (!t) return t;
            switch (ev.event) {
              case "status":
                return { ...t, statusLabel: ev.data.label };
              case "tool": {
                const tools = [...t.tools];
                const i = tools.findIndex((x) => x.name === ev.data.name && x.state === "started");
                if (i >= 0 && ev.data.state !== "started") tools[i] = ev.data;
                else tools.push(ev.data);
                return { ...t, tools, statusLabel: null };
              }
              case "text":
                return { ...t, text: t.text + ev.data.delta, statusLabel: null };
              case "widget":
                return { ...t, widgets: [...t.widgets, ev.data], statusLabel: null };
              case "action":
                return { ...t, actions: [...t.actions, ev.data], statusLabel: null };
              case "error":
                return { ...t, error: ev.data, statusLabel: null };
              default:
                return t;
            }
          });
        },
        controller.signal,
      );
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        setTurn((t) => t && {
          ...t,
          error: t.error ?? { code: "network", message: "The connection dropped — please retry." },
        });
      }
    } finally {
      setStreaming(false);
      // The persisted message replaces the live turn once the query refetches.
      await qc.invalidateQueries({ queryKey: ["lucy", "conversation", conversationId] });
      await qc.invalidateQueries({ queryKey: ["lucy", "conversations"] });
      setTurn(null);
    }
  }, [conversationId, qc]);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  return { send, stop, turn, streaming };
}
