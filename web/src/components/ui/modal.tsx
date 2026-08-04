"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Centred dialog — the sibling of `Sheet`.
 *
 * `Sheet` is for *acting on one thing* (approve this date, edit this row), so it
 * docks to the right and leaves the page visible behind it. This is for
 * *looking something up*: a reference table you open, scan, filter and close
 * without changing anything. That reading task wants the full width of the
 * viewport's centre, not a 420px column.
 *
 * Still scrolls its own body rather than the page, and still collapses to a
 * near-full-screen panel on mobile, where "centred" stops meaning anything.
 */
export function Modal({
  open,
  onOpenChange,
  title,
  description,
  children,
  size = "lg",
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  size?: "md" | "lg" | "xl";
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 flex w-[calc(100vw-1.5rem)] -translate-x-1/2 -translate-y-1/2",
            "max-h-[88dvh] flex-col overflow-hidden rounded-2xl bg-card shadow-2xl focus:outline-none",
            size === "md" && "sm:max-w-lg",
            size === "lg" && "sm:max-w-3xl",
            size === "xl" && "sm:max-w-5xl",
          )}
        >
          <div className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="text-base font-semibold">{title}</Dialog.Title>
              {description ? (
                <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
              ) : null}
            </div>
            <Dialog.Close className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>
          {/* min-h-0 so the flex child can actually shrink and scroll rather
              than pushing the dialog past its max height. */}
          <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
