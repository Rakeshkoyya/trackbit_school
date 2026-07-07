"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * Bottom-sheet on mobile, right-side panel on desktop (S5 spec).
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
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30 data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content
          aria-describedby={undefined}
          className={cn(
            "fixed z-50 bg-card shadow-xl focus:outline-none",
            // mobile: bottom sheet
            "inset-x-0 bottom-0 max-h-[92dvh] overflow-y-auto rounded-t-2xl",
            // desktop: right panel
            "lg:inset-y-0 lg:right-0 lg:left-auto lg:max-h-none lg:w-[420px] lg:rounded-none lg:rounded-l-2xl",
          )}
        >
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <Dialog.Title className="text-base font-semibold">{title}</Dialog.Title>
            <Dialog.Close className="rounded-md p-1 text-muted-foreground hover:bg-muted">
              <X className="h-5 w-5" />
            </Dialog.Close>
          </div>
          <div className="px-5 py-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
