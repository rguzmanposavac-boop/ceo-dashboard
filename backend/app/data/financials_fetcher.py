"""
Sprint 2: ROIC, WACC (CAPM), FCF, accruals ratio via yfinance financial statements.

Formulas:
  ROIC  = NOPAT / Invested Capital
          NOPAT = EBIT * (1 - effective_tax_rate)
          Invested Capital = Total Equity + Total Debt
  WACC  = Ke * E/(D+E) + Kd * D/(D+E) * (1-t)
          Ke = Rf + β × ERP   [CAPM]
  FCF   = Operating Cash Flow + CapEx  (CapEx is negative in yfinance)
  Accruals Ratio = (EBITDA - FCF) / Total Assets
"""
import logging

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

EQUITY_RISK_PREMIUM = 0.055   # standard ERP
FALLBACK_RF = 0.045            # 10Y Treasury fallback
FALLBACK_BETA = 1.0
DEFAULT_TAX_RATE = 0.25
MIN_TAX_RATE = 0.05
MAX_TAX_RATE = 0.40


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_get(df: pd.DataFrame, *keys: str) -> float | None:
    """Return the most-recent annual value from a financial statement DataFrame.

    Tries each key in order; returns first non-null float found.
    """
    if df is None or df.empty:
        return None
    for key in keys:
        if key in df.index:
            # columns are sorted most-recent first by yfinance
            for col in df.columns:
                val = df.loc[key, col]
                if val is not None and not pd.isna(val):
                    return float(val)
    return None


def _fetch_risk_free_rate() -> float:
    """Return current 10Y US Treasury yield from ^TNX (Yahoo Finance) as a decimal."""
    try:
        t = yf.Ticker("^TNX")
        hist = t.history(period="5d", interval="1d")
        if not hist.empty:
            rf = float(hist["Close"].dropna().iloc[-1]) / 100.0
            if 0.005 <= rf <= 0.20:   # sanity bounds: 0.5% – 20%
                return rf
    except Exception as exc:
        log.warning("^TNX fetch failed (%s) — using %.1f%%", exc, FALLBACK_RF * 100)
    return FALLBACK_RF


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _empty_financials(ticker: str) -> dict:
    """Return a safe all-None financials dict when data is completely unavailable."""
    return {
        "ticker": ticker,
        "roic": None, "wacc": None, "roic_wacc_ratio": None,
        "fcf": None, "fcf_yield": None, "debt_to_equity": None,
        "interest_coverage": None, "accruals_ratio": None,
        "ebit": None, "ebitda": None, "total_assets": None,
        "total_equity": None, "total_debt": None, "market_cap": 0.0,
        "effective_tax_rate": None, "beta": None,
        "rf": None, "ke": None, "kd": None,
        "e_weight": None, "d_weight": None,
    }


def fetch_financials(ticker: str) -> dict:
    """Calculate key financial metrics for a ticker from yfinance data.

    Returns a dict with: roic, wacc, roic_wacc_ratio, fcf, fcf_yield,
    debt_to_equity, interest_coverage, accruals_ratio, and intermediate values.
    Returns None for any metric that cannot be computed.
    On complete failure, logs the error and returns _empty_financials().
    """
    try:
        return _fetch_financials_inner(ticker)
    except Exception as exc:
        log.error("[financials] Unexpected error for %s: %s", ticker, exc, exc_info=True)
        return _empty_financials(ticker)


