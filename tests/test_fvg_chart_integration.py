import pandas as pd
import plotly.graph_objects as go

import ui as ui_module
from analysis_modes import FVG_ON, FVG_ONLY
from chart import SmartTradeChart
from fvg import (
    EvaluatedFVG,
    FairValueGap,
    FVGDirection,
    FVGOpportunityStatus,
    FVGScanResult,
)
from fvg.chart_overlay import FVGChartOverlay
from ui import SmartTradeUI


def evaluated(
    candle3_time=120,
    status=FVGOpportunityStatus.ACTIVE,
    direction=FVGDirection.BULLISH,
):
    return EvaluatedFVG(
        gap=FairValueGap(direction, 60, candle3_time, 100, 105),
        status=status,
        distance_percent=0 if status is FVGOpportunityStatus.ACTIVE else 0.2,
    )


def fvg_result(gaps):
    gaps = tuple(gaps)
    selected = gaps[0] if gaps else None
    status = selected.status if selected else FVGOpportunityStatus.NONE
    return FVGScanResult(102, gaps, selected, status)


def raw_frame():
    frame = pd.DataFrame({
        "time": [0, 60_000, 120_000, 180_000],
        "open": [99, 100, 101, 102],
        "high": [101, 102, 106, 107],
        "low": [98, 99, 103, 101],
        "close": [100, 101, 105, 103],
        "volume": [1, 1, 1, 1],
    })
    return frame


def scan_record(ui, gaps, *, symbol="BTCUSDT", interval="60", scan_id=7, exchange="bybit"):
    return {
        "scan_id": scan_id,
        "exchange_id": exchange,
        "symbol": symbol,
        "exchange_symbol": symbol,
        "interval": interval,
        "market_label": ui.market_label(exchange),
        "analysis_mode": FVG_ON,
        "fvg_result": fvg_result(gaps) if gaps is not None else None,
    }


def ui_shell():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_view_option = type("ModeValue", (), {"get": lambda self: FVG_ON})()
    ui.active_exchange_id = "bybit"
    ui.current_scan_id = 7
    ui.current_scan_results = {}
    ui.selected_interval = "60"
    ui.selected_symbol = "BTCUSDT"
    ui.instrument_by_symbol = {}
    return ui


class FakeChart:

    def __init__(self):
        self.calls = []
        self.fvg_updates = []

    def set_candles(self, frame, fvg_gaps=()):
        self.calls.append((frame, tuple(fvg_gaps)))

    def set_fvg_gaps(self, gaps):
        self.fvg_updates.append(tuple(gaps))


def prepare_refresh_ui(ui):
    ui.chart = FakeChart()
    ui.fetch_calls = 0

    def fetch(*_args, **_kwargs):
        ui.fetch_calls += 1
        return raw_frame()

    ui.fetch_klines = fetch
    ui.perf_log = lambda *_args, **_kwargs: None
    ui.display_symbol = lambda symbol: symbol
    ui.platform_market_name = lambda symbol: symbol
    ui.asset_class = lambda _symbol: "crypto"
    ui.update_open_chart_status = lambda *_args: None
    return ui


def test_matching_scan_record_supplies_all_gaps_without_reanalysis(monkeypatch):
    ui = ui_shell()
    gaps = [evaluated(), evaluated(150, FVGOpportunityStatus.NONE)]
    ui.current_scan_results["BTCUSDT"] = scan_record(ui, gaps)
    monkeypatch.setattr(
        ui_module,
        "FVGService",
        lambda: (_ for _ in ()).throw(AssertionError("must not reanalyze")),
    )
    assert ui.resolve_chart_fvg_gaps(raw_frame(), "BTCUSDT", "60") == tuple(gaps)


def test_matching_record_with_no_fvg_result_clears_without_reanalysis(monkeypatch):
    ui = ui_shell()
    ui.current_scan_results["BTCUSDT"] = scan_record(ui, None)
    monkeypatch.setattr(
        ui_module,
        "FVGService",
        lambda: (_ for _ in ()).throw(AssertionError("must not retry scan error")),
    )
    assert ui.resolve_chart_fvg_gaps(raw_frame(), "BTCUSDT", "60") == ()


