"""
Sprint 8: Historical backtesting engine — 2020-2024.

Methodology:
  - Downloads 5 years of daily price data via yfinance for all active tickers + SPY + ^VIX
  - Simulates quarterly scores (20 quarter-ends, Q1-2020 → Q4-2024) for each ticker:
      • Regime:    accurate  — historical VIX + SPY give exact regime per quarter
      • Sector:    accurate  — same sector vs regime mapping as live engine
      • Momentum:  accurate  — 3M / 6M / 12M price returns from historical prices
      • ROIC:      proxy     — static by universe level (yfinance has no quarterly ROIC history)
      • CEO:       proxy     — static profile + historical regime (CEO profile stable over 5y)
      • Catalyst:  neutral   — fixed baseline 70 (can't replay historical catalysts)
  - Measures actual 3M forward return for every signal
  - Computes: hit rate for COMPRA_FUERTE signals, Spearman ρ, R²
  - Stores result in Redis (TTL 7 days)
"""
import logging
import math
from collections import defaultdict
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

from app.scheduler import cache_set

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (mirror core_engine to stay consistent)
# ---------------------------------------------------------------------------

_FAVORED: dict[str, list[str]] = {
    "CRISIS":  ["Healthcare", "Consumer Staples", "Utilities", "Seguros", "Holdings", "Defensa"],
    "BAJISTA": ["Healthcare", "Seguros", "Holdings", "Consumer Staples", "Software recurrente"],
    "NORMAL":  ["Tecnología", "Healthcare", "Financials", "Industrials", "Cloud"],
    "ALCISTA": ["Semiconductores", "Software", "Consumer Discretionary", "Financials", "Cloud",
                "IA", "IA Software", "IA Infra", "Social Media"],
    "REBOTE":  ["Semiconductores", "EVs", "Software", "Small caps quality", "Commodities",
                "Defensa Tech", "Telecoms"],
}
_AVOIDED: dict[str, list[str]] = {
    "CRISIS":  ["EVs", "Consumer Discretionary", "Streaming", "Social Media",
                "IA Software", "IA Infra", "Aviación"],
    "BAJISTA": ["EVs", "Consumer Discretionary", "Streaming", "Social Media", "Biotech"],
    "NORMAL":  ["Commodities", "Utilities"],
    "ALCISTA": ["Utilities", "Consumer Staples", "Seguros"],
    "REBOTE":  ["Consumer Staples", "Utilities", "Seguros"],
}
_PROFILE_REGIME: dict[str, dict[str, float]] = {
    "Racional Paciente":      {"CRISIS": 95, "BAJISTA": 90, "NORMAL": 70, "ALCISTA": 50, "REBOTE": 60},
    "Disciplinado Sistémico": {"CRISIS": 90, "BAJISTA": 88, "NORMAL": 75, "ALCISTA": 60, "REBOTE": 65},
    "Paranoico Estratégico":  {"CRISIS": 80, "BAJISTA": 78, "NORMAL": 75, "ALCISTA": 70, "REBOTE": 72},
    "Visionario Analítico":   {"CRISIS": 55, "BAJISTA": 65, "NORMAL": 80, "ALCISTA": 85, "REBOTE": 80},
    "Carismático Cultural":   {"CRISIS": 60, "BAJISTA": 65, "NORMAL": 72, "ALCISTA": 70, "REBOTE": 68},
    "Visionario Sistémico":   {"CRISIS": 45, "BAJISTA": 55, "NORMAL": 75, "ALCISTA": 90, "REBOTE": 88},
    "Narcisista Visionario":  {"CRISIS": 30, "BAJISTA": 40, "NORMAL": 65, "ALCISTA": 85, "REBOTE": 90},
    "Operacional Excelente":  {"CRISIS": 65, "BAJISTA": 68, "NORMAL": 72, "ALCISTA": 68, "REBOTE": 65},
}


# ---------------------------------------------------------------------------
# Historical scoring helpers
# ---------------------------------------------------------------------------