def _fetch_financials_inner(ticker: str) -> dict:
    t = yf.Ticker(ticker)

    # --- Raw statements (annual, most-recent column first) ---
    try:
        income = t.income_stmt
    except Exception:
        income = pd.DataFrame()

    try:
        balance = t.balance_sheet
    except Exception:
        balance = pd.DataFrame()

    try:
        cashflow = t.cashflow
    except Exception:
        cashflow = pd.DataFrame()

    info: dict = {}
    try:
        info = t.info or {}
    except Exception:
        pass

    market_cap: float = info.get("marketCap") or 0.0

    # --- Income statement extractions ---
    ebit = _safe_get(
        income,
        "EBIT", "Operating Income", "Ebit", "Total Operating Income As Reported",
    )
    interest_expense = _safe_get(
        income,
        "Interest Expense", "Interest Expense Non Operating", "Net Non Operating Interest Income Expense",
    )
    tax_provision = _safe_get(
        income,
        "Tax Provision", "Income Tax Expense", "Tax Effect Of Unusual Items",
    )
    pretax_income = _safe_get(
        income,
        "Pretax Income", "Pre Tax Income", "Income Before Tax",
    )
    da = _safe_get(
        income,
        "Reconciled Depreciation", "Depreciation And Amortization",
        "Depreciation Amortization Depletion",
    )
    ebitda = _safe_get(income, "EBITDA", "Normalized EBITDA")
    if ebitda is None and ebit is not None and da is not None:
        ebitda = ebit + da

    # --- Balance sheet ---
    total_assets = _safe_get(balance, "Total Assets")
    total_equity = _safe_get(
        balance,
        "Total Equity Gross Minority Interest", "Stockholders Equity",
        "Total Stockholders Equity", "Common Stock Equity",
    )
    total_debt = _safe_get(balance, "Total Debt", "Long Term Debt And Capital Lease Obligation")
    if total_debt is None:
        long_debt = _safe_get(balance, "Long Term Debt") or 0.0
        curr_debt = _safe_get(
            balance, "Current Debt", "Current Portion Of Long Term Debt",
            "Short Long Term Debt", "Current Long Term Debt",
        ) or 0.0
        total_debt = long_debt + curr_debt

    cash = _safe_get(
        balance,
        "Cash And Cash Equivalents",
        "Cash Cash Equivalents And Short Term Investments",
        "Cash And Cash Equivalents And Short Term Investments",
    ) or 0.0

    # --- Cash flow ---
    ocf = _safe_get(
        cashflow,
        "Operating Cash Flow", "Cash Flow From Continuing Operating Activities",
        "Total Cash From Operating Activities",
    )
    capex = _safe_get(
        cashflow,
        "Capital Expenditure", "Purchase Of Property Plant And Equipment",
        "Capital Expenditures",
    )
    fcf_direct = _safe_get(cashflow, "Free Cash Flow")

    if fcf_direct is not None:
        fcf = fcf_direct
    elif ocf is not None and capex is not None:
        fcf = ocf + capex     # capex is negative in yfinance
    elif ocf is not None:
        fcf = ocf
    else:
        fcf = None

    # --- Effective tax rate ---
    eff_tax = DEFAULT_TAX_RATE
    if tax_provision is not None and pretax_income is not None and pretax_income != 0:
        raw = abs(tax_provision) / abs(pretax_income)
        eff_tax = max(MIN_TAX_RATE, min(raw, MAX_TAX_RATE))

    # --- ROIC ---
    roic: float | None = None
    if ebit is not None and total_equity is not None and total_debt is not None:
        nopat = ebit * (1.0 - eff_tax)
        invested_capital = total_equity + total_debt
        if invested_capital > 0:
            roic = nopat / invested_capital

    # --- WACC (CAPM) ---
    rf = _fetch_risk_free_rate()
    beta: float = float(info.get("beta") or FALLBACK_BETA)
    if beta <= 0 or pd.isna(beta):
        beta = FALLBACK_BETA
    ke = rf + beta * EQUITY_RISK_PREMIUM

    # Cost of debt
    kd = 0.04   # default 4%
    if interest_expense is not None and total_debt and total_debt > 0:
        kd = abs(interest_expense) / total_debt
        kd = max(0.01, min(kd, 0.20))

    e_val = abs(total_equity) if total_equity else 0.0
    d_val = abs(total_debt) if total_debt else 0.0
    total_cap = e_val + d_val
    e_weight = e_val / total_cap if total_cap > 0 else 0.7
    d_weight = d_val / total_cap if total_cap > 0 else 0.3

    wacc = ke * e_weight + kd * d_weight * (1.0 - eff_tax)

    # --- ROIC / WACC ratio ---
    roic_wacc_ratio: float | None = None
    if roic is not None and wacc > 0:
        roic_wacc_ratio = roic / wacc

    # --- FCF yield ---
    fcf_yield: float | None = None
    if fcf is not None and market_cap > 0:
        fcf_yield = fcf / market_cap

    # --- Debt / Equity ---
    debt_to_equity: float | None = None
    if total_debt is not None and total_equity and total_equity > 0:
        debt_to_equity = total_debt / total_equity
    elif info.get("debtToEquity") is not None:
        # yfinance sometimes returns this pre-calculated (as %)
        debt_to_equity = info["debtToEquity"] / 100.0

    # --- Interest coverage ---
    interest_coverage: float | None = None
    if ebit is not None and interest_expense is not None and interest_expense < 0:
        interest_coverage = ebit / abs(interest_expense)

    # --- Accruals ratio = (EBITDA - FCF) / Total Assets ---
    accruals_ratio: float | None = None
    if ebitda is not None and fcf is not None and total_assets and total_assets > 0:
        accruals_ratio = (ebitda - fcf) / total_assets

    def _r(v, n=4):
        return round(v, n) if v is not None else None

    return {
        "ticker": ticker,
        # Primary outputs (used by Core Engine)
        "roic": _r(roic),
        "wacc": _r(wacc),
        "roic_wacc_ratio": _r(roic_wacc_ratio),
        "fcf": fcf,
        "fcf_yield": _r(fcf_yield),
        "debt_to_equity": _r(debt_to_equity),
        "interest_coverage": _r(interest_coverage, 2),
        "accruals_ratio": _r(accruals_ratio),
        # Intermediate values (useful for debugging)
        "ebit": ebit,
        "ebitda": ebitda,
        "total_assets": total_assets,
        "total_equity": total_equity,
        "total_debt": total_debt,
        "market_cap": market_cap,
        "effective_tax_rate": _r(eff_tax),
        "beta": _r(beta, 3),
        "rf": _r(rf),
        "ke": _r(ke),
        "kd": _r(kd),
        "e_weight": _r(e_weight, 3),
        "d_weight": _r(d_weight, 3),
    }
