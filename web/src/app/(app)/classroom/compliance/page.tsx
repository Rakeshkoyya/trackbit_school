"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { schoolApi } from "@/lib/school-api";

function ComplianceInner() {
  const { data } = useQuery({ queryKey: ["compliance"], queryFn: schoolApi.compliance });
  return (
    <div>
      <Link href="/classroom" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> My Day
      </Link>
      <div className="mb-4 flex items-center justify-between">
        <PageHeader title="Logging compliance" subtitle="Who has logged today's classes" />
        {data ? <Badge tone={data.logged_count === data.total ? "success" : "warning"}>{data.logged_count}/{data.total} logged</Badge> : null}
      </div>
      <div className="space-y-2">
        {data?.rows.map((r) => (
          <div key={r.class_subject_id} className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-2.5">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{r.class_label} · {r.subject_name}</p>
              <p className="text-xs text-muted-foreground">{r.teacher_name ?? "Unassigned"}</p>
            </div>
            <Badge tone={r.logged ? "success" : "neutral"}>{r.logged ? "logged" : "not yet"}</Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function CompliancePage() {
  return (
    <AuthGuard allow={["admin", "coordinator"]}>
      <ComplianceInner />
    </AuthGuard>
  );
}
