import threading
from queue import Queue

import pandas as pd
import pytest

import ui as ui_module
from ui import RSI_VIEW_SORT, SmartTradeUI


class FakeApp:

    def __init__(self):

        self.scheduled = []
        self.cancelled = []
        self.destroyed = False

    def after(self, delay_ms, callback):

        self.scheduled.append((delay_ms, callback))
        return f"after-{len(self.scheduled)}"

    def after_cancel(self, after_id):

        self.cancelled.append(after_id)

    def destroy(self):

        self.destroyed = True


class Flag:

    def __init__(self, value):

        self.value = value

    def get(self):

        return self.value

    def set(self, value):

        self.value = value


def sample_frame():

    return pd.DataFrame(
        {
            "time": [1000, 2000, 3000],
            "open": [1.0, 2.0, 3.0],
            "high": [2.0, 3.0, 4.0],
            "low": [0.5, 1.5, 2.5],
            "close": [1.5, 2.5, 3.5],
            "volume": [10.0, 11.0, 12.0],
            "turnover": [15.0, 27.5, 42.0]
        }
    )


def test_worker_returns_plain_record_without_touching_widgets(monkeypatch):

    ui = SmartTradeUI.__new__(SmartTradeUI)
    monkeypatch.setattr(ui_module, "get_klines", lambda symbol, interval: sample_frame())
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda frame: 42.5)
    ui.find_coin_divergences_from_candles = lambda candles: []
    ui.select_freshest_best_signal = lambda divergences, count: None

    result = ui.update_watchlist_coin(
        {"symbol": "BTCUSDT"},
        4,
        scan_id=7,
        interval="15",
        total_symbols=10,
        job_id=11
    )

    assert result["scan_id"] == 7
    assert result["job_id"] == 11
    assert result["symbol"] == "BTCUSDT"
    assert result["interval"] == "15"
    assert result["index"] == 4
    assert result["total_symbols"] == 10
    assert result["status"] == "no_signal"
    assert result["rsi"] == 42.5
    assert result["candle_count"] == 3
    assert result["error"] is None
    assert "app" not in ui.__dict__


def test_stale_scan_result_is_ignored():

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.current_scan_id = 2
    ui.active_scan_job_id = 11
    ui.scan_worker_busy = True
    ui.schedule_scan_loop = lambda delay=0: (_ for _ in ()).throw(
        AssertionError("stale result must not schedule over an active new job")
    )

    result = ui.create_scan_result_record(1, "OLDUSDT", 0, "no_signal", job_id=10)

    assert ui.apply_scan_result(result) is False
    assert ui.active_scan_job_id == 11
    assert ui.scan_worker_busy is True


def test_restart_releases_completed_job_removed_from_result_queue():

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.scan_result_queue = Queue()
    ui.active_scan_job_id = 31
    ui.scan_worker_busy = True
    ui.scan_result_queue.put(
        ui.create_scan_result_record(1, "OLDUSDT", 0, "no_signal", job_id=31)
    )

    ui.clear_scan_result_queue()

    assert ui.scan_result_queue.empty()
    assert ui.active_scan_job_id is None
    assert ui.scan_worker_busy is False


def test_symbol_error_advances_scan_and_schedules_next_symbol():

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.current_scan_id = 3
    ui.current_scan_symbols = ["BADUSDT", "GOODUSDT"]
    ui.active_scan_job_id = 21
    ui.scan_worker_busy = True
    ui.refresh_index = 0
    ui.scan_batch_position = 0
    ui.last_scan_batch_time = None
    ui.scan_cycle_started_at = 1
    ui.scan_mode = "watchlist"
    ui.top_bybit_limit = 100
    ui.get_scan_batch_size = lambda: 2
    ui.is_top_bybit_mode = lambda: False
    ui.update_scan_progress = lambda *args: None
    ui.schedule_scan_loop_calls = []
    ui.schedule_scan_loop = lambda delay=0: ui.schedule_scan_loop_calls.append(delay)
    ui.perf_log = lambda *args, **kwargs: None

    result = ui.create_scan_result_record(3, "BADUSDT", 0, "error", job_id=21)
    result.update({"total_symbols": 2, "error": "network failed"})

    assert ui.apply_scan_result(result) is True
    assert ui.refresh_index == 1
    assert ui.scan_worker_busy is False
    assert ui.schedule_scan_loop_calls == [0]


def test_scan_result_can_only_be_applied_on_ui_thread():

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    result = ui.create_scan_result_record(1, "BTCUSDT", 0, "no_signal")
    errors = []

    def apply_from_worker():

        try:
            ui.apply_scan_result(result)
        except Exception as error:
            errors.append(error)

    thread = threading.Thread(target=apply_from_worker)
    thread.start()
    thread.join()

    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)


def test_shutdown_stops_planning_without_waiting_for_worker():

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.app = FakeApp()
    ui.scan_after_id = "scan-after"
    ui.scan_result_after_id = "result-after"
    ui.initialize_scan_worker()
    worker = ui.scan_worker_thread

    ui.shutdown_app()
    ui.schedule_scan_loop(0)
    ui.schedule_scan_result_poll()

    assert worker.daemon is True
    assert ui.shutdown_requested is True
    assert ui.scan_shutdown_event.is_set()
    assert ui.app.destroyed is True
    assert ui.app.scheduled == []


def test_rsi_filter_can_change_while_worker_is_busy():

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.scan_worker_busy = True
    ui.rsi_view_option = Flag(RSI_VIEW_SORT)
    ui.rsi_sort_mode_label = None
    ui.buttons = []
    ui.is_top_bybit_mode = lambda: False

    ui.apply_rsi_view_option(RSI_VIEW_SORT)

    assert ui.current_rsi_view_option() == RSI_VIEW_SORT
    assert ui.scan_worker_busy is True
