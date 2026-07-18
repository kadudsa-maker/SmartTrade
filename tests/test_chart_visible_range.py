import pandas as pd

from chart import (
    DEFAULT_VISIBLE_CANDLES,
    FVG_LEFT_MARGIN_CANDLES,
    MAX_VISIBLE_CANDLES,
    SmartTradeChart,
)
from fvg import (
    EvaluatedFVG,
    FairValueGap,
    FVGDirection,
    FVGOpportunityStatus,
)


def evaluated(candle1_time, status=FVGOpportunityStatus.ACTIVE):
    return EvaluatedFVG(
        gap=FairValueGap(
            direction=FVGDirection.BULLISH,
            candle1_time=candle1_time,
            candle3_time=candle1_time + 2,
            lower_price=100,
            upper_price=101,
        ),
        status=status,
        distance_percent=0 if status is FVGOpportunityStatus.ACTIVE else 0.2,
    )


def chart_with_history(count, gaps=()):
    chart = SmartTradeChart.__new__(SmartTradeChart)
    chart.candles = pd.DataFrame(
        {
            "time": list(range(count)),
            "open": [100.0] * count,
            "high": [101.0] * count,
            "low": [99.0] * count,
            "close": [100.5] * count,
        }
    )
    chart.rsi_series = pd.Series([50.0] * count)
    chart.fvg_gaps = tuple(gaps)
    return chart


def test_default_visible_range_is_thirty_percent_larger_than_before():
    assert DEFAULT_VISIBLE_CANDLES == 104
    assert DEFAULT_VISIBLE_CANDLES > 80


def test_no_fvg_uses_the_new_default_window():
    chart = chart_with_history(150)
    candles, rsi = chart._visible_candle_window()
    assert len(candles) == DEFAULT_VISIBLE_CANDLES
    assert len(rsi) == DEFAULT_VISIBLE_CANDLES
    assert candles.iloc[0]["time"] == 46
    assert candles.iloc[-1]["time"] == 149


def test_one_fvg_includes_candle1_and_left_margin():
    chart = chart_with_history(150, [evaluated(50)])
    candles, _rsi = chart._visible_candle_window()
    assert candles.iloc[0]["time"] == 50 - FVG_LEFT_MARGIN_CANDLES
    assert 50 in set(candles["time"])


def test_multiple_fvg_gaps_use_the_oldest_candle1():
    chart = chart_with_history(150, [evaluated(80), evaluated(30)])
    candles, _rsi = chart._visible_candle_window()
    assert candles.iloc[0]["time"] == 30 - FVG_LEFT_MARGIN_CANDLES
    assert {30, 80}.issubset(set(candles["time"]))


def test_very_old_fvg_is_clamped_to_maximum_window():
    chart = chart_with_history(300, [evaluated(10)])
    candles, rsi = chart._visible_candle_window()
    assert len(candles) == MAX_VISIBLE_CANDLES == 200
    assert len(rsi) == MAX_VISIBLE_CANDLES
    assert candles.iloc[0]["time"] == 100


def test_overlay_candle1_maps_to_the_same_visible_candle_position():
    gap = evaluated(50)
    chart = chart_with_history(150, [gap])
    visible_candles, _rsi = chart._visible_candle_window()
    captured = {}

    class Overlay:
        def draw_canvas_rectangles(self, _canvas, _gaps, **options):
            captured["candle1_x"] = options["time_to_x"](gap.gap.candle1_time)
            captured["right_edge"] = options["right_edge"]

    chart.fvg_overlay = Overlay()
    chart.canvas = object()
    chart._draw_fvg_zones(
        visible_candles,
        high=101,
        low=99,
        step=2,
        padding=10,
        width=500,
        price_top=20,
        price_bottom=300,
        price_height=280,
    )
    assert captured["candle1_x"] == 27
    assert captured["right_edge"] == 149


def test_window_selection_does_not_mutate_candles_or_fvg_results():
    gaps = (
        evaluated(30, FVGOpportunityStatus.ACTIVE),
        evaluated(80, FVGOpportunityStatus.PENDING),
    )
    chart = chart_with_history(150, gaps)
    original_candles = chart.candles.copy(deep=True)
    original_statuses = tuple(item.status for item in chart.fvg_gaps)
    chart._visible_candle_window()
    pd.testing.assert_frame_equal(chart.candles, original_candles)
    assert chart.fvg_gaps == gaps
    assert tuple(item.status for item in chart.fvg_gaps) == original_statuses
