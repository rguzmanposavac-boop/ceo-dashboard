import logging

import pandas as pd
import yfinance as yf

from app.data.fred_fetcher import fetch_yield_curve_spread

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sector mappings
# ---------------------------------------------------------------------------

SECTOR_REGIME: dict[str, list[str]] = {
    "CRISIS":  ["Healthcare", "Consumer Staples", "Utilities", "Seguros", "Holdings", "Defensa"],
    "BAJISTA": ["Healthcare", "Seguros", "Holdings", "Consumer Staples", "Software recurrente"],
    "NORMAL":  ["Tecnología", "Healthcare", "Financials", "Industrials", "Cloud"],
    "ALCISTA": ["Semiconductores", "Software", "Consumer Discretionary", "Financials", "Cloud", "IA"],
    "REBOTE":  ["Semiconductores", "EVs", "Software", "Small caps quality", "Commodities"],
}

AVOIDED_SECTORS: dict[str, list[str]] = {
    "CRISIS":  ["Semiconductores", "Software", "Consumer Discretionary", "EVs", "Social Media", "Biotech especulativo"],
    "BAJISTA": ["Semiconductores", "EVs", "Consumer Discretionary", "Social Media", "Small caps", "Biotech especulativo"],
    "NORMAL":  ["Utilities", "Consumer Staples", "Holdings"],
    "ALCISTA": ["Utilities", "Consumer Staples", "Holdings", "Defensa", "Seguros"],
    "REBOTE":  ["Healthcare", "Consumer Staples", "Utilities", "Seguros"],
}

# ---------------------------------------------------------------------------
# Core detection logic (pure function, matches CLAUDE.md spec exactly)
# ---------------------------------------------------------------------------

def detect_regime(vix: float, vix_ma20: float, spy_3m: float, spy_vs_ma50: float) -> str:
    if vix > 35:
        return "CRISIS"
    elif vix > 25 or (spy_3m < -0.10 and vix > 20):
        return "BAJISTA"
    elif vix < 18 and spy_3m > 0.10:
        return "ALCISTA"
    elif spy_3m > 0.05 and vix < 20 and vix < vix_ma20:
        return "REBOTE"
    else:
        return "NORMAL"


# ---------------------------------------------------------------------------
# Data fetchers
# ---------------------------------------------------------------------------

def _fetch_vix_data() -> tuple[float, float]:
    """Return (vix_current, vix_ma20) from Yahoo Finance."""
    ticker = yf.Ticker("^VIX")
    hist = ticker.history(period="3mo", interval="1d", auto_adjust=True)
    if hist.empty:
        raise ValueError("yfinance returned no VIX data")

    closes = hist["Close"].dropna()
    if len(closes) < 2:
        raise ValueError("Insufficient VIX history")

    vix_current = float(closes.iloc[-1])
    # Use up to last 20 bars for the moving average
    window = min(20, len(closes))
    vix_ma20 = float(closes.tail(window).mean())
    return vix_current, vix_ma20


def _fetch_spy_data() -> tuple[float, float]:
    """Return (spy_3m_return, spy_vs_ma50) from Yahoo Finance."""
    ticker = yf.Ticker("SPY")
    hist = ticker.history(period="6mo", interval="1d", auto_adjust=True)
    if hist.empty:
        raise ValueError("yfinance returned no SPY data")

    closes = hist["Close"].dropna()
    if len(closes) < 2:
        raise ValueError("Insufficient SPY history")

    current = float(closes.iloc[-1])

    # 3 months ≈ 63 trading days; use what we have if fewer bars available
    lookback_3m = min(63, len(closes) - 1)
    price_3m_ago = float(closes.iloc[-1 - lookback_3m])
    spy_3m_return = (current - price_3m_ago) / price_3m_ago

    # 50-day MA
    window_50 = min(50, len(closes))
    ma50 = float(closes.tail(window_50).mean())
    spy_vs_ma50 = (current - ma50) / ma50

    return spy_3m_return, spy_vs_ma50


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _compute_confidence(regime: str, vix: float, vix_ma20: float, spy_3m: float) -> float:
    """Return a 0-1 confidence value based on how clearly the indicators point to the detected regime."""
    if regime == "CRISIS":
        # VIX well above 35 → high confidence
        return round(min(0.98, 0.80 + (vix - 35) * 0.01), 2)

    if regime == "BAJISTA":
        if vix > 25:
            # How far above the 25 threshold?
            return round(min(0.92, 0.65 + (vix - 25) * 0.015), 2)
        # Triggered by spy_3m < -0.10 with VIX 20-25
        return 0.70

    if regime == "ALCISTA":
        # Both conditions must be clear
        vix_margin = max(0.0, 18 - vix) / 18
        spy_margin = max(0.0, spy_3m - 0.10)
        return round(min(0.90, 0.65 + vix_margin * 0.5 + spy_margin * 1.5), 2)

    if regime == "REBOTE":
        # Moderate confidence — borderline conditions
        return 0.65

    # NORMAL — default, catch-all
    return 0.60


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_regime_detection() -> dict:
    """Fetch live market data, detect regime, and return a dict ready for DB storage.

    Keys returned:
        regime, vix, vix_ma20, spy_3m_return, spy_vs_ma50,
        yield_curve_spread, confidence, favored_sectors, avoided_sectors
    """
    log.info("Fetching VIX data from Yahoo Finance…")
    vix, vix_ma20 = _fetch_vix_data()

    log.info("Fetching SPY data from Yahoo Finance…")
    spy_3m, spy_vs_ma50 = _fetch_spy_data()

    log.info("Fetching T10Y2Y yield curve from FRED…")
    try:
        yield_spread = fetch_yield_curve_spread()
    except Exception as exc:
        log.warning("FRED fetch failed (%s) — using 0.0 as fallback", exc)
        yield_spread = 0.0

    regime = detect_regime(vix, vix_ma20, spy_3m, spy_vs_ma50)
    confidence = _compute_confidence(regime, vix, vix_ma20, spy_3m)

    log.info(
        "Regime detected: %s | VIX=%.2f (MA20=%.2f) | SPY 3M=%.2f%% | T10Y2Y=%.2f | conf=%.2f",
        regime, vix, vix_ma20, spy_3m * 100, yield_spread, confidence,
    )

    return {
        "regime": regime,
        "vix": round(vix, 2),
        "vix_ma20": round(vix_ma20, 2),
        "spy_3m_return": round(spy_3m, 4),
        "spy_vs_ma50": round(spy_vs_ma50, 4),
        "yield_curve_spread": round(yield_spread, 4),
        "confidence": confidence,
        "favored_sectors": SECTOR_REGIME[regime],
        "avoided_sectors": AVOIDED_SECTORS[regime],
    }
