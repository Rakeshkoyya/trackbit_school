/**
 * The day board — the hero's one signature element.
 *
 * It is the product's core claim rendered literally: a school day is a grid of
 * periods, and TrackBit knows the state of every cell. Almost every cell is
 * quietly captured; exactly one is amber. That asymmetry is the point — capture
 * by exception means the admin looks at the one cell that needs a human, not at
 * a wall of data.
 *
 * Server component: the fill-in is pure CSS with a staggered delay, so there is
 * no JS and reduced-motion callers get the finished grid instantly.
 */

type CellState = "done" | "flag" | "now" | "idle";

const PERIODS = [1, 2, 3, 4, 5, 6, 7, 8];

const ROWS: { label: string; cells: CellState[] }[] = [
  { label: "6A", cells: ["done", "done", "done", "done", "done", "now", "idle", "idle"] },
  { label: "7B", cells: ["done", "done", "flag", "done", "done", "now", "idle", "idle"] },
  { label: "9C", cells: ["done", "done", "done", "done", "done", "now", "idle", "idle"] },
];

const MARK: Record<CellState, string> = { done: "✓", flag: "!", now: "·", idle: "" };

export function DayBoard() {
  return (
    <div>
      <div className="mk-board">
        <div className="mk-board-head">
          <p className="mk-board-title mk-mono">Today · periods 1–8</p>
          <p className="mk-board-live mk-mono">
            <span className="mk-pulse" aria-hidden="true" /> Live
          </p>
        </div>

        <div className="mk-board-body">
          <div className="mk-board-rows">
            <div className="mk-board-row" data-head="true" aria-hidden="true">
              <span />
              {PERIODS.map((p) => (
                <span key={p} className="mk-board-cell mk-mono">
                  {p}
                </span>
              ))}
            </div>

            {ROWS.map((row, r) => (
              <div key={row.label} className="mk-board-row">
                <span className="mk-board-label mk-mono">{row.label}</span>
                {row.cells.map((state, c) => (
                  <span
                    key={c}
                    className="mk-board-cell mk-mono"
                    data-state={state}
                    style={{ animationDelay: `${180 + (r * 8 + c) * 34}ms` }}
                  >
                    {MARK[state]}
                  </span>
                ))}
              </div>
            ))}
          </div>
        </div>

        <div className="mk-board-foot mk-mono">
          <span className="mk-key" data-state="done">
            <i /> Captured
          </span>
          <span className="mk-key" data-state="flag">
            <i /> Needs you
          </span>
          <span className="mk-key">
            <i /> Yet to come
          </span>
        </div>
      </div>

      <p className="mk-board-caption">
        23 of 24 periods confirmed themselves. Period 3 in 7B is amber: two students absent and no
        topic logged. That is the only thing on the head&apos;s desk today.
      </p>
    </div>
  );
}
