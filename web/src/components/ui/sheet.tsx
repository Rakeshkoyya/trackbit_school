"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * A centred dialog. Bottom sheet on mobile.
 *
 * **Founder, 2026-08-08: this used to dock to the right on desktop** (the S5
 * spec's "act on one thing, leave the page visible behind it"). It is centred
 * now, everywhere, because in practice the tall 420px column fought its own
 * contents: forms with two columns of fields, week pickers and tables all had
 * to be squeezed into a strip while most of the screen sat empty behind a
 * scrim nobody was reading.
 *
 * Deliberately kept as its own component rather than folded into `Modal`:
 * thirty-one call sites pass `title` and body content shaped for this padding,
 * and `Modal` is a wider "look something up" surface with its own sizes. Same
 * shape, different jobs — but they now agree on WHERE a dialog appears, which
 * is the thing that was inconsistent.
 *
 * Controlled via `open` / `onOpenChange`.
 */
export function Sheet({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            "fixed z-50 flex flex-col bg-card shadow-2xl focus:outline-none",
            // Mobile: still a bottom sheet — a centred box on a phone leaves
            // dead space above and below and puts the controls further from
            // the thumb.
            "inset-x-0 bottom-0 max-h-[92dvh] rounded-t-2xl",
            // Small screens and up: centred.
            "sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-1/2",
            "sm:max-h-[88dvh] sm:w-[calc(100vw-3rem)] sm:max-w-xl",
            "sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-2xl",
          )}
        >
          <div className="flex shrink-0 items-center justify-between border-b border-border px-5 py-4">
            <Dialog.Title className="text-base font-semibold">{title}</Dialog.Title>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>
          {/* min-h-0 so this child can actually shrink and scroll rather than
              pushing the dialog past its max height. */}
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
