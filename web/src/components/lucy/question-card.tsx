"use client";

// GA §4 — the clarifying-question card. A question ends the assistant's turn;
// tapping a chip sends the choice (label + carried id) as the next user
// message. Free-text answers just use the composer, so the card only renders
// the options. Chips disable once the conversation has moved on.

import { CircleHelp } from "lucide-react";

import type { LucyQuestion } from "@/lib/lucy-types";

/** The answer text a chip sends: human label plus the carried id, so the next
 * turn can use the id without re-searching. */
export function answerText(o: LucyQuestion["options"][number]): string {
  return o.value ? `${o.label} [${o.value}]` : o.label;
}

export function QuestionCard({ question, onAnswer }: {
  question: LucyQuestion;
  /** Omit to render read-only (history of an already-answered question). */
  onAnswer?: (text: string) => void;
}) {
  return (
    <div className="rounded-xl border border-primary/30 bg-accent/40 p-3">
      <p className="flex items-start gap-2 text-sm">
        <CircleHelp className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <span>{question.question}</span>
      </p>
      <div className="mt-2.5 flex flex-wrap gap-1.5 pl-6">
        {question.options.map((o, i) => (
          <button key={i} type="button" disabled={!onAnswer}
            onClick={onAnswer ? () => onAnswer(answerText(o)) : undefined}
            className={`rounded-full border px-3 py-1.5 text-left text-xs transition-colors ${
              onAnswer
                ? "border-primary/40 bg-card hover:border-primary hover:bg-accent"
                : "border-border bg-muted/30 text-muted-foreground"}`}>
            <span className="font-medium">{o.label}</span>
            {o.detail ? (
              <span className="ml-1.5 text-muted-foreground">{o.detail}</span>
            ) : null}
          </button>
        ))}
      </div>
    </div>
  );
}
