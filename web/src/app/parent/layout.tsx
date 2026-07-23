/**
 * Parent portal area — deliberately NOT the staff shell (no sidebar, no
 * bottom tabs). Mobile-first: parents live on phones.
 */
export default function ParentAreaLayout({ children }: { children: React.ReactNode }) {
  return <div className="min-h-dvh bg-background">{children}</div>;
}
