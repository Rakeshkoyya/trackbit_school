import { SubTabs } from "@/components/layout/sub-tabs";
import { FeatureGate } from "@/components/plan/upgrade";
import { FEATURES } from "@/lib/features";

/** Tasks area (SPRD2 §3): consolidates v1 Home + Boards + Done into one item.
 *
 *  Max, whole and unmetered (`D-109`): the old Free plan capped an org at 2
 *  boards and 8 members, and those quotas are gone. Take Max and every part of
 *  the module is yours. */
export default function TasksLayout({ children }: { children: React.ReactNode }) {
  return (
    <FeatureGate feature={FEATURES.tasksBoards}>
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
    </FeatureGate>
  );
}
