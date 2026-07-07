import { JoinClient } from "@/components/auth/join-client";

// params is async in Next.js 16.
export default async function JoinPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <JoinClient token={token} />;
}
