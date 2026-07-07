import { RecurringDetailView } from "@/components/tasks/recurring-detail-view";

export default async function RecurringPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <RecurringDetailView templateId={id} />;
}
