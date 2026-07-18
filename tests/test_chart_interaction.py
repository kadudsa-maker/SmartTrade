from types import SimpleNamespace

import pandas as pd
import pytest

import chart as chart_module
from chart import (
    MIN_MANUAL_VISIBLE_CANDLES,
    VIEW_MODE_AUTO,
    VIEW_MODE_MANUAL,
    SmartTradeChart,
)
from fvg import (
    EvaluatedFVG,
    FairValueGap,
    FVGDirection,
    FVGOpportunityStatus,
)


class FakeCanvas:
    def __init__(self, *_args, **_kwargs):
        self.bindings = {}
        self.width = 1000

    def pack(self, **_kwargs):
        pass

    def bind(self, event, callback):
        self.bindings[event] = callback

    def winfo_width(self):
        return self.width


class FakeFrame:
    def __init__(self, *_args, **_kwargs):
        pass


def evaluated(candle1_time=50):
    return EvaluatedFVG(
        gap=FairValueGap(
            direction=FVGDirection.BULLISH,
            candle1_time=candle1_time,
            candle3_time=candle1_time + 2,
            lower_price=100,
            upper_price=101,
        ),
        status=FVGOpportunityStatus.ACTIVE,
        distance_percent=0,
    )


def frame(count=150, *, symbol="BTCUSDT", timeframe="60"):
    value = pd.DataFrame(
        {
            "time": [index * 1000 for index in range(count)],
            "open": [100.0] * count,
            "high": [101.0] * count,
            "low": [99.0] * count,
            "close": [100.5] * count,
            "volume": [1.0] * count,
        }
    )
    value.attrs.update(
        exchange_id="bybit",
        symbol=symbol,
        timeframe=timeframe,
    )
    return value


def view_chart(count=150, gaps=()):
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
    chart.view_mode = VIEW_MODE_AUTO
    chart._manual_view_start = None
    chart._manual_view_end = None
    chart._drag_start_x = None
    chart._drag_start_bounds = None
    return chart


def configure_lightweight_refresh(chart, monkeypatch):
    chart._last_source_key = None
    chart._view_context = ("bybit", "BTCUSDT", "60")
    chart.fvg_overlay = SimpleNamespace(zone_key=lambda item: str(item.gap.candle1_time))
    chart._calculate_rsi = lambda close: pd.Series([50.0] * len(close))
    chart._update_figure = lambda: None
    chart._draw = lambda *_args: None
    monkeypatch.setattr(chart_module, "find_pivots", lambda *_args, **_kwargs: ([], []))
    monkeypatch.setattr(chart_module, "find_rsi_pivots", lambda *_args, **_kwargs: ([], []))
    monkeypatch.setattr(chart_module, "find_regular_divergences", lambda *_args: [])


def test_new_chart_starts_in_auto_and_binds_native_canvas_events(monkeypatch):
    monkeypatch.setattr(chart_module.ctk, "CTkFrame", FakeFrame)
    monkeypatch.setattr(chart_module.tk, "Canvas", FakeCanvas)
    chart = SmartTradeChart(object())
    assert chart.view_mode == VIEW_MODE_AUTO
    assert {
        "<MouseWheel>",
        "<ButtonPress-1>",
        "<B1-Motion>",
        "<ButtonRelease-1>",
        "<Double-Button-1>",
    }.issubset(chart.canvas.bindings)


def test_zoom_changes_visible_candle_count_and_enters_manual_mode():
    chart = view_chart()
    before = chart._visible_candle_bounds()
    assert chart.zoom_view(zoom_in=True, anchor_fraction=0.5)
    after = chart._visible_candle_bounds()
    assert after[1] - after[0] < before[1] - before[0]
    assert chart.view_mode == VIEW_MODE_MANUAL


