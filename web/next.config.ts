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
      { source: "/assessments", destination: "/students/academics/exams", permanent: false },
      { source: "/members", destination: "/setup/members", permanent: false },
      { source: "/settings", destination: "/setup/settings", permanent: false },
      // Founder 2026-08-05: Support lost its sidebar item — the programme lives
      // in ABC bands. Only the LIST moved; `/support/[id]`, the child page with
      // the weekly check-in, is unchanged and every link to it still resolves.
      { source: "/support", destination: "/bands/my-students", permanent: false },
      // Founder 2026-08-05 (SY-1): Plan → Classes is gone. What it checked now
      // reads off the Syllabus board by name rather than by count, so both its
      // routes land there instead of 404ing for anyone holding a bookmark.
      { source: "/plan/classes", destination: "/plan/syllabus", permanent: false },
      { source: "/plan/classes/:id", destination: "/plan/syllabus", permanent: false },
      // Founder 2026-08-05: Students split into Directory (the administration
      // record) and Academics (the record the school makes). The old flat
      // routes keep resolving — `:path*` so the exam pages under Scores, which
      // the dashboard and My Class both link into by cycle id, follow with
      // them. `/students` itself is NOT here: it is a real page that sends each
      // role to its own half.
      { source: "/students/scores/:path*", destination: "/students/academics/exams/:path*", permanent: false },
      { source: "/students/scores", destination: "/students/academics/exams", permanent: false },
      { source: "/students/trends", destination: "/students/academics/analytics", permanent: false },
      // Bands left Students with V1-9/BD-2 and now has its own area; this
      // finishes the move rather than leaving two doors to one programme.
      { source: "/students/bands/:classId", destination: "/bands/manage", permanent: false },
      { source: "/students/bands", destination: "/bands", permanent: false },
    ];
  },
};

export default nextConfig;
