import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained build (.next/standalone) so the Docker runtime image
  // ships only the files it needs — no full node_modules, no `next start`.
  output: "standalone",
};

export default nextConfig;
