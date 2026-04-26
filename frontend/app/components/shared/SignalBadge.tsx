"use client";

import type { Signal } from "@/lib/types";
import { SIGNAL_COLORS } from "@/lib/constants";

const SIGNAL_LABELS: Record<Signal, string> = {
  COMPRA_FUERTE: "COMPRA FUERTE",
  COMPRA:        "COMPRA",
  VIGILAR:       "VIGILAR",
  EVITAR:        "EVITAR",
};

interface Props {
  signal: Signal | null | undefined;
  size?: "sm" | "md" | "lg";
}

export function SignalBadge({ signal, size = "md" }: Props) {
  if (!signal) return <span className="text-text-secondary text-xs">—</span>;

  const color = SIGNAL_COLORS[signal] || "#7090b0";
  const sizeClasses = {
    sm: "text-xs px-1.5 py-0.5",
    md: "text-xs px-2 py-1 font-semibold",
    lg: "text-sm px-3 py-1.5 font-bold",
  }[size];

  return (
    <span
      className={`inline-block rounded font-mono tracking-wide ${sizeClasses}`}
      style={{ color, border: `1px solid ${color}33`, background: `${color}15` }}
    >
      {SIGNAL_LABELS[signal]}
    </span>
  );
}
