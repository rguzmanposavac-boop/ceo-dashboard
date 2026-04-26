import type { Stock, Catalyst, RegimeStatus, PricePoint, InsidersResponse, ModelStats } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  stocks: {
    list: (params?: { signal?: string; horizon?: string; sector?: string; min_score?: number }) => {
      const qs = new URLSearchParams();
      if (params?.signal)    qs.set("signal", params.signal);
      if (params?.horizon)   qs.set("horizon", params.horizon);
      if (params?.sector)    qs.set("sector", params.sector);
      if (params?.min_score) qs.set("min_score", String(params.min_score));
      const query = qs.toString() ? `?${qs}` : "";
      return get<Stock[]>(`/api/v1/stocks${query}`);
    },
    get: (ticker: string) => get<Stock>(`/api/v1/stocks/${ticker}`),
    priceHistory: (ticker: string, limit = 90) =>
      get<PricePoint[]>(`/api/v1/stocks/${ticker}/price-history?limit=${limit}`),
    insiders: (ticker: string, days = 90) =>
      get<InsidersResponse>(`/api/v1/insiders/${ticker}?days=${days}`),
  },
  regime: {
    current: () => get<RegimeStatus>("/api/v1/regime/current"),
    history: (limit = 30) => get<RegimeStatus[]>(`/api/v1/regime/history?limit=${limit}`),
  },
  catalysts: {
    list: () => get<Catalyst[]>("/api/v1/catalysts"),
    get: (id: number) => get<Catalyst>(`/api/v1/catalysts/${id}`),
    scoreForTicker: (ticker: string) =>
      get<{ ticker: string; sector: string; catalysts: unknown[] }>(
        `/api/v1/catalysts/score/${ticker}?all=true`
      ),
  },
  scores: {
    compute: (ticker: string, regime?: string) => {
      const qs = regime ? `?regime=${regime}` : "";
      return post<Record<string, unknown>>(`/api/v1/scores/${ticker}/compute${qs}`);
    },
  },
  admin: {
    modelStats: () => get<ModelStats>("/api/v1/admin/model-stats"),
    runBacktest: () => post<ModelStats & { status: string }>("/api/v1/admin/run-backtest"),
  },
};
