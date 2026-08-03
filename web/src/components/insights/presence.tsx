"use client";

// V1-14 — the morning roll.
//
// Built once, mounted twice: the dashboard overview leads with it and the
// attendance tab opens with it, so the glance and the workspace can never
// disagree about who was away this morning.
//
// THE DESIGN, and why it is this and not a dashboard.
//
// The artifact this screen is about is the **register** — the ruled ledger every
// school keeps, names in the margin, dates across the head, a mark in every box.
// So the board is built as a document of record rather than a set of widgets:
//
//   · **the medallion** — three concentric arcs, one per cohort, composed as ONE
//     object instead of three loose donuts. A school's roll is one fact with
//     three parts. The centre carries the number with no denominator problem:
//     how many people are in the building.
//   · **the ledger legend** — each cohort as a ruled row: name, `238 ⁄ 240`, the
//     share. Every figure in tabular mono, which is the face a register is
//     written in and the one face already in this app that nothing else uses.
//   · **the call list** — the people missing, as entries under a column head,
//     separated by hairlines rather than boxed in tinted cards. The medallion
//     carries the colour; three coloured boxes beside it would be noise.
//
// Everything here is painted, not decided. Tone, sentence, whether people are
// named or counted, which buttons a row offers — all arrive from
// `services/insights/presence.py`. A component that re-derived any of it would
// be the drift V1-0 exists to remove.
//
// The one rule worth restating where the pixels are: **a cohort nobody has
// marked gets a dashed track and no arc.** Not 0%, not red. "Nobody has taken
// staff attendance" and "nobody came in" are opposite facts.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, CheckCircle2, MessageSquare, NotebookPen, Phone, UserPlus, UserX,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { ActivityRing, RollMedallion, SERIES_COLORS, STATUS_COLOR } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import type {
  PresenceAction, PresenceBoard, PresenceGroup, PresenceRing, PresenceRow,
} from "@/lib/insights-types";
import { cn } from "@/lib/utils";

import { ColumnHead, TONE_BADGE, type Tone } from "./shared";

/**
 * The medallion's arcs are keyed by COHORT, not by status.
 *
 * Three concentric arcs in one status hue are three green rings — you cannot
 * tell which is which, which is the one thing the medallion has to say. Colour
 * follows the entity here (dataviz: never its rank), and status is carried in
 * text on the ledger row beside it, where it can be read with a word.
 *
 * Teal / magenta / violet, from the app's existing validated series palette.
 * All three pairs pass CVD and normal-vision separation against both surfaces,
 * and none of them is the reserved amber, which on this board means "attention"
 * and would have read as a warning on whichever cohort drew it.
 */
const COHORT_COLOR: Record<string, string> = {
  students: SERIES_COLORS[4],
  teachers: SERIES_COLORS[3],
  admins: SERIES_COLORS[5],
};

/** Status still shows — as ink on the cohort's own line, with its own words. */
const CAPTION_TONE: Record<Tone, string> = {
  neutral: "text-muted-foreground",
  green: "text-muted-foreground",
  amber: "text-warning",
  red: "text-danger",
};

const RULE: Record<Tone, string> = {
  neutral: "bg-muted-foreground/25",
  green: "bg-success",
  amber: "bg-warning",
  red: "bg-danger",
};

// ── the medallion + its ledger ───────────────────────────────────────────────

/** One cohort as a ruled ledger row: a colour key, the name, `238 ⁄ 240`, the
 *  share. The slash is a fraction slash, because that is what the figure is. */
