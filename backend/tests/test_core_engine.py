"""Unit tests for the Core Engine scoring functions."""
import pytest

from app.engines.core_engine import (
    _balance_score,
    _base_score,
    _ceo_score,
    _liquidity_score,
    _momentum_score,
    _sector_score,
    _valuation_score,
    ownership_factor,
    roic_wacc_score,
    score_core,
    succession_factor,
    tenure_multiplier,
)
from tests.conftest import make_ceo, make_mock_db_for_core, make_price_row


# ---------------------------------------------------------------------------
# Layer 0 — Sector/Regime score
# ---------------------------------------------------------------------------

class TestSectorScore:
    def test_favored_sector_gets_high_score(self):
        # Healthcare is favored in CRISIS
        s = _sector_score("Healthcare", "CRISIS", confidence=1.0)
        assert s == pytest.approx(85.0)

    def test_avoided_sector_gets_low_score(self):
        # EVs are avoided in CRISIS
        s = _sector_score("EVs", "CRISIS", confidence=1.0)
        assert s == pytest.approx(20.0)

    def test_neutral_sector_gets_mid_score(self):
        s = _sector_score("Real Estate", "NORMAL", confidence=1.0)
        assert s == pytest.approx(55.0)

    def test_partial_match_favored(self):
        # "Semiconductores" is favored in ALCISTA; "IA Software" is in ALCISTA favored too (via IA)
        s = _sector_score("Semiconductores", "ALCISTA", confidence=1.0)
        assert s == pytest.approx(85.0)

    def test_confidence_blends_toward_neutral(self):
        # With confidence=0, result should be exactly 55 (neutral)
        s = _sector_score("Healthcare", "CRISIS", confidence=0.0)
        assert s == pytest.approx(55.0)

    def test_confidence_partial(self):
        # confidence=0.5: 85*0.5 + 55*0.5 = 70
        s = _sector_score("Healthcare", "CRISIS", confidence=0.5)
        assert s == pytest.approx(70.0)

    def test_all_regimes_return_valid_range(self):
        for regime in ["CRISIS", "BAJISTA", "NORMAL", "ALCISTA", "REBOTE"]:
            s = _sector_score("Tecnología", regime, confidence=1.0)
            assert 0.0 <= s <= 100.0


# ---------------------------------------------------------------------------
# Layer 1 — Momentum
# ---------------------------------------------------------------------------

class TestMomentumScore:
    def test_all_positive_returns_give_high_score(self):
        s = _momentum_score(0.20, 0.30, 0.40)
        assert s > 70.0

    def test_all_negative_returns_give_low_score(self):
        s = _momentum_score(-0.20, -0.30, -0.40)
        assert s < 35.0

    def test_zero_returns_give_neutral_score(self):
        # 0% return → clamped=0 → (0+0.5)*100 = 50 for each
        s = _momentum_score(0.0, 0.0, 0.0)
        assert s == pytest.approx(50.0)

    def test_returns_clamped_at_boundaries(self):
        # ±50% is the clamp boundary; +50% → score 100 for each horizon
        s_max = _momentum_score(0.50, 0.50, 0.50)
        s_beyond = _momentum_score(1.00, 1.00, 1.00)
        assert s_max == pytest.approx(s_beyond)  # clamped at same value

    def test_none_returns_default_to_neutral(self):
        s = _momentum_score(None, None, None)
        assert s == pytest.approx(50.0)

    def test_weights(self):
        # 3M weight=0.40, 6M=0.30, 12M=0.30
        # Set each to a distinctive value and verify weighting
        # +50% → 100, -50% → 0, 0% → 50
        s = _momentum_score(0.50, -0.50, 0.0)
        # 100*0.40 + 0*0.30 + 50*0.30 = 40 + 0 + 15 = 55
        assert s == pytest.approx(55.0)


# ---------------------------------------------------------------------------
# Layer 1 — Balance score
# ---------------------------------------------------------------------------

