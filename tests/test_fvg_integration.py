import threading

import pandas as pd

import ui as ui_module
from analysis_modes import FVG_ON
from fvg import FVGOpportunityStatus, FVGService
from fvg import diagnostics as fvg_diagnostics
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


def build_worker_ui(frame=None):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_view_option = type("ModeValue", (), {"get": lambda self: FVG_ON})()
    ui.selected_interval = "1"
    ui.active_exchange_id = "bybit"
    ui.buttons = []
    ui.fetch_calls = 0

    def fetch_klines(_symbol, _interval, exchange_id=None):
        ui.fetch_calls += 1
        return (frame if frame is not None else sample_frame()).copy()

    ui.fetch_klines = fetch_klines
    ui.perf_log = lambda *_args, **_kwargs: None
    ui.find_coin_divergences_from_candles = lambda _candles: []
    ui.select_freshest_best_signal = lambda _divergences, _count: None
    return ui


def run_worker(ui, symbol="BTCUSDT", scan_id=1, exchange_id="bybit"):
    return ui.update_watchlist_coin(
        {"symbol": symbol},
        0,
        scan_id=scan_id,
        interval="1",
        total_symbols=1,
        exchange_id=exchange_id,
    )


def test_fvg_uses_prepared_ohlc_without_provider_call(monkeypatch):
    ui = build_worker_ui()
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 50)
    monkeypatch.setattr(
        ui_module,
        "get_klines",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("provider must not be called by FVG")
        ),
    )

    result = run_worker(ui)

    assert ui.fetch_calls == 1
    assert result["fvg_result"] is not None


def test_request_count_is_identical_when_fvg_succeeds_or_fails(monkeypatch):
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 50)
    successful = build_worker_ui()
    failed = build_worker_ui()
    failed.prepare_fvg_candles = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("FVG failed")
    )

    run_worker(successful)
    run_worker(failed)

    assert successful.fetch_calls == failed.fetch_calls == 1


def test_fvg_error_preserves_divergence_quality_and_scan_fields(monkeypatch):
    ui = build_worker_ui()
    divergence = {"type": "bullish", "quality": {"score": 88}}
    ui.find_coin_divergences_from_candles = lambda _candles: [divergence]
    ui.select_freshest_best_signal = lambda _items, _count: divergence
    ui.signal_age = lambda *_args: 1
    ui.signal_status = lambda *_args: ("ACTIVE", "green")
    ui.is_visible_signal = lambda *_args: True
    ui.prepare_fvg_candles = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("isolated failure")
    )
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 55)
    monkeypatch.setattr(ui_module, "calculate_quality_score", lambda _quality: 88)

    result = run_worker(ui)

    assert result["status"] == "signal_found"
    assert result["signal_status"] == "ACTIVE"
    assert result["divergence"] is divergence
    assert result["quality"] == 88
    assert result["ui_visible"] is True
    assert result["fvg_result"] is None
    assert result["fvg_status"] == ""
    assert result["selected_fvg"] is None


def test_fvg_error_does_not_stop_next_symbol(monkeypatch):
    ui = build_worker_ui()
    ui.prepare_fvg_candles = lambda *_args: (_ for _ in ()).throw(
        RuntimeError("isolated failure")
    )
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 50)

    first = run_worker(ui, "BADFVG")
    second = run_worker(ui, "NEXTUSDT")

    assert first["status"] == "no_signal"
    assert second["status"] == "no_signal"
    assert ui.fetch_calls == 2


def test_successful_fvg_fields_are_stored_separately(monkeypatch):
    ui = build_worker_ui()
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 50)

    result = run_worker(ui)

    assert result["fvg_result"] is not None
    assert result["fvg_status"] == result["fvg_result"].status.value
    assert result["selected_fvg"] is result["fvg_result"].selected_fvg
    assert result["status"] == "no_signal"
    assert result["signal_status"] == ""
    assert result["ui_visible"] is False


def test_missing_fvg_does_not_change_sort_key_or_cards(monkeypatch):
    ui = build_worker_ui()
    original_cards = [{"symbol_value": "BTCUSDT"}]
    ui.buttons = original_cards
    ui.sorts_by_rsi_view = lambda: False
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 50)

    result = run_worker(ui)
    without_fvg = dict(result)
    without_fvg.pop("fvg_result")
    without_fvg.pop("fvg_status")
    without_fvg.pop("selected_fvg")

    assert ui.get_signal_sort_key(result) == ui.get_signal_sort_key(without_fvg)
    assert ui.buttons is original_cards
    assert len(ui.buttons) == 1


def test_open_candle_is_current_but_not_passed_to_detector():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    prepared = pd.DataFrame(
        {
            "time": [100, 160, 220, 280],
            "open": [1, 2, 3, 4],
            "high": [2, 3, 4, 5],
            "low": [0.5, 1.5, 2.5, 3.5],
            "close": [1.5, 2.5, 3.5, 4.5],
        }
    )

    closed, current, previous = ui.prepare_fvg_candles(
        prepared, "1", now_seconds=330
    )

    assert [item.time for item in closed] == [100, 160, 220]
    assert current.time == 280
    assert previous.time == 220


def test_last_candle_is_included_when_its_interval_is_closed():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    prepared = pd.DataFrame(
        {
            "time": [100, 160, 220],
            "open": [1, 2, 3],
            "high": [2, 3, 4],
            "low": [0.5, 1.5, 2.5],
            "close": [1.5, 2.5, 3.5],
        }
    )

    closed, current, previous = ui.prepare_fvg_candles(
        prepared, "1", now_seconds=280
    )

    assert [item.time for item in closed] == [100, 160, 220]
    assert current.time == 220
    assert previous.time == 160