function LedgerRow({ ring }: { ring: PresenceRing }) {
  return (
    <Link href={ring.href}
      className="group flex items-baseline gap-2.5 border-t border-border/70 py-2 first:border-t-0 first:pt-0">
      {/* Keys the row to its arc. Identity, so the eye can map one to the other. */}
      <span className="mt-1 h-2 w-2 shrink-0 rounded-full"
        style={{ background: ring.marked ? COHORT_COLOR[ring.key] : "var(--color-muted)" }} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13px] font-medium group-hover:underline">
          {ring.label}
        </span>
        <span className={cn("mt-0.5 block text-[11px] leading-snug",
          CAPTION_TONE[ring.tone])}>
          {ring.caption}
        </span>
      </span>
      {ring.marked ? (
        <span className="shrink-0 font-mono text-[13px] tabular-nums">
          {ring.present}
          <span className="px-0.5 text-muted-foreground/60">⁄</span>
          <span className="text-muted-foreground">{ring.total}</span>
        </span>
      ) : (
        <span className="shrink-0 font-mono text-[11px] uppercase tracking-wide text-muted-foreground/70">
          &mdash;
        </span>
      )}
    </Link>
  );
}

export function RollCard({ board }: { board: PresenceBoard }) {
  const arcs = board.rings.map((r) => ({
    key: r.key, pct: r.pct, label: r.label,
    color: COHORT_COLOR[r.key] ?? STATUS_COLOR.neutral,
  }));
  const when = new Date(`${board.date}T00:00:00`).toLocaleDateString(undefined, {
    weekday: "short", day: "numeric", month: "short",
  });

  return (
    <section className="h-fit overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex items-baseline justify-between gap-2 border-b border-border px-4 py-2.5">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          The roll
        </span>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          {board.is_today ? "today" : when}
        </span>
      </header>

      <div className="flex flex-col items-center px-4 pt-5">
        <RollMedallion arcs={arcs}>
          {board.roll ? (
            <>
              <span className="font-mono text-[30px] font-semibold leading-none tabular-nums">
                {board.in_building}
              </span>
              <span className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                in
              </span>
            </>
          ) : (
            <span className="max-w-[86px] text-center text-[11px] leading-tight text-muted-foreground">
              not marked yet
            </span>
          )}
        </RollMedallion>

        {/* The sentence the medallion is for. The count of people missing is
            what the next ten minutes are actually about. */}
        <p className="mt-3.5 text-center text-[13px] leading-snug">
          {board.roll ? (
            board.away ? (
              <>
                <span className="font-mono font-semibold tabular-nums">{board.away}</span>
                {board.away === 1 ? " person is" : " people are"} not here
              </>
            ) : "Everyone is here"
          ) : "Nobody has taken attendance yet"}
        </p>
        <p className="mt-0.5 text-center font-mono text-[10px] tracking-wide text-muted-foreground">
          {board.roll_caption}
        </p>
      </div>

      <div className="px-4 pb-3 pt-4">
        {board.rings.map((r) => <LedgerRow key={r.key} ring={r} />)}
      </div>

      {!board.is_today ? (
        <p className="border-t border-border bg-muted/25 px-4 py-2 text-[11px] leading-snug text-muted-foreground">
          The last day attendance was captured. Today&rsquo;s roll appears as soon as
          one period is marked.
        </p>
      ) : null}
    </section>
  );
}

/**
 * The three cohorts as SEPARATE rings, side by side (V1-14 revision).
 *
 * The overview keeps the medallion, because there the roll is one glance in a
 * narrow column beside the call list. The attendance tab is the workspace for
 * exactly these three groups, and there each wants its own ring, its own figure
 * and its own denominator laid out to be compared — nested arcs make you decode
 * which radius belongs to whom before you can read anything.
 *
 * The arc stays keyed by cohort, as on the medallion; the FIGURE carries the
 * status, so a cohort in trouble is legible without colour alone doing the work.
 */
