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
          { label: "Catalogue", href: "/platform/catalogue" },
          { label: "Gallery", href: "/platform/gallery" },
        ]}
      />
      {children}
    </div>
  );
}
