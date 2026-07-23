import { SubTabs } from "@/components/layout/sub-tabs";

/** Platform area (super-admin only): the two things the operator does above any
 *  single school — run the schools, and work the enquiries that become them. */
export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Schools", href: "/platform" },
          { label: "Enquiries", href: "/platform/enquiries" },
        ]}
      />
      {children}
    </div>
  );
}
