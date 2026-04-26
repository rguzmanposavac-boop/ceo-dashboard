"""Unit tests for the Decision Engine."""
import pytest

from app.engines.decision_engine import (
    INVALIDATOR_TEMPLATES,
    classify_horizon,
    classify_signal,
    compute_final_score,
    estimate_expected_return,
    estimate_probability,
    select_invalidators,
)


# ---------------------------------------------------------------------------
# Final score formula
# ---------------------------------------------------------------------------

class TestComputeFinalScore:
    def test_formula_65_35(self):
        # core=80, catalyst=60 → 80*0.65 + 60*0.35 = 52 + 21 = 73
        assert compute_final_score(80.0, 60.0) == pytest.approx(73.0)

    def test_both_zero(self):
        assert compute_final_score(0.0, 0.0) == pytest.approx(0.0)

    def test_both_100(self):
        assert compute_final_score(100.0, 100.0) == pytest.approx(100.0)

    def test_weights_sum_to_1(self):
        # If core and catalyst are equal, result equals each
        assert compute_final_score(70.0, 70.0) == pytest.approx(70.0)


# ---------------------------------------------------------------------------
# Signal classification thresholds
# ---------------------------------------------------------------------------

class TestClassifySignal:
    def test_exactly_at_80_gives_compra_fuerte(self):
        assert classify_signal(80.0) == "COMPRA_FUERTE"

    def test_just_below_80_gives_compra(self):
        assert classify_signal(79.9) == "COMPRA"

    def test_exactly_at_70_gives_compra(self):
        assert classify_signal(70.0) == "COMPRA"

    def test_just_below_70_gives_vigilar(self):
        assert classify_signal(69.9) == "VIGILAR"

    def test_exactly_at_58_gives_vigilar(self):
        assert classify_signal(58.0) == "VIGILAR"

    def test_just_below_58_gives_evitar(self):
        assert classify_signal(57.9) == "EVITAR"

    def test_zero_gives_evitar(self):
        assert classify_signal(0.0) == "EVITAR"

    def test_100_gives_compra_fuerte(self):
        assert classify_signal(100.0) == "COMPRA_FUERTE"

    def test_all_thresholds_monotonic(self):
        signals = [classify_signal(s) for s in [100, 85, 80, 75, 70, 65, 58, 50, 0]]
        # Each signal is at least as strong as the next
        order = ["COMPRA_FUERTE", "COMPRA", "VIGILAR", "EVITAR"]
        prev_idx = 0
        for sig in signals:
            idx = order.index(sig)
            assert idx >= prev_idx
            prev_idx = idx


# ---------------------------------------------------------------------------
# Horizon classification
# ---------------------------------------------------------------------------

class TestClassifyHorizon:
    def test_inmediato_catalyst_with_high_score_gives_corto(self):
        h = classify_horizon(
            catalyst_window="INMEDIATO",
            catalyst_total=80.0,
            core_roic=60.0,
            core_fundamentals=60.0,
        )
        assert h == "CORTO_PLAZO"

    def test_inmediato_but_low_catalyst_score_falls_through(self):
        # catalyst_total <= 75 → doesn't qualify for CORTO
        h = classify_horizon(
            catalyst_window="INMEDIATO",
            catalyst_total=70.0,
            core_roic=60.0,
            core_fundamentals=60.0,
        )
        # Falls to MEDIANO or LARGO depending on fundamentals
        assert h in ("MEDIANO_PLAZO", "LARGO_PLAZO")

    def test_strong_fundamentals_give_largo_plazo(self):
        h = classify_horizon(
            catalyst_window="FUTURO",
            catalyst_total=60.0,
            core_roic=75.0,       # > 70
            core_fundamentals=70.0, # > 65
        )
        assert h == "LARGO_PLAZO"

    def test_weak_fundamentals_give_mediano_plazo(self):
        h = classify_horizon(
            catalyst_window="FUTURO",
            catalyst_total=60.0,
            core_roic=50.0,       # < 70
            core_fundamentals=60.0, # < 65
        )
        assert h == "MEDIANO_PLAZO"

    def test_corto_takes_priority_over_largo(self):
        # Even with strong fundamentals, INMEDIATO high catalyst → CORTO
        h = classify_horizon(
            catalyst_window="INMEDIATO",
            catalyst_total=90.0,
            core_roic=80.0,
            core_fundamentals=80.0,
        )
        assert h == "CORTO_PLAZO"


