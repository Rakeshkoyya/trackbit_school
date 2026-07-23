"use client";

// Enquiries — the operator's inbox for "book a demo" leads from the marketing
// site. Super-admin only: these arrive before a school has an org, so no org
// member can ever see them.
//
// The working model is append-only (law 3). An operator never edits a lead:
// they record what happened — a remark, a status move, or both — and that entry
// joins the lead's history. The status badge is just the newest move, so the
// list can be worked at a glance while the sheet keeps the full account of who
// said what and when.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2, Clock, Inbox, Mail, MapPin, MessageSquare, Phone, Search, Users,
} from "lucide-react";
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
import {
  DEMO_STATUSES, marketingApi,
  type DemoRequest, type DemoRequestNote, type DemoStatus,
} from "@/lib/marketing-api";

type Tone = "neutral" | "success" | "warning" | "danger" | "primary" | "outline";

// What each status means to the operator, in their words.
const STATUS: Record<DemoStatus, { label: string; tone: Tone }> = {
  new: { label: "New", tone: "primary" },
  contacted: { label: "Contacted", tone: "outline" },
  scheduled: { label: "Demo scheduled", tone: "warning" },
  won: { label: "Won", tone: "success" },
  lost: { label: "Lost", tone: "neutral" },
};

function when(iso: string): string {
  const then = new Date(iso);
  const days = Math.floor((Date.now() - then.getTime()) / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 30) return `${days} days ago`;
  return then.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function stamp(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric", month: "short", hour: "numeric", minute: "2-digit",
  });
}

function HistoryEntry({ entry }: { entry: DemoRequestNote }) {
  return (
    <li className="border-l-2 border-border pl-3">
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{entry.author_name ?? "Someone"}</span>
        <span>·</span>
        <span>{stamp(entry.created_at)}</span>
        {entry.status_to ? (
          <Badge tone={STATUS[entry.status_to].tone}>
            {entry.status_from ? `${STATUS[entry.status_from].label} → ` : ""}
            {STATUS[entry.status_to].label}
          </Badge>
        ) : null}
      </div>
      {entry.note ? <p className="mt-0.5 whitespace-pre-wrap text-sm">{entry.note}</p> : null}
    </li>
  );
}

