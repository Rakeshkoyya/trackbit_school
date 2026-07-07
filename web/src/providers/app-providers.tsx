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
      <Toaster position="bottom-center" theme={theme} richColors closeButton />
    </QueryClientProvider>
  );
}
