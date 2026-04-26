"""Unit tests for the Catalyst Engine scoring functions."""
import pytest

from app.engines.catalyst_engine import (
    _coverage_score,
    _discount_score,
    _intensity_score,
    _sensitivity_score,
    _window_score,
    score_catalyst,
)
from tests.conftest import make_catalyst, make_mock_db_for_catalyst, make_price_row


# ---------------------------------------------------------------------------
# Subfactor 1 — Intensity
# ---------------------------------------------------------------------------

class TestIntensityScore:
    def test_passes_through_raw_value(self):
        assert _intensity_score(85.0) == pytest.approx(85.0)
        assert _intensity_score(100.0) == pytest.approx(100.0)
        assert _intensity_score(0.0) == pytest.approx(0.0)

    def test_none_returns_neutral(self):
        assert _intensity_score(None) == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Subfactor 2 — Discount score
# ---------------------------------------------------------------------------

class TestDiscountScore:
    def test_flat_price_high_discount(self):
        # ret_6m <= 0 → base=90; PROXIMO boost=8 → 98, capped at 95
        s = _discount_score(ret_6m=0.0, ret_3m=None, expected_window="PROXIMO")
        assert s == pytest.approx(95.0)

    def test_already_priced_in(self):
        # ret_6m > 0.50 → base=25; INMEDIATO boost=0 → 25
        s = _discount_score(ret_6m=0.60, ret_3m=None, expected_window="INMEDIATO")
        assert s == pytest.approx(25.0)

    def test_window_boost_applied_correctly(self):
        # FUTURO boost=15 vs INMEDIATO boost=0, same return
        s_futuro   = _discount_score(ret_6m=0.10, ret_3m=None, expected_window="FUTURO")
        s_inmediato = _discount_score(ret_6m=0.10, ret_3m=None, expected_window="INMEDIATO")
        assert s_futuro > s_inmediato
        assert s_futuro - s_inmediato == pytest.approx(15.0)

    def test_fallback_to_3m_when_6m_none(self):
        s_with_6m  = _discount_score(ret_6m=0.20, ret_3m=None, expected_window="PROXIMO")
        s_fallback = _discount_score(ret_6m=None,  ret_3m=0.20, expected_window="PROXIMO")
        assert s_with_6m == pytest.approx(s_fallback)

    def test_both_none_returns_mid_plus_boost(self):
        # None → base=65, PROXIMO boost=8 → 73
        s = _discount_score(ret_6m=None, ret_3m=None, expected_window="PROXIMO")
        assert s == pytest.approx(73.0)

    def test_return_ranges(self):
        # Verify ordering: flat < small < medium < large return → decreasing discount
        s_down  = _discount_score(ret_6m=-0.10, ret_3m=None, expected_window="INMEDIATO")
        s_small = _discount_score(ret_6m=0.05,  ret_3m=None, expected_window="INMEDIATO")
        s_mid   = _discount_score(ret_6m=0.15,  ret_3m=None, expected_window="INMEDIATO")
        s_big   = _discount_score(ret_6m=0.40,  ret_3m=None, expected_window="INMEDIATO")
        s_huge  = _discount_score(ret_6m=0.60,  ret_3m=None, expected_window="INMEDIATO")
        assert s_down >= s_small >= s_mid >= s_big >= s_huge


# ---------------------------------------------------------------------------
# Subfactor 3 — Sensitivity
# ---------------------------------------------------------------------------

class TestSensitivityScore:
    def test_both_ticker_and_sector_match_gives_highest(self):
        cat = make_catalyst(
            affected_tickers=["NVDA", "AMD"],
            affected_sectors=["Semiconductores"],
        )
        s = _sensitivity_score("NVDA", "Semiconductores", cat)
        assert s == pytest.approx(92.0)

    def test_ticker_only_match(self):
        cat = make_catalyst(
            affected_tickers=["NVDA"],
            affected_sectors=["Data Centers"],
        )
        s = _sensitivity_score("NVDA", "Semiconductores", cat)
        assert s == pytest.approx(85.0)

    def test_sector_only_match(self):
        cat = make_catalyst(
            affected_tickers=["AMD"],
            affected_sectors=["Semiconductores"],
        )
        s = _sensitivity_score("NVDA", "Semiconductores", cat)
        assert s == pytest.approx(62.0)

    def test_no_match_gives_lowest(self):
        cat = make_catalyst(
            affected_tickers=["LMT"],
            affected_sectors=["Defensa"],
        )
        s = _sensitivity_score("AAPL", "Consumer Tech", cat)
        assert s == pytest.approx(12.0)

    def test_case_insensitive_ticker_match(self):
        cat = make_catalyst(
            affected_tickers=["nvda"],
            affected_sectors=[],
        )
        s = _sensitivity_score("NVDA", "Semiconductores", cat)
        # Only ticker match (sector=[] won't match) → 85
        assert s == pytest.approx(85.0)


# ---------------------------------------------------------------------------
# Subfactor 4 — Window score
# ---------------------------------------------------------------------------

