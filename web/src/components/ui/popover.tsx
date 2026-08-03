"use client";

// A popover positioned against an anchor rect, rendered through a portal.
//
// Extracted from `boards/board-table.tsx` (V1-14) so the dashboard's tables can
// use the picker language the task module already established rather than
// growing a second one. The portal is the whole point: these open inside
// `overflow-x-auto` table scrollers, and a popover that renders in place gets
// clipped by its own container.

import { createPortal } from "react-dom";

export function Popover({
  open, onClose, rect, width = 240, children,
}: {
  open: boolean;
  onClose: () => void;
  /** The anchor's bounding rect, captured on the click that opened it. */
  rect: DOMRect | null;
  width?: number;
  children: React.ReactNode;
}) {
  if (!open || typeof document === "undefined" || !rect) return null;
  const left = Math.max(12, Math.min(rect.left, window.innerWidth - width - 12));
  const spaceBelow = window.innerHeight - rect.bottom;
  const pos: React.CSSProperties =
    spaceBelow < 300
      ? { bottom: window.innerHeight - rect.top + 4, left, width }
      : { top: rect.bottom + 4, left, width };

  return createPortal(
    <>
      <div className="fixed inset-0 z-[55]" onClick={onClose} />
      <div
        style={{ position: "fixed", ...pos }}
        className="z-[56] rounded-lg border border-border bg-card p-2 shadow-lg"
      >
        {children}
      </div>
    </>,
    document.body,
  );
}
