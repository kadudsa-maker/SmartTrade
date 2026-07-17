import math

import pytest

from fvg import Candle, FairValueGap, FVGDetector, FVGDirection


def candle(time, low, high, *, open_price=None, close=None):
    open_price = (low + high) / 2 if open_price is None else open_price
    close = open_price if close is None else close
    return Candle(
        time=time,
        open=open_price,
        high=high,
        low=low,
        close=close,
    )


def test_detects_single_bullish_fvg():
    candles = (
        candle(1, 10, 12),
        candle(2, 11, 14),
        candle(3, 13, 15),
    )

    assert FVGDetector.detect(candles) == [
        FairValueGap(
            direction=FVGDirection.BULLISH,
            candle1_time=1,
            candle3_time=3,
            lower_price=12,
            upper_price=13,
        )
    ]


def test_detects_single_bearish_fvg():
    candles = (
        candle(1, 13, 15),
        candle(2, 11, 14),
        candle(3, 9, 12),
    )

    assert FVGDetector.detect(candles) == [
        FairValueGap(
            direction=FVGDirection.BEARISH,
            candle1_time=1,
            candle3_time=3,
            lower_price=12,
            upper_price=13,
        )
    ]


def test_returns_no_fvg_for_overlapping_candles():
    candles = (
        candle(1, 10, 14),
        candle(2, 11, 15),
        candle(3, 12, 16),
    )

    assert FVGDetector.detect(candles) == []


def test_detects_multiple_current_fvgs_in_chronological_order():
    candles = tuple(candle(index, index * 2, index * 2 + 1) for index in range(1, 7))

    gaps = FVGDetector.detect(candles)

    assert len(gaps) == 4
    assert all(gap.direction is FVGDirection.BULLISH for gap in gaps)
    assert [gap.candle3_time for gap in gaps] == [3, 4, 5, 6]


@pytest.mark.parametrize(
    "candles",
    [
        (
            candle(1, 10, 12),
            candle(2, 10, 13),
            candle(3, 12, 14),
        ),
        (
            candle(1, 12, 14),
            candle(2, 11, 14),
            candle(3, 10, 12),
        ),
    ],
)
def test_equal_boundaries_do_not_create_fvg(candles):
    assert FVGDetector.detect(candles) == []


def test_later_candle_fills_bullish_fvg_at_lower_boundary():
    candles = (
        candle(1, 10, 12),
        candle(2, 11, 13),
        candle(3, 13, 15),
        candle(4, 12, 14),
    )

    assert FVGDetector.detect(candles) == []


def test_partial_bullish_fill_keeps_fvg_current():
    candles = (
        candle(1, 10, 12),
        candle(2, 11, 13),
        candle(3, 13, 15),
        candle(4, 12.5, 14),
    )

    assert FVGDetector.detect(candles)[0].lower_price == 12


def test_later_candle_fills_bearish_fvg_at_upper_boundary():
    candles = (
        candle(1, 13, 15),
        candle(2, 12, 14),
        candle(3, 9, 12),
        candle(4, 10, 13),
    )

    assert FVGDetector.detect(candles) == []


def test_partial_bearish_fill_keeps_fvg_current():
    candles = (
        candle(1, 13, 15),
        candle(2, 12, 14),
        candle(3, 9, 12),
        candle(4, 10, 12.5),
    )

    assert FVGDetector.detect(candles)[0].upper_price == 13


def test_rejects_unordered_times():
    candles = (
        candle(1, 10, 11),
        candle(3, 11, 12),
        candle(2, 12, 13),
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        FVGDetector.detect(candles)


def test_rejects_duplicate_times():
    candles = (
        candle(1, 10, 11),
        candle(2, 11, 12),
        candle(2, 12, 13),
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        FVGDetector.detect(candles)


@pytest.mark.parametrize(
    "invalid_candle",
    [
        Candle(time=2, open=10, high=9, low=11, close=10),
        Candle(time=2, open=12, high=11, low=10, close=10.5),
        Candle(time=2, open=10.5, high=11, low=10, close=12),
    ],
)
def test_rejects_invalid_ohlc(invalid_candle):
    candles = (candle(1, 10, 11), invalid_candle, candle(3, 12, 13))

    with pytest.raises(ValueError):
        FVGDetector.detect(candles)


@pytest.mark.parametrize("count", [0, 1, 2])
def test_rejects_fewer_than_three_candles(count):
    candles = tuple(candle(index, 10, 11) for index in range(count))

    with pytest.raises(ValueError, match="at least three"):
        FVGDetector.detect(candles)


@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf])
def test_rejects_non_finite_prices(invalid_value):
    candles = (
        candle(1, 10, 11),
        Candle(time=2, open=10, high=11, low=invalid_value, close=10),
        candle(3, 12, 13),
    )

    with pytest.raises(ValueError, match="non-finite"):
        FVGDetector.detect(candles)


def test_handles_very_long_history_without_losing_current_gaps():
    candles = tuple(
        candle(index, index * 2.0, index * 2.0 + 1.0)
        for index in range(1, 20_001)
    )

    gaps = FVGDetector.detect(candles)

    assert len(gaps) == len(candles) - 2
    assert gaps[0].candle3_time == 3
    assert gaps[-1].candle3_time == 20_000


def test_many_fvgs_keep_exact_boundaries_without_regression():
    candles = tuple(
        candle(index, index * 3.0, index * 3.0 + 1.0)
        for index in range(1, 101)
    )

    gaps = FVGDetector.detect(candles)

    for candle3_index, gap in enumerate(gaps, start=2):
        assert gap.lower_price == candles[candle3_index - 2].high
        assert gap.upper_price == candles[candle3_index].low
        assert gap.candle1_time == candles[candle3_index - 2].time
        assert gap.candle3_time == candles[candle3_index].time
