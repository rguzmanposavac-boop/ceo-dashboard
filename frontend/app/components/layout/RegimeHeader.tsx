"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { REGIME_COLORS, FAVORED_CEO_PROFILES } from "@/lib/constants";
import type { RegimeStatus, Stock } from "@/lib/types";

const REGIME_LABELS: Record<string, string> = {
  CRISIS:  "CRISIS",
  BAJISTA: "BAJISTA",
  NORMAL:  "NORMAL",
  ALCISTA: "ALCISTA",
  REBOTE:  "REBOTE",
};

interface Props {
  stocks: Stock[];
}

export function RegimeHeader({ stocks }: Props) {
  const { data: regime } = useQuery<RegimeStatus>({
    queryKey: ["regime"],
    queryFn: api.regime.current,
    refetchInterval: 5 * 60 * 1000,
  });

  const opportunityCount = stocks.filter(
    (s) => s.score?.signal === "COMPRA_FUERTE" || s.score?.signal === "COMPRA"
  ).length;
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: api.regime.refreshVix,
    onSuccess: () => {
      queryClient.invalidateQueries(["regime"]);
    },
  });

  const color = regime ? REGIME_COLORS[regime.regime] : "#7090b0";
  const label = regime ? REGIME_LABELS[regime.regime] : "—";

  return (
    <header
      className="sticky top-0 z-20 border-b"
      style={{ background: "#0a0e1a", borderColor: "#1e3050" }}
    >
      <div className="max-w-screen-2xl mx-auto px-4 py-3 flex flex-wrap items-center gap-4">
        {/* Regime + VIX */}
        <div className="flex items-center gap-3 min-w-0">
          <span
            className="text-2xl font-bold font-mono tracking-wider px-3 py-1 rounded"
            style={{ color, border: `1px solid ${color}44`, background: `${color}15` }}
          >
            {label}
          </span>
          {regime?.vix != null && (
            <div className="flex flex-col">
              <span className="text-xs text-text-secondary">VIX</span>
              <span className="text-xl font-mono font-semibold" style={{ color }}>
                {regime.vix.toFixed(1)}
              </span>
            </div>
          )}
        </div>

        {/* Favored sectors */}
        {regime?.favored_sectors && regime.favored_sectors.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-text-secondary mr-1">Favorecidos:</span>
            {regime.favored_sectors.slice(0, 5).map((s) => (
              <span
                key={s}
                className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ background: "#3de88a20", color: "#3de88a", border: "1px solid #3de88a33" }}
              >
                {s}
              </span>
            ))}
          </div>
        )}

        {/* Avoided sectors */}
        {regime?.avoided_sectors && regime.avoided_sectors.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-text-secondary mr-1">Evitar:</span>
            {regime.avoided_sectors.slice(0, 3).map((s) => (
              <span
                key={s}
                className="text-xs px-2 py-0.5 rounded-full"
                style={{ background: "#ff5e5e20", color: "#ff5e5e", border: "1px solid #ff5e5e33" }}
              >
                {s}
              </span>
            ))}
          </div>
        )}

        {/* Favored CEO profiles */}
        {regime?.regime && FAVORED_CEO_PROFILES[regime.regime] && (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-xs text-text-secondary mr-1">CEOs:</span>
            {FAVORED_CEO_PROFILES[regime.regime].map((p) => (
              <span
                key={p}
                className="text-xs px-2 py-0.5 rounded-full"
                style={{ background: "#5ba4ff15", color: "#5ba4ff", border: "1px solid #5ba4ff33" }}
              >
                {p}
              </span>
            ))}
          </div>
        )}

        {/* Opportunity count + refresh */}
        <div className="ml-auto flex flex-col items-end gap-2">
          <span
            className="text-sm font-semibold px-3 py-1 rounded-full"
            style={{ background: "#3de88a20", color: "#3de88a", border: "1px solid #3de88a44" }}
          >
            {opportunityCount} oportunidades activas
          </span>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isLoading}
            className="text-xs rounded px-3 py-1"
            style={{
              background: "#5ba4ff18",
              border: "1px solid #5ba4ff44",
              color: "#5ba4ff",
            }}
          >
            {mutation.isLoading ? "Actualizando…" : "Actualizar VIX"}
          </button>
        </div>
      </div>
    </header>
  );
}
