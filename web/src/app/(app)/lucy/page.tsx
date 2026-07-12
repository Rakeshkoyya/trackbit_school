"use client";

// Lucy home — the on-demand dashboard: composer up top (a first message spins
// up a conversation and slides into the chat page), the member's pinned
// widgets, and their recent conversations.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, MessageSquareText, Sparkles, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";

import { Composer } from "@/components/lucy/composer";
import { PinBoard } from "@/components/lucy/pin-board";
import { showApiError } from "@/lib/errors";
import { lucyApi } from "@/lib/lucy-api";

function timeAgo(iso: string): string {
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export default function LucyHomePage() {
  const router = useRouter();
  const qc = useQueryClient();

  const { data: meta } = useQuery({ queryKey: ["lucy", "meta"], queryFn: lucyApi.meta });
  const { data: conversations } = useQuery({
    queryKey: ["lucy", "conversations"],
    queryFn: lucyApi.listConversations,
  });

  const start = useMutation({
    mutationFn: () => lucyApi.createConversation(),
    onError: (e) => showApiError(e, "Could not start a conversation."),
  });

  const remove = useMutation({
    mutationFn: (id: string) => lucyApi.deleteConversation(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["lucy"] }),
    onError: (e) => showApiError(e, "Could not delete the conversation."),
  });

  const onSend = async (content: string) => {
    const convo = await start.mutateAsync();
    sessionStorage.setItem(`lucy:first:${convo.id}`, content);
    router.push(`/lucy/${convo.id}`);
  };

  const aiOff = meta ? !meta.ai_configured : false;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-24 pt-6 lg:px-8 lg:pb-8">
      <div className="mb-6 text-center">
        <span className="mb-2 inline-flex h-11 w-11 items-center justify-center rounded-2xl bg-accent">
          <Sparkles className="h-5 w-5 text-primary" />
        </span>
        <h1 className="text-xl font-semibold">Ask Lucy</h1>
        <p className="text-sm text-muted-foreground">
          Attendance, syllabus pace, exams, students — answered with live widgets.
        </p>
      </div>

      {aiOff ? (
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-warning/50 bg-warning-soft/50 px-3 py-2.5 text-sm">
          <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
          <p>
            Lucy needs an AI key. Set <code className="rounded bg-muted px-1 text-xs">OPENROUTER_API_KEY</code> on
            the server to turn her on.
          </p>
        </div>
      ) : null}

      <div className="mb-8">
        <Composer onSend={onSend} disabled={aiOff || start.isPending} autoFocus
          suggestions={meta?.suggested_prompts ?? []} />
      </div>

      <section className="mb-8">
        <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Pinned</h2>
        <PinBoard />
      </section>

      {conversations?.length ? (
        <section>
          <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Recent chats</h2>
          <div className="overflow-hidden rounded-xl border border-border bg-card">
            {conversations.map((c) => (
              <div key={c.id}
                className="flex cursor-pointer items-center gap-3 border-b border-border px-3 py-2.5 transition-colors last:border-b-0 hover:bg-muted/40"
                role="button" tabIndex={0}
                onClick={() => router.push(`/lucy/${c.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    router.push(`/lucy/${c.id}`);
                  }
                }}>
                <MessageSquareText className="h-4 w-4 shrink-0 text-muted-foreground" />
                <p className="min-w-0 flex-1 truncate text-sm">{c.title ?? "New chat"}</p>
                <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(c.updated_at)}</span>
                <button type="button" title="Delete chat"
                  onClick={(e) => {
                    e.stopPropagation();
                    remove.mutate(c.id);
                  }}
                  className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-danger">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
