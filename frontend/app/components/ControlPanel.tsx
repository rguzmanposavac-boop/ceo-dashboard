"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { RefreshConfig, RefreshInterval, CandidateEvaluation, InvalidatorAlert } from "@/lib/types";

const STORAGE_KEY = "ceo-dashboard-refresh-prefs";
const INTERVAL_OPTIONS: { value: RefreshInterval; label: string }[] = [
  { value: "manual", label: "Manual" },
  { value: "1min", label: "Cada 1 minuto" },
  { value: "5min", label: "Cada 5 minutos" },
  { value: "1hour", label: "Cada 1 hora" },
  { value: "daily", label: "Una vez al día" },
];

function niceInterval(value: RefreshInterval) {
  return INTERVAL_OPTIONS.find((option) => option.value === value)?.label ?? value;
}

function relativeTime(ts: string | null | undefined) {
  if (!ts) return "nunca";
  const diffMs = Math.max(0, Date.now() - new Date(ts).getTime());
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "hace un momento";
  if (diffMin < 60) return `hace ${diffMin} min`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `hace ${diffH}h`;
  return `hace ${Math.floor(diffH / 24)} días`;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: "#7090b0" }}>
        {title}
      </p>
      {children}
    </div>
  );
}

function ActionButton({ children, onClick, disabled }: { children: React.ReactNode; onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="w-full rounded py-2 text-xs font-semibold transition"
      style={{
        background: disabled ? "#1e3050" : "#5ba4ff18",
        border: "1px solid #5ba4ff44",
        color: disabled ? "#7090b0" : "#5ba4ff",
      }}
    >
      {children}
    </button>
  );
}

