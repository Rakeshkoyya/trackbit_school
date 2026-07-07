import { AuthGuard } from "@/components/auth/auth-guard";
import { CelebrationProvider } from "@/components/celebration/celebration-provider";
import { BottomTabs } from "@/components/layout/bottom-tabs";
import { Sidebar } from "@/components/layout/sidebar";
import { Topbar } from "@/components/layout/topbar";
import { GuidedTour } from "@/components/onboarding/guided-tour";
import { YearProvider } from "@/contexts/year-context";

/**
 * Authenticated app shell: sidebar on desktop, bottom tabs on mobile.
 * AuthGuard redirects to /auth/login when there's no session.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <CelebrationProvider>
        <YearProvider>
        <div className="flex min-h-dvh">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <Topbar />
            <main className="flex-1 px-4 pb-24 pt-4 lg:px-8 lg:pb-8">
              <div className="mx-auto w-full max-w-2xl lg:max-w-4xl">{children}</div>
            </main>
            <BottomTabs />
          </div>
        </div>
        <GuidedTour />
        </YearProvider>
      </CelebrationProvider>
    </AuthGuard>
  );
}
