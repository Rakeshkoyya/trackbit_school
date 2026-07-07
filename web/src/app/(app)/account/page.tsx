"use client";

import { AccountScreen } from "@/components/account/account-screen";
import { AuthGuard } from "@/components/auth/auth-guard";

export default function AccountPage() {
  return (
    <AuthGuard>
      <AccountScreen />
    </AuthGuard>
  );
}
