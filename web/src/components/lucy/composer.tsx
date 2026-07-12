"use client";

// Lucy's message composer: auto-growing textarea, Enter to send
// (Shift+Enter for a newline), optional suggested-prompt chips.

import { ArrowUp } from "lucide-react";
import { useRef, useState } from "react";

export function Composer({
  onSend, disabled, placeholder = "Ask Lucy about your school…", suggestions = [], autoFocus,
}: {
  onSend: (content: string) => void;
  disabled?: boolean;
  placeholder?: string;
  suggestions?: string[];
  autoFocus?: boolean;
}) {
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);

  const submit = (text?: string) => {
    const content = (text ?? value).trim();
    if (!content || disabled) return;
    onSend(content);
    setValue("");
    if (ref.current) ref.current.style.height = "auto";
  };

  return (
    <div>
      {suggestions.length && !value ? (
        <div className="mb-2 flex flex-wrap gap-1.5">
          {suggestions.map((s) => (
            <button key={s} type="button" onClick={() => submit(s)} disabled={disabled}
              className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-muted hover:text-foreground disabled:opacity-50">
              {s}
            </button>
          ))}
        </div>
      ) : null}
      <div className="flex items-end gap-2 rounded-2xl border border-border bg-card p-2 shadow-sm focus-within:border-primary/50">
        <textarea
          ref={ref}
          rows={1}
          autoFocus={autoFocus}
          value={value}
          placeholder={placeholder}
          onChange={(e) => {
            setValue(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          className="max-h-40 min-h-[2.25rem] w-full resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground"
        />
        <button type="button" onClick={() => submit()} disabled={disabled || !value.trim()}
          title="Send"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-opacity disabled:opacity-40">
          <ArrowUp className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
