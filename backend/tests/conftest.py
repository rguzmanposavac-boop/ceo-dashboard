"""Shared pytest fixtures for unit tests."""
from unittest.mock import MagicMock


def make_price_row(price_date: str, close_price: float, volume: int = 1_000_000):
    """Create a mock PriceCache row."""
    row = MagicMock()
    row.price_date = price_date
    row.close_price = close_price
    row.volume = volume
    return row


def make_ceo(
    profile: str = "Disciplinado Sistémico",
    tenure_years: float = 5.0,
    ownership_pct: float = 1.0,
    succession_quality: str = "good",
):
    """Create a mock CEO model row."""
    ceo = MagicMock()
    ceo.profile = profile
    ceo.tenure_years = tenure_years
    ceo.ownership_pct = ownership_pct
    ceo.succession_quality = succession_quality
    return ceo


def make_catalyst(
    id: int = 1,
    name: str = "Test Catalyst",
    catalyst_type: str = "AI_INFRASTRUCTURE",
    intensity_score: float = 85.0,
    expected_window: str = "PROXIMO",
    affected_tickers: list | None = None,
    affected_sectors: list | None = None,
):
    """Create a mock Catalyst model row."""
    cat = MagicMock()
    cat.id = id
    cat.name = name
    cat.catalyst_type = catalyst_type
    cat.intensity_score = intensity_score
    cat.expected_window = expected_window
    cat.affected_tickers = affected_tickers or []
    cat.affected_sectors = affected_sectors or []
    return cat


def make_mock_db_for_core(price_rows=None, stock_id=1, ceo=None):
    """Build a mock DB session for score_core (with regime_override).

    Call order when regime_override is used:
      1. db.query(PriceCache)...
      2. db.query(Stock)...
      3. db.query(CEO)...
    """
    db = MagicMock()

    # Stock mock
    stock = MagicMock()
    stock.id = stock_id

    # CEO query chain
    ceo_mock_chain = MagicMock()
    ceo_mock_chain.filter.return_value.first.return_value = ceo

    # Stock query chain
    stock_mock_chain = MagicMock()
    stock_mock_chain.filter.return_value.first.return_value = stock

    # PriceCache query chain
    price_mock_chain = MagicMock()
    price_mock_chain.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
        price_rows or []
    )

    call_seq = [price_mock_chain, stock_mock_chain, ceo_mock_chain]
    call_idx = [0]

    def _query(*args, **kwargs):
        idx = call_idx[0]
        call_idx[0] += 1
        if idx < len(call_seq):
            return call_seq[idx]
        return MagicMock()

    db.query.side_effect = _query
    return db


def make_mock_db_for_catalyst(price_rows=None, catalysts=None):
    """Build a mock DB session for score_catalyst.

    Call order:
      1. db.query(PriceCache)...
      2. db.query(Catalyst)...
    """
    db = MagicMock()

    price_mock_chain = MagicMock()
    price_mock_chain.filter.return_value.order_by.return_value.limit.return_value.all.return_value = (
        price_rows or []
    )

    catalyst_mock_chain = MagicMock()
    catalyst_mock_chain.filter.return_value.all.return_value = catalysts or []

    call_seq = [price_mock_chain, catalyst_mock_chain]
    call_idx = [0]

    def _query(*args, **kwargs):
        idx = call_idx[0]
        call_idx[0] += 1
        return call_seq[idx] if idx < len(call_seq) else MagicMock()

    db.query.side_effect = _query
    return db
