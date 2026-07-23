"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/api-client";
import { parentApi } from "@/lib/parent-api";

/** Phone → OTP, two steps. The number must already be on the school's roster
 *  as a guardian; verify creates/loads the parent account and signs in. */
export default function ParentLoginPage() {
  const { consumeSession } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);

  async function requestCode(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await parentApi.requestOtp(phone.trim());
      setStep("code");
      if (res.debug_code) {
        // Dev-only echo (OTP_ECHO_IN_RESPONSE) — real deploys never send this.
        toast.info(`Dev code: ${res.debug_code}`);
      } else {
        toast.success(
          res.channel === "sms" ? "Code sent by SMS." : "Code sent on WhatsApp.",
        );
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not send the code.");
    } finally {
      setBusy(false);
    }
  }

  async function verify(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      consumeSession(await parentApi.verifyOtp(phone.trim(), code.trim()));
      router.replace("/parent");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not verify the code.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      title="Parent sign in"
      subtitle="Use the mobile number the school has for you."
      footer={
        <span>
          Set a password earlier?{" "}
          <a href="/auth/login" className="font-medium text-primary">
            Sign in with password
          </a>
        </span>
      }
    >
      {step === "phone" ? (
        <form onSubmit={requestCode} className="space-y-4">
          <div>
            <Label htmlFor="phone">Mobile number</Label>
            <Input
              id="phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              placeholder="98765 43210"
              required
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={busy}>
            {busy ? "Sending…" : "Send code"}
          </Button>
        </form>
      ) : (
        <form onSubmit={verify} className="space-y-4">
          <div>
            <Label htmlFor="code">Enter the 6-digit code</Label>
            <Input
              id="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              placeholder="••••••"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="text-center text-lg tracking-[0.4em]"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Sent to {phone}.{" "}
              <button
                type="button"
                className="font-medium text-primary"
                onClick={() => {
                  setStep("phone");
                  setCode("");
                }}
              >
                Change number
              </button>
            </p>
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={busy}>
            {busy ? "Verifying…" : "Verify & sign in"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
