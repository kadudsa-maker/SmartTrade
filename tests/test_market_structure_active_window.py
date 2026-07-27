from market_structure import (
    MARKET_STRUCTURE_PIVOT_WINDOW,
    MarketStructureState,
    PivotType,
    PricePivot,
    evaluate_market_structure,
    get_market_structure_pivot_window,
    normalize_price_pivots,
)


def _pivot(index, price, pivot_type):
    return PricePivot(index=index, price=price, type=pivot_type)


def _old_downtrend_confirmed():
    return [
        _pivot(1, 100.0, PivotType.HIGH),
        _pivot(2, 90.0, PivotType.LOW),
        _pivot(3, 110.0, PivotType.HIGH),
        _pivot(4, 95.0, PivotType.LOW),
        _pivot(5, 105.0, PivotType.HIGH),
        _pivot(6, 85.0, PivotType.LOW),
    ]


def _old_uptrend_confirmed():
    return [
        _pivot(1, 110.0, PivotType.HIGH),
        _pivot(2, 95.0, PivotType.LOW),
        _pivot(3, 100.0, PivotType.HIGH),
        _pivot(4, 90.0, PivotType.LOW),
        _pivot(5, 98.0, PivotType.HIGH),
        _pivot(6, 92.0, PivotType.LOW),
        _pivot(7, 115.0, PivotType.HIGH),
    ]


def _rising_sequence(start_index=100, count=16):
    pivots = []
    high_number = 0
    low_number = 0
    for offset in range(count):
        index = start_index + offset
        if offset % 2 == 0:
            pivots.append(
                _pivot(index, 120.0 + high_number * 5.0, PivotType.HIGH)
            )
            high_number += 1
        else:
            pivots.append(
                _pivot(index, 100.0 + low_number * 5.0, PivotType.LOW)
            )
            low_number += 1
    return pivots


def test_old_downtrend_confirmation_does_not_override_later_complete_uptrend():
    pivots = _old_downtrend_confirmed() + [
        _pivot(7, 115.0, PivotType.HIGH),
        _pivot(8, 92.0, PivotType.LOW),
        _pivot(9, 120.0, PivotType.HIGH),
        _pivot(10, 98.0, PivotType.LOW),
    ]

    assert evaluate_market_structure(pivots).state is MarketStructureState.UPTREND


def test_old_uptrend_confirmation_does_not_override_later_complete_downtrend():
    pivots = _old_uptrend_confirmed() + [
        _pivot(8, 85.0, PivotType.LOW),
        _pivot(9, 90.0, PivotType.HIGH),
        _pivot(10, 80.0, PivotType.LOW),
        _pivot(11, 85.0, PivotType.HIGH),
        _pivot(12, 75.0, PivotType.LOW),
    ]

    assert evaluate_market_structure(pivots).state is MarketStructureState.DOWNTREND


def test_normalization_uses_latest_sixteen_pivots_not_the_whole_history():
    result = normalize_price_pivots(_rising_sequence(count=24))

    assert len(result) == MARKET_STRUCTURE_PIVOT_WINDOW
    assert [pivot.index for pivot in result] == list(range(108, 124))


def test_older_break_outside_active_window_is_irrelevant():
    pivots = _old_downtrend_confirmed() + _rising_sequence()

    assert evaluate_market_structure(pivots).state is MarketStructureState.UPTREND


def test_fewer_than_sixteen_pivots_are_kept_without_exception():
    pivots = _rising_sequence(count=6)

    assert normalize_price_pivots(pivots) == pivots


def test_window_is_taken_from_the_end_not_the_beginning():
    result = normalize_price_pivots(_rising_sequence(start_index=1, count=20))

    assert result[0].index == 5
    assert result[-1].index == 20


def test_consecutive_highs_keep_only_the_more_extreme_high():
    pivots = [
        _pivot(1, 100.0, PivotType.HIGH),
        _pivot(2, 110.0, PivotType.HIGH),
        _pivot(3, 90.0, PivotType.LOW),
    ]

    assert normalize_price_pivots(pivots) == [pivots[1], pivots[2]]


def test_consecutive_lows_keep_only_the_more_extreme_low():
    pivots = [
        _pivot(1, 90.0, PivotType.LOW),
        _pivot(2, 80.0, PivotType.LOW),
        _pivot(3, 110.0, PivotType.HIGH),
    ]

    assert normalize_price_pivots(pivots) == [pivots[1], pivots[2]]


