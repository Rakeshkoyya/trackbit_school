"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { disablePush, enablePush, getSubscription, pushSupported } from "@/lib/push";

/** `D-14` — web push for parents.
 *
 *  `D-08` moved guardian messaging in-app, and an in-app message only reaches a
 *  parent who *opens the app*. This is what makes the absence alert arrive
 *  instead of waiting to be found.
 *
 *  `S-62` is the honest half, and it is why the copy here promises nothing:
 *  push is best-effort. iOS will not deliver it at all until the site is added
 *  to the home screen, permission can be denied, and phones are off. So the
 *  school keeps its own list of who was not reached and the office phones those
 *  families — this switch improves the odds, it is not a guarantee, and telling
 *  a parent otherwise would be the wrong kind of reassurance.
 */
export function NotificationSettings() {
  const [supported, setSupported] = useState(false);
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Resolve browser support + current subscription after mount, with setState
    // in the async callback rather than the effect body (the house pattern —
    // see components/layout/notifications-toggle.tsx).
    const ok = pushSupported();
    getSubscription().then((s) => {
      setSupported(ok);
      setOn(!!s);
    });
  }, []);

  async function toggle() {
    setBusy(true);
    try {
      if (on) {
        await disablePush();
        setOn(false);
        toast.success("Alerts turned off.");
      } else {
        const ok = await enablePush();
        setOn(ok);
        toast[ok ? "success" : "error"](
          ok
            ? "Alerts on — we'll let you know about absences and homework."
            : "Your browser didn't allow alerts. You'll still see everything under Updates.",
        );
      }
    } catch {
      toast.error("Could not change alert settings.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="mb-1 text-sm font-semibold">Alerts on this phone</h2>
      <p className="mb-3 text-xs text-muted-foreground">
        {supported
          ? "Get a notification when your child is marked absent, or homework is set."
          : "This browser can't show alerts. Everything still appears under Updates."}
      </p>
      {supported ? (
        <Button variant={on ? "outline" : "primary"} size="sm" onClick={toggle} disabled={busy}>
          {busy ? "…" : on ? "Turn off alerts" : "Turn on alerts"}
        </Button>
      ) : null}
      {supported && !on ? (
        <p className="mt-2 text-[11px] text-muted-foreground">
          On iPhone, add this page to your Home Screen first.
        </p>
      ) : null}
    </section>
  );
}
