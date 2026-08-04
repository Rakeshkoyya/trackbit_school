"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AlertTriangle, Building2, CheckCircle2, ClipboardCheck, Copy, LogIn, Plus } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { PasswordInput } from "@/components/ui/password-input";
import { Sheet } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { ApiError } from "@/lib/api-client";
import { INDIAN_STATES, INDIAN_UNION_TERRITORIES } from "@/lib/indian-states";
import { platformApi, type CreateSchoolResult, type PlatformOrg } from "@/lib/platform-api";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function OrgCard({ org, onEnter, onReadiness, entering }: {
  org: PlatformOrg;
  onEnter: (id: string) => void;
  onReadiness: (org: PlatformOrg) => void;
  entering: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate font-medium">{org.name}</span>
          {org.active_year ? <Badge tone="outline">{org.active_year}</Badge> : null}
          {org.handed_over_at ? <Badge tone="success">handed over</Badge> : null}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {org.member_count} member{org.member_count === 1 ? "" : "s"} · {org.student_count}{" "}
          student{org.student_count === 1 ? "" : "s"} · {org.class_count}{" "}
          class{org.class_count === 1 ? "" : "es"}
          {org.school_code ? <> · code <span className="font-mono">{org.school_code}</span></> : null}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Created {fmtDate(org.created_at)} · Last active {fmtDate(org.last_active_at)}
        </p>
      </div>
      <div className="flex shrink-0 gap-2">
        <Button variant="ghost" size="sm" onClick={() => onReadiness(org)}>
          <ClipboardCheck className="mr-1.5 h-4 w-4" />
          Readiness
        </Button>
        <Button variant="outline" size="sm" disabled={entering} onClick={() => onEnter(org.id)}>
          <LogIn className="mr-1.5 h-4 w-4" />
          Enter
        </Button>
      </div>
    </div>
  );
}

/** §6 ⑤ — the page the operator reads before giving the school its password.
 *  Every warning names a consequence and links to the screen that clears it
 *  (the links open inside the school, so Enter first). */
