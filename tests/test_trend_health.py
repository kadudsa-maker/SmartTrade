import inspect

import pytest

from market_structure import (
    DivergenceDirection,
    MarketStructureState,
    PivotType,
    PricePivot,
    evaluate_market_structure,
)
from trend_health import (
    TrendHealthState,
    evaluate_trend_health,
)


def _pivot(index, price, pivot_type):
    return PricePivot(index=index, price=price, type=pivot_type)


def _uptrend():
    return evaluate_market_structure([
        _pivot(1, 100.0, PivotType.HIGH),
        _pivot(2, 90.0, PivotType.LOW),
        _pivot(3, 110.0, PivotType.HIGH),
        _pivot(4, 95.0, PivotType.LOW),
    ])


def _downtrend():
    return evaluate_market_structure([
        _pivot(1, 110.0, PivotType.HIGH),
        _pivot(2, 95.0, PivotType.LOW),
        _pivot(3, 100.0, PivotType.HIGH),
        _pivot(4, 90.0, PivotType.LOW),
    ])


def _potential_distribution():
    return evaluate_market_structure(
        [
            _pivot(1, 100.0, PivotType.HIGH),
            _pivot(2, 90.0, PivotType.LOW),
            _pivot(3, 110.0, PivotType.HIGH),
            _pivot(4, 95.0, PivotType.LOW),
            _pivot(5, 105.0, PivotType.HIGH),
        ],
        divergence_direction=DivergenceDirection.BEARISH,
    )


def _potential_accumulation():
    return evaluate_market_structure(
        [
            _pivot(1, 110.0, PivotType.HIGH),
            _pivot(2, 95.0, PivotType.LOW),
            _pivot(3, 100.0, PivotType.HIGH),
            _pivot(4, 90.0, PivotType.LOW),
            _pivot(5, 98.0, PivotType.HIGH),
            _pivot(6, 92.0, PivotType.LOW),
        ],
        divergence_direction=DivergenceDirection.BULLISH,
    )


def _downtrend_confirmed():
    return evaluate_market_structure([
        _pivot(1, 100.0, PivotType.HIGH),
        _pivot(2, 90.0, PivotType.LOW),
        _pivot(3, 110.0, PivotType.HIGH),
        _pivot(4, 95.0, PivotType.LOW),
        _pivot(5, 105.0, PivotType.HIGH),
        _pivot(6, 85.0, PivotType.LOW),
    ])


def _uptrend_confirmed():
    return evaluate_market_structure([
        _pivot(1, 110.0, PivotType.HIGH),
        _pivot(2, 95.0, PivotType.LOW),
        _pivot(3, 100.0, PivotType.HIGH),
        _pivot(4, 90.0, PivotType.LOW),
        _pivot(5, 98.0, PivotType.HIGH),
        _pivot(6, 92.0, PivotType.LOW),
        _pivot(7, 115.0, PivotType.HIGH),
    ])


def test_trend_health_defines_exactly_four_domain_states():
    assert [state.value for state in TrendHealthState] == [
        "HEALTHY",
        "WEAKENING",
        "BREAKING",
        "UNDEFINED",
    ]


def test_uptrend_without_warning_and_with_intact_hl_is_healthy():
    structure = _uptrend()

    result = evaluate_trend_health(structure, last_closed_close=105.0)

    assert structure.protected_level == 95.0
    assert structure.protected_pivot_index == 4
    assert result.state is TrendHealthState.HEALTHY


def test_downtrend_without_warning_and_with_intact_lh_is_healthy():
    structure = _downtrend()

    result = evaluate_trend_health(structure, last_closed_close=95.0)

    assert structure.protected_level == 100.0
    assert structure.protected_pivot_index == 3
    assert result.state is TrendHealthState.HEALTHY


def test_uptrend_with_bearish_divergence_and_intact_hl_is_weakening():
    result = evaluate_trend_health(
        _uptrend(),
        last_closed_close=100.0,
        divergence_direction=DivergenceDirection.BEARISH,
    )

    assert result.state is TrendHealthState.WEAKENING
    assert result.reason == "Bearish divergence, protected HL intact"


def test_downtrend_with_bullish_divergence_and_intact_lh_is_weakening():
    result = evaluate_trend_health(
        _downtrend(),
        last_closed_close=95.0,
        divergence_direction=DivergenceDirection.BULLISH,
    )

    assert result.state is TrendHealthState.WEAKENING
    assert result.reason == "Bullish divergence, protected LH intact"