class TestBalanceScore:
    def test_excellent_financials_give_high_score(self):
        s = _balance_score(fcf_yield=0.10, debt_to_equity=0.3, interest_coverage=8.0)
        assert s >= 85.0  # 90+90+90 / 3

    def test_bad_financials_give_low_score(self):
        s = _balance_score(fcf_yield=-0.05, debt_to_equity=3.0, interest_coverage=0.5)
        assert s <= 25.0  # 20+25+15 / 3

    def test_none_values_use_neutral_fallback(self):
        s = _balance_score(None, None, None)
        assert 40.0 <= s <= 60.0  # neutral range

    def test_fcf_yield_thresholds(self):
        assert _balance_score(0.06, None, None) > _balance_score(0.03, None, None)
        assert _balance_score(0.03, None, None) > _balance_score(0.01, None, None)
        assert _balance_score(0.01, None, None) > _balance_score(-0.01, None, None)

    def test_interest_coverage_thresholds(self):
        s_high = _balance_score(None, None, 6.0)   # ≥5 → 90
        s_mid  = _balance_score(None, None, 4.0)   # 3-5 → 70
        s_low  = _balance_score(None, None, 2.0)   # 1.5-3 → 45
        s_bad  = _balance_score(None, None, 1.0)   # <1.5 → 15
        assert s_high > s_mid > s_low > s_bad


# ---------------------------------------------------------------------------
# Layer 1 — Liquidity score
# ---------------------------------------------------------------------------

class TestLiquidityScore:
    def test_high_volume_gives_max_score(self):
        assert _liquidity_score(100_000_000) == pytest.approx(95.0)

    def test_medium_volume_tiers(self):
        assert _liquidity_score(20_000_000) == pytest.approx(75.0)
        assert _liquidity_score(5_000_000) == pytest.approx(50.0)

    def test_low_volume_gives_min_score(self):
        assert _liquidity_score(500_000) == pytest.approx(20.0)

    def test_none_gives_neutral(self):
        assert _liquidity_score(None) == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Layer 1 — Valuation score
# ---------------------------------------------------------------------------

class TestValuationScore:
    def test_cheap_multiples_give_high_score(self):
        s = _valuation_score(pe=12.0, ev_ebitda=6.0, p_fcf=10.0)
        assert s >= 85.0  # 90+90+90 / 3

    def test_expensive_multiples_give_low_score(self):
        s = _valuation_score(pe=50.0, ev_ebitda=30.0, p_fcf=45.0)
        assert s <= 30.0  # 25+25+25 / 3

    def test_pe_thresholds(self):
        assert _valuation_score(pe=10, ev_ebitda=None, p_fcf=None) > \
               _valuation_score(pe=20, ev_ebitda=None, p_fcf=None)

    def test_negative_pe_treated_as_loss_making(self):
        s = _valuation_score(pe=-5.0, ev_ebitda=None, p_fcf=None)
        assert s == pytest.approx(30.0)

    def test_none_returns_neutral(self):
        s = _valuation_score(None, None, None)
        assert s == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Layer 1 — Base score with accruals penalty
# ---------------------------------------------------------------------------

class TestBaseScore:
    def test_accruals_penalty_applied_above_threshold(self):
        # Build a score without penalty
        base = _base_score(
            ret_3m=0.10, ret_6m=0.10, ret_12m=0.10,
            fcf_yield=0.05, debt_to_equity=0.3, interest_coverage=8.0,
            avg_daily_volume=50_000_000,
            pe=15.0, ev_ebitda=8.0, p_fcf=12.0,
            accruals_ratio=0.05,  # below threshold
        )
        penalized = _base_score(
            ret_3m=0.10, ret_6m=0.10, ret_12m=0.10,
            fcf_yield=0.05, debt_to_equity=0.3, interest_coverage=8.0,
            avg_daily_volume=50_000_000,
            pe=15.0, ev_ebitda=8.0, p_fcf=12.0,
            accruals_ratio=0.11,  # above threshold
        )
        assert base - penalized == pytest.approx(20.0)

    def test_accruals_below_threshold_no_penalty(self):
        # Exactly at 0.10 should NOT trigger penalty
        s_at   = _base_score(0, 0, 0, None, None, None, None, None, None, None, 0.10)
        s_none = _base_score(0, 0, 0, None, None, None, None, None, None, None, None)
        assert s_at == s_none

    def test_score_stays_in_valid_range(self):
        # Even with penalty, score should not go below 0
        s = _base_score(
            ret_3m=-0.50, ret_6m=-0.50, ret_12m=-0.50,
            fcf_yield=-0.10, debt_to_equity=3.0, interest_coverage=0.5,
            avg_daily_volume=100_000,
            pe=60.0, ev_ebitda=30.0, p_fcf=50.0,
            accruals_ratio=0.50,
        )
        assert 0.0 <= s <= 100.0