function ReadinessSheet({ org, onClose, onEnter }: {
  org: PlatformOrg | null;
  onClose: () => void;
  onEnter: (id: string) => void;
}) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["readiness", org?.id],
    queryFn: () => platformApi.readiness(org!.id),
    enabled: !!org,
  });
  const handover = useMutation({
    mutationFn: () => platformApi.markHandedOver(org!.id),
    onSuccess: (r) => {
      qc.setQueryData(["readiness", org?.id], r);
      qc.invalidateQueries({ queryKey: ["platform-orgs"] });
      toast.success("Marked handed over");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not mark handover"),
  });

  return (
    <Sheet open={!!org} onOpenChange={(v) => { if (!v) onClose(); }}
      title={org ? `Ready to hand over — ${org.name}` : ""}>
      {!data ? (
        <div className="h-48 animate-pulse rounded-lg bg-muted" />
      ) : (
        <div className="space-y-3">
          <p className="text-sm font-medium">
            {data.ready_count} of {data.total} ✓
            {data.school_code ? (
              <span className="ml-2 font-mono text-xs text-muted-foreground">
                code {data.school_code}
              </span>
            ) : null}
          </p>
          <ul className="space-y-1.5">
            {data.checks.map((c) => (
              <li key={c.key} className="flex items-start gap-2 text-sm">
                {c.status === "ok" ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#234a37]" />
                ) : (
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />
                )}
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{c.title}</span>
                  <span className="block text-xs text-muted-foreground">{c.summary}</span>
                  {c.items.length > 0 ? (
                    <span className="mt-0.5 block text-xs text-muted-foreground/80">
                      {c.items.slice(0, 8).join(", ")}
                      {c.items.length > 8 ? ` +${c.items.length - 8} more` : ""}
                    </span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2 border-t border-border pt-3">
            <Button variant="outline" size="sm" onClick={() => onEnter(data.org_id)}>
              <LogIn className="mr-1.5 h-4 w-4" /> Enter to fix
            </Button>
            {data.handed_over_at ? (
              <Badge tone="success">handed over {fmtDate(data.handed_over_at)}</Badge>
            ) : (
              <Button size="sm" disabled={handover.isPending}
                onClick={() => handover.mutate()}>
                Mark handed over
              </Button>
            )}
          </div>
        </div>
      )}
    </Sheet>
  );
}

const EMPTY_FORM = {
  org_name: "",
  timezone: "Asia/Kolkata",
  address: "",
  state: "",
  board: "",
  admin_name: "",
  admin_email: "",
  admin_password: "",
};

export function PlatformScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { consumeSession } = useAuth();
  const [sheetOpen, setSheetOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  // Kept after creation so the operator can copy the handover credentials.
  const [created, setCreated] = useState<(CreateSchoolResult & { password: string }) | null>(null);
  const [readinessFor, setReadinessFor] = useState<PlatformOrg | null>(null);

  const { data: orgs, isLoading } = useQuery({
    queryKey: ["platform-orgs"],
    queryFn: platformApi.orgs,
  });

  const createSchool = useMutation({
    mutationFn: () => platformApi.createSchool({
      ...form,
      address: form.address || null,
      state: form.state || null,
      board: form.board || null,
    }),
    onSuccess: (result) => {
      setCreated({ ...result, password: form.admin_password });
      setForm(EMPTY_FORM);
      queryClient.invalidateQueries({ queryKey: ["platform-orgs"] });
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Could not create the school."),
  });

  const enter = useMutation({
    mutationFn: (orgId: string) => platformApi.enterOrg(orgId),
    onSuccess: (session) => {
      consumeSession(session);
      queryClient.clear();
      router.replace("/dashboard");
    },
    onError: (err) =>
      toast.error(err instanceof ApiError ? err.message : "Could not enter the school."),
  });

  function copyCreds() {
    if (!created) return;
    navigator.clipboard.writeText(
      `TrackBit School login\nSchool: ${created.org.name}\nEmail: ${created.admin_email}\nTemporary password: ${created.password}` +
      (created.school_code ? `\nSchool code (for parents): ${created.school_code}` : "") +
      `\n(You'll be asked to set your own password on first sign-in.)`,
    );
    toast.success("Credentials copied.");
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          title="Schools"
          subtitle="Every school on this TrackBit instance. Create one, run its setup, then hand over the admin login."
        />
        <Button onClick={() => { setCreated(null); setSheetOpen(true); }}>
          <Plus className="mr-1.5 h-4 w-4" />
          New school
        </Button>
      </div>

      {isLoading ? (
        <PageLoading />
      ) : !orgs?.length ? (
        <EmptyState icon={Building2} title="No schools yet" body="Create the first one." />
      ) : (
        <div className="space-y-3">
          {orgs.map((org) => (
            <OrgCard key={org.id} org={org} onEnter={(id) => enter.mutate(id)}
              onReadiness={setReadinessFor} entering={enter.isPending} />
          ))}
        </div>
      )}

      <ReadinessSheet org={readinessFor} onClose={() => setReadinessFor(null)}
        onEnter={(id) => { setReadinessFor(null); enter.mutate(id); }} />

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen} title="New school">
        {created ? (
          <div className="space-y-4">
            <p className="text-sm">
              <span className="font-medium">{created.org.name}</span> is ready. Hand these to the
              school admin once setup is done — they&apos;ll set their own password on first sign-in.
            </p>
            <div className="rounded-lg border border-border bg-muted/40 p-3 font-mono text-sm">
              <div>{created.admin_email}</div>
              <div>{created.password}</div>
              {created.school_code ? (
                <div className="mt-1 text-xs text-muted-foreground">
                  School code (parents): <span className="tracking-widest">{created.school_code}</span>
                </div>
              ) : null}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={copyCreds}>
                <Copy className="mr-1.5 h-4 w-4" />
                Copy credentials
              </Button>
              <Button onClick={() => { setSheetOpen(false); enter.mutate(created.org.id); }}>
                <LogIn className="mr-1.5 h-4 w-4" />
                Enter &amp; set up
              </Button>
            </div>
          </div>
        ) : (
          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              createSchool.mutate();
            }}
          >
            <div>
              <Label htmlFor="org_name">School name</Label>
              <Input id="org_name" required value={form.org_name}
                onChange={(e) => setForm({ ...form, org_name: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="timezone">Timezone</Label>
              <Input id="timezone" required value={form.timezone}
                onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="sch_address">Address</Label>
              <Input id="sch_address" value={form.address} placeholder="Street, city"
                onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="sch_state">State</Label>
                {/* V1-19 — a picker, because this value is what scopes the
                    observance catalogue. Typed free text ("TN") matches no
                    corpus row, and the school then sees an empty suggestions
                    queue with nothing explaining it. */}
                <select id="sch_state" value={form.state}
                  onChange={(e) => setForm({ ...form, state: e.target.value })}
                  className="h-9 w-full rounded-md border border-border bg-card px-2 text-sm">
                  <option value="">Select a state</option>
                  <optgroup label="States">
                    {INDIAN_STATES.map((n) => <option key={n} value={n}>{n}</option>)}
                  </optgroup>
                  <optgroup label="Union territories">
                    {INDIAN_UNION_TERRITORIES.map((n) => (
                      <option key={n} value={n}>{n}</option>
                    ))}
                  </optgroup>
                </select>
              </div>
              <div>
                <Label htmlFor="sch_board">Board</Label>
                <Input id="sch_board" value={form.board} placeholder="CBSE / State board"
                  onChange={(e) => setForm({ ...form, board: e.target.value })} />
              </div>
            </div>
            <div>
              <Label htmlFor="admin_name">Admin name</Label>
              <Input id="admin_name" required value={form.admin_name}
                onChange={(e) => setForm({ ...form, admin_name: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="admin_email">Admin email</Label>
              <Input id="admin_email" type="email" required value={form.admin_email}
                onChange={(e) => setForm({ ...form, admin_email: e.target.value })} />
            </div>
            <div>
              <Label htmlFor="admin_password">Temporary password</Label>
              <PasswordInput id="admin_password" required minLength={8}
                value={form.admin_password}
                onChange={(e) => setForm({ ...form, admin_password: e.target.value })} />
              <p className="mt-1 text-xs text-muted-foreground">
                The admin is forced to change it on first sign-in.
              </p>
            </div>
            <Button type="submit" className="w-full" disabled={createSchool.isPending}>
              {createSchool.isPending ? "Creating…" : "Create school"}
            </Button>
          </form>
        )}
      </Sheet>
    </div>
  );
}
