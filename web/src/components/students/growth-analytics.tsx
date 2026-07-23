"use client";

// The analytical half of a student's report card. Everything here is computed
// from the one /students/{id}/growth read — no extra capture, no extra request.
//
// Reading order matches how a teacher actually briefs a parent: where they stand
// (tiles), what shape they are (ability + subject radars), what they are good at and
// what needs work (strengths / growth), then how they have moved (score history) and
// where they are missing the room (attendance per subject).

import { AlertTriangle, Sparkles } from "lucide-react";

import {
  AbilityRadar, ChartCard, RowBars, StatTile, TrendLine,
  SERIES_COLORS, toneForPct, type ChartRow, type Series,
} from "@/components/charts";
import type { StudentGrowth } from "@/lib/school-types";

const pct = (score: number, max: number) => (max ? Math.round((score / max) * 100) : null);

/** Latest score per subject, as a percentage. */
function latestPctBySubject(data: StudentGrowth) {
  return data.subjects.map((s) => {
    const last = s.scores[s.scores.length - 1];
    return {
      id: s.class_subject_id,
      name: s.subject_name,
      pct: last ? pct(last.score, last.max_score) : null,
      cycle: last?.cycle_name ?? null,
    };
  });
}

export function GrowthTiles({ data }: { data: StudentGrowth }) {
  const latest = latestPctBySubject(data).filter((s) => s.pct != null);
  const avg = latest.length
    ? Math.round(latest.reduce((sum, s) => sum + (s.pct ?? 0), 0) / latest.length)
    : null;
  const missed = data.subjects.reduce(
    (sum, s) => sum + s.chapters.reduce((n, c) => n + c.topics_missed, 0), 0);
  const flags = data.subjects.reduce((sum, s) => sum + s.checks_flagged, 0);
  const needsWork = data.subjects.reduce(
    (sum, s) => sum + s.observations.filter((o) => o.rating === "needs_work").length, 0);

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <StatTile
        label="Attendance"
        value={data.attendance.pct != null ? `${data.attendance.pct}%` : "—"}
        sub={`${data.attendance.absent} absent · ${data.attendance.late} late`}
        tone={data.attendance.pct == null ? "neutral"
          : data.attendance.pct >= 90 ? "green" : data.attendance.pct >= 75 ? "amber" : "red"}
      />
      <StatTile
        label="Average score"
        value={avg != null ? `${avg}%` : "—"}
        sub={latest.length ? `latest test in ${latest.length} subject${latest.length === 1 ? "" : "s"}` : "no scores yet"}
        tone={avg == null ? "neutral" : avg >= 60 ? "green" : avg >= 40 ? "amber" : "red"}
      />
      <StatTile
        label="Topics missed while absent"
        value={String(missed)}
        sub={missed ? "worth re-teaching at home" : "nothing missed"}
        tone={missed === 0 ? "green" : missed <= 3 ? "amber" : "red"}
      />
      <StatTile
        label="Flags this term"
        value={String(flags + needsWork)}
        sub={`${flags} homework/check · ${needsWork} in class`}
        tone={flags + needsWork === 0 ? "green" : flags + needsWork <= 3 ? "amber" : "red"}
      />
    </div>
  );
}

/** Ability profile (diagnostic skill areas) beside subject performance. Both
 * are radars when there are enough axes to make a shape, bars when there aren't
 * — a three-point radar is a triangle, not information. */
export function GrowthProfiles({ data }: { data: StudentGrowth }) {
  const skillRows: ChartRow[] = data.skills
    .map((sk) => ({ x: sk.skill_area, score: pct(sk.score, sk.max_score) }))
    .filter((r) => r.score != null);
  const subjectRows: ChartRow[] = latestPctBySubject(data)
    .filter((s) => s.pct != null)
    .map((s) => ({ x: s.name, score: s.pct }));

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <ChartCard title="Ability profile"
        hint={data.skills.length
          ? `Diagnostic skill areas, latest cycle${data.skills[0]?.cycle_name ? ` · ${data.skills[0].cycle_name}` : ""}.`
          : "Record a diagnostic cycle with skill areas to fill this in."}>
        {skillRows.length >= 3 ? (
          <AbilityRadar rows={skillRows} series={[{ key: "score", label: "This student" }]} height={250} />
        ) : skillRows.length ? (
          <RowBars rows={skillRows} dataKey="score" unit="%" max={100}
            height={Math.max(120, skillRows.length * 36)}
            colorFor={(r) => toneForPct(r.score as number, { good: 60, fair: 40 })} />
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">
            No skill-area scores yet. Record a diagnostic under Students → Scores and this profile builds itself.
          </p>
        )}
      </ChartCard>

      <ChartCard title="Subject performance" hint="Latest recorded test in each subject.">
        {subjectRows.length >= 3 ? (
          <AbilityRadar rows={subjectRows} series={[{ key: "score", label: "Latest score" }]} height={250} />
        ) : subjectRows.length ? (
          <RowBars rows={subjectRows} dataKey="score" unit="%" max={100}
            height={Math.max(120, subjectRows.length * 36)}
            colorFor={(r) => toneForPct(r.score as number, { good: 60, fair: 40 })} />
        ) : (
          <p className="py-10 text-center text-sm text-muted-foreground">No test scores recorded yet.</p>
        )}
      </ChartCard>
    </div>
  );
}