# ---------------------------------------------------------------------------
# Invalidator selection
# ---------------------------------------------------------------------------

class TestSelectInvalidators:
    def _base_inputs(self, signal="COMPRA", horizon="MEDIANO_PLAZO",
                     cat_total=60.0, cat_id=1, fcf=1e9,
                     roic_ratio=1.8, succession="good", dte=0.5):
        core_result     = {"roic_wacc_ratio": roic_ratio}
        catalyst_result = {"catalyst_total": cat_total, "catalyst_id": cat_id}
        financials      = {"fcf": fcf, "debt_to_equity": dte}
        return dict(
            signal=signal, horizon=horizon,
            core_result=core_result, catalyst_result=catalyst_result,
            financials=financials, ceo_succession=succession,
        )

    def test_macro_shock_always_present(self):
        inv = select_invalidators(**self._base_inputs(signal="EVITAR", horizon="MEDIANO_PLAZO",
                                                       cat_total=0.0, cat_id=None,
                                                       fcf=-1e9, roic_ratio=2.5,
                                                       succession="excellent", dte=0.1))
        keys = [i["key"] for i in inv]
        assert "MACRO_SHOCK" in keys

    def test_compra_fuerte_adds_earnings_miss(self):
        inv = select_invalidators(**self._base_inputs(signal="COMPRA_FUERTE"))
        keys = [i["key"] for i in inv]
        assert "EARNINGS_MISS" in keys
        assert "REGIMEN_CHANGE" in keys

    def test_corto_plazo_adds_sector_rotation(self):
        inv = select_invalidators(**self._base_inputs(horizon="CORTO_PLAZO"))
        keys = [i["key"] for i in inv]
        assert "SECTOR_ROTATION" in keys

    def test_high_cat_total_adds_catalyst_priced_in(self):
        inv = select_invalidators(**self._base_inputs(cat_total=60.0))
        keys = [i["key"] for i in inv]
        assert "CATALYST_PRICED_IN" in keys

    def test_cat_total_below_40_no_catalyst_priced_in(self):
        inv = select_invalidators(**self._base_inputs(cat_total=35.0, cat_id=None))
        keys = [i["key"] for i in inv]
        assert "CATALYST_PRICED_IN" not in keys

    def test_positive_fcf_adds_fcf_deterioration(self):
        inv = select_invalidators(**self._base_inputs(fcf=1_000_000))
        keys = [i["key"] for i in inv]
        assert "FCF_DETERIORATION" in keys

    def test_negative_fcf_no_fcf_deterioration(self):
        inv = select_invalidators(**self._base_inputs(fcf=-500_000))
        keys = [i["key"] for i in inv]
        assert "FCF_DETERIORATION" not in keys

    def test_roic_near_threshold_adds_roic_drop(self):
        inv = select_invalidators(**self._base_inputs(roic_ratio=1.2))  # < 1.5
        keys = [i["key"] for i in inv]
        assert "ROIC_DROP" in keys

    def test_high_roic_no_roic_drop(self):
        inv = select_invalidators(**self._base_inputs(roic_ratio=2.0))  # ≥ 1.5
        keys = [i["key"] for i in inv]
        assert "ROIC_DROP" not in keys

    def test_poor_succession_adds_ceo_departure(self):
        inv = select_invalidators(**self._base_inputs(succession="poor"))
        keys = [i["key"] for i in inv]
        assert "CEO_DEPARTURE" in keys

    def test_good_succession_no_ceo_departure(self):
        inv = select_invalidators(**self._base_inputs(succession="good"))
        keys = [i["key"] for i in inv]
        assert "CEO_DEPARTURE" not in keys

    def test_high_debt_adds_debt_surge(self):
        inv = select_invalidators(**self._base_inputs(dte=1.5))  # > 1.0
        keys = [i["key"] for i in inv]
        assert "DEBT_SURGE" in keys

    def test_all_invalidator_keys_have_descriptions(self):
        inv = select_invalidators(**self._base_inputs(
            signal="COMPRA_FUERTE", horizon="CORTO_PLAZO",
            cat_total=80.0, cat_id=1, fcf=1e9, roic_ratio=1.2,
            succession="poor", dte=2.0,
        ))
        for item in inv:
            assert item["key"] in INVALIDATOR_TEMPLATES
            assert len(item["description"]) > 10

    def test_output_is_sorted_deterministically(self):
        # Run twice, should return same order (sorted by key)
        inv1 = select_invalidators(**self._base_inputs())
        inv2 = select_invalidators(**self._base_inputs())
        assert [i["key"] for i in inv1] == [i["key"] for i in inv2]