def test_zoom_in_stops_at_minimum_visible_count():
    chart = view_chart()
    for _index in range(30):
        chart.zoom_view(zoom_in=True)
    start, end = chart._visible_candle_bounds()
    assert end - start == MIN_MANUAL_VISIBLE_CANDLES == 24


def test_zoom_out_stops_at_available_candle_count():
    chart = view_chart(150)
    for _index in range(30):
        chart.zoom_view(zoom_in=False)
    assert chart._visible_candle_bounds() == (0, 150)


def test_pan_preserves_visible_count_and_enters_manual_mode():
    chart = view_chart(300)
    chart.zoom_view(zoom_in=True)
    before = chart._visible_candle_bounds()
    chart.pan_view(-10)
    after = chart._visible_candle_bounds()
    assert after[1] - after[0] == before[1] - before[0]
    assert chart.view_mode == VIEW_MODE_MANUAL


def test_pan_is_clamped_before_first_candle():
    chart = view_chart(300)
    chart.zoom_view(zoom_in=True)
    chart.pan_view(-10_000)
    assert chart._visible_candle_bounds()[0] == 0


def test_pan_is_clamped_after_last_candle():
    chart = view_chart(300)
    chart.zoom_view(zoom_in=True)
    chart.pan_view(10_000)
    assert chart._visible_candle_bounds()[1] == len(chart.candles)


def test_same_context_data_refresh_preserves_manual_mode(monkeypatch):
    chart = view_chart()
    configure_lightweight_refresh(chart, monkeypatch)
    chart.zoom_view(zoom_in=True)
    manual_count = chart._manual_view_end - chart._manual_view_start
    chart.set_candles(frame(151), fvg_gaps=())
    assert chart.view_mode == VIEW_MODE_MANUAL
    start, end = chart._visible_candle_bounds()
    assert end - start == manual_count


def test_double_click_reset_restores_auto_fvg_window():
    chart = view_chart(150, [evaluated(50)])
    chart._draw = lambda: None
    chart.zoom_view(zoom_in=True)
    chart._on_view_reset(SimpleNamespace())
    assert chart.view_mode == VIEW_MODE_AUTO
    assert chart._visible_candle_bounds() == (42, 150)


@pytest.mark.parametrize(
    "changed_frame",
    [
        frame(symbol="ETHUSDT"),
        frame(timeframe="15"),
    ],
)
def test_symbol_or_timeframe_change_restores_auto(monkeypatch, changed_frame):
    chart = view_chart()
    configure_lightweight_refresh(chart, monkeypatch)
    chart.zoom_view(zoom_in=True)
    chart.set_candles(changed_frame, fvg_gaps=())
    assert chart.view_mode == VIEW_MODE_AUTO
    assert chart._manual_view_start is None
    assert chart._manual_view_end is None


def test_overlay_stays_aligned_after_zoom_and_pan():
    gap = evaluated(100)
    chart = view_chart(300, [gap])
    chart.zoom_view(zoom_in=True, anchor_fraction=0.5)
    chart.pan_view(-30)
    visible, _rsi = chart._visible_candle_window()
    visible_times = list(visible["time"])
    assert gap.gap.candle1_time in visible_times
    assert visible_times.index(gap.gap.candle1_time) == (
        gap.gap.candle1_time - visible.attrs["source_start_index"]
    )
    assert gap.status is FVGOpportunityStatus.ACTIVE


def test_gui_zoom_and_pan_handlers_do_not_request_data():
    chart = view_chart(300)
    chart.canvas = FakeCanvas()
    chart._draw = lambda: None
    chart.fetch_klines = lambda *_args, **_kwargs: pytest.fail("OHLC request")
    chart._on_mouse_wheel(SimpleNamespace(delta=120, num=None, x=500))
    chart._on_drag_start(SimpleNamespace(x=500))
    chart._on_drag_motion(SimpleNamespace(x=600))
    chart._on_drag_end(SimpleNamespace())
    assert chart.view_mode == VIEW_MODE_MANUAL