/** Strengths and growth areas, side by side. A report that lists only deficits
 * is a complaint — the left column is what you open the conversation with. */
export function StrengthsAndGrowth({ data }: { data: StudentGrowth }) {
  if (!data.strengths.length && !data.growth_areas.length) return null;
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <section className="rounded-xl border border-success/30 bg-success/5 p-4">
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
          <Sparkles className="h-4 w-4 text-success" /> Strengths
        </h3>
        {data.strengths.length ? (
          <ul className="space-y-1 text-sm">
            {data.strengths.map((s, i) => (
              <li key={i} className="flex gap-2"><span className="text-success">•</span>{s}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            Nothing has crossed the bar yet — strengths appear from high attendance,
            strong scores and “excellent” notes in class.
          </p>
        )}
      </section>

      <section className="rounded-xl border border-warning/40 bg-warning/5 p-4">
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
          <AlertTriangle className="h-4 w-4 text-warning" /> Growth areas
        </h3>
        {data.growth_areas.length ? (
          <ul className="space-y-1 text-sm">
            {data.growth_areas.map((g, i) => (
              <li key={i} className="flex gap-2"><span className="text-warning">•</span>{g}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">Nothing is flagged for attention.</p>
        )}
      </section>
    </div>
  );
}

/** Score history — one line per subject across the cycles this student sat.
 * Subjects without two scores are dropped: a single dot is not a trend. */
export function ScoreHistory({ data }: { data: StudentGrowth }) {
  const withHistory = data.subjects.filter((s) => s.scores.length >= 2).slice(0, SERIES_COLORS.length);
  if (!withHistory.length) return null;

  // Cycle names ordered by date across every subject — the shared x axis.
  const seen = new Map<string, string>();   // cycle_name → date
  for (const s of data.subjects) for (const sc of s.scores) seen.set(sc.cycle_name, sc.date);
  const cycles = [...seen.entries()].sort((a, b) => a[1].localeCompare(b[1])).map(([name]) => name);

  const rows: ChartRow[] = cycles.map((name) => {
    const row: ChartRow = { x: name };
    for (const s of withHistory) {
      const hit = s.scores.find((sc) => sc.cycle_name === name);
      row[s.class_subject_id] = hit ? pct(hit.score, hit.max_score) : null;
    }
    return row;
  });
  const series: Series[] = withHistory.map((s, i) => ({
    key: s.class_subject_id, label: s.subject_name, color: SERIES_COLORS[i % SERIES_COLORS.length],
  }));

  return (
    <ChartCard title="Score history" hint="Percentage in each test, subject by subject.">
      <TrendLine rows={rows} series={series} yUnit="%" yDomain={[0, 100]} height={240} />
    </ChartCard>
  );
}

/** Attendance per subject — which room they are actually missing. */
export function AttendanceBySubject({ data }: { data: StudentGrowth }) {
  const rows: ChartRow[] = data.subjects
    .filter((s) => s.attendance.pct != null)
    .map((s) => ({ x: s.subject_name, pct: s.attendance.pct }));
  if (!rows.length) return null;
  return (
    <ChartCard title="Attendance by subject" hint="Share of that subject’s marked periods they were present for.">
      <RowBars rows={rows} dataKey="pct" unit="%" max={100}
        height={Math.max(120, rows.length * 32)}
        colorFor={(r) => toneForPct(r.pct as number, { good: 90, fair: 75 })} />
    </ChartCard>
  );
}
