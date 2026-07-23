"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Building2, Copy, LogIn, Plus } from "lucide-react";
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
import { platformApi, type CreateSchoolResult, type PlatformOrg } from "@/lib/platform-api";

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function OrgCard({ org, onEnter, entering }: {
  org: PlatformOrg;
  onEnter: (id: string) => void;
  entering: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-xl border border-border bg-card p-4">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate font-medium">{org.name}</span>
          {org.active_year ? <Badge tone="outline">{org.active_year}</Badge> : null}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          {org.member_count} member{org.member_count === 1 ? "" : "s"} · {org.student_count}{" "}
          student{org.student_count === 1 ? "" : "s"} · {org.class_count}{" "}
          class{org.class_count === 1 ? "" : "es"}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Created {fmtDate(org.created_at)} · Last active {fmtDate(org.last_active_at)}
        </p>
      </div>
      <Button variant="outline" size="sm" disabled={entering} onClick={() => onEnter(org.id)}>
        <LogIn className="mr-1.5 h-4 w-4" />
        Enter
      </Button>
    </div>
  );
}

const EMPTY_FORM = {
  org_name: "",
  timezone: "Asia/Kolkata",
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

  const { data: orgs, isLoading } = useQuery({
    queryKey: ["platform-orgs"],
    queryFn: platformApi.orgs,
  });

  const createSchool = useMutation({
    mutationFn: () => platformApi.createSchool(form),
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
      `TrackBit School login\nSchool: ${created.org.name}\nEmail: ${created.admin_email}\nTemporary password: ${created.password}\n(You'll be asked to set your own password on first sign-in.)`,
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
              entering={enter.isPending} />
          ))}
        </div>
      )}

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
