import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained build (.next/standalone) so the Docker runtime image
  // ships only the files it needs — no full node_modules, no `next start`.
  output: "standalone",

  // V2-P0-B IA reshell (SPRD2 §3, §12): old v1 routes redirect to their new
  // consolidated homes. Exact sources, so nested routes like /boards/:id and
  // /setup/:tab keep resolving to their own pages.
  async redirects() {
    return [
      { source: "/home", destination: "/tasks", permanent: false },
      { source: "/boards", destination: "/tasks/boards", permanent: false },
      { source: "/done", destination: "/tasks/done", permanent: false },
      { source: "/insights", destination: "/dashboard", permanent: false },
      { source: "/classroom/compliance", destination: "/dashboard", permanent: false },
      { source: "/classroom", destination: "/my-day", permanent: false },
      { source: "/academics", destination: "/setup", permanent: false },
      { source: "/planner/plan", destination: "/plan/syllabus", permanent: false },
      { source: "/planner", destination: "/plan", permanent: false },
      { source: "/assessments", destination: "/students/scores", permanent: false },
      { source: "/members", destination: "/setup/members", permanent: false },
      { source: "/settings", destination: "/setup/settings", permanent: false },
    ];
  },
};

export default nextConfig;
