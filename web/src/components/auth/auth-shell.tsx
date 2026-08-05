import Link from "next/link";

/**
 * The shell every auth screen sits in — staff sign-in, password reset, and both
 * parent doors.
 *
 * It used to be a card floating in the middle of an empty page: correct, and it
 * read as a blank screen. Signing in is the first thing a new teacher or parent
 * ever sees of the product, so the page now carries the same board the landing
 * page does, with the form beside it.
 *
 * The left panel deliberately uses the marketing surface's palette rather than
 * the app's light/dark tokens: this screen is the seam between the two, and the
 * product should look like one thing across it. It is `aria-hidden` (it repeats
 * nothing the form needs) and hidden outright below `lg` — on a phone the form
 * is the whole job, and a decorative half-screen above it would push the
 * password field under the fold.
 *
 * Server component: no hooks, so `audience` is passed in by the page rather than
 * read from the router.
 */

type CellState = "done" | "flag" | "idle";
type Audience = "staff" | "parent";

interface AuthShellProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  /** Renders the staff/parent door switcher. Omit on screens that are neither. */
  audience?: Audience;
}

const BOARD = {
  board: "#0d1a15",
  slate: "#132420",
  rule: "#1f3831",
  chalk: "#ebe8dd",
  chalk2: "#b9c4bd",
  dim: "#7f948b",
  live: "#55c48f",
  signal: "#f2b33d",
} as const;

/** The landing hero's motif, small: a day of periods, almost all self-confirmed. */
const ROWS: { label: string; cells: CellState[] }[] = [
  { label: "6A", cells: ["done", "done", "done", "done", "done", "idle"] },
  { label: "7B", cells: ["done", "done", "flag", "done", "done", "idle"] },
  { label: "9C", cells: ["done", "done", "done", "done", "done", "idle"] },
];

const CELL_STYLE: Record<CellState, React.CSSProperties> = {
  done: {
    background: "rgba(85,196,143,0.12)",
    borderColor: "rgba(85,196,143,0.32)",
    color: BOARD.live,
  },
  flag: {
    background: "rgba(242,179,61,0.14)",
    borderColor: "rgba(242,179,61,0.42)",
    color: BOARD.signal,
  },
  idle: { borderColor: BOARD.rule, borderStyle: "dashed", color: "transparent" },
};

const CELL_MARK: Record<CellState, string> = { done: "✓", flag: "!", idle: "" };

function BoardMotif() {
  return (
    <div
      className="rounded-md border p-4"
      style={{ background: BOARD.slate, borderColor: BOARD.rule }}
    >
      <p
        className="font-mono text-[0.62rem] uppercase tracking-[0.18em]"
        style={{ color: BOARD.dim }}
      >
        Today · periods 1–6
      </p>
      <div className="mt-3 space-y-1.5">
        {ROWS.map((row) => (
          <div key={row.label} className="flex items-center gap-1.5">
            <span className="w-6 shrink-0 font-mono text-[0.62rem]" style={{ color: BOARD.dim }}>
              {row.label}
            </span>
            {row.cells.map((state, i) => (
              <span
                key={i}
                className="flex h-6 flex-1 items-center justify-center rounded-[3px] border font-mono text-[0.6rem]"
                style={CELL_STYLE[state]}
              >
                {CELL_MARK[state]}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Staff and parents sign in through different doors with different credentials,
 * and a parent who lands on the staff form has no way to tell — they simply
 * fail, against a correct-looking error. So both doors are named on both screens.
 */
function AudienceSwitch({ audience }: { audience: Audience }) {
  const tabs: { key: Audience; label: string; href: string }[] = [
    { key: "staff", label: "Staff", href: "/auth/login" },
    { key: "parent", label: "Parent", href: "/parent/login" },
  ];

  return (
    <div className="mb-4 grid grid-cols-2 gap-1 rounded-lg border border-border bg-muted/40 p-1">
      {tabs.map((t) => {
        const on = t.key === audience;
        return (
          <Link
            key={t.key}
            href={t.href}
            aria-current={on ? "page" : undefined}
            className={
              on
                ? "rounded-md bg-card px-3 py-2 text-center text-sm font-semibold text-foreground shadow-sm"
                : "rounded-md px-3 py-2 text-center text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            }
          >
            {t.label}
          </Link>
        );
      })}
    </div>
  );
}

export function AuthShell({ title, subtitle, children, footer, audience }: AuthShellProps) {
  return (
    <main className="grid min-h-dvh lg:grid-cols-[1.05fr_1fr]">
      {/* ── The board ─────────────────────────────────────────────────────── */}
      <aside
        aria-hidden="true"
        className="relative hidden flex-col justify-between p-10 lg:flex xl:p-14"
        style={{ background: BOARD.board, color: BOARD.chalk }}
      >
        <div className="flex items-baseline gap-2">
          <span className="text-lg font-bold tracking-tight">TrackBit</span>
          <span
            className="font-mono text-[0.62rem] uppercase tracking-[0.18em]"
            style={{ color: BOARD.live }}
          >
            School
          </span>
        </div>

        <div className="max-w-md">
          <p
            className="font-mono text-[0.66rem] uppercase tracking-[0.2em]"
            style={{ color: BOARD.dim }}
          >
            The school&apos;s daily operating system
          </p>
          <p className="mt-4 text-3xl font-bold leading-[1.08] tracking-tight xl:text-[2.4rem]">
            Every period of every day,{" "}
            <span style={{ color: BOARD.live }}>on the record.</span>
          </p>
          <p className="mt-5 text-sm leading-relaxed" style={{ color: BOARD.chalk2 }}>
            Attendance, syllabus pace, homework, exams, fees and the parent portal — all computed
            from one record, captured a tap at a time.
          </p>

          <div className="mt-8">
            <BoardMotif />
          </div>
        </div>

        <p className="font-mono text-[0.66rem]" style={{ color: BOARD.dim }}>
          23 of 24 periods confirmed themselves today.
        </p>
      </aside>

      {/* ── The form ──────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <Link href="/" className="mb-8 flex items-baseline justify-center gap-2 lg:hidden">
            <span className="text-xl font-bold tracking-tight text-foreground">TrackBit</span>
            <span className="font-mono text-[0.6rem] uppercase tracking-[0.18em] text-primary">
              School
            </span>
          </Link>

          {audience ? <AudienceSwitch audience={audience} /> : null}

          <div className="rounded-xl border border-border bg-card p-6 shadow-sm">
            <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
            {subtitle ? <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p> : null}
            <div className="mt-6">{children}</div>
          </div>

          {footer ? (
            <div className="mt-4 text-center text-sm text-muted-foreground">{footer}</div>
          ) : null}

          <p className="mt-6 text-center text-xs text-muted-foreground">
            <Link href="/" className="transition-colors hover:text-foreground">
              ← Back to the site
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
