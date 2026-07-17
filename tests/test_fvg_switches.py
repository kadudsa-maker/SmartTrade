import threading

import pandas as pd

import ui as ui_module
from fvg import FVGOpportunityStatus, FVGService
from fvg import diagnostics as fvg_diagnostics
from fvg.filtering import FVG_ANALYSIS_DEFAULT, FVG_ONLY_DEFAULT
from ui import SmartTradeUI


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


def worker_ui(enabled):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.fvg_enabled = enabled
    ui.fvg_only_enabled = False
    ui.selected_interval = "1"
    ui.active_exchange_id = "bybit"
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


def run_worker(ui):
    return ui.update_watchlist_coin(
        {"symbol": "BTCUSDT"},
        0,
        scan_id=1,
        interval="1",
        total_symbols=1,
        exchange_id="bybit",
    )


class FakeButton:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)


class FakeChart:
    def __init__(self):
        self.updates = []

    def set_fvg_gaps(self, gaps):
        self.updates.append(tuple(gaps))


def switch_ui(*, enabled=False, only=False):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.fvg_enabled = enabled
    ui.fvg_only_enabled = only
    ui.fvg_enabled_button = FakeButton()
    ui.fvg_only_button = FakeButton()
    ui.current_scan_results = {}
    ui.top50_results = {}
    ui.buttons = []
    ui.cards_by_symbol = {}
    ui.chart = FakeChart()
    ui.active_exchange_id = "bybit"
    ui.current_scan_id = 1
    ui.selected_interval = "1"
    ui.selected_symbol = "BTCUSDT"
    ui.market_label = lambda exchange_id=None: "Bybit Futures"
    ui.get_active_exchange_id = lambda: "bybit"
    return ui


def test_fvg_analysis_is_off_by_default():
    assert FVG_ANALYSIS_DEFAULT is False
    assert FVG_ONLY_DEFAULT is False


def test_off_skips_service_detector_preparation_and_result_fields(monkeypatch):
    ui = worker_ui(False)
    ui.prepare_fvg_candles = lambda *_args: (_ for _ in ()).throw(
        AssertionError("FVG candle preparation must not run")
    )
    monkeypatch.setattr(
        ui_module,
        "FVGService",
        lambda: (_ for _ in ()).throw(AssertionError("FVGService must not run")),
    )

    result = run_worker(ui)

    assert "fvg_result" not in result
    assert "fvg_status" not in result
    assert "selected_fvg" not in result


def test_off_skips_diagnostics_even_when_diagnostics_flag_is_on(monkeypatch):
    ui = worker_ui(False)
    monkeypatch.setattr(fvg_diagnostics, "FVG_DIAGNOSTICS_ENABLED", True)
    monkeypatch.setattr(
        fvg_diagnostics,
        "record_analysis",
        lambda **_fields: (_ for _ in ()).throw(AssertionError("diagnostics")),
    )
    run_worker(ui)


def test_on_runs_existing_service_once(monkeypatch):
    ui = worker_ui(True)
    original_service = FVGService
    calls = []

    class SpyService:
        def analyze(self, *args, **kwargs):
            calls.append((args, kwargs))
            return original_service().analyze(*args, **kwargs)

    monkeypatch.setattr(ui_module, "FVGService", SpyService)
    result = run_worker(ui)

    assert len(calls) == 1
    assert result["fvg_result"] is not None


def test_off_chart_path_skips_service_and_returns_no_overlay(monkeypatch):
    ui = switch_ui(enabled=False)
    monkeypatch.setattr(
        ui_module,
        "FVGService",
        lambda: (_ for _ in ()).throw(AssertionError("FVGService must not run")),
    )
    assert ui.resolve_chart_fvg_gaps(sample_frame(), "BTCUSDT", "1") == ()


def test_disabling_fvg_clears_overlay_and_card_sections():
    ui = switch_ui(enabled=True, only=True)
    cleared_cards = []
    ui.clear_fvg_card_sections = lambda: cleared_cards.append(True)

    ui.toggle_fvg_enabled()

    assert ui.fvg_enabled is False
    assert ui.fvg_only_enabled is False
    assert ui.chart.updates == [()]
    assert cleared_cards == [True]


def test_disabling_fvg_removes_stored_fvg_fields_only():
    ui = switch_ui(enabled=True)
    record = {
        "fvg_result": object(),
        "fvg_status": "ACTIVE",
        "selected_fvg": object(),
        "divergence": {"type": "bullish"},
        "quality": 88,
    }
    ui.current_scan_results["BTCUSDT"] = record

    ui.toggle_fvg_enabled()

    assert set(record) == {"divergence", "quality"}


