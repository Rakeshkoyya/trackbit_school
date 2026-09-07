"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Toaster } from "sonner";

import { AuthProvider } from "@/contexts/auth-context";
import { useTheme } from "@/lib/theme";

export function AppProviders({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );
  const theme = useTheme();

  return (
    <QueryClientProvider client={client}>
      <AuthProvider>{children}</AuthProvider>
      {/* FB-1h — clear of the mobile bottom nav.
          At `bottom-center` with no offset the toast landed ON the tab bar, so
          "Upload failed" sat across My Day / Tasks / Students / Lucy and the
          teacher could read neither. The mobile offset clears the 4rem bar plus
          the phone's home indicator; desktop has no bar and keeps an ordinary
          margin. */}
      <Toaster position="bottom-center" theme={theme} richColors closeButton
        offset="1.5rem"
        mobileOffset="calc(5rem + env(safe-area-inset-bottom))" />
    </QueryClientProvider>
  );
}