def test_potential_distribution_is_weakening():
    result = evaluate_trend_health(
        _potential_distribution(),
        last_closed_close=100.0,
    )

    assert result.state is TrendHealthState.WEAKENING


def test_potential_accumulation_is_weakening():
    result = evaluate_trend_health(
        _potential_accumulation(),
        last_closed_close=95.0,
    )

    assert result.state is TrendHealthState.WEAKENING


def test_close_below_protected_hl_is_breaking():
    result = evaluate_trend_health(_uptrend(), last_closed_close=94.0)

    assert result.state is TrendHealthState.BREAKING
    assert result.reason == "Close below protected HL"


def test_low_below_hl_does_not_break_when_close_remains_above_hl():
    candle_low = 90.0
    result = evaluate_trend_health(_uptrend(), last_closed_close=96.0)

    assert candle_low < _uptrend().protected_level
    assert result.state is TrendHealthState.HEALTHY


def test_close_above_protected_lh_is_breaking():
    result = evaluate_trend_health(_downtrend(), last_closed_close=101.0)

    assert result.state is TrendHealthState.BREAKING
    assert result.reason == "Close above protected LH"


def test_high_above_lh_does_not_break_when_close_remains_below_lh():
    candle_high = 105.0
    result = evaluate_trend_health(_downtrend(), last_closed_close=99.0)

    assert candle_high > _downtrend().protected_level
    assert result.state is TrendHealthState.HEALTHY


def test_breaking_has_priority_over_divergence_warning():
    result = evaluate_trend_health(
        _uptrend(),
        last_closed_close=94.0,
        divergence_direction=DivergenceDirection.BEARISH,
    )

    assert result.state is TrendHealthState.BREAKING


@pytest.mark.parametrize(
    ("structure", "close"),
    [
        (_downtrend_confirmed(), 100.0),
        (_uptrend_confirmed(), 100.0),
    ],
)
def test_confirmed_transition_is_breaking(structure, close):
    assert structure.state in {
        MarketStructureState.DOWNTREND_CONFIRMED,
        MarketStructureState.UPTREND_CONFIRMED,
    }

    assert (
        evaluate_trend_health(structure, last_closed_close=close).state
        is TrendHealthState.BREAKING
    )


def test_undefined_market_structure_is_undefined_health():
    structure = evaluate_market_structure([])

    result = evaluate_trend_health(structure, last_closed_close=100.0)

    assert result.state is TrendHealthState.UNDEFINED


def test_missing_protected_level_is_undefined():
    structure = _uptrend()
    invalid = structure.__class__(
        **{
            **structure.__dict__,
            "protected_level": None,
            "protected_pivot_index": None,
        }
    )

    result = evaluate_trend_health(invalid, last_closed_close=100.0)

    assert result.state is TrendHealthState.UNDEFINED
    assert result.reason == "Protected level unavailable"


@pytest.mark.parametrize("close", [None, float("nan"), float("inf")])
def test_missing_or_invalid_closed_candle_is_not_healthy(close):
    result = evaluate_trend_health(_uptrend(), last_closed_close=close)

    assert result.state is TrendHealthState.UNDEFINED


def test_non_opposing_divergence_does_not_weaken_new_structure():
    result = evaluate_trend_health(
        _uptrend(),
        last_closed_close=100.0,
        divergence_direction=DivergenceDirection.BULLISH,
    )

    assert result.state is TrendHealthState.HEALTHY


@pytest.mark.parametrize("rsi_value", [20.0, 50.0, 80.0])
def test_rsi_value_alone_does_not_change_health(rsi_value):
    result = evaluate_trend_health(
        _uptrend(),
        last_closed_close=100.0,
        rsi_value=rsi_value,
    )

    assert result.state is TrendHealthState.HEALTHY


def test_quality_and_fvg_context_do_not_enter_health_evaluation():
    before = evaluate_trend_health(_uptrend(), last_closed_close=100.0)
    after = evaluate_trend_health(_uptrend(), last_closed_close=100.0)
    parameters = inspect.signature(evaluate_trend_health).parameters

    assert "quality" not in parameters
    assert "fvg" not in parameters
    assert before == after