def test_open_candle_cannot_invalidate_gap_used_by_service():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    prepared = pd.DataFrame(
        {
            "time": [100, 160, 220, 280],
            "open": [95, 98, 103, 100.5],
            "high": [100, 102, 105, 101],
            "low": [90, 95, 101, 90],
            "close": [95, 98, 103, 100.5],
        }
    )
    closed, current, previous = ui.prepare_fvg_candles(
        prepared, "1", now_seconds=330
    )

    result = FVGService().analyze(closed, current, previous)

    assert len(result.gaps) == 1
    assert result.gaps[0].gap.lower_price == 100
    assert result.status is FVGOpportunityStatus.ACTIVE


def build_apply_ui():
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_view_option = type("ModeValue", (), {"get": lambda self: FVG_ON})()
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.current_scan_id = 2
    ui.active_exchange_id = "bybit"
    ui.current_scan_symbols = ["BTCUSDT"]
    ui.instrument_by_symbol = {}
    ui.current_scan_results = {"BTCUSDT": {"fvg_status": "CURRENT"}}
    ui.current_scan_rendered = 0
    ui.active_scan_job_id = None
    ui.scan_worker_busy = False
    ui.refresh_index = 0
    ui.scan_batch_position = 0
    ui.scan_cycle_started_at = 1
    ui.scan_mode = "watchlist"
    ui.top_bybit_limit = 100
    ui.buttons = []
    ui.cards_by_symbol = {}
    ui.is_top_bybit_mode = lambda: False
    ui.get_scan_batch_size = lambda: 1
    ui.schedule_scan_loop = lambda *_args: None
    ui.mark_scan_cycle_completed = lambda *_args: None
    ui.process_alert_candidate = lambda *_args, **_kwargs: False
    ui.perf_log = lambda *_args, **_kwargs: None
    return ui


def test_stale_scan_id_does_not_overwrite_current_fvg():
    ui = build_apply_ui()
    stale = ui.create_scan_result_record(1, "BTCUSDT", 0, "no_signal")
    stale["fvg_status"] = "ACTIVE"

    assert ui.apply_scan_result(stale) is False
    assert ui.current_scan_results["BTCUSDT"]["fvg_status"] == "CURRENT"


def test_valid_scan_id_updates_full_record_with_fvg():
    ui = build_apply_ui()
    current = ui.create_scan_result_record(2, "BTCUSDT", 0, "no_signal")
    current["fvg_status"] = FVGOpportunityStatus.NONE.value

    assert ui.apply_scan_result(current) is True
    assert ui.current_scan_results["BTCUSDT"] is current


def test_exchange_and_timeframe_remain_owned_by_parent_scan_record():
    ui = build_worker_ui()
    record = ui.create_scan_result_record(
        3,
        "BTC-USDT",
        0,
        "no_signal",
        exchange_id="okx_spot",
        interval="15",
    )

    assert record["exchange_id"] == "okx_spot"
    assert record["interval"] == "15"
    assert "fvg_result" not in record


def test_default_record_has_no_visual_fvg_state():
    ui = build_worker_ui()
    record = ui.create_scan_result_record(1, "BTCUSDT", 0, "pending")

    assert "fvg_result" not in record
    assert "fvg_status" not in record
    assert "selected_fvg" not in record


def test_diagnostics_write_error_preserves_scan_divergence_and_quality(
    monkeypatch, tmp_path
):
    ui = build_worker_ui()
    divergence = {"type": "bullish", "quality": {"score": 88}}
    ui.find_coin_divergences_from_candles = lambda _candles: [divergence]
    ui.select_freshest_best_signal = lambda _items, _count: divergence
    ui.signal_age = lambda *_args: 1
    ui.signal_status = lambda *_args: ("ACTIVE", "green")
    ui.is_visible_signal = lambda *_args: True
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 55)
    monkeypatch.setattr(ui_module, "calculate_quality_score", lambda _quality: 88)
    monkeypatch.setattr(fvg_diagnostics, "FVG_DIAGNOSTICS_ENABLED", True)
    monkeypatch.setattr(fvg_diagnostics, "diagnostics_path", lambda: tmp_path)

    result = run_worker(ui)

    assert result["divergence"] is divergence
    assert result["quality"] == 88
    assert result["fvg_result"] is not None


def test_chart_waits_for_matching_scan_result_when_diagnostics_are_enabled(monkeypatch, tmp_path):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_view_option = type("ModeValue", (), {"get": lambda self: FVG_ON})()
    ui.active_exchange_id = "bybit"
    ui.current_scan_id = 1
    ui.current_scan_results = {}
    monkeypatch.setattr(fvg_diagnostics, "FVG_DIAGNOSTICS_ENABLED", True)
    monkeypatch.setattr(fvg_diagnostics, "diagnostics_path", lambda: tmp_path)

    gaps = ui.resolve_chart_fvg_gaps(sample_frame(), "BTCUSDT", "1")

    assert gaps == ()


def test_enabled_diagnostics_add_no_market_request(monkeypatch, tmp_path):
    ui = build_worker_ui()
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 50)
    monkeypatch.setattr(fvg_diagnostics, "FVG_DIAGNOSTICS_ENABLED", True)
    monkeypatch.setattr(
        fvg_diagnostics,
        "diagnostics_path",
        lambda: tmp_path / "fvg_diagnostics.jsonl",
    )

    run_worker(ui)

    assert ui.fetch_calls == 1
