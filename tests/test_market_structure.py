from dataclasses import FrozenInstanceError

import pytest

from market_structure import (
    DivergenceDirection,
    MarketStructureState,
    PivotType,
    PricePivot,
    SemanticColor,
    Strength,
    evaluate_market_structure,
)


def _p(index, price, kind):
    return PricePivot(index=index, price=price, type=kind)


def _uptrend():
    return [
        _p(1, 100, PivotType.HIGH),
        _p(2, 90, PivotType.LOW),
        _p(3, 110, PivotType.HIGH),
        _p(4, 95, PivotType.LOW),
    ]


def _downtrend():
    return [
        _p(1, 110, PivotType.HIGH),
        _p(2, 95, PivotType.LOW),
        _p(3, 100, PivotType.HIGH),
        _p(4, 90, PivotType.LOW),
    ]


def test_market_structure_state_contains_all_expected_values():
    assert [state.value for state in MarketStructureState] == [
        "UPTREND",
        "POTENTIAL_DISTRIBUTION",
        "DOWNTREND_CONFIRMED",
        "DOWNTREND",
        "POTENTIAL_ACCUMULATION",
        "UPTREND_CONFIRMED",
        "UNDEFINED",
    ]


def test_too_few_pivots_returns_undefined():
    result = evaluate_market_structure(_uptrend()[:3])
    assert result.state is MarketStructureState.UNDEFINED


def test_mixed_structure_returns_undefined():
    pivots = _uptrend() + [_p(5, 105, PivotType.HIGH)]
    result = evaluate_market_structure(pivots)
    assert result.state is MarketStructureState.UNDEFINED


def test_higher_high_and_higher_low_returns_uptrend():
    result = evaluate_market_structure(_uptrend())
    assert result.state is MarketStructureState.UPTREND


def test_lower_high_and_lower_low_returns_downtrend():
    result = evaluate_market_structure(_downtrend())
    assert result.state is MarketStructureState.DOWNTREND


def test_high_rsi_without_divergence_does_not_create_distribution():
    result = evaluate_market_structure(_uptrend(), rsi_value=85)
    assert result.state is MarketStructureState.UPTREND
    assert result.rsi_value == 85


def test_low_rsi_without_divergence_does_not_create_accumulation():
    result = evaluate_market_structure(_downtrend(), rsi_value=15)
    assert result.state is MarketStructureState.DOWNTREND
    assert result.rsi_value == 15


def test_uptrend_with_bearish_divergence_and_lower_high_returns_distribution():
    pivots = _uptrend() + [_p(5, 105, PivotType.HIGH)]
    result = evaluate_market_structure(
        pivots,
        divergence_direction=DivergenceDirection.BEARISH,
    )
    assert result.state is MarketStructureState.POTENTIAL_DISTRIBUTION
    assert result.strength is Strength.MEDIUM


def test_downtrend_with_bullish_divergence_and_higher_low_returns_accumulation():
    pivots = _downtrend() + [
        _p(5, 98, PivotType.HIGH),
        _p(6, 92, PivotType.LOW),
    ]
    result = evaluate_market_structure(
        pivots,
        divergence_direction=DivergenceDirection.BULLISH,
    )
    assert result.state is MarketStructureState.POTENTIAL_ACCUMULATION


def test_single_lower_high_does_not_confirm_downtrend():
    pivots = _uptrend() + [_p(5, 105, PivotType.HIGH)]
    result = evaluate_market_structure(pivots)
    assert result.state is MarketStructureState.UNDEFINED


def test_single_higher_low_does_not_confirm_uptrend():
    pivots = _downtrend() + [
        _p(5, 98, PivotType.HIGH),
        _p(6, 92, PivotType.LOW),
    ]
    result = evaluate_market_structure(pivots)
    assert result.state is MarketStructureState.UNDEFINED


def test_break_of_higher_low_with_new_lower_structure_confirms_downtrend():
    pivots = _uptrend() + [
        _p(5, 105, PivotType.HIGH),
        _p(6, 85, PivotType.LOW),
    ]
    result = evaluate_market_structure(pivots)
    assert result.state is MarketStructureState.DOWNTREND_CONFIRMED


def test_break_of_lower_high_with_new_higher_structure_confirms_uptrend():
    pivots = _downtrend() + [
        _p(5, 98, PivotType.HIGH),
        _p(6, 92, PivotType.LOW),
        _p(7, 115, PivotType.HIGH),
    ]
    result = evaluate_market_structure(pivots)
    assert result.state is MarketStructureState.UPTREND_CONFIRMED


def test_missing_divergence_is_supported():
    result = evaluate_market_structure(_uptrend(), divergence_direction=None)
    assert result.divergence_direction is None


def test_missing_rsi_is_supported():
    result = evaluate_market_structure(_uptrend(), rsi_value=None)
    assert result.rsi_value is None


def test_input_pivot_list_is_not_modified():
    pivots = _uptrend()
    snapshot = list(pivots)
    evaluate_market_structure(pivots)
    assert pivots == snapshot


def test_identical_input_is_deterministic():
    pivots = _uptrend()
    first = evaluate_market_structure(pivots, rsi_value=55)
    second = evaluate_market_structure(pivots, rsi_value=55)
    assert first == second


def test_module_import_has_no_runtime_side_effects(capsys):
    import importlib
    import market_structure

    importlib.reload(market_structure)

    assert callable(market_structure.evaluate_market_structure)
    assert capsys.readouterr() == ("", "")


def test_result_and_pivot_models_are_immutable():
    pivot = _uptrend()[0]
    result = evaluate_market_structure(_uptrend())

    with pytest.raises(FrozenInstanceError):
        pivot.price = 999
    with pytest.raises(FrozenInstanceError):
        result.reason = "changed"


def test_rsi_does_not_change_strength():
    pivots = _uptrend() + [_p(5, 105, PivotType.HIGH)]
    without_rsi = evaluate_market_structure(
        pivots,
        divergence_direction=DivergenceDirection.BEARISH,
    )
    with_rsi = evaluate_market_structure(
        pivots,
        divergence_direction=DivergenceDirection.BEARISH,
        rsi_value=75,
    )
    assert with_rsi.state is MarketStructureState.POTENTIAL_DISTRIBUTION
    assert with_rsi.strength is without_rsi.strength is Strength.MEDIUM


def test_states_expose_semantic_colors_without_gui_values():
    assert evaluate_market_structure(_uptrend()).color_key is SemanticColor.POSITIVE
    assert evaluate_market_structure([]).color_key is SemanticColor.NEUTRAL


def test_high_and_low_on_same_candle_are_valid_distinct_pivots():
    pivots = [
        _p(1, 100, PivotType.HIGH),
        _p(2, 90, PivotType.LOW),
        _p(3, 110, PivotType.HIGH),
        _p(3, 95, PivotType.LOW),
    ]
    assert evaluate_market_structure(pivots).state is MarketStructureState.UPTREND
