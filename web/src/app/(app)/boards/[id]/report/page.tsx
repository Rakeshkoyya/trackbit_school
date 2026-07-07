import { BoardReport } from "@/components/reports/board-report";

export default async function BoardReportPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <BoardReport boardId={id} />;
}
