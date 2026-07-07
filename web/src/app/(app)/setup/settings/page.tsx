"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { SettingsScreen } from "@/components/settings/settings-screen";

export default function SettingsPage() {
  return (
    <AuthGuard requireRole="admin">
      <SettingsScreen />
    </AuthGuard>
  );
}