function LeadSheet({ leadId, onClose }: { leadId: string | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [note, setNote] = useState("");
  const [status, setStatus] = useState<DemoStatus | null>(null);

  const { data: lead } = useQuery({
    queryKey: ["demo-request", leadId],
    queryFn: () => marketingApi.demoRequest(leadId!),
    enabled: !!leadId,
  });

  const close = () => { setNote(""); setStatus(null); onClose(); };

  const save = useMutation({
    mutationFn: () => marketingApi.addDemoRequestNote(leadId!, {
      ...(status ? { status } : {}),
      ...(note.trim() ? { note: note.trim() } : {}),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["demo-requests"] });
      qc.invalidateQueries({ queryKey: ["demo-request", leadId] });
      setNote(""); setStatus(null);
      toast.success("Update recorded");
    },
    onError: (e) => showApiError(e, "Could not record the update"),
  });

  // The picker starts on the lead's current status; a save only counts as a
  // move when the operator actually changes it.
  const picked = status ?? lead?.status ?? "new";
  const canSave = !!lead && (note.trim().length > 0 || picked !== lead.status);

  return (
    <Sheet open={!!leadId} onOpenChange={(v) => { if (!v) close(); }}
      title={lead ? lead.school_name : "Enquiry"}>
      {!lead ? <p className="text-sm text-muted-foreground">Loading…</p> : (
        <div className="space-y-5">
          <div className="space-y-1.5 text-sm">
            <p className="font-medium">{lead.contact_name}</p>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
              <a href={`tel:${lead.phone}`} className="inline-flex items-center gap-1 hover:text-foreground">
                <Phone className="h-3.5 w-3.5" /> {lead.phone}
              </a>
              <a href={`mailto:${lead.email}`} className="inline-flex items-center gap-1 hover:text-foreground">
                <Mail className="h-3.5 w-3.5" /> {lead.email}
              </a>
            </p>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              {lead.city ? <span className="inline-flex items-center gap-1"><MapPin className="h-3.5 w-3.5" /> {lead.city}</span> : null}
              {lead.student_count != null ? (
                <span className="inline-flex items-center gap-1">
                  <Users className="h-3.5 w-3.5" /> {lead.student_count} students
                </span>
              ) : null}
              <span className="inline-flex items-center gap-1">
                <Clock className="h-3.5 w-3.5" /> asked {when(lead.created_at)}
              </span>
              <span>via {lead.source}</span>
            </p>
          </div>

          {lead.message ? (
            <p className="whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-3 text-sm">
              {lead.message}
            </p>
          ) : null}

          <div className="space-y-3 rounded-lg border border-border p-3">
            <div>
              <Label>Status</Label>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {DEMO_STATUSES.map((s) => (
                  <button key={s} type="button" onClick={() => setStatus(s)}
                    className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                      picked === s
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border text-muted-foreground hover:text-foreground"}`}>
                    {STATUS[s].label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <Label htmlFor="remark">Remark</Label>
              <textarea id="remark" value={note} onChange={(e) => setNote(e.target.value)}
                placeholder="What happened? Spoke to the principal, asked us to call back Monday…"
                className="mt-1.5 min-h-24 w-full rounded-md border border-border bg-card px-2.5 py-2 text-sm" />
            </div>
            <Button className="w-full" disabled={!canSave || save.isPending}
              onClick={() => save.mutate()}>
              Record update
            </Button>
            <p className="text-xs text-muted-foreground">
              Every update is added to the history below. Nothing is overwritten.
            </p>
          </div>

          <div>
            <h3 className="mb-2 text-sm font-semibold">History</h3>
            {lead.notes.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No one has worked this enquiry yet.
              </p>
            ) : (
              <ul className="space-y-3">
                {lead.notes.map((n) => <HistoryEntry key={n.id} entry={n} />)}
              </ul>
            )}
          </div>
        </div>
      )}
    </Sheet>
  );
}

function LeadRow({ lead, onOpen }: { lead: DemoRequest; onOpen: (id: string) => void }) {
  return (
    <button type="button" onClick={() => onOpen(lead.id)}
      className="w-full rounded-xl border border-border bg-card p-4 text-left transition-colors hover:border-primary/40">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 truncate font-medium">{lead.school_name}</span>
        <Badge tone={STATUS[lead.status].tone}>{STATUS[lead.status].label}</Badge>
      </div>
      <p className="mt-1 truncate text-sm text-muted-foreground">
        {lead.contact_name} · {lead.phone} · {lead.email}
      </p>
      <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {lead.city ? <span>{lead.city}</span> : null}
        {lead.student_count != null ? <span>{lead.student_count} students</span> : null}
        <span>asked {when(lead.created_at)}</span>
        <span>via {lead.source}</span>
        {lead.note_count > 0 ? (
          <span className="inline-flex items-center gap-1">
            <MessageSquare className="h-3 w-3" /> {lead.note_count}
          </span>
        ) : null}
      </p>
    </button>
  );
}

export function EnquiriesScreen() {
  const [openId, setOpenId] = useState<string | null>(null);
  const [filter, setFilter] = useState<DemoStatus | "all">("all");
  const [q, setQ] = useState("");
  const { data: leads, isLoading } = useQuery({
    queryKey: ["demo-requests"],
    queryFn: marketingApi.demoRequests,
  });

  if (isLoading) return <PageLoading label="Loading enquiries…" />;

  const all = leads ?? [];
  const counts = DEMO_STATUSES.reduce(
    (acc, s) => ({ ...acc, [s]: all.filter((l) => l.status === s).length }),
    {} as Record<DemoStatus, number>);

  const needle = q.trim().toLowerCase();
  const shown = all
    .filter((l) => filter === "all" || l.status === filter)
    .filter((l) => !needle || [l.school_name, l.contact_name, l.email, l.phone, l.city ?? ""]
      .some((f) => f.toLowerCase().includes(needle)));

  const tabs: { key: DemoStatus | "all"; label: string; count: number }[] = [
    { key: "all", label: "All", count: all.length },
    ...DEMO_STATUSES.map((s) => ({ key: s, label: STATUS[s].label, count: counts[s] })),
  ];

  return (
    <div>
      <PageHeader title="Enquiries"
        subtitle="Demo requests from the marketing site. Only you can see these." />

      {all.length === 0 ? (
        <EmptyState icon={Inbox} title="No enquiries yet"
          body="When a school books a demo on the website, it lands here." />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-1.5">
              {tabs.map((t) => (
                <button key={t.key} type="button" onClick={() => setFilter(t.key)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    filter === t.key
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground hover:text-foreground"}`}>
                  {t.label} {t.count}
                </button>
              ))}
            </div>
            <div className="relative ml-auto w-full sm:w-64">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-8" placeholder="Search school, name, phone…"
                value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
          </div>

          {shown.length === 0 ? (
            <EmptyState icon={Building2} title="Nothing matches"
              body="No enquiry matches this filter. Clear the search or pick another status." />
          ) : (
            <div className="space-y-2">
              {shown.map((l) => <LeadRow key={l.id} lead={l} onOpen={setOpenId} />)}
            </div>
          )}
        </>
      )}

      <LeadSheet leadId={openId} onClose={() => setOpenId(null)} />
    </div>
  );
}
