function scoreColor(score: number): string {
  if (score >= 7.5) return "var(--color-good)";
  if (score >= 5) return "var(--color-warn)";
  return "var(--color-bad)";
}

export function ScoreBadge({ score, size = "md" }: { score: number; size?: "sm" | "md" | "lg" }) {
  const dims = { sm: "h-9 w-9 text-xs", md: "h-14 w-14 text-base", lg: "h-20 w-20 text-xl" }[size];
  const color = scoreColor(score);
  return (
    <div
      className={`flex ${dims} shrink-0 items-center justify-center rounded-full border font-semibold`}
      style={{
        borderColor: color,
        color,
        background: `${color}1a`,
        boxShadow: `inset 0 0 16px ${color}22`,
      }}
    >
      {score.toFixed(1)}
    </div>
  );
}
