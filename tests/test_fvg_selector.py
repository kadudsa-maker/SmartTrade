import itertools

import pytest

from fvg import (
    Candle,
    EvaluatedFVG,
    FairValueGap,
    FVGDirection,
    FVGOpportunityStatus,
    FVGSelector,
)


def candle(price=100.0):
    return Candle(time=10, open=price, high=price, low=price, close=price)


def evaluated(
    status,
    *,
    lower=99.0,
    upper=101.0,
    distance=0.0,
    candle1_time=1,
    candle3_time=3,
    direction=FVGDirection.BULLISH,
):
    return EvaluatedFVG(
        gap=FairValueGap(
            direction=direction,
            candle1_time=candle1_time,
            candle3_time=candle3_time,
            lower_price=lower,
            upper_price=upper,
        ),
        status=status,
        distance_percent=distance,
    )


def test_selects_single_active():
    active = evaluated(FVGOpportunityStatus.ACTIVE)
    assert FVGSelector.select([active], candle()) is active


def test_selects_single_pending():
    pending = evaluated(FVGOpportunityStatus.PENDING, distance=0.2)
    assert FVGSelector.select([pending], candle()) is pending


def test_active_has_priority_over_pending():
    active = evaluated(FVGOpportunityStatus.ACTIVE)
    pending = evaluated(
        FVGOpportunityStatus.PENDING, distance=0.01, candle3_time=20
    )

    assert FVGSelector.select([pending, active], candle()) is active


def test_active_with_closest_midpoint_wins():
    farther = evaluated(
        FVGOpportunityStatus.ACTIVE, lower=90, upper=106
    )
    closer = evaluated(
        FVGOpportunityStatus.ACTIVE, lower=99, upper=103
    )

    assert FVGSelector.select([farther, closer], candle(100)) is closer


def test_active_midpoint_tie_uses_newest_candle3_time():
    older = evaluated(FVGOpportunityStatus.ACTIVE, candle3_time=10)
    newer = evaluated(FVGOpportunityStatus.ACTIVE, candle3_time=20)

    assert FVGSelector.select([newer, older], candle()) is newer


def test_pending_with_smallest_distance_wins():
    farther = evaluated(FVGOpportunityStatus.PENDING, distance=0.2)
    closer = evaluated(
        FVGOpportunityStatus.PENDING, distance=0.1, candle3_time=1
    )

    assert FVGSelector.select([farther, closer], candle()) is closer


def test_pending_distance_tie_uses_newest_candle3_time():
    older = evaluated(
        FVGOpportunityStatus.PENDING, distance=0.1, candle3_time=10
    )
    newer = evaluated(
        FVGOpportunityStatus.PENDING, distance=0.1, candle3_time=20
    )

    assert FVGSelector.select([newer, older], candle()) is newer


def test_only_none_returns_none():
    none_gap = evaluated(FVGOpportunityStatus.NONE, distance=10)
    assert FVGSelector.select([none_gap], candle()) is None


def test_empty_list_returns_none():
    assert FVGSelector.select([], candle()) is None


@pytest.mark.parametrize(
    "items",
    list(
        itertools.permutations(
            [
                evaluated(
                    FVGOpportunityStatus.ACTIVE,
                    lower=90,
                    upper=110,
                    candle3_time=5,
                ),
                evaluated(
                    FVGOpportunityStatus.ACTIVE,
                    lower=95,
                    upper=105,
                    candle3_time=6,
                ),
                evaluated(
                    FVGOpportunityStatus.PENDING,
                    distance=0.01,
                    candle3_time=20,
                ),
            ]
        )
    ),
)
def test_input_order_does_not_change_selection(items):
    selected = FVGSelector.select(items, candle(100))
    assert selected.gap.candle3_time == 6


def test_selector_does_not_mutate_input_or_statuses():
    items = [
        evaluated(FVGOpportunityStatus.PENDING, distance=0.2),
        evaluated(FVGOpportunityStatus.ACTIVE, candle3_time=4),
    ]
    snapshot = list(items)
    statuses = [item.status for item in items]

    FVGSelector.select(items, candle())

    assert items == snapshot
    assert [item.status for item in items] == statuses


def test_final_geometric_tie_breaker_is_order_independent():
    wider = evaluated(
        FVGOpportunityStatus.ACTIVE,
        lower=90,
        upper=110,
        candle1_time=1,
        candle3_time=10,
    )
    narrower = evaluated(
        FVGOpportunityStatus.ACTIVE,
        lower=95,
        upper=105,
        candle1_time=1,
        candle3_time=10,
    )

    assert FVGSelector.select([narrower, wider], candle()) is wider
    assert FVGSelector.select([wider, narrower], candle()) is wider


def test_final_time_tie_breaker_prefers_newer_candle1_time():
    older = evaluated(
        FVGOpportunityStatus.ACTIVE,
        candle1_time=1,
        candle3_time=10,
    )
    newer = evaluated(
        FVGOpportunityStatus.ACTIVE,
        candle1_time=2,
        candle3_time=10,
    )

    assert FVGSelector.select([older, newer], candle()) is newer
