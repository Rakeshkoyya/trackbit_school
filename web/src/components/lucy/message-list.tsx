"use client";

// The conversation feed. On desktop the widgets live on the canvas next door,
// so bubbles here stay text + tool chips; on mobile (`inlineWidgets`) widgets
// render inside the flow between messages.

import { Check, Loader2, Sparkles, TriangleAlert } from "lucide-react";

import { ConfirmCard } from "@/components/lucy/confirm-card";
import { QuestionCard } from "@/components/lucy/question-card";
import { ViewCard } from "@/components/lucy/view-card";
import { WidgetFrame } from "@/components/lucy/widget-frame";
import { MarkdownWidget } from "@/components/lucy/widgets/simple";
import type { LucyMessage } from "@/lib/lucy-types";
import type { LiveTurn } from "@/components/lucy/use-lucy-stream";

export function ToolChip({ label, state }: { label: string; state: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted/40 px-2.5 py-1 text-xs text-muted-foreground">
      {state === "started"
        ? <Loader2 className="h-3 w-3 animate-spin" />
        : state === "error"
          ? <TriangleAlert className="h-3 w-3 text-warning" />
          : <Check className="h-3 w-3 text-success" />}
      {label}
    </span>
  );
}

export function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-primary px-3.5 py-2 text-sm text-primary-foreground">
        {content}
      </div>
    </div>
  );
}

export function AssistantText({ content }: { content: string }) {
  if (!content.trim()) return null;
  return (
    <div className="flex items-start gap-2">
      <span className="mt-1 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent">
        <Sparkles className="h-3.5 w-3.5 text-primary" />
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <MarkdownWidget data={{ md: content }} />
      </div>
    </div>
  );
}

export function MessageList({ messages, inlineWidgets, onAnswer }: {
  messages: LucyMessage[];
  inlineWidgets: boolean;
  /** Answer handler for a question on the LAST message; earlier questions render read-only. */
  onAnswer?: (text: string) => void;
}) {
  const last = messages[messages.length - 1];
  return (
    <div className="space-y-4">
      {messages.map((m) =>
        m.role === "user" ? (
          <UserBubble key={m.id} content={m.content} />
        ) : (
          <div key={m.id} className="space-y-2">
            <AssistantText content={m.content} />
            {inlineWidgets
              ? m.widgets.map((w) => (
                  <WidgetFrame key={w.id} id={w.id} type={w.type} title={w.title}
                    data={w.data} sourceTool={w.source_tool} pinned={w.pinned}
                    refreshedAt={w.refreshed_at} />
                ))
              : null}
            {m.question ? (
              <QuestionCard question={m.question}
                onAnswer={m.id === last?.id ? onAnswer : undefined} />
            ) : null}
            {m.view_id ? <ViewCard viewId={m.view_id} /> : null}
            {m.actions.map((a) => (
              <ConfirmCard key={a.id} id={a.id} tool={a.tool} summary={a.summary}
                paramsPreview={Object.entries(a.params).map(([k, v]) => ({
                  label: k.replace(/_/g, " "),
                  value: typeof v === "string" ? v : JSON.stringify(v),
                }))}
                status={a.status} error={a.error} />
            ))}
          </div>
        ),
      )}
    </div>
  );
}

export function LiveTurnView({ turn, inlineWidgets, onAnswer }: {
  turn: LiveTurn;
  inlineWidgets: boolean;
  onAnswer?: (text: string) => void;
}) {
  return (
    <div className="space-y-4">
      <UserBubble content={turn.userContent} />
      <div className="space-y-2">
        {turn.tools.length ? (
          <div className="flex flex-wrap gap-1.5 pl-8">
            {turn.tools.map((t, i) => <ToolChip key={i} label={t.label} state={t.state} />)}
          </div>
        ) : null}
        {inlineWidgets
          ? turn.widgets.map((w) => (
              <WidgetFrame key={w.id} id={w.id} type={w.type} title={w.title}
                data={w.data} sourceTool={w.source_tool} persisted={false} />
            ))
          : null}
        {turn.actions.map((a) => (
          <ConfirmCard key={a.id} id={a.id} tool={a.tool} summary={a.summary}
            paramsPreview={a.params_preview} status={a.status} />
        ))}
        <AssistantText content={turn.text} />
        {turn.question ? (
          <QuestionCard question={turn.question} onAnswer={onAnswer} />
        ) : null}
        {turn.view ? (
          <ViewCard viewId={turn.view.id} title={turn.view.title}
            summary={turn.view.summary} />
        ) : null}
        {turn.statusLabel ? (
          <p className="flex items-center gap-2 pl-8 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" /> {turn.statusLabel}
          </p>
        ) : null}
        {turn.error ? (
          <p className="flex items-center gap-2 pl-8 text-xs text-danger">
            <TriangleAlert className="h-3.5 w-3.5" /> {turn.error.message}
          </p>
        ) : null}
      </div>
    </div>
  );
}
