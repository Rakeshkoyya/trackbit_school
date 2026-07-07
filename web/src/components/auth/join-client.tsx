"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";

import { AuthShell } from "@/components/auth/auth-shell";
import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/api-client";
import { authApi } from "@/lib/auth-api";

/** Redeems an invite token, then lands the user on Home (or set-password). */
export function JoinClient({ token }: { token: string }) {
  const { consumeSession } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false); // guard React StrictMode double-invoke (token is single-use)

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;
    (async () => {
      try {
        const session = await authApi.verifyToken(token);
        consumeSession(session);
        router.replace(session.must_set_password ? "/auth/set-password" : "/home");
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "This link could not be opened.",
        );
      }
    })();
  }, [token, consumeSession, router]);

  if (error) {
    return (
      <AuthShell
        title="Link problem"
        subtitle={error}
        footer={
          <Link href="/auth/login" className="font-medium text-primary">
            Go to sign in
          </Link>
        }
      >
        <p className="text-sm text-muted-foreground">
          Ask whoever invited you to send a fresh link.
        </p>
      </AuthShell>
    );
  }

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-3 px-4">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      <p className="text-sm text-muted-foreground">Opening TrackBit…</p>
    </main>
  );
}
