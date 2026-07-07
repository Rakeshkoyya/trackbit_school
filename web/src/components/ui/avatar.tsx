import { cn } from "@/lib/utils";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// Deterministic soft tint per name so people are visually distinguishable.
const TINTS = [
  "bg-[#e7efe9] text-[#234a37]",
  "bg-[#f3ece0] text-[#6b5326]",
  "bg-[#e6edf3] text-[#274058]",
  "bg-[#f1e9ef] text-[#5a2f50]",
  "bg-[#eaeee0] text-[#46532a]",
];

export function Avatar({ name, className }: { name: string; className?: string }) {
  const tint = TINTS[Math.abs(hash(name)) % TINTS.length];
  return (
    <span
      className={cn(
        "inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold",
        tint,
        className,
      )}
      title={name}
    >
      {initials(name)}
    </span>
  );
}

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h << 5) - h + s.charCodeAt(i);
  return h;
}
