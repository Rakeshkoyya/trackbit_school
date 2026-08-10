"use client";

/**
 * `/fees/structures` → `/fees/structure` (FE-1).
 *
 * The old page listed the structures that existed and let an admin type a class
 * *label* ("6-B") into a free-text box. Both are gone: a structure now prices a
 * whole class (`D-116`) and the screen is a coverage grid that shows the classes
 * with **no** price too (`D-117`), because "have I priced everything?" is the
 * question it exists to answer.
 *
 * Kept as a redirect rather than deleted — the plural path is a year old, it is
 * in people's history and bookmarks, and a 404 is a worse answer than the right
 * screen.
 */

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function LegacyStructuresPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/fees/structure");
  }, [router]);
  return <p className="text-sm text-muted-foreground">Taking you to Structure…</p>;
}
