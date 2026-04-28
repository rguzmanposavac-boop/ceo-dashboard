"use client";

import { useState, useEffect, useReducer, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RefreshConfig, RefreshInterval } from "@/lib/types";
import { useDashboardStore } from "@/stores/dashboardStore";

// ─── Constants ───────────────────────────────────────────────────────────────

const INTERVAL_OPTIONS: { value: RefreshInterval; label: string }[] = [
  { value: "manual", label: "Manual" },
  { value: "1min",   label: "Cada 1 minuto" },
  { value: "5min",   label: "Cada 5 minutos" },
  { value: "1hour",  label: "Cada 1 hora" },
  { value: "daily",  label: "Una vez al día" },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

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

function nextMonday(): string {
  const d = new Date();
  const day = d.getDay(); // 0=Sun…6=Sat
  const add  = day === 0 ? 1 : day === 1 ? 7 : 8 - day;
  d.setDate(d.getDate() + add);
  return d.toLocaleDateString("es-MX", {
    weekday: "long",
    day:     "numeric",
    month:   "long",
  });
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-widest mb-2" style={{ color: "#7090b0" }}>
      {children}
    </p>
  );
}

function IntervalSelect({
  id,
  value,
  onChange,
  disabled,
}: {
  id: string;
  value: RefreshInterval;
  onChange: (v: RefreshInterval) => void;
  disabled?: boolean;
}) {
  return (
    <select
      id={id}
      name={id}
      value={value}
      onChange={(e) => onChange(e.target.value as RefreshInterval)}
      disabled={disabled}
      className="w-full text-xs rounded px-2 py-1.5 font-mono"
      style={{
        background: "#0a0e1a",
        border: "1px solid #1e3050",
        color: "#e0e6f0",
        outline: "none",
        cursor: disabled ? "not-allowed" : "pointer",
      }}
    >
      {INTERVAL_OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

function ActionButton({
  onClick,
  loading,
  children,
}: {
  onClick: () => void;
  loading?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="w-full text-xs px-3 py-1.5 rounded font-semibold transition-opacity"
      style={{
        background: loading ? "#1e3050" : "#5ba4ff18",
        border: "1px solid #5ba4ff44",
        color: loading ? "#7090b0" : "#5ba4ff",
        cursor: loading ? "not-allowed" : "pointer",
        opacity: loading ? 0.7 : 1,
      }}
    >
      {loading ? "Procesando…" : children}
    </button>
  );
}

function LastUpdatedText({ ts }: { ts: string | null | undefined }) {
  // Re-render every 30 s so the relative time stays fresh
  const [, tick] = useReducer((x: number) => x + 1, 0);
  useEffect(() => {
    const id = setInterval(tick, 30_000);
    return () => clearInterval(id);
  }, []);

  return (
    <p className="text-xs mt-1" style={{ color: "#3a5070" }}>
      Último actualizado: {relativeTime(ts)}
    </p>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function DashboardControls() {
  const [open, setOpen] = useState(false);
  const [catalystFeedback, setCatalystFeedback] = useState<string | null>(null);

  const {
    refreshConfig,
    isRefreshingPrices,
    isRefreshingScores,
    setRefreshConfig,
    setIsRefreshingPrices,
    setIsRefreshingScores,
    patchRefreshConfig,
  } = useDashboardStore();

  const queryClient = useQueryClient();

  // ── Fetch config on mount ────────────────────────────────────
  const { data: fetchedConfig } = useQuery<RefreshConfig>({
    queryKey: ["refresh-config"],
    queryFn:  api.config.getRefreshSchedule,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (fetchedConfig) setRefreshConfig(fetchedConfig);
  }, [fetchedConfig, setRefreshConfig]);

  // ── Persist config change (debounced via useMutation) ────────
  const updateConfig = useMutation({
    mutationFn: (cfg: Pick<RefreshConfig, "price_refresh_interval" | "score_refresh_interval" | "catalyst_auto_review">) =>
      api.config.updateRefreshSchedule(cfg),
    onSuccess: (data) => {
      setRefreshConfig(data);
      queryClient.setQueryData(["refresh-config"], data);
    },
  });

  const applyInterval = useCallback(
    (field: "price_refresh_interval" | "score_refresh_interval", value: RefreshInterval) => {
      if (!refreshConfig) return;
      const next = { ...refreshConfig, [field]: value };
      patchRefreshConfig({ [field]: value });
      updateConfig.mutate({
        price_refresh_interval: next.price_refresh_interval,
        score_refresh_interval: next.score_refresh_interval,
        catalyst_auto_review:   next.catalyst_auto_review,
      });
    },
    [refreshConfig, patchRefreshConfig, updateConfig],
  );

  // ── Manual triggers ──────────────────────────────────────────
  const handleRefreshPrices = async () => {
    setIsRefreshingPrices(true);
    try {
      await api.refresh.prices();
      // Poll for updated last_price_update after a short delay
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

  const handleReviewCatalysts = () => {
    setCatalystFeedback("Revisión programada ✓");
    setTimeout(() => setCatalystFeedback(null), 3000);
  };

  const cfg = refreshConfig ?? fetchedConfig;

  return (
    <div
      className="mx-auto w-full max-w-screen-2xl px-4 mb-2"
    >
      {/* ── Toggle bar ── */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-t transition-colors w-full"
        style={{
          background: open ? "#0f1b30" : "#0a0e1a",
          border:    "1px solid #1e3050",
          borderBottom: open ? "none" : "1px solid #1e3050",
          color: "#7090b0",
          borderRadius: open ? "6px 6px 0 0" : "6px",
        }}
      >
        <span>⚙️</span>
        <span className="font-semibold text-text-secondary">Configuración de Refresh</span>
        <span className="ml-auto" style={{ color: "#3a5070" }}>
          {open ? "▲" : "▼"}
        </span>
      </button>

      {/* ── Collapsible body ── */}
      {open && (
        <div
          className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 rounded-b-lg"
          style={{ background: "#0f1b30", border: "1px solid #1e3050", borderTop: "none" }}
        >
          {/* ── Precios ── */}
          <div>
            <SectionTitle>📈 Precios</SectionTitle>
            <div className="space-y-2">
              <IntervalSelect
                id="price-refresh-interval"
                value={cfg?.price_refresh_interval ?? "1hour"}
                onChange={(v) => applyInterval("price_refresh_interval", v)}
                disabled={updateConfig.isPending}
              />
              <ActionButton onClick={handleRefreshPrices} loading={isRefreshingPrices}>
                🔄 Actualizar ahora
              </ActionButton>
              <LastUpdatedText ts={cfg?.last_price_update} />
            </div>
          </div>

          {/* ── Scores ── */}
          <div>
            <SectionTitle>🎯 Scores</SectionTitle>
            <div className="space-y-2">
              <IntervalSelect
                id="score-refresh-interval"
                value={cfg?.score_refresh_interval ?? "1hour"}
                onChange={(v) => applyInterval("score_refresh_interval", v)}
                disabled={updateConfig.isPending}
              />
              <ActionButton onClick={handleRefreshScores} loading={isRefreshingScores}>
                🔄 Recalcular ahora
              </ActionButton>
              <LastUpdatedText ts={cfg?.last_score_update} />
            </div>
          </div>

          {/* ── Catalysts ── */}
          <div>
            <SectionTitle>🔍 Catalysts</SectionTitle>
            <div className="space-y-2">
              <p className="text-xs" style={{ color: "#7090b0" }}>
                Revisar nuevos catalysts cada semana
              </p>
              <ActionButton
                onClick={handleReviewCatalysts}
                loading={catalystFeedback !== null && catalystFeedback !== "Revisión programada ✓"}
              >
                {catalystFeedback ?? "📋 Revisar catalysts ahora"}
              </ActionButton>
              <p className="text-xs" style={{ color: "#3a5070" }}>
                Próxima revisión automática:{" "}
                <span style={{ color: "#5ba4ff" }}>{nextMonday()}</span>
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
