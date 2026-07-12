"use client";

// The app shell's <main> wrapper. Every screen gets the centered max-w column
// EXCEPT Lucy, whose chat canvas wants the full viewport (it manages its own
// scrolling and padding, including room for the mobile bottom tabs).

import { usePathname } from "next/navigation";

export function MainContainer({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const fullBleed = pathname === "/lucy" || pathname.startsWith("/lucy/");
  if (fullBleed) {
    return <main className="flex min-h-0 flex-1 flex-col">{children}</main>;
  }
  return (
    <main className="flex-1 px-4 pb-24 pt-4 lg:px-8 lg:pb-8">
      <div className="mx-auto w-full max-w-2xl lg:max-w-4xl">{children}</div>
    </main>
  );
}
