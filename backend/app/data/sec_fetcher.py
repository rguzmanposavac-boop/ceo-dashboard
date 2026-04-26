"""
Sprint 2: Form 4 insider transactions via SEC EDGAR public APIs (no key required).

Flow:
  1. Ticker  →  CIK  via https://www.sec.gov/files/company_tickers.json
  2. CIK     →  recent Form 4 filings  via https://data.sec.gov/submissions/CIK{cik}.json
  3. Filing  →  parsed transactions  via XML document in EDGAR Archives
"""
import logging
import re
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

import httpx

log = logging.getLogger(__name__)

# SEC requires a descriptive User-Agent; bare "python-requests" may be blocked
EDGAR_HEADERS = {
    "User-Agent": "CEO-Dashboard rguzmanposavac@gmail.com",
    "Accept-Encoding": "gzip, deflate",
    "Host": "data.sec.gov",
}
ARCHIVES_HEADERS = {
    "User-Agent": "CEO-Dashboard rguzmanposavac@gmail.com",
    "Accept-Encoding": "gzip, deflate",
}

MAX_FILINGS_PER_TICKER = 15   # cap HTTP requests; enough to cover 90 days

# In-memory CIK cache (reset each process start)
_cik_cache: dict[str, str] = {}


# ---------------------------------------------------------------------------
# CIK lookup
# ---------------------------------------------------------------------------

def _get_cik(ticker: str) -> str:
    """Return the zero-padded 10-digit CIK for a ticker symbol.

    Tries the exact ticker, then without hyphens (BRK-B → BRKB).
    Raises ValueError if not found.
    """
    candidates = [ticker.upper(), ticker.upper().replace("-", ""), ticker.upper().replace(".", "")]
    for c in candidates:
        if c in _cik_cache:
            return _cik_cache[c]

    url = "https://www.sec.gov/files/company_tickers.json"
    with httpx.Client(timeout=20.0, headers=ARCHIVES_HEADERS) as client:
        resp = client.get(url)
        resp.raise_for_status()

    data = resp.json()
    for entry in data.values():
        sec_ticker = str(entry.get("ticker", "")).upper()
        cik = str(entry["cik_str"]).zfill(10)
        _cik_cache[sec_ticker] = cik

    for c in candidates:
        if c in _cik_cache:
            return _cik_cache[c]

    raise ValueError(f"CIK not found for ticker '{ticker}' in SEC company_tickers.json")


# ---------------------------------------------------------------------------
# Submissions / filing list
# ---------------------------------------------------------------------------

def _get_recent_form4_filings(cik: str, days: int) -> list[dict]:
    """Return metadata for Form 4 filings in the last N days for a CIK."""
    url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    headers = dict(EDGAR_HEADERS)
    headers["Host"] = "data.sec.gov"

    with httpx.Client(timeout=20.0, headers=headers) as client:
        resp = client.get(url)
        resp.raise_for_status()

    data = resp.json()
    recent = data.get("filings", {}).get("recent", {})

    forms        = recent.get("form", [])
    dates        = recent.get("filingDate", [])
    accessions   = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])

    cutoff = datetime.utcnow() - timedelta(days=days)
    cik_int = str(int(cik))     # numeric, no leading zeros, for archive URL

    result = []
    for form, date_str, accession, primary_doc in zip(forms, dates, accessions, primary_docs):
        if form != "4":
            continue
        try:
            filing_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if filing_date < cutoff:
            break   # filings are in reverse-chronological order; stop early

        accession_nodash = accession.replace("-", "")

        # Strip XSLT viewer prefix added by EDGAR (e.g. "xslF345X06/filename.xml" → "filename.xml").
        # Requesting the raw filename returns XML; the prefixed path returns rendered HTML.
        clean_doc = re.sub(r"^xsl[A-Za-z0-9]+/", "", primary_doc)

        doc_url = (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{cik_int}/{accession_nodash}/{clean_doc}"
        )
        result.append({
            "filing_date": date_str,
            "accession": accession,
            "doc_url": doc_url,
        })

    return result


# ---------------------------------------------------------------------------
# XML parser
# ---------------------------------------------------------------------------

# Human-readable transaction type labels
_TX_CODE_LABELS = {
    "P": "BUY",        # Open-market purchase
    "S": "SELL",       # Open-market sale
    "A": "GRANT",      # Award/grant
    "D": "RETURN",     # Disposition to company
    "F": "TAX_WHOLD",  # Tax withholding
    "G": "GIFT",
    "M": "EXERCISE",   # Exercise of derivative
    "C": "CONVERT",
}


