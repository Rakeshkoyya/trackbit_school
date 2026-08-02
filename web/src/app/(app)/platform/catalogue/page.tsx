"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { CatalogueScreen } from "@/components/school/catalogue-screen";

export default function CataloguePage() {
  return (
    <AuthGuard requireSuperAdmin>
      <CatalogueScreen />
    </AuthGuard>
  );
}
