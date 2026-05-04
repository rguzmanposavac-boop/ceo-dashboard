"use client";

import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { Stock, Signal, Horizon, Catalyst } from "@/lib/types";
import { SIGNAL_COLORS, HORIZON_LABELS } from "@/lib/constants";
import { SignalBadge } from "@/app/components/shared/SignalBadge";
import { useDashboardStore } from "@/stores/dashboardStore";
import { api } from "@/lib/api";
import { ComparisonModal } from "@/app/components/opportunities/ComparisonModal";

interface Props {
  stocks: Stock[];
  onSelect: (ticker: string) => void;
  selectedTicker: string | null;
}

const SIGNALS: Array<Signal | ""> = ["", "COMPRA_FUERTE", "COMPRA", "COMPRA CON CAUTION", "VIGILAR", "SALIR", "EVITAR"];
const HORIZONS: Array<Horizon | ""> = ["", "CORTO_PLAZO", "MEDIANO_PLAZO", "LARGO_PLAZO"];

function pct(v: number | null | undefined) {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
}

function price(v: number | null | undefined) {
  if (v == null) return "—";
  return `$${v.toFixed(2)}`;
}

function scoreCell(v: number | null | undefined) {
  if (v == null) return <span className="text-text-muted">—</span>;
  const color =
    v >= 80 ? "#3de88a" : v >= 70 ? "#f5c542" : v >= 58 ? "#ff8c42" : "#ff5e5e";
  return (
    <span className="font-mono font-bold text-base" style={{ color }}>
      {v.toFixed(1)}
    </span>
  );
}

function invalidatorSummary(stock: Stock) {
  const invalidators = stock.score?.invalidators;
  if (!invalidators || invalidators.length === 0) return null;
  const keys = invalidators.map((item) =>
    typeof item === "string" ? item : item.key ?? String(item)
  );
  return `${keys.length} invalidadores activos: ${keys.join(", ")}`;
}

