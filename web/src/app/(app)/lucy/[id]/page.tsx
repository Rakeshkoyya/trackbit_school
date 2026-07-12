"use client";

// One Lucy conversation. Desktop (lg+): the founder's split view — a widget
// canvas fills the center and the conversation rides in a right rail with the
// composer pinned at its foot. Mobile: one column, widgets inline in the flow.
// Widgets render in BOTH containers and CSS picks one (hidden lg:block vs
// lg:hidden), so no viewport JS and no hydration mismatch.

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Sparkles } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useRef } from "react";

import { Composer } from "@/components/lucy/composer";
import {
  LiveTurnView,
  MessageList,
} from "@/components/lucy/message-list";
import { useLucyStream } from "@/components/lucy/use-lucy-stream";
import { WidgetFrame } from "@/components/lucy/widget-frame";
import { lucyApi } from "@/lib/lucy-api";

export default function LucyChatPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const qc = useQueryClient();
  const { send, turn, streaming } = useLucyStream(id);

  const { data: detail } = useQuery({
    queryKey: ["lucy", "conversation", id],
    queryFn: () => lucyApi.conversation(id),
  });

  // The landing composer hands the first message over via sessionStorage.
  const firstSent = useRef(false);
  useEffect(() => {
    if (firstSent.current) return;
    const first = sessionStorage.getItem(`lucy:first:${id}`);
    if (first) {
      sessionStorage.removeItem(`lucy:first:${id}`);
      firstSent.current = true;
      void send(first);
    }
  }, [id, send]);

  const messages = detail?.messages ?? [];
  const persistedWidgets = messages.flatMap((m) => m.widgets);
  const liveWidgets = turn?.widgets ?? [];

  // Keep both panes pinned to the newest content.
  const railEnd = useRef<HTMLDivElement>(null);
  const canvasEnd = useRef<HTMLDivElement>(null);
  useEffect(() => {
    railEnd.current?.scrollIntoView({ block: "end" });
    canvasEnd.current?.scrollIntoView({ block: "end" });
  }, [messages.length, turn?.text, liveWidgets.length, turn?.tools.length]);

  useEffect(() => {
    // A finished stream may have retitled the conversation (first message).
    if (!streaming) qc.invalidateQueries({ queryKey: ["lucy", "conversations"] });
  }, [streaming, qc]);

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] min-h-0 flex-col lg:flex-row">
      {/* Widget canvas — desktop only; mobile gets widgets inline in the rail. */}
      <div className="hidden min-w-0 flex-1 overflow-y-auto p-4 lg:block lg:p-6">
        {persistedWidgets.length || liveWidgets.length ? (
          <div className="mx-auto max-w-3xl space-y-4">
            {persistedWidgets.map((w) => (
              <WidgetFrame key={w.id} id={w.id} type={w.type} title={w.title}
                data={w.data} sourceTool={w.source_tool} pinned={w.pinned}
                refreshedAt={w.refreshed_at} />
            ))}
            {liveWidgets.map((w) => (
              <WidgetFrame key={w.id} id={w.id} type={w.type} title={w.title}
                data={w.data} sourceTool={w.source_tool} persisted={false} />
            ))}
            <div ref={canvasEnd} />
          </div>
        ) : (
          <div className="flex h-full items-center justify-center">
            <div className="text-center text-muted-foreground">
              <Sparkles className="mx-auto mb-2 h-6 w-6" />
              <p className="text-sm">Widgets appear here as Lucy answers.</p>
            </div>
          </div>
        )}
      </div>

      {/* Conversation rail (full width on mobile). */}
      <div className="flex min-h-0 w-full flex-col border-border lg:w-[400px] lg:shrink-0 lg:border-l">
        <div className="flex items-center gap-2 border-b border-border px-3 py-2">
          <Link href="/lucy" title="Back to Lucy home"
            className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <p className="min-w-0 flex-1 truncate text-sm font-semibold">
            {detail?.title ?? "New chat"}
          </p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          <div className="lg:hidden">
            <MessageList messages={messages} inlineWidgets />
            {turn ? <div className="mt-4"><LiveTurnView turn={turn} inlineWidgets /></div> : null}
          </div>
          <div className="hidden lg:block">
            <MessageList messages={messages} inlineWidgets={false} />
            {turn ? <div className="mt-4"><LiveTurnView turn={turn} inlineWidgets={false} /></div> : null}
          </div>
          {!messages.length && !turn ? (
            <p className="px-2 py-6 text-center text-sm text-muted-foreground">
              Ask about attendance, syllabus pace, a student, an exam…
            </p>
          ) : null}
          <div ref={railEnd} />
        </div>

        <div className="border-t border-border p-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] max-lg:mb-16">
          <Composer onSend={(c) => void send(c)} disabled={streaming} autoFocus
            placeholder={streaming ? "Lucy is answering…" : "Ask a follow-up…"} />
        </div>
      </div>
    </div>
  );
}