export function ControlPanel() {
  const queryClient = useQueryClient();
  const [lastCandidates, setLastCandidates] = useState<CandidateEvaluation[] | null>(null);
  const [lastInvalidators, setLastInvalidators] = useState<InvalidatorAlert[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const { data: refreshConfig } = useQuery<RefreshConfig>({
    queryKey: ["refresh-config"],
    queryFn: api.config.getRefreshSchedule,
    staleTime: 30_000,
  });

  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const parsed = JSON.parse(saved) as Partial<RefreshConfig>;
        if (parsed.price_refresh_interval || parsed.score_refresh_interval) {
          queryClient.setQueryData(["refresh-config"], (current: RefreshConfig | undefined) => ({
            ...(current ?? {}),
            ...parsed,
          }));
        }
      } catch {
        // ignore invalid local state
      }
    }
  }, [queryClient]);

  useEffect(() => {
    if (!refreshConfig) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
      price_refresh_interval: refreshConfig.price_refresh_interval,
      score_refresh_interval: refreshConfig.score_refresh_interval,
    }));
  }, [refreshConfig]);

  const updateConfigMutation = useMutation({
    mutationFn: (payload: Partial<RefreshConfig>) => api.config.updateRefreshSchedule({
      price_refresh_interval: payload.price_refresh_interval ?? refreshConfig?.price_refresh_interval ?? "daily",
      score_refresh_interval: payload.score_refresh_interval ?? refreshConfig?.score_refresh_interval ?? "daily",
      catalyst_auto_review: payload.catalyst_auto_review ?? refreshConfig?.catalyst_auto_review ?? true,
    }),
    onSuccess: (data) => {
      queryClient.setQueryData(["refresh-config"], data);
      setMessage("Preferencias guardadas");
      setTimeout(() => setMessage(null), 2500);
    },
  });

  const handlePriceRefreshNow = async () => {
    setMessage("Actualizando precios…");
    try {
      await api.refresh.prices();
      setMessage("Actualización de precios en curso");
      setTimeout(() => queryClient.invalidateQueries(["refresh-config"]), 4000);
    } catch (error) {
      setMessage("Error actualizando precios");
    }
  };

  const handleScoreRefreshNow = async () => {
    setMessage("Recalculando scores…");
    try {
      await api.refresh.scores();
      setMessage("Recalculando scores en curso");
      queryClient.invalidateQueries(["stocks"]);
      setTimeout(() => queryClient.invalidateQueries(["refresh-config"]), 8000);
    } catch (error) {
      setMessage("Error recalculando scores");
    }
  };

  const handleRefreshVixNow = async () => {
    setMessage("Actualizando régimen/VIX…");
    try {
      await api.regime.refreshVix();
      setMessage("Refresco de régimen iniciado");
      queryClient.invalidateQueries(["regime"]);
    } catch (error) {
      setMessage("Error al actualizar VIX");
    }
  };

  const handleEvaluateCandidates = async () => {
    setMessage("Evaluando candidatos…");
    try {
      const data = await api.evaluate.candidates();
      setLastCandidates(data.candidates);
      setMessage(`Candidatos evaluados: ${data.candidates.length}`);
    } catch {
      setMessage("Error evaluando candidatos");
    }
  };

  const handleCheckInvalidators = async () => {
    setMessage("Chequeando invalidadores…");
    try {
      const data = await api.invalidators.check();
      setLastInvalidators(data.invalidators);
      setMessage(`Invalidadores encontrados: ${data.invalidators.length}`);
    } catch {
      setMessage("Error revisando invalidadores");
    }
  };

  const config = refreshConfig;

  return (
    <section className="mx-auto w-full max-w-screen-2xl px-4 py-4">
      <div className="rounded-lg border border-[#1e3050] bg-[#0f1b30] p-4 grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Intervalos de actualización">
              <div className="grid gap-3">
                <label className="text-xs text-text-secondary">Precios</label>
                <select
                  className="text-sm rounded px-2 py-2 bg-[#111e35] border border-[#1e3050] text-text-primary"
                  value={config?.price_refresh_interval ?? "daily"}
                  onChange={(e) => updateConfigMutation.mutate({ price_refresh_interval: e.target.value as RefreshInterval })}
                >
                  {INTERVAL_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
                <label className="text-xs text-text-secondary">Scores</label>
                <select
                  className="text-sm rounded px-2 py-2 bg-[#111e35] border border-[#1e3050] text-text-primary"
                  value={config?.score_refresh_interval ?? "daily"}
                  onChange={(e) => updateConfigMutation.mutate({ score_refresh_interval: e.target.value as RefreshInterval })}
                >
                  {INTERVAL_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </div>
            </Section>

            <Section title="Acciones manuales">
              <div className="grid gap-2">
                <ActionButton onClick={handleRefreshVixNow} disabled={updateConfigMutation.isLoading}>
                  Actualizar régimen/VIX ahora
                </ActionButton>
                <ActionButton onClick={handlePriceRefreshNow} disabled={updateConfigMutation.isLoading}>
                  Actualizar precios ahora
                </ActionButton>
                <ActionButton onClick={handleScoreRefreshNow} disabled={updateConfigMutation.isLoading}>
                  Recalcular scores ahora
                </ActionButton>
              </div>
            </Section>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <Section title="Evaluaciones">
              <div className="grid gap-2">
                <ActionButton onClick={handleEvaluateCandidates} disabled={updateConfigMutation.isLoading}>
                  Evaluar candidatos retail
                </ActionButton>
                <ActionButton onClick={handleCheckInvalidators} disabled={updateConfigMutation.isLoading}>
                  Chequear invalidadores
                </ActionButton>
              </div>
            </Section>

            <Section title="Resumen de estado">
              <div className="text-xs leading-relaxed text-text-secondary">
                <p>Precios: {niceInterval(config?.price_refresh_interval ?? "daily")}</p>
                <p>Scores: {niceInterval(config?.score_refresh_interval ?? "daily")}</p>
                <p>Último precio: {relativeTime(config?.last_price_update)}</p>
                <p>Último score: {relativeTime(config?.last_score_update)}</p>
              </div>
            </Section>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-lg bg-[#111e35] border border-[#1e3050] p-4">
            <p className="text-xs uppercase tracking-widest text-text-secondary mb-2">Última evaluación</p>
            {lastCandidates ? (
              <div className="space-y-2 text-xs text-text-primary">
                {lastCandidates.slice(0, 5).map((candidate) => (
                  <div key={candidate.ticker} className="flex justify-between gap-2">
                    <span>{candidate.ticker}</span>
                    <span>{candidate.score.toFixed(1)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-text-secondary">Ninguna evaluación reciente</p>
            )}
          </div>

          <div className="rounded-lg bg-[#111e35] border border-[#1e3050] p-4">
            <p className="text-xs uppercase tracking-widest text-text-secondary mb-2">Últimos invalidadores</p>
            {lastInvalidators ? (
              <div className="space-y-2 text-xs text-text-primary">
                {lastInvalidators.slice(0, 4).map((item, index) => (
                  <div key={`${item.ticker}-${item.key}-${index}`}>
                    <p className="font-semibold">{item.ticker}</p>
                    <p>{item.description}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-text-secondary">No hay invalidadores recientes</p>
            )}
          </div>

          {message && (
            <div className="rounded-md border border-[#5ba4ff44] bg-[#5ba4ff10] p-3 text-sm text-blue-100">
              {message}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