def test_fvg_only_automatically_enables_analysis_without_running_it(monkeypatch):
    ui = switch_ui(enabled=False, only=False)
    monkeypatch.setattr(
        ui_module,
        "FVGService",
        lambda: (_ for _ in ()).throw(AssertionError("toggle must not analyze")),
    )

    ui.toggle_fvg_only()

    assert ui.fvg_enabled is True
    assert ui.fvg_only_enabled is True


def test_fvg_on_click_updates_visual_state_without_analysis(monkeypatch):
    ui = switch_ui(enabled=False)
    monkeypatch.setattr(
        ui_module,
        "FVGService",
        lambda: (_ for _ in ()).throw(AssertionError("toggle must not analyze")),
    )

    ui.toggle_fvg_enabled()

    assert ui.fvg_enabled is True
    assert ui.fvg_enabled_button.options["fg_color"] == ui_module.BLUE


def test_fvg_on_click_performs_no_request():
    ui = switch_ui(enabled=False)
    ui.fetch_klines = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("request")
    )
    ui.toggle_fvg_enabled()


def test_fvg_only_toggle_performs_no_request_or_signal_calculation():
    ui = switch_ui(enabled=True)
    ui.fetch_klines = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("request")
    )
    ui.find_coin_divergences_from_candles = lambda *_args: (_ for _ in ()).throw(
        AssertionError("divergence")
    )
    ui.toggle_fvg_only()


def test_switches_do_not_mutate_divergence_quality_or_sort_order():
    ui = switch_ui(enabled=True)
    record = {"divergence": {"type": "bearish"}, "quality": 91}
    ui.current_scan_results["BTCUSDT"] = record
    original_order = list(ui.buttons)

    ui.toggle_fvg_enabled()

    assert record == {"divergence": {"type": "bearish"}, "quality": 91}
    assert ui.buttons == original_order


def test_reenabled_fvg_waits_for_next_analysis_result_before_overlay():
    ui = switch_ui(enabled=False)
    ui.toggle_fvg_enabled()
    assert ui.chart.updates == []

    analyzed = worker_ui(True)
    result = run_worker(analyzed)
    result.update(
        {
            "scan_id": ui.current_scan_id,
            "exchange_id": "bybit",
            "exchange_symbol": "BTCUSDT",
            "symbol": "BTCUSDT",
            "interval": "1",
            "market_label": "Bybit Futures",
        }
    )
    ui.current_scan_results["BTCUSDT"] = result

    assert ui.update_selected_chart_fvg(result) is True
    assert ui.chart.updates[-1] == tuple(result["fvg_result"].gaps)


def test_off_worker_preserves_rsi_divergence_and_quality(monkeypatch):
    ui = worker_ui(False)
    divergence = {"type": "bullish", "quality": {"score": 87}}
    ui.find_coin_divergences_from_candles = lambda _candles: [divergence]
    ui.select_freshest_best_signal = lambda _items, _count: divergence
    ui.signal_age = lambda *_args: 1
    ui.signal_status = lambda *_args: ("ACTIVE", "green")
    ui.is_visible_signal = lambda *_args: True
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 52)
    monkeypatch.setattr(ui_module, "calculate_quality_score", lambda _quality: 87)

    result = run_worker(ui)

    assert result["rsi"] == 52
    assert result["divergence"] is divergence
    assert result["quality"] == 87


def test_apply_result_while_off_discards_late_fvg_payload():
    ui = switch_ui(enabled=False)
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.current_scan_symbols = ["BTCUSDT"]
    ui.instrument_by_symbol = {}
    ui.current_scan_rendered = 0
    ui.active_scan_job_id = None
    ui.scan_worker_busy = False
    ui.refresh_index = 0
    ui.scan_batch_position = 0
    ui.scan_cycle_started_at = 1
    ui.scan_mode = "watchlist"
    ui.top_bybit_limit = 100
    ui.schedule_scan_loop = lambda *_args: None
    ui.mark_scan_cycle_completed = lambda *_args: None
    ui.process_alert_candidate = lambda *_args, **_kwargs: False
    ui.perf_log = lambda *_args, **_kwargs: None
    result = ui.create_scan_result_record(1, "BTCUSDT", 0, "no_signal", interval="1")
    result.update(
        {
            "fvg_result": object(),
            "fvg_status": FVGOpportunityStatus.ACTIVE.value,
            "selected_fvg": object(),
        }
    )

    assert ui.apply_scan_result(result) is True
    assert "fvg_result" not in ui.current_scan_results["BTCUSDT"]