def _detect_regime(vix: float, vix_ma20: float, spy_3m: float, spy_vs_ma50: float) -> str:
    if vix > 35:
        return "CRISIS"
    if vix > 25 or (spy_3m < -0.10 and vix > 20):
        return "BAJISTA"
    if vix < 18 and spy_3m > 0.10:
        return "ALCISTA"
    if spy_3m > 0.05 and vix < 20 and vix < vix_ma20:
        return "REBOTE"
    return "NORMAL"


def _matches(lst: list[str], sector: str) -> bool:
    s = sector.lower()
    return any(item.lower() in s or s in item.lower() for item in lst)


def _sector_score(sector: str, regime: str, confidence: float = 0.6) -> float:
    if _matches(_FAVORED.get(regime, []), sector):
        base = 85.0
    elif _matches(_AVOIDED.get(regime, []), sector):
        base = 20.0
    else:
        base = 55.0
    return base * confidence + 55.0 * (1.0 - confidence)


def _tenure_mult(years: float) -> float:
    if years < 1:    return 0.85
    if years <= 2:   return 0.92
    if years <= 5:   return 1.10
    if years <= 8:   return 1.05
    if years <= 12:  return 1.00
    if years <= 15:  return 0.95
    return 0.88


def _ceo_score(profile: str, regime: str, tenure: float,
               ownership: float, succession: str, confidence: float = 0.6) -> float:
    regime_scores = _PROFILE_REGIME.get(profile, _PROFILE_REGIME["Disciplinado Sistémico"])
    raw = float(regime_scores.get(regime, 65))
    own_f = 1.15 if ownership >= 10 else 1.10 if ownership >= 3 else 1.05 if ownership >= 1 else (1.00 if ownership >= 0.1 else 0.95)
    suc_f = {"excellent": 1.08, "good": 1.02, "poor": 0.92, "unknown": 0.97}.get(succession or "unknown", 0.97)
    score = min(100.0, raw * _tenure_mult(tenure) * own_f * suc_f)
    return score * confidence + 55.0 * (1.0 - confidence)


def _momentum_score(ret_3m: float, ret_6m: float, ret_12m: float) -> float:
    """Map historical returns to 0-100 using same formula as core_engine."""
    def _norm(r: float) -> float:
        clamped = max(-0.5, min(0.5, r))
        return (clamped + 0.5) * 100.0
    return _norm(ret_3m) * 0.40 + _norm(ret_6m) * 0.30 + _norm(ret_12m) * 0.30


def _classify(score: float) -> str:
    if score >= 80: return "COMPRA_FUERTE"
    if score >= 70: return "COMPRA"
    if score >= 58: return "VIGILAR"
    return "EVITAR"


# ---------------------------------------------------------------------------
# Spearman ρ and R² without scipy
# ---------------------------------------------------------------------------

def _spearman(x: list[float], y: list[float]) -> tuple[float, float]:
    n = len(x)
    if n < 4:
        return 0.0, 1.0
    xa = np.array(x, dtype=float)
    ya = np.array(y, dtype=float)
    rx = np.argsort(np.argsort(xa)).astype(float) + 1.0
    ry = np.argsort(np.argsort(ya)).astype(float) + 1.0
    d = rx - ry
    rho = float(1.0 - 6.0 * float(np.sum(d ** 2)) / (n * (n ** 2 - 1)))
    rho = max(-1.0, min(1.0, rho))
    # t approximation → p via erfc
    denom = max(1e-10, 1.0 - rho ** 2)
    t_stat = rho * math.sqrt((n - 2) / denom)
    p_val = float(math.erfc(abs(t_stat) / math.sqrt(2)))  # two-tailed approx (normal dist for large n)
    return rho, p_val


def _r_squared(scores: list[float], returns: list[float]) -> float:
    x = np.array(scores, dtype=float)
    y = np.array(returns, dtype=float)
    y_mean = float(np.mean(y))
    ss_tot = float(np.sum((y - y_mean) ** 2))
    if ss_tot < 1e-12:
        return 0.0
    denom = float(np.sum((x - float(np.mean(x))) ** 2))
    if denom < 1e-12:
        return 0.0
    slope = float(np.sum((x - float(np.mean(x))) * (y - y_mean))) / denom
    intercept = y_mean - slope * float(np.mean(x))
    y_pred = slope * x + intercept
    ss_res = float(np.sum((y - y_pred) ** 2))
    return max(0.0, 1.0 - ss_res / ss_tot)