# ---------------------------------------------------------------------------
# Layer 2 — ROIC/WACC score
# ---------------------------------------------------------------------------

class TestRoicWaccScore:
    def test_ratio_above_2_gives_100(self):
        assert roic_wacc_score(2.0) == pytest.approx(100.0)
        assert roic_wacc_score(3.5) == pytest.approx(100.0)

    def test_ratio_1_5_to_2_gives_80(self):
        assert roic_wacc_score(1.5) == pytest.approx(80.0)
        assert roic_wacc_score(1.9) == pytest.approx(80.0)

    def test_ratio_1_0_to_1_5_gives_60(self):
        assert roic_wacc_score(1.0) == pytest.approx(60.0)
        assert roic_wacc_score(1.4) == pytest.approx(60.0)

    def test_ratio_below_1_gives_0(self):
        assert roic_wacc_score(0.99) == pytest.approx(0.0)
        assert roic_wacc_score(0.0) == pytest.approx(0.0)

    def test_boundary_exactly_at_1_gives_60(self):
        # ratio=1.0 falls into the "≥1.0" bucket → 60
        assert roic_wacc_score(1.0) == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# Layer 3 — CEO multipliers
# ---------------------------------------------------------------------------

class TestCeoMultipliers:
    def test_tenure_multiplier_peak_at_3_to_5_years(self):
        assert tenure_multiplier(4.0) == pytest.approx(1.10)

    def test_tenure_multiplier_new_ceo_discounted(self):
        assert tenure_multiplier(0.5) == pytest.approx(0.85)

    def test_tenure_multiplier_long_tenure_discounted(self):
        assert tenure_multiplier(20.0) == pytest.approx(0.88)

    def test_ownership_high_gets_boost(self):
        assert ownership_factor(15.0) == pytest.approx(1.15)

    def test_ownership_low_gets_penalty(self):
        assert ownership_factor(0.05) == pytest.approx(0.95)

    def test_succession_excellent_boost(self):
        assert succession_factor("excellent") == pytest.approx(1.08)

    def test_succession_poor_penalty(self):
        assert succession_factor("poor") == pytest.approx(0.92)

    def test_succession_unknown_falls_back(self):
        assert succession_factor("unknown") == pytest.approx(0.97)


class TestCeoScore:
    def test_racional_paciente_high_in_crisis(self):
        s = _ceo_score("Racional Paciente", "CRISIS", 5.0, 1.0, "good")
        # base=95, tenure_mult=1.10, ownership=1.05, succession=1.02 → ~112 capped at 100
        assert s == pytest.approx(100.0)

    def test_narcisista_visionario_low_in_crisis(self):
        s = _ceo_score("Narcisista Visionario", "CRISIS", 5.0, 1.0, "poor")
        # base=30, tenure=1.10, ownership=1.05, succession=0.92 → ~31.8
        assert s < 40.0

    def test_visionario_sistemico_high_in_alcista(self):
        s = _ceo_score("Visionario Sistémico", "ALCISTA", 5.0, 5.0, "good")
        # base=90, tenure=1.10, ownership=1.10, succession=1.02 → ~110 capped 100
        assert s == pytest.approx(100.0)

    def test_unknown_profile_uses_fallback(self):
        # Unknown profile → uses default base 60
        s = _ceo_score("Unknown Profile XYZ", "NORMAL", 5.0, 0.1, "good")
        assert 30.0 <= s <= 100.0

    def test_none_values_handled_gracefully(self):
        s = _ceo_score(None, "NORMAL", None, None, None)
        assert 0.0 <= s <= 100.0


