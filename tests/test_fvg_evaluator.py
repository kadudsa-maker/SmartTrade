import math

import pytest

from fvg import (
    Candle,
    EvaluatedFVG,
    FairValueGap,
    FVGDirection,
    FVGEvaluator,
    FVGOpportunityStatus,
)


def candle(time, price):
    return Candle(
        time=time,
        open=price,
        high=price,
        low=price,
        close=price,
    )


def gap(
    lower=100.0,
    upper=110.0,
    *,
    direction=FVGDirection.BULLISH,
    candle1_time=1,
    candle3_time=3,
):
    return FairValueGap(
        direction=direction,
        candle1_time=candle1_time,
        candle3_time=candle3_time,
        lower_price=lower,
        upper_price=upper,
    )


@pytest.mark.parametrize(
    "direction",
    [FVGDirection.BULLISH, FVGDirection.BEARISH],
)
def test_price_inside_gap_is_active(direction):
    evaluated = FVGEvaluator.evaluate(
        [gap(direction=direction)], candle(2, 105), candle(1, 99)
    )

    assert evaluated[0].status is FVGOpportunityStatus.ACTIVE
    assert evaluated[0].distance_percent == 0.0


@pytest.mark.parametrize("price", [100.0, 110.0])
def test_price_on_either_boundary_is_active(price):
    evaluated = FVGEvaluator.evaluate(
        [gap()], candle(2, price), candle(1, 99)
    )

    assert evaluated[0].status is FVGOpportunityStatus.ACTIVE
    assert evaluated[0].distance_percent == 0.0


def test_near_and_approaching_from_below_is_pending():
    evaluated = FVGEvaluator.evaluate(
        [gap()], candle(2, 99.8), candle(1, 99.0)
    )

    assert evaluated[0].status is FVGOpportunityStatus.PENDING


def test_near_and_approaching_from_above_is_pending():
    evaluated = FVGEvaluator.evaluate(
        [gap()], candle(2, 110.2), candle(1, 111.0)
    )

    assert evaluated[0].status is FVGOpportunityStatus.PENDING


def test_near_but_moving_away_is_none():
    evaluated = FVGEvaluator.evaluate(
        [gap()], candle(2, 99.7), candle(1, 99.8)
    )

    assert evaluated[0].status is FVGOpportunityStatus.NONE


def test_near_with_equal_distance_is_none():
    evaluated = FVGEvaluator.evaluate(
        [gap()], candle(2, 99.8), candle(1, 99.8)
    )

    assert evaluated[0].status is FVGOpportunityStatus.NONE


def test_approaching_but_outside_threshold_is_none():
    evaluated = FVGEvaluator.evaluate(
        [gap()], candle(2, 99.5), candle(1, 99.0)
    )

    assert evaluated[0].status is FVGOpportunityStatus.NONE


def test_exact_pending_threshold_is_inclusive():
    current_price = 100.0 / 1.003
    exact_threshold = (100.0 - current_price) / current_price * 100.0

    evaluated = FVGEvaluator.evaluate(
        [gap()],
        candle(2, current_price),
        candle(1, 99.0),
        pending_distance_percent=exact_threshold,
    )

    assert evaluated[0].status is FVGOpportunityStatus.PENDING
    assert evaluated[0].distance_percent == exact_threshold


def test_distant_gap_remains_in_result_as_none():
    source_gap = gap(200, 210)

    evaluated = FVGEvaluator.evaluate(
        [source_gap], candle(2, 100), candle(1, 90)
    )

    assert evaluated == [
        EvaluatedFVG(
            gap=source_gap,
            status=FVGOpportunityStatus.NONE,
            distance_percent=100.0,
        )
    ]


def test_mixed_gaps_receive_independent_statuses():
    active = gap(100, 110, candle3_time=3)
    pending = gap(105.2, 106, candle3_time=4)
    distant = gap(200, 210, candle3_time=5)

    evaluated = FVGEvaluator.evaluate(
        [active, pending, distant], candle(2, 105), candle(1, 104)
    )

    assert [item.status for item in evaluated] == [
        FVGOpportunityStatus.ACTIVE,
        FVGOpportunityStatus.PENDING,
        FVGOpportunityStatus.NONE,
    ]


def test_empty_gap_list_returns_empty_result():
    assert FVGEvaluator.evaluate([], candle(2, 100), candle(1, 99)) == []


def test_evaluator_does_not_mutate_input():
    gaps = [gap(), gap(200, 210, candle3_time=4)]
    snapshot = list(gaps)

    FVGEvaluator.evaluate(gaps, candle(2, 105), candle(1, 99))

    assert gaps == snapshot


@pytest.mark.parametrize("invalid_price", [0.0, -1.0, math.nan, math.inf, -math.inf])
def test_rejects_invalid_current_price(invalid_price):
    with pytest.raises(ValueError, match="current.*positive and finite"):
        FVGEvaluator.evaluate(
            [gap()], candle(2, invalid_price), candle(1, 99)
        )


@pytest.mark.parametrize("invalid_price", [0.0, -1.0, math.nan, math.inf, -math.inf])
def test_rejects_invalid_previous_price(invalid_price):
    with pytest.raises(ValueError, match="previous.*positive and finite"):
        FVGEvaluator.evaluate(
            [gap()], candle(2, 99.8), candle(1, invalid_price)
        )


@pytest.mark.parametrize("invalid_threshold", [-0.01, math.nan, math.inf, -math.inf])
def test_rejects_invalid_pending_threshold(invalid_threshold):
    with pytest.raises(ValueError, match="non-negative and finite"):
        FVGEvaluator.evaluate(
            [gap()],
            candle(2, 99.8),
            candle(1, 99),
            pending_distance_percent=invalid_threshold,
        )


@pytest.mark.parametrize(
    "lower, upper",
    [
        (100.0, 100.0),
        (101.0, 100.0),
        (math.nan, 100.0),
        (100.0, math.inf),
    ],
)
def test_rejects_invalid_gap_boundaries(lower, upper):
    with pytest.raises(ValueError, match="boundaries|lower price"):
        FVGEvaluator.evaluate(
            [gap(lower, upper)], candle(2, 99.8), candle(1, 99)
        )
