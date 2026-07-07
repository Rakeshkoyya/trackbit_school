import { SubTabs } from "@/components/layout/sub-tabs";

/** Tasks area (SPRD2 §3): consolidates v1 Home + Boards + Done into one item. */
export default function TasksLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <SubTabs
        tabs={[
          { label: "Today", href: "/tasks" },
          { label: "Boards", href: "/tasks/boards" },
          { label: "Done", href: "/tasks/done" },
        ]}
      />
      {children}
    </div>
  );
}