# ---------------------------------------------------------------------------
# Expected return estimates
# ---------------------------------------------------------------------------

class TestEstimateExpectedReturn:
    def _cat_result(self, total=60.0, discount=50.0):
        return {"catalyst_total": total, "discount_score": discount}

    def test_compra_fuerte_range(self):
        low, high = estimate_expected_return("COMPRA_FUERTE", self._cat_result(), {})
        assert low == pytest.approx(0.25)
        assert high >= 0.60

    def test_evitar_range_includes_negative(self):
        low, high = estimate_expected_return("EVITAR", self._cat_result(), {})
        assert low < 0

    def test_catalyst_boost_increases_high_end(self):
        # High catalyst + high discount → high end gets boosted
        low_base, high_base = estimate_expected_return(
            "COMPRA_FUERTE", self._cat_result(total=60.0, discount=50.0), {}
        )
        low_boost, high_boost = estimate_expected_return(
            "COMPRA_FUERTE", self._cat_result(total=80.0, discount=70.0), {}
        )
        assert high_boost > high_base

    def test_returns_are_sensible_range(self):
        for sig in ["COMPRA_FUERTE", "COMPRA", "VIGILAR", "EVITAR"]:
            low, high = estimate_expected_return(sig, self._cat_result(), {})
            assert -0.20 <= low <= 0.50
            assert 0.0 <= high <= 1.50


# ---------------------------------------------------------------------------
# Probability estimates
# ---------------------------------------------------------------------------

class TestEstimateProbability:
    def test_compra_fuerte_base_probability(self):
        # Score exactly at threshold (80) → base 0.62 + 0 fine-tune
        p = estimate_probability("COMPRA_FUERTE", 80.0)
        assert p == pytest.approx(0.62)

    def test_evitar_base_probability(self):
        p = estimate_probability("EVITAR", 0.0)
        # base=0.20, fine-tune = 0*0.003 = 0 → 0.20
        assert p == pytest.approx(0.20)

    def test_high_score_boosts_probability(self):
        p_base = estimate_probability("COMPRA_FUERTE", 80.0)
        p_high = estimate_probability("COMPRA_FUERTE", 90.0)
        assert p_high > p_base

    def test_probability_capped_at_0_85(self):
        p = estimate_probability("COMPRA_FUERTE", 200.0)
        assert p == pytest.approx(0.85)

    def test_probability_floors_at_0_10(self):
        p = estimate_probability("EVITAR", -100.0)
        assert p == pytest.approx(0.10)

    def test_probability_in_valid_range_all_signals(self):
        for sig in ["COMPRA_FUERTE", "COMPRA", "VIGILAR", "EVITAR"]:
            for score in [0, 50, 75, 90, 100]:
                p = estimate_probability(sig, score)
                assert 0.10 <= p <= 0.85