def test_stale_scan_id_is_not_used_for_chart(monkeypatch):
    ui = ui_shell()
    ui.current_scan_results["BTCUSDT"] = scan_record(ui, [evaluated()], scan_id=6)
    calls = []

    class Service:
        def analyze(self, *_args):
            calls.append(True)
            return fvg_result([])

    monkeypatch.setattr(ui_module, "FVGService", Service)
    ui.prepare_engine_candles = lambda frame, interval=None: frame
    ui.prepare_fvg_candles = lambda frame, interval: ((1, 2), 3, 2)
    assert ui.resolve_chart_fvg_gaps(raw_frame(), "BTCUSDT", "60") == ()
    assert calls == []


def test_record_for_other_symbol_is_not_used(monkeypatch):
    ui = ui_shell()
    ui.current_scan_results["BTCUSDT"] = scan_record(ui, [evaluated()], symbol="ETHUSDT")
    monkeypatch.setattr(ui_module, "FVGService", lambda: type(
        "Service", (), {"analyze": lambda self, *_args: fvg_result([])}
    )())
    ui.prepare_engine_candles = lambda frame, interval=None: frame
    ui.prepare_fvg_candles = lambda frame, interval: ((1, 2), 3, 2)
    assert ui.resolve_chart_fvg_gaps(raw_frame(), "BTCUSDT", "60") == ()


def test_record_for_other_timeframe_is_not_used(monkeypatch):
    ui = ui_shell()
    ui.current_scan_results["BTCUSDT"] = scan_record(ui, [evaluated()], interval="15")
    calls = []

    class Service:
        def analyze(self, *_args):
            calls.append(True)
            return fvg_result([])

    monkeypatch.setattr(ui_module, "FVGService", Service)
    ui.prepare_engine_candles = lambda frame, interval=None: frame
    ui.prepare_fvg_candles = lambda frame, interval: ((1, 2), 3, 2)
    ui.resolve_chart_fvg_gaps(raw_frame(), "BTCUSDT", "60")
    assert calls == []


def test_record_for_other_exchange_is_not_used(monkeypatch):
    ui = ui_shell()
    ui.current_scan_results["BTCUSDT"] = scan_record(ui, [evaluated()], exchange="okx")
    calls = []

    class Service:
        def analyze(self, *_args):
            calls.append(True)
            return fvg_result([])

    monkeypatch.setattr(ui_module, "FVGService", Service)
    ui.prepare_engine_candles = lambda frame, interval=None: frame
    ui.prepare_fvg_candles = lambda frame, interval: ((1, 2), 3, 2)
    ui.resolve_chart_fvg_gaps(raw_frame(), "BTCUSDT", "60")
    assert calls == []


def test_record_from_previous_analysis_mode_is_not_used(monkeypatch):
    ui = ui_shell()
    old = scan_record(ui, [evaluated()])
    old["analysis_mode"] = FVG_ONLY
    ui.current_scan_results["BTCUSDT"] = old
    monkeypatch.setattr(
        ui_module,
        "FVGService",
        lambda: (_ for _ in ()).throw(AssertionError("chart must not reanalyze")),
    )
    assert ui.resolve_chart_fvg_gaps(raw_frame(), "BTCUSDT", "60") == ()


def test_missing_scan_record_does_not_reanalyze_chart_candles(monkeypatch):
    ui = ui_shell()
    analyzed = []
    prepared = object()
    ui.prepare_engine_candles = lambda frame, interval=None: prepared
    ui.prepare_fvg_candles = lambda frame, interval: (("closed",), "current", "previous")

    monkeypatch.setattr(ui_module, "FVGService", lambda: (_ for _ in ()).throw(
        AssertionError("chart must wait for scanner result")
    ))
    gaps = ui.resolve_chart_fvg_gaps(raw_frame(), "BTCUSDT", "60")
    assert gaps == ()
    assert analyzed == []


def test_missing_scan_record_skips_closed_candle_helper(monkeypatch):
    ui = ui_shell()
    helper_calls = []
    ui.prepare_engine_candles = lambda frame, interval=None: frame

    def prepare(frame, interval):
        helper_calls.append((frame, interval))
        return ((1, 2), 3, 2)

    ui.prepare_fvg_candles = prepare
    monkeypatch.setattr(ui_module, "FVGService", lambda: type(
        "Service", (), {"analyze": lambda self, *_args: fvg_result([])}
    )())
    frame = raw_frame()
    ui.resolve_chart_fvg_gaps(frame, "BTCUSDT", "60")
    assert helper_calls == []


