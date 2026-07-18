import threading

import pandas as pd
import pytest

import ui as ui_module
from analysis_modes import (
    FVG_ON,
    FVG_ONLY,
    FVG_RSI,
    RSI_VIEW_ON,
    capabilities_for_mode,
)
from fvg import FVGService
from ui import SmartTradeUI


class ModeValue:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def sample_frame():
    return pd.DataFrame(
        {
            "time": [1_000, 2_000, 3_000, 4_000],
            "open": [10.5, 11.5, 13.5, 13.8],
            "high": [11.0, 12.0, 14.0, 14.2],
            "low": [10.0, 11.0, 13.0, 13.2],
            "close": [10.5, 11.5, 13.5, 13.8],
            "volume": [1.0, 1.0, 1.0, 1.0],
            "turnover": [1.0, 1.0, 1.0, 1.0],
        }
    )


def worker_ui(mode):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_view_option = ModeValue(mode)
    ui.selected_interval = "1"
    ui.active_exchange_id = "bybit"
    ui.instrument_by_symbol = {}
    ui.buttons = []
    ui.fetch_calls = 0

    def fetch_klines(*_args, **_kwargs):
        ui.fetch_calls += 1
        return sample_frame().copy()

    ui.fetch_klines = fetch_klines
    ui.perf_log = lambda *_args, **_kwargs: None
    ui.find_coin_divergences_from_candles = lambda _candles: []
    ui.select_freshest_best_signal = lambda _items, _count: None
    return ui


def run_worker(ui, mode):
    return ui.update_watchlist_coin(
        {"symbol": "BTCUSDT"},
        0,
        scan_id=1,
        interval="1",
        total_symbols=1,
        exchange_id="bybit",
        market_label="Bybit Futures",
        analysis_mode=mode,
    )


@pytest.mark.parametrize(
    "mode, expected",
    [
        (RSI_VIEW_ON, (False, True, True, True, False, False)),
        (FVG_ON, (True, True, True, True, False, False)),
        (FVG_ONLY, (True, False, False, False, True, False)),
        (FVG_RSI, (True, True, False, False, False, False)),
    ],
)
def test_central_mode_capabilities(mode, expected):
    profile = capabilities_for_mode(mode)
    assert (
        profile.analyze_fvg,
        profile.analyze_rsi,
        profile.analyze_divergence,
        profile.analyze_quality,
        profile.require_fvg,
        profile.require_good_rsi,
    ) == expected


@pytest.mark.parametrize("mode", [FVG_ON, FVG_ONLY, FVG_RSI])
def test_fvg_modes_run_existing_service(mode, monkeypatch):
    ui = worker_ui(mode)
    original_service = FVGService
    calls = []

    class SpyService:
        def analyze(self, *args, **kwargs):
            calls.append(1)
            return original_service().analyze(*args, **kwargs)

    monkeypatch.setattr(ui_module, "FVGService", SpyService)
    result = run_worker(ui, mode)
    assert calls == [1]
    assert result["fvg_result"] is not None


def test_fvg_on_keeps_standard_analysis_and_quality(monkeypatch):
    ui = worker_ui(FVG_ON)
    divergence = {"type": "bullish", "quality": {"score": 87}}
    ui.find_coin_divergences_from_candles = lambda _candles: [divergence]
    ui.select_freshest_best_signal = lambda _items, _count: divergence
    ui.signal_age = lambda *_args: 1
    ui.signal_status = lambda *_args: ("ACTIVE", "green")
    ui.is_visible_signal = lambda *_args: True
    monkeypatch.setattr(ui_module, "calculate_quality_score", lambda _quality: 87)
    result = run_worker(ui, FVG_ON)
    assert result["divergence"] is divergence
    assert result["quality"] == 87


def test_fvg_only_skips_rsi_divergence_and_quality(monkeypatch):
    ui = worker_ui(FVG_ONLY)
    monkeypatch.setattr(
        ui_module, "calculate_rsi", lambda *_args: pytest.fail("RSI must be skipped")
    )
    ui.find_coin_divergences_from_candles = lambda *_args: pytest.fail(
        "divergence must be skipped"
    )
    monkeypatch.setattr(
        ui_module,
        "calculate_quality_score",
        lambda *_args: pytest.fail("Quality must be skipped"),
    )
    result = run_worker(ui, FVG_ONLY)
    assert result["rsi"] is None
    assert result["divergence"] is None
    assert result["quality"] is None