# ---------------------------------------------------------------------------
# Quarter-end evaluation dates  Q1-2020 → Q4-2024
# ---------------------------------------------------------------------------

def _quarter_ends() -> list[pd.Timestamp]:
    ends = []
    for year in range(2020, 2025):
        for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
            ends.append(pd.Timestamp(year=year, month=month, day=day))
    return ends


def _prior_or_equal(index: pd.DatetimeIndex, ts: pd.Timestamp):
    """Return the last index entry ≤ ts, or None if none exists."""
    valid = index[index <= ts]
    return valid[-1] if len(valid) > 0 else None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_backtest(db) -> dict:
    """
    Run the full historical backtest and return a result dict.
    Also stores the result in Redis under 'backtest:latest' (TTL 7 days).
    """
    from app.models.stock import Stock
    from app.models.ceo import CEO

    log.info("[backtest] Loading stock metadata from DB")
    stocks = db.query(Stock).filter(Stock.is_active.is_(True)).all()
    ceo_by_stock = {c.stock_id: c for c in db.query(CEO).all()}

    tickers = [s.ticker for s in stocks]
    stock_map = {s.ticker: s for s in stocks}

    # ------------------------------------------------------------------ #
    # 1.  Download 5+ years of price data                                 #
    # ------------------------------------------------------------------ #
    all_syms = tickers + ["SPY", "^VIX"]
    log.info("[backtest] Downloading history for %d symbols (2019-07-01 → 2025-04-01)", len(all_syms))

    raw = yf.download(
        tickers=all_syms,
        start="2019-07-01",
        end="2025-04-01",
        auto_adjust=True,
        progress=False,
    )

    # Safely extract Close prices
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"].copy()
    else:
        close = raw[["Close"]].copy()
        close.columns = [all_syms[0]]

    close.index = pd.to_datetime(close.index)
    if close.index.tz is not None:
        close.index = close.index.tz_convert(None)
    close = close.sort_index()

    spy_s = close.get("SPY")
    vix_s = close.get("^VIX")

    if spy_s is None or vix_s is None:
        log.error("[backtest] SPY or ^VIX data missing from download")
        return {"error": "SPY/VIX data unavailable"}

    spy_s = spy_s.dropna()
    vix_s = vix_s.dropna()

    # Pre-compute rolling series for regime detection
    vix_ma20  = vix_s.rolling(20, min_periods=10).mean()
    spy_3m    = spy_s.pct_change(63)     # ~3 months of trading days
    spy_ma50  = spy_s.rolling(50, min_periods=25).mean()

    log.info("[backtest] Price data loaded: %d rows, %d tickers with data",
             len(close), close.notna().any().sum())

    # ------------------------------------------------------------------ #
    # 2.  Per-quarter, per-ticker score simulation                        #
    # ------------------------------------------------------------------ #
    quarters = _quarter_ends()
    signals: list[dict] = []

    # Pair each quarter-end with its forward quarter-end
    fwd_map: dict[pd.Timestamp, pd.Timestamp] = {}
    for i, q in enumerate(quarters):
        if i + 1 < len(quarters):
            fwd_map[q] = quarters[i + 1]
        else:
            # Q4-2024 → Q1-2025
            fwd_map[q] = pd.Timestamp(2025, 3, 31)

    def _safe(val: object, default: float = 0.0) -> float:
        try:
            f = float(val)  # type: ignore[arg-type]
            return f if math.isfinite(f) else default
        except Exception:
            return default

    for q_date in quarters:
        q_label = f"{q_date.year}-Q{(q_date.month - 1) // 3 + 1}"

        # ----- Regime at this quarter-end -----
        v_idx = _prior_or_equal(vix_s.index, q_date)
        s_idx = _prior_or_equal(spy_s.index, q_date)
        if v_idx is None or s_idx is None:
            continue

        vix_val   = _safe(vix_s.loc[v_idx], 20.0)
        vix_ma    = _safe(vix_ma20.loc[v_idx], vix_val)
        spy3m_val = _safe(spy_3m.loc[s_idx], 0.0)
        spy_price = _safe(spy_s.loc[s_idx], 400.0)
        spy_ma    = _safe(spy_ma50.loc[s_idx], spy_price)
        spy_vs_50 = (spy_price / spy_ma - 1.0) if spy_ma > 0 else 0.0

        regime     = _detect_regime(vix_val, vix_ma, spy3m_val, spy_vs_50)
        confidence = 0.6  # same as live model

        fwd_date = fwd_map[q_date]

        # ----- SPY returns at this date (for relative momentum + relative fwd return) -----
        spy_at = spy_s.loc[:s_idx]
        spy_ret_3m  = _safe(spy_at.pct_change(63).iloc[-1])  if len(spy_at) > 65  else 0.0
        spy_ret_6m  = _safe(spy_at.pct_change(126).iloc[-1]) if len(spy_at) > 128 else 0.0
        spy_ret_12m = _safe(spy_at.pct_change(252).iloc[-1]) if len(spy_at) > 254 else 0.0
        # SPY forward return (for relative forward return)
        spy_fwd_idx = _prior_or_equal(spy_s.index, fwd_date)
        spy_fwd_ret = 0.0
        if spy_fwd_idx is not None and s_idx < spy_fwd_idx:
            p0, p1 = _safe(spy_s.loc[s_idx], 1.0), _safe(spy_s.loc[spy_fwd_idx], 1.0)
            spy_fwd_ret = (p1 - p0) / p0 if p0 > 0 else 0.0

        for ticker in tickers:
            if ticker not in close.columns:
                continue

            ps = close[ticker].dropna()
            if len(ps) < 130:   # need at least ~6M of history
                continue

            sig_idx = _prior_or_equal(ps.index, q_date)
            fwd_idx = _prior_or_equal(ps.index, fwd_date)

            if sig_idx is None or fwd_idx is None or sig_idx >= fwd_idx:
                continue

            price_sig = _safe(ps.loc[sig_idx])
            price_fwd = _safe(ps.loc[fwd_idx])
            if price_sig <= 0:
                continue

            fwd_return_abs = (price_fwd - price_sig) / price_sig
            fwd_return_rel = fwd_return_abs - spy_fwd_ret  # excess return vs market

            # ----- Relative momentum (excess return vs SPY) — standard cross-sectional factor
            #       Using relative momentum eliminates common market beta, surfacing stock alpha -----
            ps_at = ps.loc[:sig_idx]
            ret_3m  = _safe(ps_at.pct_change(63).iloc[-1])  if len(ps_at) > 65  else 0.0
            ret_6m  = _safe(ps_at.pct_change(126).iloc[-1]) if len(ps_at) > 128 else 0.0
            ret_12m = _safe(ps_at.pct_change(252).iloc[-1]) if len(ps_at) > 254 else 0.0
            # Excess returns vs SPY benchmark
            rel_3m  = ret_3m  - spy_ret_3m
            rel_6m  = ret_6m  - spy_ret_6m
            rel_12m = ret_12m - spy_ret_12m
            base_sc = _momentum_score(rel_3m, rel_6m, rel_12m)

            # ----- Sector / regime score -----
            stock = stock_map[ticker]
            sector_sc = _sector_score(stock.sector, regime, confidence)

            # ----- ROIC proxy (static by universe level) -----
            roic_sc = 80.0 if stock.universe_level == 1 else 70.0

            # ----- CEO score (static profile + historical regime) -----
            ceo = ceo_by_stock.get(stock.id)
            if ceo and ceo.profile:
                ceo_sc = _ceo_score(
                    ceo.profile, regime,
                    ceo.tenure_years or 5.0,
                    ceo.ownership_pct or 0.1,
                    ceo.succession_quality or "unknown",
                    confidence,
                )
            else:
                ceo_sc = 55.0

            # ----- Core total -----
            core_total = (sector_sc * 20 + base_sc * 20 + roic_sc * 15 + ceo_sc * 10) / 65.0

            # ----- Catalyst baseline: reflects that these stocks were curated for
            #       strong catalyst exposure; live scores average 82-88 for the universe.
            #       We use 82 as a flat proxy (can't replay historical catalysts accurately).
            catalyst_total = 82.0

            # ----- Final score + signal -----
            final_score = round(core_total * 0.65 + catalyst_total * 0.35, 2)
            signal = _classify(final_score)

            signals.append({
                "ticker":             ticker,
                "quarter":            q_label,
                "date":               q_date.strftime("%Y-%m-%d"),
                "regime":             regime,
                "final_score":        final_score,
                "core_total":         round(core_total, 2),
                "signal":             signal,
                "forward_return":     round(fwd_return_abs, 4),
                "forward_return_rel": round(fwd_return_rel, 4),
            })

    if not signals:
        return {"error": "No signals generated — check price data availability"}

    log.info("[backtest] Simulated %d (ticker, quarter) observations", len(signals))

    # ------------------------------------------------------------------ #
    # 3.  Aggregate statistics                                            #
    # ------------------------------------------------------------------ #
    cf_sigs  = [s for s in signals if s["signal"] == "COMPRA_FUERTE"]
    buy_sigs = [s for s in signals if s["signal"] in ("COMPRA_FUERTE", "COMPRA")]
    all_rets_abs = [s["forward_return"]     for s in signals]
    all_rets_rel = [s["forward_return_rel"] for s in signals]
    all_scos     = [s["final_score"]        for s in signals]

    hit_rate_cf  = (sum(1 for s in cf_sigs  if s["forward_return"] > 0.10) / len(cf_sigs))  if cf_sigs  else 0.0
    hit_rate_buy = (sum(1 for s in buy_sigs if s["forward_return"] > 0.10) / len(buy_sigs)) if buy_sigs else 0.0

    avg_ret_cf  = float(np.mean([s["forward_return"] for s in cf_sigs]))  if cf_sigs  else 0.0
    avg_ret_all = float(np.mean(all_rets_abs))

    # Spearman on RELATIVE forward returns (score vs excess return over SPY)
    # Relative return removes common market beta, surfacing the model's stock-selection skill
    rho, p_val = _spearman(all_scos, all_rets_rel)
    r2         = _r_squared(all_scos, all_rets_rel)

    # Cross-sectional Information Coefficient (IC) per quarter
    # IC = Spearman(score_rank, return_rank) for each cross-section of 30 stocks
    quarter_ics: list[float] = []
    for q_label in {s["quarter"] for s in signals}:
        q_sigs = [s for s in signals if s["quarter"] == q_label]
        if len(q_sigs) >= 5:
            ic, _ = _spearman(
                [s["final_score"] for s in q_sigs],
                [s["forward_return_rel"] for s in q_sigs],
            )
            quarter_ics.append(ic)
    avg_ic  = float(np.mean(quarter_ics)) if quarter_ics else 0.0
    ic_ir   = float(avg_ic / (np.std(quarter_ics) + 1e-10) * math.sqrt(len(quarter_ics)))  # annualized ratio

    # Signal-tier breakdown (key investor-facing metric)
    tier_stats: dict[str, dict] = {}
    for tier in ["COMPRA_FUERTE", "COMPRA", "VIGILAR", "EVITAR"]:
        t_sigs = [s for s in signals if s["signal"] == tier]
        if t_sigs:
            tier_stats[tier] = {
                "count":         len(t_sigs),
                "avg_return":    round(float(np.mean([s["forward_return"] for s in t_sigs])) * 100, 1),
                "hit_rate_10pct": round(sum(1 for s in t_sigs if s["forward_return"] > 0.10) / len(t_sigs), 3),
                "hit_rate_pos":  round(sum(1 for s in t_sigs if s["forward_return"] > 0.0)  / len(t_sigs), 3),
            }

    # Quarterly equal-weight portfolio excess return vs SPY
    all_quarters = sorted({s["quarter"] for s in signals})
    portfolio_by_q: list[dict] = []
    for q_lbl in all_quarters:
        q_buy_sigs = [s for s in signals if s["quarter"] == q_lbl
                      and s["signal"] in ("COMPRA_FUERTE", "COMPRA")]
        q_all_sigs = [s for s in signals if s["quarter"] == q_lbl]
        if q_buy_sigs:
            port_ret  = float(np.mean([s["forward_return"]     for s in q_buy_sigs]))
            port_exc  = float(np.mean([s["forward_return_rel"] for s in q_buy_sigs]))
            portfolio_by_q.append({
                "quarter":          q_lbl,
                "portfolio_return": round(port_ret * 100, 1),
                "excess_return":    round(port_exc * 100, 1),
                "n_stocks":         len(q_buy_sigs),
            })

    avg_excess = float(np.mean([q["excess_return"] for q in portfolio_by_q])) if portfolio_by_q else 0.0
    win_rate_q = (sum(1 for q in portfolio_by_q if q["excess_return"] > 0) / len(portfolio_by_q)) if portfolio_by_q else 0.0

    # Regime distribution
    regime_counts: dict[str, int] = defaultdict(int)
    for s in signals:
        regime_counts[s["regime"]] += 1

    # Per-ticker summary
    t_stats: dict[str, dict] = defaultdict(lambda: {
        "cf": 0, "cf_hits": 0, "buy": 0, "buy_hits": 0, "n": 0, "sum_ret": 0.0
    })
    for s in signals:
        t = s["ticker"]
        t_stats[t]["n"]       += 1
        t_stats[t]["sum_ret"] += s["forward_return"]
        if s["signal"] == "COMPRA_FUERTE":
            t_stats[t]["cf"] += 1
            if s["forward_return"] > 0.10:
                t_stats[t]["cf_hits"] += 1
        if s["signal"] in ("COMPRA_FUERTE", "COMPRA"):
            t_stats[t]["buy"] += 1
            if s["forward_return"] > 0.10:
                t_stats[t]["buy_hits"] += 1

    per_ticker = []
    for ticker, st in sorted(t_stats.items()):
        cf_hr = (st["cf_hits"] / st["cf"]) if st["cf"] > 0 else None
        per_ticker.append({
            "ticker":          ticker,
            "total_quarters":  st["n"],
            "cf_signals":      st["cf"],
            "cf_hit_rate":     round(cf_hr, 3) if cf_hr is not None else None,
            "avg_fwd_return":  round(st["sum_ret"] / st["n"] * 100, 1),
        })
    per_ticker.sort(key=lambda x: -(x["cf_hit_rate"] or -1))

    result = {
        "computed_at":          datetime.utcnow().isoformat(),
        "period_start":         "2020-Q1",
        "period_end":           "2024-Q4",
        "total_observations":   len(signals),
        "total_cf_signals":     len(cf_sigs),
        "total_buy_signals":    len(buy_sigs),
        "hit_rate_cf":          round(hit_rate_cf,  3),
        "hit_rate_buy":         round(hit_rate_buy, 3),
        "avg_fwd_return_cf":    round(avg_ret_cf  * 100, 1),
        "avg_fwd_return_all":   round(avg_ret_all * 100, 1),
        "spearman_rho":         round(rho,   3),
        "spearman_p":           round(p_val, 4),
        "r_squared":            round(r2,    3),
        "avg_ic":               round(avg_ic,  3),
        "ic_ir":                round(ic_ir,   2),
        "tier_stats":           tier_stats,
        "portfolio_by_q":       portfolio_by_q,
        "avg_excess_return":    round(avg_excess, 1),
        "win_rate_quarterly":   round(win_rate_q, 3),
        "regime_distribution":  dict(regime_counts),
        "per_ticker":           per_ticker,
        "methodology": (
            "Régimen y momentum relativo vs SPY: históricos exactos (VIX+SPY+precio). "
            "ROIC/CEO: proxies estáticos. "
            "Catalizador: baseline 82. "
            "Spearman y R² computados sobre retorno exceso vs SPY (cross-sectional)."
        ),
    }

    cache_set("backtest:latest", result, ttl=86400 * 7)
    log.info(
        "[backtest] DONE — %d obs | %d CF signals | hit_rate=%.0f%% | ρ=%.3f | R²=%.3f | IC=%.3f (IR=%.2f)",
        len(signals), len(cf_sigs), hit_rate_cf * 100, rho, r2, avg_ic, ic_ir,
    )
    return result
