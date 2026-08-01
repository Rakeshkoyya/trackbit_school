"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet } from "@/components/ui/sheet";

/** D-46: completing a follow-up asks ONE optional question — what happened?
 *
 *  "Spoke to the father — fever, back Monday" is the fact the admin wanted when
 *  they pressed the button. Both actions complete the task; the note rides
 *  along only when given, so the one-tap complete stays one tap for everything
 *  that isn't about a person. */
export function OutcomeSheet({
  target,
  onClose,
  onConfirm,
}: {
  /** The row being completed, or null when closed. */
  target: { title: string; subjectName?: string | null } | null;
  onClose: () => void;
  onConfirm: (outcome: string | null) => void;
}) {
  const [text, setText] = useState("");

  const confirm = (withText: boolean) => {
    onConfirm(withText && text.trim() ? text.trim() : null);
    setText("");
  };

  return (
    <Sheet
      open={!!target}
      onOpenChange={(v) => {
        if (!v) {
          setText("");
          onClose();
        }
      }}
      title="Done — what happened?"
    >
      <div className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {target?.subjectName ? (
            <>
              About <span className="font-medium text-foreground">{target.subjectName}</span> —{" "}
              {target.title}
            </>
          ) : (
            target?.title
          )}
        </p>
        <textarea
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          placeholder="e.g. Spoke to the father — fever, back Monday"
          className="w-full resize-y rounded-md border border-input bg-card px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => confirm(false)}>
            Done, skip the note
          </Button>
          <Button onClick={() => confirm(true)} disabled={!text.trim()}>
            Save &amp; complete
          </Button>
        </div>
      </div>
    </Sheet>
  );
}
