import { TaskDetailView } from "@/components/tasks/task-detail-view";

export default async function TaskPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <TaskDetailView taskId={id} />;
}
