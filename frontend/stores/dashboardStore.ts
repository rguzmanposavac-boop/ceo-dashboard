import { create } from "zustand";
import type { Stock, Catalyst, RegimeStatus, Signal, Horizon } from "@/lib/types";

interface Filters {
  signal: Signal | "";
  horizon: Horizon | "";
  sector: string;
  min_score: number | null;
}

interface DashboardState {
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
}

const DEFAULT_FILTERS: Filters = {
  signal: "",
  horizon: "",
  sector: "",
  min_score: null,
};

export const useDashboardStore = create<DashboardState>((set) => ({
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
}));