export function PresenceRingRow({ rings }: { rings: PresenceRing[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {rings.map((r) => (
        <Link key={r.key} href={r.href}
          className="flex items-center gap-4 rounded-xl border border-border bg-card px-4 py-4 transition-colors hover:border-primary/40">
          <ActivityRing pct={r.pct} tone={r.tone} label={r.label} size={78} stroke={9}
            color={COHORT_COLOR[r.key]}>
            {r.marked ? (
              <span className={cn("font-mono text-[15px] font-semibold leading-none tabular-nums",
                r.tone === "red" ? "text-danger" : r.tone === "amber" ? "text-warning" : "")}>
                {r.pct != null ? Math.round(r.pct) : "—"}
                <span className="text-[9px] text-muted-foreground">%</span>
              </span>
            ) : (
              <span className="px-1 text-center text-[9px] leading-tight text-muted-foreground">
                not marked
              </span>
            )}
          </ActivityRing>
          <span className="min-w-0 flex-1">
            <span className="block font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              {r.label}
            </span>
            <span className="mt-1 block font-mono text-[19px] leading-none tabular-nums">
              {r.marked ? (
                <>
                  {r.present}
                  <span className="px-0.5 text-muted-foreground/50">⁄</span>
                  <span className="text-muted-foreground">{r.total}</span>
                </>
              ) : (
                <span className="text-[13px] text-muted-foreground">not marked yet</span>
              )}
            </span>
            <span className={cn("mt-1.5 block text-[11px] leading-snug", CAPTION_TONE[r.tone])}>
              {r.caption}
            </span>
          </span>
        </Link>
      ))}
    </div>
  );
}

// ── one person, with what can be done to them ────────────────────────────────

const ACTION_META: Record<PresenceAction, {
  label: string; doneLabel: string; icon: ReactNode;
}> = {
  remind_guardian: {
    label: "Remind", doneLabel: "Reminded",
    icon: <MessageSquare className="h-3.5 w-3.5" />,
  },
  assign_followup: {
    label: "Follow up", doneLabel: "Assigned",
    icon: <UserPlus className="h-3.5 w-3.5" />,
  },
  record_reason: {
    label: "Add reason", doneLabel: "Recorded",
    icon: <NotebookPen className="h-3.5 w-3.5" />,
  },
  arrange_cover: {
    label: "Arrange cover", doneLabel: "Covered",
    icon: <UserX className="h-3.5 w-3.5" />,
  },
  reassign_work: {
    label: "Move work", doneLabel: "Moved",
    icon: <ArrowRight className="h-3.5 w-3.5" />,
  },
};

function Row({
  row, onCover, onReason,
}: {
  row: PresenceRow;
  onCover?: (row: PresenceRow) => void;
  onReason?: (row: PresenceRow) => void;
}) {
  const qc = useQueryClient();
  const fire = useMutation({
    mutationFn: (kind: "guardian_reminded" | "followup_assigned") =>
      insightsApi.action(kind, { student_id: row.id }),
    onSuccess: (res) => {
      // `already_done` is the rail refusing to pester, not a failure — three
      // people looking at the same absent child in one morning is the normal
      // case, and this is what stops the family getting three messages.
      if (res.already_done) toast.info(res.message);
      else toast.success(res.message);
      qc.invalidateQueries({ queryKey: ["insights", "presence"] });
      qc.invalidateQueries({ queryKey: ["insights", "calls"] });
    },
    onError: (e) => showApiError(e, "Could not complete that"),
  });

  const button = (action: PresenceAction) => {
    const meta = ACTION_META[action];
    if (row.done.includes(action)) {
      return (
        <span key={action}
          className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-success">
          <CheckCircle2 className="h-3 w-3" /> {meta.doneLabel}
        </span>
      );
    }
    const onClick = () => {
      if (action === "remind_guardian") fire.mutate("guardian_reminded");
      else if (action === "assign_followup") fire.mutate("followup_assigned");
      else if (action === "record_reason") onReason?.(row);
      else if (action === "arrange_cover" || action === "reassign_work") onCover?.(row);
    };
    return (
      <Button key={action} size="sm" variant="outline" onClick={onClick}
        disabled={fire.isPending} className="h-7 px-2 text-xs">
        {meta.icon} {meta.label}
      </Button>
    );
  };

  const name = (
    <span className="text-[13px] font-medium">{row.name}</span>
  );

  return (
    <li className="border-t border-border/60 px-4 py-3 first:border-t-0">
      <div className="flex items-start gap-2">
        {/* The margin rule — a ledger entry is keyed at its left edge, not
            wrapped in a coloured box. */}
        <span className={cn("mt-[5px] h-3 w-[2px] shrink-0 rounded-full", RULE[row.tone])} />
        {/* One flow, so a long name wraps naturally instead of being squeezed
            into a column two words wide by the badge next to it. */}
        <span className="min-w-0 flex-1">
          {row.href ? (
            <Link href={row.href} className="hover:underline">{name}</Link>
          ) : name}
          {row.badge ? (
            <span className="ml-1.5 whitespace-nowrap align-[2px]">
              <Badge tone={TONE_BADGE[row.tone]}>{row.badge}</Badge>
            </span>
          ) : null}
        </span>
      </div>
      <p className="mt-1 pl-[10px] text-[11px] leading-snug text-muted-foreground">
        {row.subtitle}
      </p>
      {row.actions.length ? (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 pl-[10px]">
          {row.actions.map(button)}
        </div>
      ) : null}
    </li>
  );
}

// ── one block ────────────────────────────────────────────────────────────────

/**
 * Named under the threshold, one sentence over it.
 *
 * The server decides which (`inline`), because the same rule has to hold on the
 * overview, on the tab and in anything that reads this board later. A block
 * that chose for itself would put three names on one screen and a count on
 * another for the same morning.
 */
export function PresenceBlock({
  group, onCover, onReason,
}: {
  group: PresenceGroup;
  onCover?: (row: PresenceRow) => void;
  onReason?: (row: PresenceRow) => void;
}) {
  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-border bg-card">
      <header className="border-b border-border px-4 py-2.5">
        <ColumnHead tone={group.tone} count={group.count}>{group.label}</ColumnHead>
      </header>

      {/* The sentence first, always — the figures are what it rests on. */}
      <p className="px-4 py-3 text-[13px] leading-snug">{group.headline}</p>

      {group.inline && group.rows.length ? (
        <ul className="mt-auto border-t border-border">
          {group.rows.map((r) => (
            <Row key={r.id} row={r} onCover={onCover} onReason={onReason} />
          ))}
        </ul>
      ) : null}

      <footer className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border bg-muted/25 px-4 py-2">
        {group.note ? (
          group.note_href ? (
            <Link href={group.note_href}
              className="font-mono text-[10px] tracking-wide text-muted-foreground hover:underline">
              {group.note}
            </Link>
          ) : (
            <span className="font-mono text-[10px] tracking-wide text-muted-foreground">
              {group.note}
            </span>
          )
        ) : null}
        <Link href={group.href}
          className="ml-auto inline-flex shrink-0 items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] text-primary hover:underline">
          {group.action_label} <ArrowRight className="h-3 w-3" />
        </Link>
      </footer>
    </section>
  );
}

