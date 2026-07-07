"use client";

import {
  Building2,
  Check,
  Clock,
  Copy,
  Loader2,
  LogOut,
  Mail,
  Phone,
  Plus,
  Settings,
  Sparkles,
  User as UserIcon,
  UserCog,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuth } from "@/contexts/auth-context";

/**
 * Topbar account control: an avatar button that opens a popover with the
 * signed-in user's details, their organization, a couple of useful shortcuts,
 * and sign out. Replaces the bare sign-out button.
 *
 * No popover primitive ships in this project, so the panel is a plain absolutely
 * positioned element closed on outside-click / Escape — no new dependency.
 */
export function AccountMenu() {
  const { me, logout, switchOrg, createOrg } = useAuth();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [orgName, setOrgName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  // Close on click outside the menu or on Escape, only while it's open.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (!me) return null;

  const { user, org, org_role } = me;
  const isAdmin = org_role === "admin";
  const secondary = user.email ?? user.username ?? user.phone ?? null;
  // Orgs the user can switch into, excluding the current one. Empty => single-org
  // user, so no switcher is shown (per requirement).
  const otherOrgs = (me.orgs ?? []).filter((o) => o.id !== org.id);

  async function handleSwitch(orgId: string) {
    if (switchingId) return;
    setSwitchingId(orgId);
    try {
      await switchOrg(orgId); // swaps tokens, clears cache, redirects to /home
      setOpen(false);
    } catch {
      setSwitchingId(null);
      toast.error("Couldn't switch organization");
    }
  }

  async function handleCreateOrg(e: React.FormEvent) {
    e.preventDefault();
    const name = orgName.trim();
    if (!name || submitting) return;
    setSubmitting(true);
    try {
      await createOrg(name, "Asia/Kolkata");
      setOpen(false);
      setCreating(false);
      setOrgName("");
    } catch {
      setSubmitting(false);
      toast.error("Couldn't create organization");
    }
  }

  async function copy(label: string, value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);
      toast.success(`${label} copied`);
      window.setTimeout(() => setCopied((c) => (c === label ? null : c)), 1500);
    } catch {
      toast.error("Couldn't copy");
    }
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="rounded-full ring-offset-1 ring-offset-card transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Avatar name={user.name} className="h-8 w-8" />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Account"
          className="tb-menu-in absolute right-0 top-full z-50 mt-2 w-72 overflow-hidden rounded-xl border border-border bg-card shadow-xl"
        >
          {/* Identity */}
          <div className="flex items-start gap-3 border-b border-border px-4 py-4">
            <Avatar name={user.name} className="h-10 w-10" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{user.name}</p>
              {secondary && <p className="truncate text-xs text-muted-foreground">{secondary}</p>}
            </div>
            <Badge tone={isAdmin ? "primary" : "neutral"}>{isAdmin ? "Admin" : "Member"}</Badge>
          </div>

          {/* Copyable account details */}
          {(user.email || user.username || user.phone) && (
            <div className="border-b border-border px-2 py-2">
              {user.email && (
                <DetailRow
                  icon={Mail}
                  label="Email"
                  value={user.email}
                  copied={copied === "Email"}
                  onCopy={() => copy("Email", user.email!)}
                />
              )}
              {user.username && (
                <DetailRow
                  icon={UserIcon}
                  label="Username"
                  value={user.username}
                  copied={copied === "Username"}
                  onCopy={() => copy("Username", user.username!)}
                />
              )}
              {user.phone && (
                <DetailRow
                  icon={Phone}
                  label="Phone"
                  value={user.phone}
                  copied={copied === "Phone"}
                  onCopy={() => copy("Phone", user.phone!)}
                />
              )}
            </div>
          )}

          {/* Organization */}
          <div className="border-b border-border px-4 py-3">
            <p className="mb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Organization
            </p>
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0 flex-1 truncate text-sm font-medium">{org.name}</span>
              <Badge tone={org.plan === "pro" ? "success" : "outline"}>
                {org.plan === "pro" ? "Pro" : "Free"}
              </Badge>
            </div>
            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{org.timezone}</span>
            </div>
            {isAdmin && org.plan === "free" && (
              <Link
                href="/settings"
                onClick={() => setOpen(false)}
                className="mt-3 flex items-center justify-center gap-1.5 rounded-md bg-accent px-3 py-2 text-xs font-medium text-accent-foreground transition hover:opacity-90"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Upgrade to Pro
              </Link>
            )}

            {/* Switch organization — only when the user belongs to more than one */}
            {otherOrgs.length > 0 && (
              <div className="mt-3 border-t border-border pt-3">
                <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  Switch to
                </p>
                <div className="space-y-0.5">
                  {otherOrgs.map((o) => (
                    <button
                      key={o.id}
                      type="button"
                      role="menuitem"
                      disabled={switchingId !== null}
                      onClick={() => handleSwitch(o.id)}
                      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-muted disabled:opacity-60"
                    >
                      <Building2 className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="min-w-0 flex-1 truncate">{o.name}</span>
                      {switchingId === o.id ? (
                        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-muted-foreground" />
                      ) : (
                        o.org_role === "admin" && <Badge tone="neutral">Admin</Badge>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Create a new organization */}
            <div className="mt-3 border-t border-border pt-3">
              {creating ? (
                <form onSubmit={handleCreateOrg} className="space-y-2">
                  <Input
                    autoFocus
                    value={orgName}
                    onChange={(e) => setOrgName(e.target.value)}
                    placeholder="New organization name"
                    aria-label="New organization name"
                  />
                  <div className="flex gap-2">
                    <Button
                      type="submit"
                      size="sm"
                      disabled={!orgName.trim() || submitting}
                      className="flex-1"
                    >
                      {submitting ? "Creating…" : "Create"}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setCreating(false);
                        setOrgName("");
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                </form>
              ) : (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => setCreating(true)}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm font-medium text-primary transition-colors hover:bg-muted"
                >
                  <Plus className="h-4 w-4 shrink-0" />
                  Create organization
                </button>
              )}
            </div>
          </div>

          {/* Shortcuts */}
          <div className="border-b border-border px-2 py-2">
            <MenuLink
              href="/account"
              icon={UserCog}
              label="Account settings"
              onNavigate={() => setOpen(false)}
            />
            {isAdmin && (
              <MenuLink
                href="/settings"
                icon={Settings}
                label="Organization settings"
                onNavigate={() => setOpen(false)}
              />
            )}
          </div>

          {/* Sign out */}
          <div className="p-2">
            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                logout();
              }}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium text-danger transition-colors hover:bg-danger/10"
            >
              <LogOut className="h-4 w-4" />
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({
  icon: Icon,
  label,
  value,
  copied,
  onCopy,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onCopy}
      title={`Copy ${label.toLowerCase()}`}
      className="group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted"
    >
      <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
      <span className="min-w-0 flex-1 truncate text-sm">{value}</span>
      {copied ? (
        <Check className="h-3.5 w-3.5 shrink-0 text-primary" />
      ) : (
        <Copy className="h-3.5 w-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      )}
    </button>
  );
}

function MenuLink({
  href,
  icon: Icon,
  label,
  onNavigate,
}: {
  href: string;
  icon: LucideIcon;
  label: string;
  onNavigate: () => void;
}) {
  return (
    <Link
      href={href}
      role="menuitem"
      onClick={onNavigate}
      className="flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-muted"
    >
      <Icon className="h-4 w-4 text-muted-foreground" />
      {label}
    </Link>
  );
}
