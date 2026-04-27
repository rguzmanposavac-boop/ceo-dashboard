export type Signal = "COMPRA_FUERTE" | "COMPRA" | "VIGILAR" | "EVITAR";
export type RefreshInterval = "manual" | "1min" | "5min" | "1hour" | "daily";

export interface RefreshConfig {
  price_refresh_interval: RefreshInterval;
  score_refresh_interval: RefreshInterval;
  catalyst_auto_review: boolean;
  updated_at: string | null;
  last_price_update: string | null;
  last_score_update: string | null;
}
export type Horizon = "CORTO_PLAZO" | "MEDIANO_PLAZO" | "LARGO_PLAZO";
export type Regime = "CRISIS" | "BAJISTA" | "NORMAL" | "ALCISTA" | "REBOTE";

export interface Invalidator {
  key: string;
  description: string;
}

export interface CEOProfile {
  name: string;
  profile: string;
  tenure_years: number;
  ownership_pct: number;
  succession_quality: "excellent" | "good" | "poor" | "unknown";
  is_founder: boolean;
  notes?: string | null;
}

export interface ScoreBreakdown {
  final_score: number | null;
  signal: Signal | null;
  horizon: Horizon | null;
  core_total: number | null;
  catalyst_total: number | null;
  sector_score?: number | null;
  base_score?: number | null;
  ceo_score?: number | null;
  roic_wacc_score?: number | null;
  catalyst_id?: number | null;
  regime: Regime | null;
  invalidators?: Invalidator[] | null;
  expected_return_low?: number | null;
  expected_return_high?: number | null;
  probability?: number | null;
  scored_at: string | null;
}

export interface Stock {
  ticker: string;
  company: string;
  sector: string;
  sub_sector: string | null;
  market_cap_category: string | null;
  exchange: string | null;
  universe_level: 1 | 2;
  current_price?: number | null;
  change_pct?: number | null;
  ceo: CEOProfile | null;
  score: ScoreBreakdown | null;
}

export interface Catalyst {
  id: number;
  name: string;
  catalyst_type: string;
  description: string;
  affected_sectors: string[];
  affected_tickers: string[];
  intensity_score: number;
  expected_window: "INMEDIATO" | "PROXIMO" | "FUTURO" | "INCIERTO";
  is_active?: boolean;
  detected_at: string;
}

export interface RegimeStatus {
  regime: Regime;
  vix: number | null;
  spy_3m_return: number | null;
  yield_curve_spread: number | null;
  confidence: number | null;
  favored_sectors: string[];
  avoided_sectors: string[];
  detected_at: string;
}

export interface PricePoint {
  price_date: string;
  close_price: number;
  volume: number | null;
  change_pct: number | null;
}

export interface InsiderTransaction {
  filing_date: string;
  transaction_date: string | null;
  insider_name: string;
  title: string | null;
  transaction_type: string;
  shares: number | null;
  price_per_share: number | null;
  total_value: number | null;
}

export interface InsidersResponse {
  ticker: string;
  days: number;
  count: number;
  transactions: InsiderTransaction[];
  source?: string;
}

export interface TickerBacktestStat {
  ticker: string;
  total_quarters: number;
  cf_signals: number;
  cf_hit_rate: number | null;
  avg_fwd_return: number;
}

export interface TierStat {
  count: number;
  avg_return: number;
  hit_rate_10pct: number;
  hit_rate_pos: number;
}

export interface QuarterlyPortfolio {
  quarter: string;
  portfolio_return: number;
  excess_return: number;
  n_stocks: number;
}

export interface ModelStats {
  r_squared: number | null;
  spearman_rho: number | null;
  spearman_p: number | null;
  avg_ic?: number | null;
  ic_ir?: number | null;
  hit_rate_cf: number | null;
  hit_rate_buy?: number | null;
  total_cf_signals?: number | null;
  total_observations?: number | null;
  avg_fwd_return_cf?: number | null;
  avg_fwd_return_all?: number | null;
  period_start?: string | null;
  period_end?: string | null;
  computed_at?: string | null;
  tier_stats?: Record<string, TierStat> | null;
  portfolio_by_q?: QuarterlyPortfolio[] | null;
  avg_excess_return?: number | null;
  win_rate_quarterly?: number | null;
  regime_distribution?: Record<string, number> | null;
  per_ticker?: TickerBacktestStat[] | null;
  methodology?: string | null;
  source: "backtest" | "static";
  note?: string;
}
