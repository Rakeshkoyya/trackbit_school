"use client";

import { useEffect, useRef, useState } from "react";

/**
 * In-product guided tour shown right after registration (?tour=1). Spotlights
 * the key first actions — add team, create a board, add a task — anchored to
 * elements carrying a `data-tour` attribute (nav items + the create button).
 *
 * Client-only by design: it reads the URL/localStorage and measures the DOM, so
 * all state changes happen inside timeouts or event handlers (never synchronously
 * in an effect body) to satisfy the project's lint rules.
 */

type Step = { selector: string; title: string; body: string };

const STEPS: Step[] = [
  {
    selector: '[data-tour="nav-members"]',
    title: "Add your team",
    body: "Invite people here — each gets a join link you can share on WhatsApp or SMS.",
  },
  {
    selector: '[data-tour="nav-boards"]',
    title: "Create a board",
    body: "Boards hold your tasks. Make one for each area of work.",
  },
  {
    selector: '[data-tour="new-task"]',
    title: "Add your first task",
    body: "Use + to add a task — type a title and hit Enter. You can make it recurring too.",
  },
];

const SEEN_KEY = "tb_tour_seen";
const TW = 288; // tooltip width (px)

type Rect = { top: number; left: number; width: number; height: number };

function visibleTarget(selector: string): HTMLElement | null {
  const els = Array.from(document.querySelectorAll<HTMLElement>(selector));
  return (
    els.find((el) => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    }) ?? null
  );
}

export function GuidedTour() {
  const [active, setActive] = useState(false);
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const stepRef = useRef(0);

  // Start (deferred so targets have laid out + to keep setState out of the body).
  useEffect(() => {
    const wants = new URLSearchParams(window.location.search).get("tour") === "1";
    let seen = false;
    try {
      seen = localStorage.getItem(SEEN_KEY) === "1";
    } catch {
      seen = false;
    }
    if (!wants || seen) return;
    const id = window.setTimeout(() => {
      try {
        localStorage.setItem(SEEN_KEY, "1");
        window.history.replaceState(null, "", window.location.pathname);
      } catch {
        /* ignore */
      }
      start();
    }, 500);
    return () => window.clearTimeout(id);
    // Runs once on mount; `start` is stable for our purposes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keep the spotlight glued to its target while scrolling/resizing.
  useEffect(() => {
    if (!active) return;
    const onMove = () => measure(stepRef.current);
    window.addEventListener("resize", onMove);
    window.addEventListener("scroll", onMove, true);
    return () => {
      window.removeEventListener("resize", onMove);
      window.removeEventListener("scroll", onMove, true);
    };
  }, [active]);

  function measure(idx: number) {
    const el = visibleTarget(STEPS[idx].selector);
    if (!el) {
      setRect(null);
      return;
    }
    const r = el.getBoundingClientRect();
    setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
  }

  function goTo(idx: number, dir: 1 | -1) {
    let i = idx;
    while (i >= 0 && i < STEPS.length && !visibleTarget(STEPS[i].selector)) i += dir;
    if (i < 0 || i >= STEPS.length) {
      finish();
      return;
    }
    stepRef.current = i;
    setStep(i);
    measure(i);
  }

  function start() {
    setActive(true);
    goTo(0, 1);
  }
  function finish() {
    setActive(false);
    setRect(null);
  }

  if (!active) return null;

  const s = STEPS[step];
  const isLast = !STEPS.slice(step + 1).some((st) => visibleTarget(st.selector));

  // Tooltip placement: right of left-side nav, above bottom items, else below.
  let tipStyle: React.CSSProperties = {
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
  };
  let spotStyle: React.CSSProperties | null = null;
  if (rect) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    spotStyle = {
      top: rect.top - 6,
      left: rect.left - 6,
      width: rect.width + 12,
      height: rect.height + 12,
      boxShadow: "0 0 0 9999px rgba(28,27,25,0.55)",
    };
    const clampLeft = (x: number) => Math.max(12, Math.min(x, vw - TW - 12));
    if (rect.left < vw * 0.4 && rect.left + rect.width + TW + 24 < vw) {
      // to the right (desktop sidebar)
      tipStyle = { top: Math.max(12, rect.top), left: rect.left + rect.width + 14 };
    } else if (rect.top > vh * 0.6) {
      // above (bottom tabs / floating button)
      tipStyle = { bottom: vh - rect.top + 14, left: clampLeft(rect.left + rect.width / 2 - TW / 2) };
    } else {
      // below
      tipStyle = { top: rect.top + rect.height + 14, left: clampLeft(rect.left + rect.width / 2 - TW / 2) };
    }
  }

  return (
    <>
      {/* Click-blocker (transparent; dim comes from the spotlight box-shadow). */}
      <div className="fixed inset-0 z-[60]" />
      {spotStyle ? (
        <div
          style={spotStyle}
          className="pointer-events-none fixed z-[61] rounded-lg ring-2 ring-primary transition-all"
        />
      ) : null}
      <div
        style={{ width: TW, ...tipStyle }}
        className="tb-pop-in fixed z-[62] rounded-xl border border-border bg-card p-4 shadow-xl"
      >
        <p className="text-xs font-medium text-muted-foreground">
          Step {step + 1} of {STEPS.length}
        </p>
        <h3 className="mt-1 font-semibold">{s.title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{s.body}</p>
        <div className="mt-4 flex items-center justify-between">
          <button
            onClick={finish}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Skip
          </button>
          <div className="flex items-center gap-2">
            {step > 0 ? (
              <button
                onClick={() => goTo(stepRef.current - 1, -1)}
                className="rounded-md px-3 py-1 text-sm text-muted-foreground hover:bg-muted"
              >
                Back
              </button>
            ) : null}
            <button
              onClick={() => (isLast ? finish() : goTo(stepRef.current + 1, 1))}
              className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-primary-foreground"
            >
              {isLast ? "Done" : "Next"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