def test_normalization_orders_pivots_chronologically():
    pivots = [
        _pivot(5, 120.0, PivotType.HIGH),
        _pivot(2, 90.0, PivotType.LOW),
        _pivot(3, 110.0, PivotType.HIGH),
        _pivot(4, 95.0, PivotType.LOW),
    ]

    assert [p.index for p in normalize_price_pivots(pivots)] == [2, 3, 4, 5]


def test_duplicate_pivots_keep_the_more_extreme_value():
    pivots = [
        _pivot(1, 100.0, PivotType.HIGH),
        _pivot(1, 110.0, PivotType.HIGH),
        _pivot(2, 90.0, PivotType.LOW),
        _pivot(2, 95.0, PivotType.LOW),
    ]

    result = normalize_price_pivots(pivots)
    assert [(p.index, p.price) for p in result] == [(1, 110.0), (2, 90.0)]


def test_invalid_indexes_and_non_finite_prices_are_removed():
    valid_high = _pivot(1, 110.0, PivotType.HIGH)
    valid_low = _pivot(2, 90.0, PivotType.LOW)
    pivots = [
        _pivot(-1, 120.0, PivotType.HIGH),
        _pivot("bad", 80.0, PivotType.LOW),
        _pivot(3, float("nan"), PivotType.HIGH),
        valid_high,
        valid_low,
    ]

    assert normalize_price_pivots(pivots) == [valid_high, valid_low]


def test_current_higher_highs_and_higher_lows_return_uptrend():
    result = evaluate_market_structure(_rising_sequence(count=6))

    assert result.state is MarketStructureState.UPTREND


def test_current_lower_highs_and_lower_lows_return_downtrend():
    pivots = [
        _pivot(1, 120.0, PivotType.HIGH),
        _pivot(2, 100.0, PivotType.LOW),
        _pivot(3, 115.0, PivotType.HIGH),
        _pivot(4, 95.0, PivotType.LOW),
        _pivot(5, 110.0, PivotType.HIGH),
        _pivot(6, 90.0, PivotType.LOW),
    ]

    assert evaluate_market_structure(pivots).state is MarketStructureState.DOWNTREND


def test_current_higher_low_then_lower_low_break_returns_downtrend_confirmed():
    result = evaluate_market_structure(_old_downtrend_confirmed())

    assert result.state is MarketStructureState.DOWNTREND_CONFIRMED


def test_current_lower_high_then_higher_high_break_returns_uptrend_confirmed():
    result = evaluate_market_structure(_old_uptrend_confirmed())

    assert result.state is MarketStructureState.UPTREND_CONFIRMED


def test_lone_lower_high_does_not_confirm_downtrend():
    pivots = [
        _pivot(1, 100.0, PivotType.HIGH),
        _pivot(2, 90.0, PivotType.LOW),
        _pivot(3, 95.0, PivotType.HIGH),
        _pivot(4, 92.0, PivotType.LOW),
    ]

    assert (
        evaluate_market_structure(pivots).state
        is not MarketStructureState.DOWNTREND_CONFIRMED
    )


def test_lone_higher_low_does_not_confirm_uptrend():
    pivots = [
        _pivot(1, 100.0, PivotType.HIGH),
        _pivot(2, 90.0, PivotType.LOW),
        _pivot(3, 95.0, PivotType.HIGH),
        _pivot(4, 92.0, PivotType.LOW),
    ]

    assert (
        evaluate_market_structure(pivots).state
        is not MarketStructureState.UPTREND_CONFIRMED
    )


def test_mixed_recent_sequence_is_undefined():
    pivots = _old_downtrend_confirmed() + [
        _pivot(7, 120.0, PivotType.HIGH),
        _pivot(8, 80.0, PivotType.LOW),
    ]

    assert evaluate_market_structure(pivots).state is MarketStructureState.UNDEFINED


def test_rsi_does_not_change_active_structure_result():
    pivots = _rising_sequence(count=6)
    low_rsi = evaluate_market_structure(pivots, rsi_value=10.0)
    high_rsi = evaluate_market_structure(pivots, rsi_value=90.0)

    assert low_rsi.state is high_rsi.state
    assert low_rsi.strength is high_rsi.strength
    assert low_rsi.reason == high_rsi.reason


def test_window_configuration_is_centralized_and_same_for_all_timeframes():
    assert MARKET_STRUCTURE_PIVOT_WINDOW == 16
    assert get_market_structure_pivot_window("1") == 16
    assert get_market_structure_pivot_window("D") == 16
