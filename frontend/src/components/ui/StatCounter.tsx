import { useCountUp } from "../../hooks/useCountUp";

export function StatCounter({
  value,
  label,
  suffix = "",
}: {
  value: number;
  label: string;
  suffix?: string;
}) {
  const animated = useCountUp(value);
  return (
    <div className="text-center">
      <div className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
        {animated.toLocaleString()}
        {suffix}
      </div>
      <div className="mt-1 text-sm text-white/55">{label}</div>
    </div>
  );
}
