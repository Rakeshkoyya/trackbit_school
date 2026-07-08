import { SubTabs } from "@/components/layout/sub-tabs";

/** Setup area (SPRD2 §3, admin): Academics · Members · Settings. Absorbs v1
 *  /academics + skill areas + Members + org settings; hosts the wizard (V2-P5). */
export default function SetupLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Wizard", href: "/setup/wizard" },
          { label: "Academics", href: "/setup" },
          { label: "Members", href: "/setup/members" },
          { label: "Settings", href: "/setup/settings" },
        ]}
      />
      {children}
    </div>
  );
}
