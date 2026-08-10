"use client";

import { useState } from "react";

import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

/** Click-to-edit text.
 *
 *  The setup and calendar screens were create-and-delete only, so correcting a
 *  typo meant deleting the row — which cascades into everything filed under it:
 *  a term's chapters lose their scoping, a class takes its students, syllabus,
 *  plans and timetable with it. Most of the PATCH routes behind these have
 *  existed since P0-C with no screen ever wired to them.
 *
 *  Commits on blur and on Enter, reverts on Escape, and never fires for an
 *  unchanged or emptied value — a blank name is a delete, and a delete should be
 *  the button that says so.
 */
export function InlineText({
  value, onSave, canEdit, placeholder, className, width = "w-40", title = "Click to edit",
}: {
  value: string;
  onSave: (next: string) => void;
  canEdit: boolean;
  placeholder?: string;
  className?: string;
  width?: string;
  title?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  if (!canEdit) return <span className={className}>{value || placeholder}</span>;

  if (editing) {
    const commit = () => {
      const next = draft.trim();
      setEditing(false);
      if (next && next !== value) onSave(next);
      else setDraft(value);
    };
    return (
      <Input
        autoFocus
        className={cn("h-7 text-sm", width)}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") commit();
          if (e.key === "Escape") { setDraft(value); setEditing(false); }
        }}
      />
    );
  }
  return (
    <button
      type="button"
      // Seed the box as editing STARTS rather than syncing it in an effect: while
      // the row is idle the draft is irrelevant, and after a save the server's
      // value — normalised or not — is what the next edit should begin from.
      onClick={() => { setDraft(value); setEditing(true); }}
      title={title}
      className={cn("-mx-1 rounded px-1 text-left hover:bg-muted/50", className)}
    >
      {value || <span className="text-muted-foreground">{placeholder ?? "set"}</span>}
    </button>
  );
}

/** The same, for a date. Saves on change — a date input is a picker, so there is
 *  no half-typed state worth waiting for. `label` lets a caller show a formatted
 *  date while still editing the ISO value the API wants. */
export function InlineDate({
  value, onSave, canEdit, label, className,
}: {
  value: string;
  onSave: (next: string) => void;
  canEdit: boolean;
  label?: string;
  className?: string;
}) {
  const [editing, setEditing] = useState(false);
  if (!canEdit) return <span className={className}>{label ?? value}</span>;
  if (editing) {
    return (
      <Input
        autoFocus
        type="date"
        className="h-7 w-36 text-xs"
        defaultValue={value}
        onBlur={() => setEditing(false)}
        onChange={(e) => {
          if (e.target.value) { onSave(e.target.value); setEditing(false); }
        }}
      />
    );
  }
  return (
    <button
      type="button"
      onClick={() => setEditing(true)}
      title="Click to change"
      className={cn("-mx-1 rounded px-1 hover:bg-muted/50", className)}
    >
      {label ?? value}
    </button>
  );
}
