"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Catalyst } from "@/lib/types";

const WINDOW_LABELS: Record<string, string> = {
  INMEDIATO: "Inmediato",
  PROXIMO:   "Próximo",
  FUTURO:    "Futuro",
  INCIERTO:  "Incierto",
};

const WINDOW_COLORS: Record<string, string> = {
  INMEDIATO: "#3de88a",
  PROXIMO:   "#f5c542",
  FUTURO:    "#ff8c42",
  INCIERTO:  "#7090b0",
};

function IntensityBar({ value }: { value: number }) {
  const color = value >= 80 ? "#3de88a" : value >= 60 ? "#f5c542" : "#ff8c42";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 rounded-full bg-border overflow-hidden">
        <div
          className="h-full rounded-full"
          style={{ width: `${value}%`, background: color }}
        />
      </div>
      <span className="text-xs font-mono" style={{ color }}>{value}</span>
    </div>
  );
}

export function CatalystMonitor() {
  const { data: catalysts, isLoading } = useQuery<Catalyst[]>({
    queryKey: ["catalysts"],
    queryFn: api.catalysts.list,
    refetchInterval: 10 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div
        className="p-4 rounded-lg"
        style={{ background: "#0f1b30", border: "1px solid #1e3050" }}
      >
        <div className="animate-pulse space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-16 rounded bg-border" />
          ))}
        </div>
      </div>
    );
  }

  const sorted = (catalysts ?? [])
    .slice()
    .sort((a, b) => (b.intensity_score ?? 0) - (a.intensity_score ?? 0));

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{ background: "#0f1b30", border: "1px solid #1e3050" }}
    >
      <div
        className="px-4 py-3 border-b flex items-center justify-between"
        style={{ borderColor: "#1e3050" }}
      >
        <h3 className="text-sm font-semibold text-text-primary">Monitor de Catalizadores</h3>
        <span className="text-xs text-text-muted">{sorted.length} activos</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 p-4">
        {sorted.map((cat) => {
          const wColor = WINDOW_COLORS[cat.expected_window] || "#7090b0";
          return (
            <div
              key={cat.id}
              className="p-3 rounded-lg"
              style={{ background: "#111e35", border: "1px solid #1e3050" }}
            >
              <div className="flex items-start justify-between gap-2 mb-2">
                <p className="text-sm font-semibold text-text-primary leading-snug line-clamp-2">
                  {cat.name}
                </p>
                <span
                  className="text-xs px-1.5 py-0.5 rounded shrink-0 font-mono"
                  style={{ color: wColor, background: `${wColor}18`, border: `1px solid ${wColor}33` }}
                >
                  {WINDOW_LABELS[cat.expected_window] || cat.expected_window}
                </span>
              </div>
              <span
                className="inline-block text-xs px-1.5 py-0.5 rounded mb-2 font-mono"
                style={{ background: "#1e3050", color: "#7090b0" }}
              >
                {cat.catalyst_type}
              </span>

              <IntensityBar value={cat.intensity_score ?? 0} />

              {cat.affected_sectors && cat.affected_sectors.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {cat.affected_sectors.slice(0, 4).map((s) => (
                    <span
                      key={s}
                      className="text-xs px-1.5 py-0.5 rounded"
                      style={{ background: "#5ba4ff15", color: "#5ba4ff", border: "1px solid #5ba4ff22" }}
                    >
                      {s}
                    </span>
                  ))}
                </div>
              )}

              {cat.affected_tickers && cat.affected_tickers.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {cat.affected_tickers.slice(0, 5).map((t) => (
                    <span key={t} className="text-xs font-mono text-blue-400">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