class TestWindowScore:
    def test_all_windows_mapped_correctly(self):
        assert _window_score("INMEDIATO") == pytest.approx(95.0)
        assert _window_score("PROXIMO")   == pytest.approx(75.0)
        assert _window_score("FUTURO")    == pytest.approx(55.0)
        assert _window_score("INCIERTO")  == pytest.approx(30.0)

    def test_none_returns_incierto(self):
        assert _window_score(None) == pytest.approx(30.0)

    def test_unknown_window_returns_incierto(self):
        assert _window_score("INVALID") == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# Subfactor 5 — Coverage score
# ---------------------------------------------------------------------------

class TestCoverageScore:
    def test_mega_cap_gets_lowest_coverage_score(self):
        # Mega cap → well covered → low score (28)
        s = _coverage_score("NVDA", 1, "AI_INFRASTRUCTURE")
        assert s == pytest.approx(28.0)

    def test_large_cap_gets_mid_coverage_score(self):
        s = _coverage_score("AMD", 1, "AI_INFRASTRUCTURE")
        assert s == pytest.approx(60.0)

    def test_universe_2_gets_higher_coverage(self):
        s = _coverage_score("VKTX", 2, "BIOTECH_BREAKTHROUGH")
        assert s == pytest.approx(72.0)

    def test_unknown_ticker_gets_high_coverage_score(self):
        s = _coverage_score("UNKNWN", 1, "EARNINGS_REVISION_UP")
        assert s == pytest.approx(80.0)

    def test_mega_cap_lower_than_large_cap(self):
        mega  = _coverage_score("AAPL", 1, "AI_INFRASTRUCTURE")
        large = _coverage_score("CRWD", 1, "AI_INFRASTRUCTURE")
        mid   = _coverage_score("VRT",  2, "AI_INFRASTRUCTURE")
        assert mega < large < mid


# ---------------------------------------------------------------------------
# score_catalyst — integration with mocked DB
# ---------------------------------------------------------------------------

class TestScoreCatalyst:
    def _price_rows_flat(self):
        return [
            make_price_row(f"2024-{(12 - i // 28):02d}-{(28 - i % 28):02d}", 100.0, 2_000_000)
            for i in range(140)
        ]

    def test_returns_expected_keys(self):
        cat = make_catalyst(
            affected_tickers=["NVDA"],
            affected_sectors=["Semiconductores"],
        )
        db = make_mock_db_for_catalyst(
            price_rows=self._price_rows_flat(),
            catalysts=[cat],
        )
        result = score_catalyst("NVDA", "Semiconductores", 1, db)
        for key in ["catalyst_id", "catalyst_name", "catalyst_type",
                    "expected_window", "intensity_score", "discount_score",
                    "sensitivity_score", "window_score", "coverage_score",
                    "catalyst_total"]:
            assert key in result

    def test_no_catalysts_returns_null_result(self):
        db = make_mock_db_for_catalyst(catalysts=[])
        result = score_catalyst("NVDA", "Semiconductores", 1, db)
        assert result["catalyst_id"] is None
        assert result["catalyst_total"] == pytest.approx(0.0)

    def test_best_catalyst_selected(self):
        cat_weak = make_catalyst(
            id=1, name="Weak", intensity_score=30.0,
            affected_tickers=[], affected_sectors=[],
        )
        cat_strong = make_catalyst(
            id=2, name="Strong", intensity_score=95.0,
            affected_tickers=["NVDA"], affected_sectors=["Semiconductores"],
        )
        db = make_mock_db_for_catalyst(
            price_rows=self._price_rows_flat(),
            catalysts=[cat_weak, cat_strong],
        )
        result = score_catalyst("NVDA", "Semiconductores", 1, db)
        assert result["catalyst_id"] == 2
        assert result["catalyst_name"] == "Strong"

    def test_catalyst_total_in_valid_range(self):
        cat = make_catalyst(
            intensity_score=100.0,
            affected_tickers=["NVDA"],
            affected_sectors=["Semiconductores"],
        )
        db = make_mock_db_for_catalyst(
            price_rows=self._price_rows_flat(),
            catalysts=[cat],
        )
        result = score_catalyst("NVDA", "Semiconductores", 1, db)
        assert 0.0 <= result["catalyst_total"] <= 100.0

    def test_direct_ticker_match_increases_total(self):
        cat_match = make_catalyst(
            intensity_score=80.0,
            affected_tickers=["NVDA"],
            affected_sectors=["Semiconductores"],
        )
        cat_no_match = make_catalyst(
            intensity_score=80.0,
            affected_tickers=["LMT"],
            affected_sectors=["Defensa"],
        )
        db_match = make_mock_db_for_catalyst(
            price_rows=self._price_rows_flat(), catalysts=[cat_match]
        )
        db_no_match = make_mock_db_for_catalyst(
            price_rows=self._price_rows_flat(), catalysts=[cat_no_match]
        )
        result_match    = score_catalyst("NVDA", "Semiconductores", 1, db_match)
        result_no_match = score_catalyst("NVDA", "Semiconductores", 1, db_no_match)
        assert result_match["catalyst_total"] > result_no_match["catalyst_total"]
