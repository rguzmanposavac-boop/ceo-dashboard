"use client";

import type { Signal } from "@/lib/types";
import { SIGNAL_COLORS } from "@/lib/constants";

const SIGNAL_LABELS: Record<Signal, string> = {
  COMPRA_FUERTE: "COMPRA FUERTE",
  COMPRA:        "COMPRA",
  "COMPRA CON CAUTION": "COMPRA CON CAUTION",
  VIGILAR:       "VIGILAR",
  SALIR:         "SALIR",
  EVITAR:        "EVITAR",
};

const SIGNAL_CLASSES: Record<Signal, string> = {
  COMPRA_FUERTE: "bg-green-600 text-white border-green-500",
  COMPRA: "bg-yellow-600 text-black border-yellow-500",
  "COMPRA CON CAUTION": "bg-yellow-500 text-black border-yellow-400",
  VIGILAR: "bg-orange-600 text-white border-orange-500",
  SALIR: "bg-red-600 text-white border-red-500",
  EVITAR: "bg-red-600 text-white border-red-500",
};

interface Props {
  signal: Signal | null | undefined;
  size?: "sm" | "md" | "lg";
}

export function SignalBadge({ signal, size = "md" }: Props) {
  if (!signal) return <span className="text-text-secondary text-xs">—</span>;

  const sizeClasses = {
    sm: "text-xs px-1.5 py-0.5",
    md: "text-xs px-2 py-1 font-semibold",
    lg: "text-sm px-3 py-1.5 font-bold",
  }[size];

  return (
    <span
      className={`inline-block rounded font-mono tracking-wide ${sizeClasses} border ${SIGNAL_CLASSES[signal]}`}
    >
      {SIGNAL_LABELS[signal]}
    </span>
  );
}
