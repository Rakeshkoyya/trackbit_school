"use client";

// The observance catalogue — the operator's curation tab (`D-60`, `S-149`).
//
// Platform data: no `org_id`, no RLS, super-admin on every write, exactly the
// `demo_requests` / Enquiries shape next to it. One curation serves every
// school and one correction fixes every school **without a deploy** — which is
// the entire reason this is a table and not a checked file in the repo.
//
// Two things this screen must keep saying out loud:
//
//   * **Storing a date in a database does not make it true.** Every entry
//     carries `source` and it is required (`S-150`), because the admin
//     approving it is the last human in the chain and *"Suggested · Telangana
//     state holiday list"* and *"Suggested · an internet list"* ask for very
//     different amounts of trust.
//   * **A school's decision is downstream of this row.** `decided_count` says
//     how many schools have already acted on it, so the operator knows whether
//     they are editing a draft or correcting something already in use.
//
// Scoping is `D-61`: `state` + `board`, both of which setup already collects.
// Leave both empty for "everybody". A school is never asked to declare a region
// or a religion, so nothing here should tempt anyone to add that question.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarRange, Globe2, Plus, Search, Upload } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { eventsApi, type Observance, type ObservancePayload } from "@/lib/events-api";
import { cn } from "@/lib/utils";

const KINDS = ["holiday", "festival", "observance"] as const;
const TIERS = ["major", "minor"] as const;

const fmt = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", {
    weekday: "short", day: "numeric", month: "short", year: "numeric",
  });

type Draft = {
  key: string;
  name: string;
  date: string;
  end_date: string;
  kind: (typeof KINDS)[number];
  tier: (typeof TIERS)[number];
  prep_days: number;
  state: string;
  board: string;
  tradition: string;
  source: string;
  note: string;
  is_active: boolean;
};

const EMPTY: Draft = {
  key: "", name: "", date: "", end_date: "", kind: "festival", tier: "major",
  prep_days: 7, state: "", board: "", tradition: "", source: "", note: "",
  is_active: true,
};

function toDraft(o: Observance): Draft {
  return {
    key: o.key, name: o.name, date: o.date, end_date: o.end_date ?? "",
    kind: o.kind, tier: o.tier, prep_days: o.prep_days, state: o.state ?? "",
    board: o.board ?? "", tradition: o.tradition ?? "", source: o.source,
    note: o.note ?? "", is_active: o.is_active,
  };
}