export function OpportunityRadar({ stocks, onSelect, selectedTicker }: Props) {
  const { filters, setFilter, resetFilters } = useDashboardStore();
  const [sortField, setSortField] = useState<"score" | "ticker" | "change_pct">("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [compareSet, setCompareSet] = useState<string[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);

  const handleSort = (field: "score" | "ticker" | "change_pct") => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir(field === "ticker" ? "asc" : "desc");
    }
  };

  const { data: catalysts = [] } = useQuery<Catalyst[]>({
    queryKey: ["catalysts"],
    queryFn: api.catalysts.list,
    staleTime: 5 * 60 * 1000,
  });
  const catalystById = useMemo(() => {
    const m = new Map<number, Catalyst>();
    catalysts.forEach((c) => m.set(c.id, c));
    return m;
  }, [catalysts]);

  const toggleCompare = (ticker: string) => {
    setCompareSet((current) => {
      if (current.includes(ticker)) {
        return current.filter((item) => item !== ticker);
      }
      if (current.length < 2) {
        return [...current, ticker];
      }
      return [ticker];
    });
  };

  const compareStocks = compareSet
    .map((ticker) => stocks.find((item) => item.ticker === ticker))
    .filter((item): item is Stock => Boolean(item));

  const filtered = useMemo(() => {
    const list = stocks.filter((s) => {
      if (filters.signal && s.score?.signal !== filters.signal) return false;
      if (filters.horizon && s.score?.horizon !== filters.horizon) return false;
      if (filters.sector && s.sector !== filters.sector) return false;
      if (filters.min_score != null && (s.score?.final_score ?? 0) < filters.min_score) return false;
      return true;
    });
    
    list.sort((a, b) => {
      let aVal: any, bVal: any;
      if (sortField === "score") {
        aVal = a.score?.final_score ?? -1;
        bVal = b.score?.final_score ?? -1;
      } else if (sortField === "ticker") {
        aVal = a.ticker;
        bVal = b.ticker;
      } else if (sortField === "change_pct") {
        aVal = a.change_pct ?? -999;
        bVal = b.change_pct ?? -999;
      }
      if (aVal < bVal) return sortDir === "asc" ? -1 : 1;
      if (aVal > bVal) return sortDir === "asc" ? 1 : -1;
      return 0;
    });

    return list;
  }, [stocks, filters, sortField, sortDir]);

  const sectors = useMemo(() => {
    const set = new Set(stocks.map((s) => s.sector));
    return Array.from(set).sort();
  }, [stocks]);

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: "#0f1b30", border: "1px solid #1e3050" }}
    >
      {/* Filter bar */}
      <div
        className="flex flex-wrap items-center gap-2 px-4 py-3 border-b"
        style={{ borderColor: "#1e3050" }}
      >
        <span className="text-xs text-text-secondary font-semibold uppercase tracking-widest mr-1">
          Filtros
        </span>

        <select
          id="filter-signal"
          name="filter-signal"
          className="text-xs px-2 py-1 rounded text-text-primary focus:outline-none"
          style={{ background: "#111e35", border: "1px solid #1e3050" }}
          value={filters.signal}
          onChange={(e) => setFilter("signal", e.target.value as Signal | "")}
        >
          {SIGNALS.map((s) => (
            <option key={s} value={s}>{s || "Todas las señales"}</option>
          ))}
        </select>

        <select
          id="filter-horizon"
          name="filter-horizon"
          className="text-xs px-2 py-1 rounded text-text-primary focus:outline-none"
          style={{ background: "#111e35", border: "1px solid #1e3050" }}
          value={filters.horizon}
          onChange={(e) => setFilter("horizon", e.target.value as Horizon | "")}
        >
          {HORIZONS.map((h) => (
            <option key={h} value={h}>{h ? HORIZON_LABELS[h] : "Todos los horizontes"}</option>
          ))}
        </select>

        <select
          id="filter-sector"
          name="filter-sector"
          className="text-xs px-2 py-1 rounded text-text-primary focus:outline-none"
          style={{ background: "#111e35", border: "1px solid #1e3050" }}
          value={filters.sector}
          onChange={(e) => setFilter("sector", e.target.value)}
        >
          <option value="">Todos los sectores</option>
          {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>

        <input
          id="filter-min-score"
          name="filter-min-score"
          type="number"
          placeholder="Score mín."
          className="text-xs px-2 py-1 rounded text-text-primary focus:outline-none w-24"
          style={{ background: "#111e35", border: "1px solid #1e3050" }}
          value={filters.min_score ?? ""}
          onChange={(e) => setFilter("min_score", e.target.value ? Number(e.target.value) : null)}
        />

        {(filters.signal || filters.horizon || filters.sector || filters.min_score) && (
          <button
            onClick={resetFilters}
            className="text-xs px-2 py-1 rounded text-text-secondary hover:text-text-primary transition-colors"
            style={{ border: "1px solid #1e3050" }}
          >
            Limpiar
          </button>
        )}

        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-text-secondary">
            {filtered.length} / {stocks.length} acciones
          </span>
          <button
            type="button"
            onClick={() => setCompareOpen(true)}
            disabled={compareSet.length < 2}
            className="text-xs rounded px-3 py-1"
            style={{
              background: compareSet.length < 2 ? "#1e3050" : "#5ba4ff18",
              border: "1px solid #5ba4ff44",
              color: compareSet.length < 2 ? "#7090b0" : "#5ba4ff",
            }}
          >
            Comparar ({compareSet.length}/2)
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr
              className="text-left text-xs text-text-secondary uppercase tracking-wider"
              style={{ borderBottom: "1px solid #1e3050" }}
            >
              <th className="px-4 py-3"> </th>
              <th className="px-4 py-3 cursor-pointer hover:text-white transition-colors" onClick={() => handleSort("ticker")}>
                Ticker {sortField === "ticker" ? (sortDir === "asc" ? "↑" : "↓") : ""}
              </th>
              <th className="px-4 py-3">Empresa</th>
              <th className="px-4 py-3">Sector</th>
              <th className="px-4 py-3 text-right">Precio</th>
              <th className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors" onClick={() => handleSort("change_pct")}>
                Var% {sortField === "change_pct" ? (sortDir === "asc" ? "↑" : "↓") : ""}
              </th>
              <th className="px-4 py-3 text-right">Tendencia 12M</th>
              <th className="px-4 py-3 text-right">Momentum 3M</th>
              <th className="px-4 py-3 text-right cursor-pointer hover:text-white transition-colors" onClick={() => handleSort("score")}>
                Score {sortField === "score" ? (sortDir === "asc" ? "↑" : "↓") : ""}
              </th>
              <th className="px-4 py-3">Señal</th>
              <th className="px-4 py-3">Horizonte</th>
              <th className="px-4 py-3">Catalizador</th>
              <th className="px-4 py-3 text-right">Ret. Est.</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((stock) => {
              const isSelected = stock.ticker === selectedTicker;
              const retLow = stock.score?.expected_return_low;
              const retHigh = stock.score?.expected_return_high;
              const retStr =
                retLow != null && retHigh != null
                  ? `${pct(retLow)} – ${pct(retHigh)}`
                  : "—";
              const catalyst = stock.score?.catalyst_id
                ? catalystById.get(stock.score.catalyst_id)
                : undefined;
              const changePct = stock.change_pct;
              const changeColor =
                changePct == null ? "#7090b0" : changePct >= 0 ? "#3de88a" : "#ff5e5e";
              const invalidatorCount = stock.score?.invalidators?.length ?? 0;
              const hasInvalidators = invalidatorCount > 0;
              const invalidatorTooltip = hasInvalidators ? invalidatorSummary(stock) : "";

              return (
                <tr
                  key={stock.ticker}
                  onClick={() => onSelect(stock.ticker)}
                  className="cursor-pointer transition-colors"
                  style={{
                    borderBottom: "1px solid #1e3050",
                    background: isSelected
                      ? "#1a2d4a"
                      : hasInvalidators
                      ? "rgba(239, 68, 68, 0.1)"
                      : "transparent",
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) (e.currentTarget as HTMLElement).style.background = "#111e35";
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) (e.currentTarget as HTMLElement).style.background =
                      hasInvalidators ? "rgba(239, 68, 68, 0.1)" : "transparent";
                  }}
                >
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={compareSet.includes(stock.ticker)}
                      onChange={(e) => {
                        e.stopPropagation();
                        toggleCompare(stock.ticker);
                      }}
                      className="h-4 w-4 rounded border-[#1e3050] text-blue-400 bg-[#111e35]"
                    />
                  </td>
                  <td className="px-4 py-3 font-mono font-bold text-blue-400">
                    <div className="inline-flex items-center gap-1">
                      <span>{stock.ticker}</span>
                      {hasInvalidators && (
                        <span
                          className="text-[#EF4444]"
                          title={invalidatorTooltip ?? undefined}
                          style={{ fontSize: 16, lineHeight: 1 }}
                        >
                          🚨
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-text-primary max-w-[180px] truncate">
                    {stock.company}
                  </td>
                  <td className="px-4 py-3 text-text-secondary text-xs">{stock.sector}</td>
                  <td className="px-4 py-3 text-right font-mono text-text-primary">
                    {price(stock.current_price)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm" style={{ color: changeColor }}>
                    {changePct != null
                      ? `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%`
                      : "—"}
                  </td>
                  <td className="px-4 py-3 text-xs" style={{
                    color:
                      (stock.trend_12m ?? 0) > 30 ? '#22c55e' : (stock.trend_12m ?? 0) < 0 ? '#ef4444' : '#9ca3af',
                  }}>
                    {stock.trend_12m != null
                      ? `${stock.trend_12m > 0 ? '+' : ''}${stock.trend_12m.toFixed(1)}% (${stock.trend_label ?? '—'})`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-xs" style={{
                    color:
                      (stock.momentum_3m ?? 0) > 10 ? '#22c55e' : (stock.momentum_3m ?? 0) < 0 ? '#ef4444' : '#9ca3af',
                  }}>
                    {stock.momentum_3m != null
                      ? `${stock.momentum_3m > 0 ? '+' : ''}${stock.momentum_3m.toFixed(1)}% (${stock.momentum_label ?? '—'})`
                      : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">{scoreCell(stock.score?.final_score)}</td>
                  <td className="px-4 py-3">
                    <SignalBadge signal={stock.score?.signal} size="sm" />
                  </td>
                  <td className="px-4 py-3 text-xs text-text-secondary">
                    {stock.score?.horizon ? HORIZON_LABELS[stock.score.horizon] : "—"}
                  </td>
                  <td className="px-4 py-3 max-w-[160px]">
                    {catalyst ? (
                      <span
                        className="text-xs truncate block max-w-full"
                        style={{ color: "#5ba4ff" }}
                        title={catalyst.name}
                      >
                        {catalyst.name.length > 28
                          ? catalyst.name.slice(0, 28) + "…"
                          : catalyst.name}
                      </span>
                    ) : (
                      <span className="text-text-muted text-xs">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right text-xs font-mono text-text-secondary">
                    {retStr}
                  </td>
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr>
                <td colSpan={13} className="px-4 py-10 text-center text-text-secondary">
                  No hay acciones con los filtros seleccionados
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <ComparisonModal
        open={compareOpen}
        left={compareStocks[0]}
        right={compareStocks[1]}
        onClose={() => setCompareOpen(false)}
      />
    </div>
  );
}
