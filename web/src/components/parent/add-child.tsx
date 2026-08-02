"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api-client";
import { parentApi, type ParentChildMatch, type SchoolLookup } from "@/lib/parent-api";

/** `Q-25` (b) — *"Add another child"*.
 *
 *  Per-child DOB login would otherwise mean a parent of three signing in three
 *  times, which is how a portal gets abandoned. Instead each child is **proved
 *  once**, with their own date of birth, and the sibling switcher that already
 *  exists then works exactly as it does today.
 *
 *  Note what this deliberately does NOT do: proving one child never hands over
 *  a sibling automatically, even when the family shares one phone number. One
 *  proof, one child.
 */
const MIN_QUERY = 3;

export function AddChild() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const [code, setCode] = useState("");
  const [school, setSchool] = useState<SchoolLookup | null>(null);
  const [classId, setClassId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  // Keyed to the query it answers — see the login page for why.
  const [result, setResult] = useState<{ q: string; rows: ParentChildMatch[] }>({
    q: "",
    rows: [],
  });
  const [child, setChild] = useState<ParentChildMatch | null>(null);
  const [dob, setDob] = useState("");

  useEffect(() => {
    const q = query.trim();
    if (!school || !classId || q.length < MIN_QUERY) return;
    let live = true;
    const t = setTimeout(async () => {
      if (!live) return;
      try {
        const rows = await parentApi.findChild(school.org_id, classId, q);
        if (live) setResult({ q, rows });
      } catch {
        if (live) setResult({ q, rows: [] });
      }
    }, 300);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [query, school, classId]);

  function reset() {
    setOpen(false);
    setCode("");
    setSchool(null);
    setClassId(null);
    setQuery("");
    setResult({ q: "", rows: [] });
    setChild(null);
    setDob("");
  }

  async function lookup(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      setSchool(await parentApi.lookupSchool(code.trim()));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not find that school.");
    } finally {
      setBusy(false);
    }
  }

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!child) return;
    setBusy(true);
    try {
      const res = await parentApi.addChild(child.student_id, dob);
      toast.success(`${res.full_name} added.`);
      qc.invalidateQueries({ queryKey: ["parent", "me"] });
      reset();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not add that child.");
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <section className="rounded-xl border border-border bg-card p-4">
        <h2 className="mb-1 text-sm font-semibold">Another child at this school?</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          Add them here and switch between them at the top of the screen.
        </p>
        <Button variant="outline" size="sm" onClick={() => setOpen(true)}>
          Add another child
        </Button>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">Add another child</h2>
        <button onClick={reset} className="text-xs text-muted-foreground">
          Cancel
        </button>
      </div>

      {!school ? (
        <form onSubmit={lookup} className="space-y-3">
          <div>
            <Label htmlFor="add-code">School code</Label>
            <Input
              id="add-code"
              autoCapitalize="characters"
              value={code}
              onChange={(e) => setCode(e.target.value.toUpperCase())}
              required
            />
          </div>
          <Button type="submit" size="sm" disabled={busy}>
            {busy ? "Checking…" : "Continue"}
          </Button>
        </form>
      ) : !classId ? (
        <div className="grid grid-cols-3 gap-2">
          {school.classes.map((c) => (
            <Button
              key={c.class_id}
              variant="outline"
              size="sm"
              onClick={() => setClassId(c.class_id)}
            >
              {c.label ?? c.name}
            </Button>
          ))}
        </div>
      ) : !child ? (
        <div className="space-y-2">
          <Label htmlFor="add-q">Child&apos;s name</Label>
          <Input
            id="add-q"
            placeholder="First few letters"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {result.q === query.trim() && result.rows.length ? (
            <ul className="divide-y rounded-md border">
              {result.rows.map((mch) => (
                <li key={mch.student_id}>
                  <button
                    type="button"
                    className="w-full px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => setChild(mch)}
                  >
                    {mch.full_name}
                  </button>
                </li>
              ))}
            </ul>
          ) : query.trim().length >= MIN_QUERY ? (
            <p className="text-xs text-muted-foreground">No match in this class.</p>
          ) : (
            <p className="text-xs text-muted-foreground">Type at least {MIN_QUERY} letters.</p>
          )}
        </div>
      ) : (
        <form onSubmit={add} className="space-y-3">
          <div>
            <Label htmlFor="add-dob">{child.full_name}&apos;s date of birth</Label>
            <Input
              id="add-dob"
              type="date"
              value={dob}
              onChange={(e) => setDob(e.target.value)}
              required
            />
          </div>
          <Button type="submit" size="sm" disabled={busy || !dob}>
            {busy ? "Adding…" : "Add child"}
          </Button>
        </form>
      )}
    </section>
  );
}
