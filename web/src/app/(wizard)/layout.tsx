/**
 * The wizard lives outside the (app) shell on purpose: no sidebar, no sub-tabs,
 * nothing to click away to. Setup is a one-time heavy process and it deserves the
 * whole screen (SPRD2 §5.1).
 */
export default function WizardLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-dvh bg-background">{children}</div>;
}
