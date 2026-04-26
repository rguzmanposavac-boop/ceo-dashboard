import logging
import os
from io import StringIO

import httpx
import pandas as pd

log = logging.getLogger(__name__)

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_JSON_URL = "https://api.stlouisfed.org/fred/series/observations"


FALLBACK_SPREAD = 0.50  # historical approximate 10Y-2Y average

def fetch_yield_curve_spread() -> float:
    """Return the most recent 10Y-2Y Treasury yield spread (T10Y2Y) in percentage points.

    Tries the JSON API first (if FRED_API_KEY is set), then falls back to
    the public CSV endpoint which requires no authentication.
    A negative value means the curve is inverted.
    Returns FALLBACK_SPREAD (0.50) if both methods fail.
    """
    if FRED_API_KEY:
        try:
            return _fetch_via_json_api()
        except Exception as exc:
            log.warning("FRED JSON API failed (%s), falling back to CSV", exc)

    try:
        return _fetch_via_csv()
    except Exception as exc:
        log.error(
            "Both FRED fetch methods failed: %s — using fallback spread %.2f%%",
            exc, FALLBACK_SPREAD,
        )
        return FALLBACK_SPREAD


def _fetch_via_json_api() -> float:
    params = {
        "series_id": "T10Y2Y",
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "limit": 10,
        "sort_order": "desc",
    }
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(FRED_JSON_URL, params=params)
        resp.raise_for_status()

    observations = resp.json().get("observations", [])
    for obs in observations:
        if obs.get("value", ".") != ".":
            return float(obs["value"])
    raise ValueError("No valid T10Y2Y observation in FRED JSON response")


def _fetch_via_csv() -> float:
    url = f"{FRED_CSV_URL}?id=T10Y2Y"
    with httpx.Client(timeout=15.0) as client:
        resp = client.get(url)
        resp.raise_for_status()

    df = pd.read_csv(StringIO(resp.text))
    df.columns = ["date", "value"]
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])

    if df.empty:
        raise ValueError("FRED CSV returned no valid T10Y2Y data")

    return float(df["value"].iloc[-1])