function Pills<T extends string>({
  value, onChange, options,
}: { value: T; onChange: (v: T) => void; options: readonly T[] }) {
  return (
    <div className="mt-1.5 flex flex-wrap gap-1.5">
      {options.map((o) => (
        <button key={o} type="button" onClick={() => onChange(o)}
          className={cn("rounded-full border px-3 py-1.5 text-xs capitalize transition-colors",
            value === o
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-card hover:bg-muted")}>
          {o}
        </button>
      ))}
    </div>
  );
}

/** Parse pasted rows into catalogue entries.
 *
 *  Deliberately dumb and deterministic: `name, date, kind, tier, state, board,
 *  tradition`, comma or tab separated, one per line, blank cells allowed. No
 *  model reads this — `S-123`'s rejected row was "ask a model for dates", and
 *  a paste box that guesses is the same mistake with a smaller blast radius.
 *  Anything it cannot read comes back as an error the operator fixes, never as
 *  a best guess. */
function parseRows(text: string): {
  rows: Partial<ObservancePayload>[];
  errors: string[];
} {
  const rows: Partial<ObservancePayload>[] = [];
  const errors: string[] = [];
  text.split(/\r?\n/).forEach((line, i) => {
    const raw = line.trim();
    if (!raw) return;
    const cells = raw.split(/\t|,/).map((c) => c.trim().replace(/^"|"$/g, ""));
    const [name, date, kind, tier, state, board, tradition] = cells;
    if (!name || !date) {
      errors.push(`Line ${i + 1}: needs at least a name and a date.`);
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      errors.push(`Line ${i + 1}: "${date}" is not a YYYY-MM-DD date.`);
      return;
    }
    rows.push({
      name, date,
      kind: (KINDS as readonly string[]).includes(kind) ? (kind as Observance["kind"]) : "festival",
      tier: (TIERS as readonly string[]).includes(tier) ? (tier as Observance["tier"]) : "major",
      state: state || null, board: board || null, tradition: tradition || null,
    });
  });
  return { rows, errors };
}

const PLACEHOLDER = [
  "Name, YYYY-MM-DD, kind, tier, state, board, tradition",
  "Diwali, 2027-11-05, holiday, major, Telangana, ,",
].join("\n");

function ImportSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [source, setSource] = useState("");
  const [text, setText] = useState("");
  const { rows, errors } = parseRows(text);

  const run = useMutation({
    mutationFn: () => eventsApi.importObservances(source.trim(), rows),
    onSuccess: (r) => {
      qc.invalidateQueries({ queryKey: ["observances"] });
      toast.success(`${r.created} added, ${r.updated} corrected`);
      setText("");
      onClose();
    },
    onError: (e) => showApiError(e, "Could not import those"),
  });

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) onClose(); }} title="Import a year">
      <div className="space-y-3">
        <div>
          <Label htmlFor="imp-source">Where are these from?</Label>
          <Input id="imp-source" placeholder="e.g. Telangana gazette 2027" value={source}
                 onChange={(e) => setSource(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="imp-rows">Rows</Label>
          <textarea
            id="imp-rows"
            rows={10}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={PLACEHOLDER}
            className="mt-1 w-full rounded-lg border border-border bg-card px-3 py-2 font-mono text-xs"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            One per line. Only the name and the date are required.
          </p>
        </div>

        {errors.length ? (
          <div className="rounded-lg bg-danger/10 px-3 py-2 text-xs text-danger">
            {errors.slice(0, 5).map((e) => <p key={e}>{e}</p>)}
            {errors.length > 5 ? <p>…and {errors.length - 5} more.</p> : null}
          </div>
        ) : null}

        {rows.length ? (
          <div className="rounded-lg border border-border px-3 py-2">
            <p className="mb-1 text-xs font-medium">{rows.length} row(s) read</p>
            <ul className="space-y-0.5 text-xs text-muted-foreground">
              {rows.slice(0, 6).map((r, i) => (
                <li key={i}>{r.name} · {r.date} · {r.state ?? "all states"}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <Button className="w-full" disabled={run.isPending || !rows.length || !source.trim()
                                             || errors.length > 0}
                onClick={() => run.mutate()}>
          {run.isPending ? "Importing…" : `Import ${rows.length} date(s)`}
        </Button>
        <p className="text-xs text-muted-foreground">
          Re-importing a corrected file updates the matching dates rather than adding them
          again — one correction fixes every school.
        </p>
      </div>
    </Sheet>
  );
}

export function CatalogueScreen() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [editing, setEditing] = useState<Observance | null>(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [importing, setImporting] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["observances", q],
    queryFn: () => eventsApi.catalogue({ q: q.trim() || undefined }),
  });

  const done = () => {
    qc.invalidateQueries({ queryKey: ["observances"] });
    setOpen(false);
    setEditing(null);
  };

  const payload = () => ({
    ...draft,
    key: draft.key.trim() || undefined,
    end_date: draft.end_date || null,
    state: draft.state.trim() || null,
    board: draft.board.trim() || null,
    tradition: draft.tradition.trim() || null,
    note: draft.note.trim() || null,
  });

  const save = useMutation({
    mutationFn: () => editing
      ? eventsApi.updateObservance(editing.id, payload())
      : eventsApi.createObservance(payload()),
    onSuccess: () => { toast.success(editing ? "Updated" : "Added"); done(); },
    onError: (e) => showApiError(e, "Could not save that"),
  });

  const retire = useMutation({
    mutationFn: (id: string) => eventsApi.retireObservance(id),
    onSuccess: () => { toast.success("Retired — schools stop seeing it"); done(); },
    onError: (e) => showApiError(e, "Could not retire that"),
  });

  const startNew = () => { setEditing(null); setDraft(EMPTY); setOpen(true); };
  const startEdit = (o: Observance) => { setEditing(o); setDraft(toDraft(o)); setOpen(true); };

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <PageHeader
          title="Catalogue"
          subtitle="Dates every school is offered. Nothing here reaches a school's calendar until their admin approves it."
        />
        <div className="flex gap-2">
          <Button size="sm" variant="outline" onClick={() => setImporting(true)}>
            <Upload className="h-4 w-4" /> Import a year
          </Button>
          <Button size="sm" onClick={startNew}><Plus className="h-4 w-4" /> Add a date</Button>
        </div>
      </div>

      <div className="mb-4 flex items-center gap-2">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Search by name" value={q}
                 onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>

      {isLoading ? (
        <PageLoading label="Loading the catalogue…" />
      ) : !data?.length ? (
        <EmptyState
          icon={CalendarRange}
          title="The catalogue is empty"
          body="That is the honest state until the sources are curated — schools see no suggestions, and their own calendars are unaffected. Add dates from a named source, or import a year in bulk."
        />
      ) : (
        <div className="space-y-1.5">
          {data.map((o) => (
            <button key={o.id} type="button" onClick={() => startEdit(o)}
              className={cn(
                "flex w-full items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-2.5 text-left transition-colors hover:bg-muted/50",
                !o.is_active && "opacity-55")}>
              <span className="min-w-0">
                <span className="flex items-center gap-2">
                  <span className="truncate text-sm font-medium">{o.name}</span>
                  {o.tier === "minor" ? <Badge tone="outline">minor</Badge> : null}
                  {!o.is_active ? <Badge tone="neutral">retired</Badge> : null}
                </span>
                <span className="block truncate text-xs text-muted-foreground">
                  {fmt(o.date)}
                  {o.end_date ? ` – ${fmt(o.end_date)}` : ""} · {o.source}
                </span>
              </span>
              <span className="flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
                <Globe2 className="h-3.5 w-3.5" />
                {o.state ?? "all states"}{o.board ? ` · ${o.board}` : ""}
                {o.decided_count
                  ? <Badge tone="primary">{o.decided_count} decided</Badge>
                  : null}
              </span>
            </button>
          ))}
        </div>
      )}

      <ImportSheet open={importing} onClose={() => setImporting(false)} />

      <Sheet open={open} onOpenChange={(v) => { if (!v) { setOpen(false); setEditing(null); } }}
             title={editing ? `Edit · ${editing.name}` : "Add a date"}>
        <form className="space-y-3"
              onSubmit={(e) => { e.preventDefault(); if (draft.name && draft.date && draft.source) save.mutate(); }}>
          {editing?.decided_count ? (
            <p className="rounded-lg bg-warning-soft px-3 py-2 text-xs text-warning">
              {editing.decided_count} school decision(s) already point at this entry. Changing
              the date corrects the suggestion, not the calendars they already wrote.
            </p>
          ) : null}

          <div>
            <Label htmlFor="ob-name">Name</Label>
            <Input id="ob-name" value={draft.name}
                   onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ob-date">Date</Label>
              <Input id="ob-date" type="date" value={draft.date}
                     onChange={(e) => setDraft({ ...draft, date: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="ob-end">Until (regional spread)</Label>
              <Input id="ob-end" type="date" value={draft.end_date}
                     onChange={(e) => setDraft({ ...draft, end_date: e.target.value })} />
            </div>
          </div>

          <div>
            {/* S-150 — and this is why it is not optional. */}
            <Label htmlFor="ob-source">Where did this date come from?</Label>
            <Input id="ob-source" placeholder="e.g. Telangana gazette 2026" value={draft.source}
                   onChange={(e) => setDraft({ ...draft, source: e.target.value })} />
            <p className="mt-1 text-xs text-muted-foreground">
              Shown to every admin who is asked to approve it.
            </p>
          </div>

          <div>
            <Label>Kind</Label>
            <Pills value={draft.kind} options={KINDS}
                   onChange={(kind) => setDraft({ ...draft, kind })} />
          </div>
          <div>
            <Label>Tier</Label>
            <Pills value={draft.tier} options={TIERS}
                   onChange={(tier) => setDraft({ ...draft, tier })} />
            <p className="mt-1 text-xs text-muted-foreground">
              There is an international day for almost everything — minor keeps the card readable.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ob-state">State (blank = all)</Label>
              <Input id="ob-state" value={draft.state}
                     onChange={(e) => setDraft({ ...draft, state: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="ob-board">Board (blank = all)</Label>
              <Input id="ob-board" value={draft.board}
                     onChange={(e) => setDraft({ ...draft, board: e.target.value })} />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="ob-tradition">Tradition (optional)</Label>
              <Input id="ob-tradition" value={draft.tradition}
                     onChange={(e) => setDraft({ ...draft, tradition: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="ob-prep">Lead time (days)</Label>
              <Input id="ob-prep" type="number" min={0} max={120} value={draft.prep_days}
                     onChange={(e) => setDraft({ ...draft, prep_days: Number(e.target.value) })} />
            </div>
          </div>

          <div>
            <Label htmlFor="ob-note">Note (optional)</Label>
            <Input id="ob-note" value={draft.note}
                   onChange={(e) => setDraft({ ...draft, note: e.target.value })} />
          </div>

          <div className="flex gap-2 pt-1">
            <Button type="submit" className="flex-1"
                    disabled={save.isPending || !draft.name || !draft.date || !draft.source}>
              {save.isPending ? "Saving…" : editing ? "Save" : "Add to the catalogue"}
            </Button>
            {editing && editing.is_active ? (
              <Button type="button" variant="ghost" disabled={retire.isPending}
                      onClick={() => retire.mutate(editing.id)}>
                Retire
              </Button>
            ) : null}
          </div>
          <p className="text-xs text-muted-foreground">
            Retiring stops schools seeing it. Nothing is deleted — a school may already have
            approved against it.
          </p>
        </form>
      </Sheet>
    </div>
  );
}
