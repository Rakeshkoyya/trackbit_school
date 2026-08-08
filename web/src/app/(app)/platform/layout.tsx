import { SubTabs } from "@/components/layout/sub-tabs";

/** Platform area (super-admin only): what the operator does above any single
 *  school — run the schools, work the enquiries that become them, and curate
 *  the one observance catalogue every school reads (V1-7, `S-149`). */
export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Schools", href: "/platform" },
          { label: "Enquiries", href: "/platform/enquiries" },
          // `D-106`: schools that hit a wall and asked to move up. Sits beside
          // Enquiries because it is the same job — a conversation to have —
          // just with a school we already have rather than one we want.
          { label: "Upgrades", href: "/platform/upgrades" },
          { label: "Catalogue", href: "/platform/catalogue" },
          { label: "Gallery", href: "/platform/gallery" },
        ]}
      />
      {children}
    </div>
  );
}
