"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import { api } from "@/lib/api";

interface Props {
  ticker: string;
}

interface ScoreHistoryRow {
  id: number;
  scored_at: string;
  final_score: number;
  core_total: number;
  catalyst_total: number;
  signal: string;
  horizon: string;
  regime: string;
}

function formatDelta(value: number | null | undefined) {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}`;
}

function tooltipFormatter(value: number | string) {
  return typeof value === "number" ? `${value.toFixed(1)} pts` : value;
}

export function ScoreEvolution({ ticker }: Props) {
  const { data: history } = useQuery<ScoreHistoryRow[]>({
    queryKey: ["score-history", ticker],
    queryFn: () => api.scores.history(ticker, 30),
    staleTime: 60_000,
  });

  const sorted = useMemo(() => {
    if (!history) return [] as ScoreHistoryRow[];
    return [...history].sort(
      (a, b) => new Date(a.scored_at).getTime() - new Date(b.scored_at).getTime(),
    );
  }, [history]);

  const enriched = useMemo(() => {
    return sorted.map((row, index) => {
      const prev = sorted[index - 1];
      return {
        ...row,
        dateLabel: new Date(row.scored_at).toLocaleDateString("es-MX", { day: "2-digit", month: "short" }),
        coreDelta: prev ? row.core_total - prev.core_total : 0,
        catalystDelta: prev ? row.catalyst_total - prev.catalyst_total : 0,
      };
    });
  }, [sorted]);

  if (!history || history.length === 0) {
    return (
      <div className="rounded-lg border border-[#1e3050] bg-[#111e35] p-3 text-xs text-text-secondary">
        Historial de score no disponible.
      </div>
    );
  }

  const changes = enriched.slice(-5).reverse();

  return (
    <div className="rounded-lg border border-[#1e3050] bg-[#111e35] p-3 text-sm">
      <div className="flex items-center justify-between mb-3">
        <span className="font-semibold text-text-primary">Evolución del score</span>
        <span className="text-xs text-text-secondary">Últimos {history.length} registros</span>
      </div>

      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={enriched} margin={{ top: 10, right: 10, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="#1e3050" strokeDasharray="3 3" />
            <XAxis dataKey="dateLabel" tick={{ fill: "#7090b0", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fill: "#7090b0", fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{ backgroundColor: "#0f1b30", borderColor: "#1e3050", color: "#e0e6f0" }}
              itemStyle={{ color: "#e0e6f0" }}
              labelStyle={{ color: "#5ba4ff" }}
              formatter={tooltipFormatter}
              labelFormatter={(label) => `Fecha: ${label}`}
              cursor={{ stroke: "#5ba4ff", strokeWidth: 2 }}
            />
            <Line
              type="monotone"
              dataKey="final_score"
              stroke="#5ba4ff"
              strokeWidth={2}
              dot={{ fill: "#5ba4ff" }}
              activeDot={{ r: 6 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 text-xs text-text-secondary">
        <div className="grid grid-cols-[1fr_1fr_1fr_1fr] gap-2 rounded border border-[#1e3050] bg-[#111e35] p-3 text-text-secondary">
          <span className="font-semibold text-text-primary">Fecha</span>
          <span className="font-semibold text-text-primary">Score</span>
          <span className="font-semibold text-text-primary">Core Δ</span>
          <span className="font-semibold text-text-primary">Catalyst Δ</span>
        </div>
        <div className="space-y-2 mt-2">
          {changes.map((row) => (
            <div key={row.id} className="grid grid-cols-[1fr_1fr_1fr_1fr] gap-2 rounded border border-[#1e3050] bg-[#111e35] p-3 text-text-secondary">
              <span className="text-text-primary">{new Date(row.scored_at).toLocaleDateString("es-MX", { day: "2-digit", month: "short" })}</span>
              <span className="font-semibold text-text-primary">{row.final_score.toFixed(1)}</span>
              <span className={row.coreDelta >= 0 ? "text-[#3de88a]" : "text-[#ff5e5e]"}>{formatDelta(row.coreDelta)}</span>
              <span className={row.catalystDelta >= 0 ? "text-[#3de88a]" : "text-[#ff5e5e]"}>{formatDelta(row.catalystDelta)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
