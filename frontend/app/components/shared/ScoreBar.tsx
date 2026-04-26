"use client";

interface Props {
  value: number | null | undefined;
  max?: number;
  label?: string;
  showValue?: boolean;
}

function scoreColor(v: number): string {
  if (v >= 80) return "#3de88a";
  if (v >= 70) return "#f5c542";
  if (v >= 58) return "#ff8c42";
  return "#ff5e5e";
}

export function ScoreBar({ value, max = 100, label, showValue = true }: Props) {
  const v = value ?? 0;
  const pct = Math.min(100, Math.max(0, (v / max) * 100));
  const color = scoreColor(v);

  return (
    <div className="w-full">
      {(label || showValue) && (
        <div className="flex justify-between items-center mb-1">
          {label && <span className="text-xs text-text-secondary">{label}</span>}
          {showValue && (
            <span className="text-xs font-mono" style={{ color }}>
              {value != null ? v.toFixed(1) : "—"}
            </span>
          )}
        </div>
      )}
      <div className="h-1.5 rounded-full bg-border overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}