def _parse_form4_xml(xml_text: str, filing_date: str) -> list[dict]:
    """Parse Form 4 XML and return a list of transaction dicts.

    Handles both nonDerivativeTransaction and derivativeTransaction tables.
    """
    transactions: list[dict] = []

    try:
        # SEC XML sometimes has encoding declaration issues; strip BOM if present
        xml_clean = xml_text.strip().lstrip("﻿")
        root = ET.fromstring(xml_clean)
    except ET.ParseError as exc:
        log.debug("XML parse error for Form 4 filing %s: %s", filing_date, exc)
        return []

    # Reporting owner name
    owner_el = root.find(".//reportingOwner/reportingOwnerId/rptOwnerName")
    owner_name = owner_el.text.strip() if owner_el is not None and owner_el.text else "Unknown"

    # Owner title / relationship
    title_el = root.find(".//reportingOwner/reportingOwnerRelationship/officerTitle")
    owner_title = title_el.text.strip() if title_el is not None and title_el.text else ""

    def _text(el_path: str) -> str | None:
        el = root.find(el_path)
        return el.text.strip() if el is not None and el.text else None

    def _float(el_path: str) -> float | None:
        v = _text(el_path)
        try:
            return float(v) if v else None
        except ValueError:
            return None

    def _parse_table(table_tag: str, tx_tag: str, is_derivative: bool):
        for tx_el in root.findall(f".//{tx_tag}"):
            try:
                tx_date   = _text(".//transactionDate/value") or filing_date
                security  = _text(".//securityTitle/value") or ""
                tx_code   = _text(".//transactionCoding/transactionCode") or ""
                shares    = _float(".//transactionShares/value") or 0.0
                price     = _float(".//transactionPricePerShare/value")
                acq_disp  = _text(".//transactionAcquiredDisposedCode/value") or ""
                owned_after = _float(".//sharesOwnedFollowingTransaction/value")

                tx_type = _TX_CODE_LABELS.get(tx_code, f"OTHER_{tx_code}")
                value_usd = round(shares * price, 2) if price and shares else None

                transactions.append({
                    "owner_name":        owner_name,
                    "owner_title":       owner_title,
                    "transaction_date":  tx_date,
                    "filing_date":       filing_date,
                    "security":          security,
                    "transaction_code":  tx_code,
                    "transaction_type":  tx_type,
                    "shares":            shares,
                    "price_per_share":   price,
                    "acquired_disposed": acq_disp,
                    "shares_owned_after": owned_after,
                    "is_derivative":     is_derivative,
                    "value_usd":         value_usd,
                })
            except Exception as exc:
                log.debug("Skipping transaction row: %s", exc)

    _parse_table("nonDerivativeTable", "nonDerivativeTransaction", False)
    _parse_table("derivativeTable",    "derivativeTransaction",    True)

    return transactions


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def fetch_insider_transactions(ticker: str, days: int = 90) -> list[dict]:
    """Return insider Form 4 transactions from the last N days via SEC EDGAR.

    Returns list of dicts sorted by transaction_date descending.
    Returns empty list on any lookup failure (never raises).
    """
    try:
        cik = _get_cik(ticker)
    except ValueError as exc:
        log.warning("SEC CIK lookup failed for %s: %s", ticker, exc)
        return []
    except Exception as exc:
        log.error("Unexpected error in CIK lookup for %s: %s", ticker, exc)
        return []

    try:
        filings = _get_recent_form4_filings(cik, days)
    except Exception as exc:
        log.error("Failed to get Form 4 filings for %s (CIK %s): %s", ticker, cik, exc)
        return []

    log.info("%s: %d Form 4 filing(s) in last %d days", ticker, len(filings), days)

    all_transactions: list[dict] = []

    with httpx.Client(
        timeout=15.0,
        headers=ARCHIVES_HEADERS,
        follow_redirects=True,
    ) as client:
        for filing in filings[:MAX_FILINGS_PER_TICKER]:
            try:
                resp = client.get(filing["doc_url"])
                if resp.status_code != 200:
                    log.debug("HTTP %d for %s", resp.status_code, filing["doc_url"])
                    continue
                txns = _parse_form4_xml(resp.text, filing["filing_date"])
                all_transactions.extend(txns)
            except Exception as exc:
                log.warning("Failed to process filing %s: %s", filing["accession"], exc)

    # Sort most-recent first
    all_transactions.sort(
        key=lambda x: x.get("transaction_date") or x.get("filing_date") or "",
        reverse=True,
    )
    return all_transactions
