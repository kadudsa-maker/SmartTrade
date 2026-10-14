from types import SimpleNamespace

import pandas as pd
import pytest

import chart as chart_module
from chart import (
    CROSSHAIR_CANVAS_TAG,
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
        self.height = 600
        self.idle_callbacks = {}
        self.next_after_id = 1
        self.cancelled_after_ids = []
        self.deleted = []
        self.lines = []
        self.rectangles = []
        self.texts = []

    def pack(self, **_kwargs):
        pass

    def bind(self, event, callback):
        self.bindings[event] = callback

    def winfo_width(self):
        return self.width

    def winfo_height(self):
        return self.height

    def after_idle(self, callback):
        after_id = f"after-{self.next_after_id}"
        self.next_after_id += 1
        self.idle_callbacks[after_id] = callback
        return after_id

    def after_cancel(self, after_id):
        self.cancelled_after_ids.append(after_id)
        self.idle_callbacks.pop(after_id, None)

    def run_idle_callbacks(self):
        callbacks = list(self.idle_callbacks.values())
        self.idle_callbacks.clear()
        for callback in callbacks:
            callback()

    def delete(self, target):
        self.deleted.append(target)

    def create_line(self, *coordinates, **options):
        self.lines.append((coordinates, options))

    def create_rectangle(self, *coordinates, **options):
        self.rectangles.append((coordinates, options))

    def create_text(self, *coordinates, **options):
        self.texts.append((coordinates, options))


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


def test_tk_data_refresh_invalidates_but_does_not_build_plotly(monkeypatch):
    chart = view_chart()
    configure_lightweight_refresh(chart, monkeypatch)
    chart.figure = object()
    chart._update_figure = lambda: pytest.fail("eager Plotly build")

    chart.set_candles(frame(151), fvg_gaps=())

    assert chart.figure is None


def test_plotly_figure_remains_available_as_an_explicit_lazy_build():
    chart = view_chart()
    marker = object()
    chart.figure = None

    def build():
        chart.figure = marker

    chart._update_figure = build

    assert chart.build_plotly_figure() is marker


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


def test_drag_repaints_only_when_visible_candle_offset_changes():
    chart = view_chart(300)
    chart.canvas = FakeCanvas()
    redraws = []
    chart._draw = lambda: redraws.append(True)
    chart._on_drag_start(SimpleNamespace(x=500))
    chart._on_drag_motion(SimpleNamespace(x=510))
    chart._on_drag_motion(SimpleNamespace(x=511))
    assert redraws == [True]


def test_mouse_motion_coalesces_to_one_lightweight_crosshair_redraw():
    chart = view_chart(300)
    chart.canvas = FakeCanvas()
    chart.crosshair_x = None
    chart.crosshair_y = None
    chart._crosshair_after_id = None
    chart._crosshair_context = {
        "width": 1000,
        "top": 28,
        "bottom": 572,
        "padding": 28,
        "high": 101,
        "low": 99,
        "price_top": 28,
        "price_height": 400,
    }
    chart._draw = lambda *_args: pytest.fail("full chart redraw")

    for index in range(100):
        chart._on_mouse_move(SimpleNamespace(x=100 + index, y=200 + index))

    assert len(chart.canvas.idle_callbacks) == 1
    assert chart.canvas.lines == []
    chart.canvas.run_idle_callbacks()

    assert chart.crosshair_x == 199
    assert chart.crosshair_y == 299
    assert chart.canvas.deleted == [CROSSHAIR_CANVAS_TAG]
    assert len(chart.canvas.lines) == 2
    assert len(chart.canvas.rectangles) == 1
    assert len(chart.canvas.texts) == 1
    assert all(
        options["tags"] == (CROSSHAIR_CANVAS_TAG,)
        for _coordinates, options in (
            chart.canvas.lines + chart.canvas.rectangles + chart.canvas.texts
        )
    )


def test_mouse_leave_cancels_pending_redraw_and_removes_only_crosshair():
    chart = view_chart()
    chart.canvas = FakeCanvas()
    chart.crosshair_x = 200
    chart.crosshair_y = 300
    chart._crosshair_after_id = None
    chart._crosshair_context = None
    chart._on_mouse_move(SimpleNamespace(x=220, y=320))
    pending_id = chart._crosshair_after_id

    chart._on_mouse_leave(SimpleNamespace())

    assert chart.crosshair_x is None
    assert chart.crosshair_y is None
    assert chart._crosshair_after_id is None
    assert chart.canvas.cancelled_after_ids == [pending_id]
    assert chart.canvas.deleted == [CROSSHAIR_CANVAS_TAG]
    assert chart.canvas.idle_callbacks == {}


def test_resize_events_are_coalesced_to_one_full_redraw():
    chart = view_chart()
    chart.canvas = FakeCanvas()
    chart._draw_after_id = None
    redraws = []
    chart._draw = lambda *_args: redraws.append(True)

    for _index in range(100):
        chart._on_canvas_configure(SimpleNamespace())

    assert len(chart.canvas.idle_callbacks) == 1
    chart.canvas.run_idle_callbacks()
    assert redraws == [True]


def test_real_tk_canvas_motion_reuses_one_crosshair_layer_and_closes_safely():
    try:
        root = chart_module.ctk.CTk()
    except chart_module.tk.TclError:
        pytest.skip("Tk display is unavailable")

    destroyed = False
    try:
        root.geometry("1000x600+20+20")
        chart = SmartTradeChart(root)
        chart.pack(fill="both", expand=True)
        root.update()
        chart.set_candles(frame(300))
        root.update_idletasks()

        original_draw = chart._draw
        full_redraws = []

        def counted_draw(*args, **kwargs):
            full_redraws.append(True)
            return original_draw(*args, **kwargs)

        chart._draw = counted_draw
        for index in range(1000):
            chart.canvas.event_generate(
                "<Motion>",
                x=100 + index % 700,
                y=100 + index % 350,
            )
        root.update_idletasks()

        assert full_redraws == []
        assert len(chart.canvas.find_withtag(CROSSHAIR_CANVAS_TAG)) == 4

        for index in range(100):
            chart.canvas.event_generate(
                "<Motion>",
                x=150 + index,
                y=250,
            )
        root.update_idletasks()
        assert len(chart.canvas.find_withtag(CROSSHAIR_CANVAS_TAG)) == 4

        chart._on_mouse_move(SimpleNamespace(x=300, y=300))
        root.destroy()
        destroyed = True
    finally:
        if not destroyed:
            root.destroy()