def test_fvg_analysis_error_returns_empty_gaps_and_chart_can_render(monkeypatch):
    ui = prepare_refresh_ui(ui_shell())
    ui.prepare_engine_candles = lambda frame, interval=None: frame
    ui.prepare_fvg_candles = lambda frame, interval: ((1, 2), 3, 2)
    monkeypatch.setattr(ui_module, "FVGService", lambda: type(
        "Service", (), {"analyze": lambda self, *_args: (_ for _ in ()).throw(RuntimeError("bad FVG"))}
    )())
    ui.refresh_selected()
    assert len(ui.chart.calls) == 1
    assert ui.chart.calls[0][1] == ()


def test_chart_refresh_uses_one_ohlc_request_with_matching_record(monkeypatch):
    ui = prepare_refresh_ui(ui_shell())
    gap = evaluated()
    ui.current_scan_results["BTCUSDT"] = scan_record(ui, [gap])
    monkeypatch.setattr(ui_module, "FVGService", lambda: (_ for _ in ()).throw(
        AssertionError("matching record must be used")
    ))
    ui.refresh_selected()
    assert ui.fetch_calls == 1
    assert ui.chart.calls[0][1] == (gap,)


def test_chart_refresh_uses_one_ohlc_request_with_fallback(monkeypatch):
    ui = prepare_refresh_ui(ui_shell())
    ui.prepare_engine_candles = lambda frame, interval=None: frame
    ui.prepare_fvg_candles = lambda frame, interval: ((1, 2), 3, 2)
    monkeypatch.setattr(ui_module, "FVGService", lambda: type(
        "Service", (), {"analyze": lambda self, *_args: fvg_result([])}
    )())
    ui.refresh_selected()
    assert ui.fetch_calls == 1


def test_new_scan_result_updates_selected_chart_without_request():
    ui = prepare_refresh_ui(ui_shell())
    gap = evaluated()
    record = scan_record(ui, [gap])
    ui.current_scan_results["BTCUSDT"] = record
    assert ui.update_selected_chart_fvg(record) is True
    assert ui.chart.fvg_updates == [(gap,)]
    assert ui.fetch_calls == 0


def test_new_scan_result_for_other_symbol_does_not_update_chart():
    ui = prepare_refresh_ui(ui_shell())
    record = scan_record(ui, [evaluated()], symbol="ETHUSDT")
    assert ui.update_selected_chart_fvg(record) is False
    assert ui.chart.fvg_updates == []


def test_symbol_timeframe_and_exchange_clear_existing_overlay():
    ui = ui_shell()
    ui.chart = FakeChart()
    ui.clear_chart_fvg()
    ui.clear_chart_fvg()
    ui.clear_chart_fvg()
    assert ui.chart.fvg_updates == [(), (), ()]


def test_chart_set_fvg_gaps_skips_duplicate_redraw():
    chart = SmartTradeChart.__new__(SmartTradeChart)
    chart.fvg_overlay = FVGChartOverlay()
    chart.fvg_gaps = ()
    chart._last_source_key = "old"
    redraws = []
    chart._update_figure = lambda: redraws.append("figure")
    chart._draw = lambda: redraws.append("canvas")
    gap = evaluated()
    chart.set_fvg_gaps([gap])
    chart.set_fvg_gaps([gap])
    assert redraws == ["figure", "canvas"]


def test_chart_set_fvg_gaps_empty_removes_previous_overlay():
    chart = SmartTradeChart.__new__(SmartTradeChart)
    chart.fvg_overlay = FVGChartOverlay()
    chart.fvg_gaps = (evaluated(),)
    chart._last_source_key = "old"
    redraws = []
    chart._update_figure = lambda: redraws.append("figure")
    chart._draw = lambda: redraws.append("canvas")
    chart.set_fvg_gaps(())
    assert chart.fvg_gaps == ()
    assert redraws == ["figure", "canvas"]


def test_plotly_refresh_replaces_old_fvg_shapes():
    figure = go.Figure()
    first = evaluated(candle3_time=120)
    second = evaluated(candle3_time=180)
    FVGChartOverlay.add_plotly_shapes(figure, [first], 240)
    FVGChartOverlay.add_plotly_shapes(figure, [second], 240)
    fvg_shapes = [shape for shape in figure.layout.shapes if shape.name.startswith("FVG:")]
    assert len(fvg_shapes) == 1
    assert fvg_shapes[0].x0 == 180
