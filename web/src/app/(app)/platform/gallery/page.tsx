"use client";

// The School UI Kit gallery (GA §3.4): every catalog component rendered from
// committed sample data. Internal QA surface — if a component or its data
// contract drifts, it shows here first.

import { AuthGuard } from "@/components/auth/auth-guard";
import { GALLERY } from "@/components/lucy/gallery-samples";
import { WidgetBody } from "@/components/lucy/widget-renderer";

export default function GalleryPage() {
  return (
    <AuthGuard requireSuperAdmin>
      <div className="mx-auto max-w-5xl space-y-4 p-4">
        <div>
          <h1 className="text-lg font-semibold">Component gallery</h1>
          <p className="text-sm text-muted-foreground">
            All {GALLERY.length} School UI Kit components, rendered from sample data.
            Lucy answers, Views and (later) custom modules compose from exactly these.
          </p>
        </div>
        <div className="columns-1 gap-4 md:columns-2 [&>*]:mb-4">
          {GALLERY.map((sample) => (
            <section key={sample.type}
              className="break-inside-avoid rounded-xl border border-border bg-card p-3 shadow-sm">
              <div className="mb-2">
                <p className="text-sm font-semibold">{sample.title}
                  <code className="ml-2 rounded bg-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                    {sample.type}
                  </code>
                </p>
                <p className="text-xs text-muted-foreground">{sample.summary}</p>
              </div>
              <WidgetBody type={sample.type} data={sample.data} />
            </section>
          ))}
        </div>
      </div>
    </AuthGuard>
  );
}
