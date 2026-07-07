import { ResetClient } from "@/components/auth/reset-client";

export default async function ResetPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <ResetClient token={token} />;
}
