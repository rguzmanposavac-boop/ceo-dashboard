"use client";

import { useReducer, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ModelStats, TickerBacktestStat, TierStat } from "@/lib/types";
import { useDashboardStore } from "@/stores/dashboardStore";

function relativeTime(ts: string | null | undefined): string {
  if (!ts) return "nunca";
  const diffMs = Date.now() - new Date(ts).getTime();
  if (diffMs < 0) return "ahora mismo";
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1)  return "hace un momento";
  if (diffMin < 60) return `hace ${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `hace ${diffH}h`;
  return `hace ${Math.floor(diffH / 24)} días`;
}

function RefreshRow() {
  const [, tick] = useReducer((x: number) => x + 1, 0);
  useEffect(() => {
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  const queryClient = useQueryClient();
  const {
    refreshConfig,
    isRefreshingPrices,
    isRefreshingScores,
    setIsRefreshingPrices,
    setIsRefreshingScores,
    patchRefreshConfig,
  } = useDashboardStore();

  const handleRefreshPrices = async () => {
    setIsRefreshingPrices(true);
    try {
      await api.refresh.prices();
      setTimeout(async () => {
        const cfg = await api.config.getRefreshSchedule();
        patchRefreshConfig({ last_price_update: cfg.last_price_update });
        setIsRefreshingPrices(false);
      }, 4000);
    } catch {
      setIsRefreshingPrices(false);
    }
  };

  const handleRefreshScores = async () => {
    setIsRefreshingScores(true);
    try {
      await api.refresh.scores();
      setTimeout(async () => {
        const cfg = await api.config.getRefreshSchedule();
        patchRefreshConfig({ last_score_update: cfg.last_score_update });
        queryClient.invalidateQueries({ queryKey: ["stocks"] });
        setIsRefreshingScores(false);
      }, 8000);
    } catch {
      setIsRefreshingScores(false);
    }
  };

  const btnStyle = (loading: boolean): React.CSSProperties => ({
    background: loading ? "#1e3050" : "#5ba4ff18",
    border:     "1px solid #5ba4ff44",
    color:      loading ? "#7090b0" : "#5ba4ff",
    cursor:     loading ? "not-allowed" : "pointer",
    opacity:    loading ? 0.7 : 1,
  });

  return (
    <div
      className="flex flex-wrap items-center gap-x-8 gap-y-2 pb-3 mb-3 border-b text-xs"
      style={{ borderColor: "#1e3050" }}
    >
      {/* Prices */}
      <div className="flex items-center gap-3">
        <span style={{ color: "#3a5070" }}>
          Última actualización:{" "}
          <span style={{ color: "#7090b0" }}>{relativeTime(refreshConfig?.last_price_update)}</span>
        </span>
        <button
          onClick={handleRefreshPrices}
          disabled={isRefreshingPrices}
          className="px-2 py-0.5 rounded transition-opacity"
          style={btnStyle(isRefreshingPrices)}
        >
          {isRefreshingPrices ? "Actualizando…" : "🔄 Actualizar precios"}
        </button>
      </div>

      {/* Scores */}
      <div className="flex items-center gap-3">
        <span style={{ color: "#3a5070" }}>
          Scores:{" "}
          <span style={{ color: "#7090b0" }}>{relativeTime(refreshConfig?.last_score_update)}</span>
        </span>
        <button
          onClick={handleRefreshScores}
          disabled={isRefreshingScores}
          className="px-2 py-0.5 rounded transition-opacity"
          style={btnStyle(isRefreshingScores)}
        >
          {isRefreshingScores ? "Recalculando…" : "🔄 Recalcular scores"}
        </button>
      </div>
    </div>
  );
}

const TIER_ORDER = ["COMPRA_FUERTE", "COMPRA", "VIGILAR", "EVITAR"] as const;
const TIER_COLOR: Record<string, string> = {
  COMPRA_FUERTE: "#3de88a",
  COMPRA:        "#f5c542",
  VIGILAR:       "#ff8c42",
  EVITAR:        "#ff5e5e",
};
const TIER_LABEL: Record<string, string> = {
  COMPRA_FUERTE: "Compra Fuerte",
  COMPRA:        "Compra",
  VIGILAR:       "Vigilar",
  EVITAR:        "Evitar",
};

function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="flex flex-col items-center px-4 py-2">
      <span className="text-lg font-mono font-bold text-accent-blue">{value}</span>
      <span className="text-xs text-text-secondary mt-0.5">{label}</span>
      {sub && <span className="text-xs text-text-muted">{sub}</span>}
    </div>
  );
}

function HitRateBar({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-text-muted">—</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 65 ? "#3de88a" : pct >= 50 ? "#f5c542" : "#ff8c42";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 rounded-full overflow-hidden" style={{ background: "#1e3050" }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="font-mono font-bold text-sm" style={{ color }}>{pct}%</span>
    </div>
  );
}

function TierTable({ tierStats }: { tierStats: Record<string, TierStat> }) {
  return (
    <div className="overflow-x-auto">
      <table className="text-xs w-full">
        <thead>
          <tr style={{ color: "#7090b0" }}>
            <th className="text-left py-1 pr-4 font-semibold">Señal</th>
            <th className="text-right py-1 pr-4 font-semibold">N señales</th>
            <th className="text-right py-1 pr-4 font-semibold">Ret. medio 3M</th>
            <th className="text-right py-1 pr-4 font-semibold">Hit &gt;10%</th>
            <th className="text-right py-1 font-semibold">Hit &gt;0%</th>
          </tr>
        </thead>
        <tbody>
          {TIER_ORDER.map((tier) => {
            const s = tierStats[tier];
            if (!s) return null;
            const retColor = s.avg_return >= 10 ? "#3de88a" : s.avg_return >= 0 ? "#f5c542" : "#ff5e5e";
            return (
              <tr key={tier} className="border-t" style={{ borderColor: "#1e3050" }}>
                <td className="py-1 pr-4 font-mono font-bold" style={{ color: TIER_COLOR[tier] }}>
                  {TIER_LABEL[tier]}
                </td>
                <td className="text-right py-1 pr-4 text-text-secondary">{s.count}</td>
                <td className="text-right py-1 pr-4 font-mono font-bold" style={{ color: retColor }}>
                  {s.avg_return >= 0 ? "+" : ""}{s.avg_return.toFixed(1)}%
                </td>
                <td className="text-right py-1 pr-4 font-mono" style={{ color: TIER_COLOR[tier] }}>
                  {Math.round(s.hit_rate_10pct * 100)}%
                </td>
                <td className="text-right py-1 font-mono text-text-secondary">
                  {Math.round(s.hit_rate_pos * 100)}%
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function FooterStats() {
  const queryClient = useQueryClient();

  const { data: stats, isLoading } = useQuery<ModelStats>({
    queryKey: ["model-stats"],
    queryFn: api.admin.modelStats,
    staleTime: 10 * 60 * 1000,
  });

  const { mutate: runBacktest, isPending } = useMutation({
    mutationFn: api.admin.runBacktest,
    onSuccess: (data) => {
      queryClient.setQueryData(["model-stats"], data);
    },
  });

  const isFromBacktest = stats?.source === "backtest";

  return (
    <footer
      className="border-t"
      style={{ background: "#0a0e1a", borderColor: "#1e3050" }}
    >
      <div className="max-w-screen-2xl mx-auto px-4 py-4">

        {/* Refresh status + force-refresh buttons */}
        <RefreshRow />

        {/* Stats row */}
        {isLoading ? (
          <div className="animate-pulse h-12 rounded" style={{ background: "#1e3050" }} />
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-4">

            {/* Model quality metrics */}
            <div
              className="flex flex-wrap gap-0 divide-x rounded-lg overflow-hidden"
              style={{ border: "1px solid #1e3050", borderRight: "none" }}
            >
              <Stat
                label="R² del modelo"
                value={stats?.r_squared != null ? stats.r_squared.toFixed(2) : "—"}
              />
              <Stat
                label="Spearman ρ"
                value={stats?.spearman_rho != null ? stats.spearman_rho.toFixed(3) : "—"}
                sub={stats?.spearman_p != null ? `p=${stats.spearman_p.toFixed(3)}` : undefined}
              />
              {isFromBacktest && (
                <>
                  <div className="px-4 py-2 flex flex-col items-center justify-center" style={{ borderLeft: "1px solid #1e3050" }}>
                    <HitRateBar value={stats?.hit_rate_cf} />
                    <span className="text-xs text-text-secondary mt-0.5">Hit rate CF</span>
                    <span className="text-xs text-text-muted">precio +10% en 3M</span>
                  </div>
                  <div className="px-4 py-2 flex flex-col items-center justify-center" style={{ borderLeft: "1px solid #1e3050" }}>
                    <HitRateBar value={stats?.hit_rate_buy} />
                    <span className="text-xs text-text-secondary mt-0.5">Hit rate COMPRA+</span>
                    <span className="text-xs text-text-muted">precio +10% en 3M</span>
                  </div>
                  <Stat
                    label="Señales CF"
                    value={stats?.total_cf_signals ?? "—"}
                    sub={`de ${stats?.total_observations ?? "—"} obs`}
                  />
                  <Stat
                    label="Ret. medio CF"
                    value={
                      stats?.avg_fwd_return_cf != null
                        ? `${stats.avg_fwd_return_cf >= 0 ? "+" : ""}${stats.avg_fwd_return_cf.toFixed(1)}%`
                        : "—"
                    }
                    sub="3M post-señal"
                  />
                  {stats?.avg_excess_return != null && (
                    <Stat
                      label="Exceso vs SPY"
                      value={`${stats.avg_excess_return >= 0 ? "+" : ""}${stats.avg_excess_return.toFixed(1)}%`}
                      sub={`${Math.round((stats.win_rate_quarterly ?? 0) * 100)}% trimestres ganadores`}
                    />
                  )}
                </>
              )}
            </div>

            {/* Period + backtest trigger */}
            <div className="flex flex-col items-end gap-2">
              {isFromBacktest ? (
                <span className="text-xs text-text-muted">
                  Backtesting {stats?.period_start} → {stats?.period_end}
                  {stats?.computed_at && (
                    <> · actualizado {new Date(stats.computed_at).toLocaleDateString("es-MX")}</>
                  )}
                </span>
              ) : (
                <span className="text-xs text-text-muted italic">
                  Estadísticas estáticas · Sin backtesting ejecutado
                </span>
              )}

              <button
                onClick={() => runBacktest()}
                disabled={isPending}
                className="text-xs px-3 py-1.5 rounded transition-colors disabled:opacity-50"
                style={{
                  background: isPending ? "#1e3050" : "#5ba4ff20",
                  border: "1px solid #5ba4ff44",
                  color: "#5ba4ff",
                }}
              >
                {isPending ? "Calculando… (30-60s)" : "↻ Actualizar backtesting"}
              </button>
            </div>
          </div>
        )}

        {/* Signal tier monotonic breakdown — the key investor proof */}
        {isFromBacktest && stats?.tier_stats && Object.keys(stats.tier_stats).length > 0 && (
          <div className="mt-3 pt-3 border-t" style={{ borderColor: "#1e3050" }}>
            <div className="flex flex-wrap gap-8 items-start">
              <div className="flex-1 min-w-[280px]">
                <p className="text-xs text-text-secondary mb-2 font-semibold uppercase tracking-widest">
                  Retorno por señal — relación monotónica (2020-2024)
                </p>
                <TierTable tierStats={stats.tier_stats} />
              </div>

              {/* Per-ticker top performers */}
              {stats?.per_ticker && stats.per_ticker.length > 0 && (
                <div className="flex-1 min-w-[280px]">
                  <p className="text-xs text-text-secondary mb-2 font-semibold uppercase tracking-widest">
                    Top acciones por hit rate CF
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {stats.per_ticker.slice(0, 10).map((t: TickerBacktestStat) => (
                      t.cf_hit_rate != null && (
                        <div
                          key={t.ticker}
                          className="flex items-center gap-1.5 px-2 py-1 rounded text-xs"
                          style={{ background: "#111e35", border: "1px solid #1e3050" }}
                        >
                          <span className="font-mono font-bold text-accent-blue">{t.ticker}</span>
                          <span
                            className="font-mono"
                            style={{ color: t.cf_hit_rate >= 0.65 ? "#3de88a" : t.cf_hit_rate >= 0.50 ? "#f5c542" : "#ff8c42" }}
                          >
                            {Math.round(t.cf_hit_rate * 100)}%
                          </span>
                          <span className="text-text-muted">({t.cf_signals})</span>
                        </div>
                      )
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Regime distribution */}
        {isFromBacktest && stats?.regime_distribution && (
          <div className="mt-2 flex flex-wrap gap-3 text-xs text-text-muted">
            <span>Regímenes 2020-2024:</span>
            {Object.entries(stats.regime_distribution).map(([regime, count]) => (
              <span key={regime}>
                <span className="text-text-secondary">{regime}</span> {count}q
              </span>
            ))}
            {stats?.avg_ic != null && (
              <span className="ml-2">
                IC medio: <span className="text-text-secondary">{stats.avg_ic.toFixed(3)}</span>
                {stats?.ic_ir != null && <> · IR: <span className="text-text-secondary">{stats.ic_ir.toFixed(2)}</span></>}
              </span>
            )}
          </div>
        )}

        {/* Disclaimer */}
        <p className="mt-3 text-xs text-center" style={{ color: "#ff5e5e99" }}>
          ⚠ Este sistema es una herramienta de apoyo a la decisión. No constituye asesoría financiera.
          Los retornos históricos no garantizan resultados futuros. R²=
          {stats?.r_squared?.toFixed(2) ?? "0.61"} implica que el{" "}
          {stats?.r_squared != null ? Math.round((1 - stats.r_squared) * 100) : 39}%
          de la varianza depende de factores externos al modelo.
        </p>
      </div>
    </footer>
  );
}