// ── the whole board ──────────────────────────────────────────────────────────

export function PresencePanorama({
  board, onCover, onReason,
}: {
  board: PresenceBoard;
  onCover?: (row: PresenceRow) => void;
  onReason?: (row: PresenceRow) => void;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(230px,270px)_1fr]">
      <RollCard board={board} />
      {/* The admin block earns its place only when somebody is away. On a normal
          day it is a card spent on "every admin is in" — a sentence nobody
          needed, in a row where the other two carry names and buttons. The
          pending-work figure it also carried is on the Tasks tab, which is
          where an admin goes looking for it. */}
      <div className="grid gap-4 sm:grid-cols-2">
        {board.groups
          .filter((g) => g.key !== "admins" || g.count > 0)
          .map((g) => (
            <PresenceBlock key={g.key} group={g} onCover={onCover} onReason={onReason} />
          ))}
      </div>
    </div>
  );
}

/** A dialable number, wherever a row carries one. Its own element so it is
 *  never nested inside another link (V1-13 fixed exactly that on the reach
 *  board — an <a> in an <a> is invalid and stops the number being tappable). */
export function PhoneLink({ phone }: { phone: string }) {
  return (
    <a href={`tel:${phone}`} onClick={(e) => e.stopPropagation()}
      className="inline-flex items-center gap-1 whitespace-nowrap font-mono text-xs font-medium text-primary hover:underline">
      <Phone className="h-3 w-3" /> {phone}
    </a>
  );
}