def test_fvg_rsi_uses_rsi_but_skips_divergence_and_quality(monkeypatch):
    ui = worker_ui(FVG_RSI)
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda *_args: 29)
    ui.find_coin_divergences_from_candles = lambda *_args: pytest.fail(
        "divergence must be skipped"
    )
    monkeypatch.setattr(
        ui_module,
        "calculate_quality_score",
        lambda *_args: pytest.fail("Quality must be skipped"),
    )
    result = run_worker(ui, FVG_RSI)
    assert result["rsi"] == 29
    assert result["divergence"] is None
    assert result["quality"] is None


def test_standard_mode_skips_fvg_service(monkeypatch):
    ui = worker_ui(RSI_VIEW_ON)
    monkeypatch.setattr(
        ui_module, "FVGService", lambda: pytest.fail("FVGService must be skipped")
    )
    result = run_worker(ui, RSI_VIEW_ON)
    assert "fvg_result" not in result


def test_mode_change_does_not_scan_fetch_or_analyze(monkeypatch):
    ui = worker_ui(RSI_VIEW_ON)
    ui.scan_generation = 3
    ui.current_scan_id = 3
    ui.current_scan_results = {}
    ui.top50_results = {}
    ui.last_top50_order = []
    ui.last_card_texts = {}
    ui.watchlist_scroll = None
    ui.clear_chart_fvg = lambda: None
    ui.apply_card_filters = lambda: None
    ui.scan_now = lambda: pytest.fail("scan")
    ui.schedule_scan_loop = lambda *_args: pytest.fail("schedule")
    ui.fetch_klines = lambda *_args, **_kwargs: pytest.fail("OHLC")
    monkeypatch.setattr(ui_module, "FVGService", lambda: pytest.fail("FVG"))
    ui.apply_rsi_view_option(FVG_ONLY)
    assert ui.current_analysis_mode() == FVG_ONLY
    assert ui.current_scan_id == 4


def test_worker_job_carries_mode_snapshot():
    ui = worker_ui(FVG_ON)
    ui.shutdown_requested = False
    ui.scan_worker_busy = False
    ui.scan_job_sequence = 0
    ui.current_scan_id = 7
    ui.selected_interval = "1"
    ui.scan_job_lock = threading.Lock()
    ui.pending_scan_job = None
    ui.active_scan_job_id = None
    ui.scan_job_event = threading.Event()
    ui.update_scan_progress = lambda *_args: None
    ui.get_alert_scan_range = lambda: "watchlist"
    assert ui.scan_symbol_with_progress("BTCUSDT", 0, 1)
    assert ui.pending_scan_job["analysis_mode"] == FVG_ON


def test_late_result_from_previous_mode_is_rejected():
    ui = worker_ui(FVG_ONLY)
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.current_scan_id = 7
    ui.current_scan_symbols = ["BTCUSDT"]
    ui.current_scan_results = {}
    ui.active_scan_job_id = 11
    ui.scan_worker_busy = True
    ui.log_card_state = lambda *_args, **_kwargs: None
    scheduled = []
    ui.schedule_scan_loop = lambda delay=0: scheduled.append(delay)
    result = ui.create_scan_result_record(
        7,
        "BTCUSDT",
        0,
        "no_signal",
        interval="1",
        job_id=11,
        market_label="Bybit Futures",
        analysis_mode=FVG_ON,
    )
    assert ui.apply_scan_result(result) is False
    assert ui.current_scan_results == {}
    assert scheduled == [0]


def test_mode_change_clears_overlay_without_request():
    ui = worker_ui(FVG_ON)
    updates = []
    ui.chart = type("Chart", (), {"set_fvg_gaps": lambda self, gaps: updates.append(tuple(gaps))})()
    ui.scan_generation = 1
    ui.current_scan_results = {}
    ui.top50_results = {}
    ui.last_top50_order = []
    ui.last_card_texts = {}
    ui.watchlist_scroll = None
    ui.apply_card_filters = lambda: None
    ui.fetch_klines = lambda *_args, **_kwargs: pytest.fail("OHLC")
    ui.apply_rsi_view_option(FVG_RSI)
    assert updates == [()]
