"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/api-client";
import { parentApi, type ParentChildMatch, type SchoolLookup } from "@/lib/parent-api";

/** `D-13` — school code → class → section → child → date of birth.
 *
 *  This replaces phone-OTP as the *primary* path because `D-08` took WhatsApp
 *  out of this version: a login that depends on message delivery is a login the
 *  school cannot hand out. A code printed once in the diary works for every
 *  parent, including the one whose number the office recorded wrong.
 *
 *  Two things on this screen are load-bearing rather than cosmetic:
 *
 *  - **`S-55` the child step is a search box, never a list.** A dropdown of
 *    every child in a section hands the roster to anyone holding a code, before
 *    any password is entered. The server enforces the minimum too — this is the
 *    manners, not the guard.
 *  - **Nothing reveals whether a child exists** until the date of birth is
 *    right. A wrong code says "we don't recognise that code" and stops.
 *
 *  `Q-29` keeps OTP as the recovery door, linked at the bottom: it is the only
 *  way in for a family whose child has no date of birth on record.
 */
type Step = "code" | "class" | "child" | "dob";

const MIN_QUERY = 3;

export default function ParentLoginPage() {
  const { consumeSession } = useAuth();
  const router = useRouter();

  const [step, setStep] = useState<Step>("code");
  const [busy, setBusy] = useState(false);

  const [code, setCode] = useState("");
  const [school, setSchool] = useState<SchoolLookup | null>(null);
  const [grade, setGrade] = useState<string | null>(null);
  const [classId, setClassId] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  // Results are stored WITH the query they answer, so a slow response for
  // "Aa" can never be rendered under "Aarav" — and nothing has to be cleared
  // from inside an effect to keep that true.
  const [result, setResult] = useState<{ q: string; rows: ParentChildMatch[] }>({
    q: "",
    rows: [],
  });
  const [searching, setSearching] = useState(false);
  const [child, setChild] = useState<ParentChildMatch | null>(null);
  const [dob, setDob] = useState("");

  // Grades first, then sections — one decision per screen on a phone.
  const grades = Array.from(new Set((school?.classes ?? []).map((c) => c.name)));
  const sections = (school?.classes ?? []).filter((c) => c.name === grade);

  async function lookup(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await parentApi.lookupSchool(code.trim());
      setSchool(res);
      setStep("class");
      if (res.classes.length === 0) {
        toast.info("This school hasn't set up its classes yet — please call the office.");
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not find that school.");
    } finally {
      setBusy(false);
    }
  }

  // Debounced so a parent typing "Aar…" doesn't fire four searches, and so the
  // rate limit protects the roster rather than the parent.
  useEffect(() => {
    const q = query.trim();
    if (!school || !classId || q.length < MIN_QUERY) return;
    let live = true;
    const t = setTimeout(async () => {
      if (!live) return;
      setSearching(true);
      try {
        const rows = await parentApi.findChild(school.org_id, classId, q);
        if (live) setResult({ q, rows });
      } catch {
        if (live) setResult({ q, rows: [] });
      } finally {
        if (live) setSearching(false);
      }
    }, 300);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [query, school, classId]);

  async function signIn(e: React.FormEvent) {
    e.preventDefault();
    if (!child) return;
    setBusy(true);
    try {
      consumeSession(await parentApi.verifyDob(child.student_id, dob));
      router.replace("/parent");
    } catch (err) {
      if (err instanceof ApiError && err.code === "dob_not_on_record") {
        // The school's gap, not the parent's mistake — and never a dead end.
        toast.error(err.message, {
          action: { label: "Use my mobile", onClick: () => router.push("/parent/login/otp") },
        });
      } else {
        toast.error(err instanceof ApiError ? err.message : "Could not sign in.");
      }
    } finally {
      setBusy(false);
    }
  }

  function back() {
    if (step === "dob") {
      setChild(null);
      setDob("");
      setStep("child");
    } else if (step === "child") {
      setQuery("");
      setResult({ q: "", rows: [] });
      setClassId(null);
      setStep("class");
    } else if (step === "class") {
      setSchool(null);
      setGrade(null);
      setStep("code");
    }
  }

  const subtitle = {
    code: "Enter the code your school gave you.",
    class: school ? `${school.school_name} — which class?` : "",
    child: "Type the first few letters of your child's name.",
    dob: child ? `Enter ${child.full_name}'s date of birth.` : "",
  }[step];

  return (
    <AuthShell
      audience="parent"
      title="Parent sign in"
      subtitle={subtitle}
      footer={
        <span className="space-x-3">
          <a href="/parent/login/otp" className="font-medium text-primary">
            Sign in with mobile instead
          </a>
          <a href="/auth/login" className="text-muted-foreground">
            Staff sign in
          </a>
        </span>
      }
    >
      {step !== "code" && (
        <button
          type="button"
          onClick={back}
          className="mb-3 text-xs font-medium text-muted-foreground"
        >
          ← Back
        </button>
      )}

      {step === "code" && (
        <form onSubmit={lookup} className="space-y-4">
          <div>
            <Label htmlFor="code">School code</Label>
            <Input
              id="code"
              autoCapitalize="characters"
              autoComplete="off"
              placeholder="e.g. K7M2QP4"
              required
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              className="text-center text-lg tracking-[0.3em]"
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              Ask the school office if you don&apos;t have it.
            </p>
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={busy}>
            {busy ? "Checking…" : "Continue"}
          </Button>
        </form>
      )}

      {step === "class" && school && (
        <div className="space-y-4">
          {!grade ? (
            <div className="grid grid-cols-3 gap-2">
              {grades.map((g) => (
                <Button key={g} variant="outline" onClick={() => setGrade(g)}>
                  {g}
                </Button>
              ))}
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground">Class {grade} — section</p>
              <div className="grid grid-cols-3 gap-2">
                {sections.map((c) => (
                  <Button
                    key={c.class_id}
                    variant="outline"
                    onClick={() => {
                      setClassId(c.class_id);
                      setStep("child");
                    }}
                  >
                    {c.section ?? c.label ?? c.name}
                  </Button>
                ))}
              </div>
              <button
                type="button"
                onClick={() => setGrade(null)}
                className="text-xs font-medium text-muted-foreground"
              >
                Choose a different class
              </button>
            </div>
          )}
        </div>
      )}

      {step === "child" && (
        <div className="space-y-3">
          <div>
            <Label htmlFor="q">Your child&apos;s name</Label>
            <Input
              id="q"
              autoComplete="off"
              placeholder="First few letters"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          {query.trim().length < MIN_QUERY ? (
            <p className="text-xs text-muted-foreground">
              Type at least {MIN_QUERY} letters.
            </p>
          ) : searching || result.q !== query.trim() ? (
            <p className="text-xs text-muted-foreground">Searching…</p>
          ) : result.rows.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No match in this class. Check the spelling, or the class you picked.
            </p>
          ) : (
            <ul className="divide-y rounded-md border">
              {result.rows.map((mch) => (
                <li key={mch.student_id}>
                  <button
                    type="button"
                    className="w-full px-3 py-2.5 text-left text-sm hover:bg-muted"
                    onClick={() => {
                      setChild(mch);
                      setStep("dob");
                    }}
                  >
                    {mch.full_name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {step === "dob" && child && (
        <form onSubmit={signIn} className="space-y-4">
          <div>
            <Label htmlFor="dob">Date of birth</Label>
            <Input
              id="dob"
              type="date"
              required
              value={dob}
              onChange={(e) => setDob(e.target.value)}
            />
            <p className="mt-1.5 text-xs text-muted-foreground">
              As recorded on the school register.
              {school?.school_phone ? ` Stuck? Call ${school.school_phone}.` : ""}
            </p>
          </div>
          <Button type="submit" size="lg" className="w-full" disabled={busy || !dob}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
