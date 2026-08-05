"use client";

/**
 * `/students` has no screen of its own any more — it sends you to your half.
 *
 * An admin lands on **Directory**, because the thing they open this area for is
 * a child's record; a teacher lands on **Academics**, because Directory is
 * admin-only to write and read-only to her, and dropping a teacher on a table
 * she cannot act on is a dead end wearing a landing page.
 *
 * A redirect rather than a rewrite: every link, bookmark and back-button in the
 * app that still says `/students` keeps working and ends up somewhere real.
 */

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { PageLoading } from "@/components/ui/page-loading";
import { useAuth } from "@/contexts/auth-context";

function StudentsLanding() {
  const router = useRouter();
  const { me } = useAuth();

  useEffect(() => {
    if (!me) return;
    router.replace(me.org_role === "admin" ? "/students/directory" : "/students/academics");
  }, [me, router]);

  return <PageLoading />;
}

export default function StudentsPage() {
  return (
    <AuthGuard>
      <StudentsLanding />
    </AuthGuard>
  );
}
