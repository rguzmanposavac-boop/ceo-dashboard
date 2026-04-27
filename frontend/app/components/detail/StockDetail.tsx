"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { SIGNAL_COLORS, HORIZON_LABELS } from "@/lib/constants";
import type { Stock, InsidersResponse, Catalyst } from "@/lib/types";
import { SignalBadge } from "@/app/components/shared/SignalBadge";
import { ScoreBar } from "@/app/components/shared/ScoreBar";
import { PriceChart } from "./PriceChart";
import { ScoreBreakdown } from "./ScoreBreakdown";
import { InvalidatorsList } from "./InvalidatorsList";

interface Props {
  ticker: string;
  onClose: () => void;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <h4 className="text-xs font-semibold uppercase tracking-widest text-text-secondary mb-2 border-b pb-1" style={{ borderColor: "#1e3050" }}>
        {title}
      </h4>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-center py-0.5 text-sm">
      <span className="text-text-secondary">{label}</span>
      <span className="text-text-primary font-mono text-xs">{value}</span>
    </div>
  );
}

export function StockDetail({ ticker, onClose }: Props) {
  const { data: stock, isLoading } = useQuery<Stock>({
    queryKey: ["stock", ticker],
    queryFn: () => api.stocks.get(ticker),
    staleTime: 60 * 1000,
  });

  const { data: insiders } = useQuery<InsidersResponse>({
    queryKey: ["insiders", ticker],
    queryFn: () => api.stocks.insiders(ticker),
    staleTime: 10 * 60 * 1000,
    retry: false,
  });

  const { data: catalysts } = useQuery<Catalyst[]>({
    queryKey: ["catalysts"],
    queryFn: api.catalysts.list,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <aside
        className="h-full overflow-y-auto p-4 rounded-lg"
        style={{ background: "#0f1b30", border: "1px solid #1e3050" }}
      >
        <div className="animate-pulse space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-4 rounded bg-border" />
          ))}
        </div>
      </aside>
    );
  }

  if (!stock) return null;

  const score = stock.score;
  const signalColor = score?.signal ? SIGNAL_COLORS[score.signal] : "#7090b0";
  const catalyst = catalysts?.find((c) => c.id === score?.catalyst_id);

  const retStr =
    score?.expected_return_low != null && score?.expected_return_high != null
      ? `+${(score.expected_return_low * 100).toFixed(0)}% – +${(score.expected_return_high * 100).toFixed(0)}%`
      : "—";

  return (
    <aside
      className="h-full overflow-y-auto p-4 rounded-lg"
      style={{ background: "#0f1b30", border: "1px solid #1e3050" }}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold font-mono text-blue-400">{stock.ticker}</span>
            {score?.signal && <SignalBadge signal={score.signal} size="md" />}
          </div>
          <p className="text-text-secondary text-sm mt-0.5">{stock.company}</p>
          <p className="text-text-muted text-xs">{stock.sector}</p>
        </div>
        <button
          onClick={onClose}
          className="text-text-muted hover:text-text-primary text-lg leading-none"
          aria-label="Cerrar"
        >
          ✕
        </button>
      </div>

      {/* Price + interactive chart */}
      <Section title="Precio">
        <div className="flex items-baseline gap-2 mb-3">
          <span className="text-2xl font-mono font-bold text-text-primary">
            {stock.current_price != null ? `$${stock.current_price.toFixed(2)}` : "—"}
          </span>
          {stock.change_pct != null && (
            <span
              className="text-sm font-mono"
              style={{ color: stock.change_pct >= 0 ? "#3de88a" : "#ff5e5e" }}
            >
              {stock.change_pct >= 0 ? "+" : ""}{stock.change_pct.toFixed(2)}%
            </span>
          )}
        </div>
        <PriceChart ticker={ticker} />
      </Section>

      {/* Score summary */}
      {score && (
        <Section title="Score total">
          <div className="flex items-center gap-3 mb-3">
            <span
              className="text-4xl font-mono font-bold"
              style={{ color: signalColor }}
            >
              {score.final_score?.toFixed(1) ?? "—"}
            </span>
            <div className="text-xs text-text-secondary">
              <div>Horizonte: <span className="text-text-primary">{score.horizon ? HORIZON_LABELS[score.horizon] : "—"}</span></div>
              <div>Prob.: <span className="text-text-primary">{score.probability != null ? `${(score.probability * 100).toFixed(0)}%` : "—"}</span></div>
              <div>Ret. esperado: <span className="text-text-primary">{retStr}</span></div>
            </div>
          </div>

          {/* Score bars */}
          <div className="space-y-2 mb-4">
            <ScoreBar value={score.core_total} label="Core total" />
            <ScoreBar value={score.catalyst_total} label="Catalyst total" />
          </div>

          {/* Radar chart */}
          <ScoreBreakdown score={score} />
        </Section>
      )}

      {/* Catalyst */}
      {catalyst && (
        <Section title="Catalizador activo">
          <div
            className="p-3 rounded text-sm"
            style={{ background: "#5ba4ff10", border: "1px solid #5ba4ff22" }}
          >
            <p className="text-text-primary font-semibold mb-1">{catalyst.name}</p>
            <p className="text-text-secondary text-xs mb-2">{catalyst.description}</p>
            <div className="flex gap-4 text-xs text-text-secondary">
              <span>Intensidad: <span className="text-blue-400 font-mono">{catalyst.intensity_score}</span></span>
              <span>Ventana: <span className="text-blue-400">{catalyst.expected_window}</span></span>
            </div>
          </div>
        </Section>
      )}

      {/* Invalidators */}
      {score?.invalidators && score.invalidators.length > 0 && (
        <Section title="">
          <InvalidatorsList invalidators={score.invalidators} />
        </Section>
      )}

      {/* CEO */}
      {stock.ceo && (
        <Section title="CEO">
          <Row label="Nombre" value={stock.ceo.name} />
          <Row label="Perfil" value={stock.ceo.profile} />
          <Row label="Tenure" value={`${stock.ceo.tenure_years} años`} />
          <Row label="Ownership" value={`${stock.ceo.ownership_pct}%`} />
          <Row label="Sucesión" value={stock.ceo.succession_quality} />
          {stock.ceo.is_founder && (
            <span
              className="inline-block mt-1 text-xs px-2 py-0.5 rounded"
              style={{ background: "#f5c54220", color: "#f5c542", border: "1px solid #f5c54244" }}
            >
              Fundador
            </span>
          )}
        </Section>
      )}

      {/* Insiders */}
      {insiders && insiders.transactions.length > 0 && (
        <Section title={`Insiders Form 4 (${insiders.count})`}>
          <div className="space-y-1.5">
            {insiders.transactions.slice(0, 5).map((txn, i) => {
              const isBuy = txn.transaction_type?.toLowerCase().includes("p");
              return (
                <div
                  key={i}
                  className="text-xs flex justify-between items-center p-2 rounded"
                  style={{ background: "#111e35" }}
                >
                  <div>
                    <span className="text-text-primary">{txn.insider_name}</span>
                    {txn.title && <span className="text-text-muted ml-1">({txn.title})</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span style={{ color: isBuy ? "#3de88a" : "#ff5e5e" }}>
                      {txn.transaction_type}
                    </span>
                    {txn.shares != null && (
                      <span className="text-text-secondary font-mono">
                        {txn.shares.toLocaleString()}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Section>
      )}
    </aside>
  );
}
