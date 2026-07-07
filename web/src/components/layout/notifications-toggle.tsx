"use client";

import { Bell, BellOff } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { disablePush, enablePush, getSubscription, pushSupported } from "@/lib/push";

/** Bell control in the topbar to enable/disable web push for this device. */
export function NotificationsToggle() {
  const [supported, setSupported] = useState(false);
  const [on, setOn] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Resolve browser support + current subscription after mount. setState lives
    // in the async callback (not the effect body) to avoid cascading renders.
    const ok = pushSupported();
    getSubscription().then((s) => {
      setSupported(ok);
      setOn(!!s);
    });
  }, []);

  if (!supported) return null;

  async function toggle() {
    setBusy(true);
    try {
      if (on) {
        await disablePush();
        setOn(false);
        toast("Notifications off for this device");
      } else {
        const ok = await enablePush();
        setOn(ok);
        toast[ok ? "success" : "error"](
          ok ? "Notifications on — we'll ping you here" : "Permission denied",
        );
      }
    } catch {
      toast.error("Could not change notification setting");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={toggle}
      disabled={busy}
      aria-label={on ? "Disable notifications" : "Enable notifications"}
      title={on ? "Notifications on" : "Enable notifications"}
    >
      {on ? <Bell className="h-4 w-4 text-primary" /> : <BellOff className="h-4 w-4 text-muted-foreground" />}
    </Button>
  );
}