# ---------------------------------------------------------------------------
# score_core — integration with mocked DB
# ---------------------------------------------------------------------------

class TestScoreCore:
    def _financials_good(self):
        return {
            "roic_wacc_ratio": 1.8,
            "fcf": 5_000_000_000,
            "fcf_yield": 0.04,
            "debt_to_equity": 0.4,
            "interest_coverage": 7.0,
            "accruals_ratio": 0.03,
            "market_cap": 120_000_000_000,
            "ebitda": 10_000_000_000,
            "ebit": 8_000_000_000,
            "total_debt": 5_000_000_000,
            "net_income": 6_000_000_000,
            "cash": 10_000_000_000,
        }

    def _price_rows(self):
        # 270 rows descending, starting at $100, each day $0.10 lower
        return [
            make_price_row(f"2024-{(12 - i // 30):02d}-{(28 - i % 28):02d}", 100.0 - i * 0.10, 5_000_000)
            for i in range(270)
        ]

    def test_returns_expected_keys(self):
        db = make_mock_db_for_core(price_rows=self._price_rows())
        result = score_core("MSFT", "Software", db,
                            financials=self._financials_good(),
                            regime_override="NORMAL")
        for key in ["regime", "excluded", "sector_score", "base_score",
                    "roic_wacc_score", "ceo_score", "core_total",
                    "accruals_penalized", "roic_wacc_ratio"]:
            assert key in result

    def test_roic_below_wacc_triggers_hard_exclusion(self):
        db = make_mock_db_for_core()
        fin = {"roic_wacc_ratio": 0.8}
        result = score_core("TEST", "Tecnología", db,
                            financials=fin, regime_override="NORMAL")
        assert result["excluded"] is True
        assert result["core_total"] == pytest.approx(0.0)
        assert result["signal"] == "EVITAR" if "signal" in result else True

    def test_good_financials_give_high_core_total(self):
        db = make_mock_db_for_core(price_rows=self._price_rows())
        result = score_core("MSFT", "Software", db,
                            financials=self._financials_good(),
                            regime_override="ALCISTA")
        assert result["core_total"] >= 60.0
        assert result["excluded"] is False

    def test_accruals_flag_set_when_high(self):
        db = make_mock_db_for_core(price_rows=self._price_rows())
        fin = {**self._financials_good(), "accruals_ratio": 0.15}
        result = score_core("TEST", "Software", db,
                            financials=fin, regime_override="NORMAL")
        assert result["accruals_penalized"] is True

    def test_ceo_profile_affects_score(self):
        price_rows = self._price_rows()
        ceo_good = make_ceo("Racional Paciente", 5.0, 1.0, "excellent")
        ceo_bad  = make_ceo("Narcisista Visionario", 20.0, 0.05, "poor")

        db_good = make_mock_db_for_core(price_rows, ceo=ceo_good)
        db_bad  = make_mock_db_for_core(price_rows, ceo=ceo_bad)

        result_good = score_core("X", "Holdings", db_good,
                                 financials=self._financials_good(),
                                 regime_override="CRISIS")
        result_bad  = score_core("X", "Holdings", db_bad,
                                 financials=self._financials_good(),
                                 regime_override="CRISIS")
        assert result_good["ceo_score"] > result_bad["ceo_score"]

    def test_regime_override_respected(self):
        db = make_mock_db_for_core(price_rows=self._price_rows())
        result = score_core("X", "Seguros", db,
                            financials=self._financials_good(),
                            regime_override="BAJISTA")
        assert result["regime"] == "BAJISTA"
        # Seguros is favored in BAJISTA → sector_score should be high
        assert result["sector_score"] > 70.0

    def test_core_total_in_valid_range(self):
        for regime in ["CRISIS", "BAJISTA", "NORMAL", "ALCISTA", "REBOTE"]:
            db = make_mock_db_for_core(price_rows=self._price_rows())
            result = score_core("X", "Healthcare", db,
                                financials=self._financials_good(),
                                regime_override=regime)
            assert 0.0 <= result["core_total"] <= 100.0
