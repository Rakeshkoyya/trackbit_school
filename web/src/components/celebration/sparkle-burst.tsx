"use client";

// A short, centered sparkle burst — the "variable reward" (plan §3.1, ~1 in 7).
const PARTICLES = Array.from({ length: 10 }, (_, i) => {
  const angle = (i / 10) * Math.PI * 2;
  const dist = 42 + (i % 3) * 12;
  return { dx: Math.cos(angle) * dist, dy: Math.sin(angle) * dist, hue: i };
});

const COLORS = ["#2f8f5b", "#b5791f", "#2f6f4f", "#d8a23a"];

export function SparkleBurst() {
  return (
    <div className="pointer-events-none fixed inset-0 z-[60] flex items-center justify-center">
      <div className="relative">
        {PARTICLES.map((p, i) => (
          <span
            key={i}
            className="absolute h-2 w-2 rounded-full"
            style={
              {
                background: COLORS[i % COLORS.length],
                ["--dx" as string]: `${p.dx}px`,
                ["--dy" as string]: `${p.dy}px`,
                animation: "tb-sparkle 620ms ease-out forwards",
              } as React.CSSProperties
            }
          />
        ))}
      </div>
    </div>
  );
}
