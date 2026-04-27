import { create } from "zustand";
import type { Stock, Catalyst, RegimeStatus, Signal, Horizon, RefreshConfig, RefreshInterval } from "@/lib/types";

interface Filters {
  signal: Signal | "";
  horizon: Horizon | "";
  sector: string;
  min_score: number | null;
}

interface DashboardState {
  // ── Core dashboard ──────────────────────────────────────────
  stocks: Stock[];
  catalysts: Catalyst[];
  regime: RegimeStatus | null;
  selectedTicker: string | null;
  filters: Filters;

  setStocks: (stocks: Stock[]) => void;
  setCatalysts: (catalysts: Catalyst[]) => void;
  setRegime: (regime: RegimeStatus) => void;
  selectTicker: (ticker: string | null) => void;
  setFilter: <K extends keyof Filters>(key: K, value: Filters[K]) => void;
  resetFilters: () => void;

  // ── Refresh config ───────────────────────────────────────────
  refreshConfig: RefreshConfig | null;
  isRefreshingPrices: boolean;
  isRefreshingScores: boolean;

  setRefreshConfig: (cfg: RefreshConfig) => void;
  patchRefreshConfig: (patch: Partial<RefreshConfig>) => void;
  setPriceInterval: (v: RefreshInterval) => void;
  setScoreInterval: (v: RefreshInterval) => void;
  setCatalystAutoReview: (v: boolean) => void;
  setIsRefreshingPrices: (v: boolean) => void;
  setIsRefreshingScores: (v: boolean) => void;
}

const DEFAULT_FILTERS: Filters = {
  signal: "",
  horizon: "",
  sector: "",
  min_score: null,
};

export const useDashboardStore = create<DashboardState>((set, get) => ({
  // ── Core dashboard ──────────────────────────────────────────
  stocks: [],
  catalysts: [],
  regime: null,
  selectedTicker: null,
  filters: DEFAULT_FILTERS,

  setStocks: (stocks) => set({ stocks }),
  setCatalysts: (catalysts) => set({ catalysts }),
  setRegime: (regime) => set({ regime }),
  selectTicker: (ticker) => set({ selectedTicker: ticker }),
  setFilter: (key, value) =>
    set((state) => ({ filters: { ...state.filters, [key]: value } })),
  resetFilters: () => set({ filters: DEFAULT_FILTERS }),

  // ── Refresh config ───────────────────────────────────────────
  refreshConfig: null,
  isRefreshingPrices: false,
  isRefreshingScores: false,

  setRefreshConfig: (cfg) => set({ refreshConfig: cfg }),
  patchRefreshConfig: (patch) =>
    set((state) => ({
      refreshConfig: state.refreshConfig ? { ...state.refreshConfig, ...patch } : null,
    })),
  setPriceInterval: (v) => {
    const cfg = get().refreshConfig;
    if (cfg) set({ refreshConfig: { ...cfg, price_refresh_interval: v } });
  },
  setScoreInterval: (v) => {
    const cfg = get().refreshConfig;
    if (cfg) set({ refreshConfig: { ...cfg, score_refresh_interval: v } });
  },
  setCatalystAutoReview: (v) => {
    const cfg = get().refreshConfig;
    if (cfg) set({ refreshConfig: { ...cfg, catalyst_auto_review: v } });
  },
  setIsRefreshingPrices: (v) => set({ isRefreshingPrices: v }),
  setIsRefreshingScores: (v) => set({ isRefreshingScores: v }),
}));
