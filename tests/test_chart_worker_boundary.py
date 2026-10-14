import threading

import pandas as pd

from ui import SmartTradeUI


class FakeChart:

    def __init__(self):
        self.calls = []

    def set_candles(self, frame, fvg_gaps=()):
        self.calls.append((frame, tuple(fvg_gaps)))


def sample_frame():
    return pd.DataFrame({
        "time": [1000, 2000],
        "open": [1.0, 2.0],
        "high": [2.0, 3.0],
        "low": [0.5, 1.5],
        "close": [1.5, 2.5],
        "volume": [10.0, 11.0],
    })


def chart_ui(*, start_worker=False):
    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.selected_symbol = "BTCUSDT"
    ui.selected_interval = "60"
    ui.active_exchange_id = "bybit"
    ui.display_symbol = lambda symbol: symbol
    ui.platform_market_name = lambda symbol: symbol
    ui.market_label = lambda *_args: "Bybit Futures"
    ui.asset_class = lambda _symbol: "crypto"
    ui.resolve_chart_fvg_gaps = lambda *_args: ()
    ui.update_open_chart_status = lambda *_args: None
    ui.perf_log = lambda *_args, **_kwargs: None
    ui.chart = FakeChart()
    if start_worker:
        ui.initialize_chart_worker()
    else:
        ui.chart_job_sequence = 0
        ui.chart_job_lock = threading.Lock()
        ui.chart_job_event = threading.Event()
        ui.pending_chart_job = None
        ui.active_chart_job_id = None
        ui.chart_worker_busy = False
    return ui


def stop_worker(ui):
    ui.chart_shutdown_event.set()
    ui.chart_job_event.set()
    ui.chart_worker_thread.join(timeout=1)


def test_refresh_selected_only_schedules_and_coalesces_latest_request():
    ui = chart_ui()
    ui.fetch_klines = lambda *_args: (_ for _ in ()).throw(
        AssertionError("network fetch must not run on the GUI thread")
    )

    assert ui.refresh_selected() is True
    ui.selected_symbol = "ETHUSDT"
    ui.selected_interval = "15"
    assert ui.refresh_selected() is True

    assert ui.pending_chart_job["job_id"] == 2
    assert ui.pending_chart_job["symbol"] == "ETHUSDT"
    assert ui.pending_chart_job["timeframe"] == "15"
    assert ui.active_chart_job_id == 2
    assert ui.chart_worker_busy is True


def test_chart_fetch_runs_off_ui_thread_and_rendering_stays_on_ui_thread():
    ui = chart_ui(start_worker=True)
    fetch_thread_ids = []

    def fetch(*_args):
        fetch_thread_ids.append(threading.get_ident())
        return sample_frame()

    ui.fetch_klines = fetch
    try:
        assert ui.refresh_selected() is True
        result = ui.chart_result_queue.get(timeout=1)
        assert fetch_thread_ids != [ui.ui_thread_id]
        assert ui.chart.calls == []
        assert ui.apply_chart_result(result) is True
        assert len(ui.chart.calls) == 1
        assert ui.chart_worker_busy is False
    finally:
        stop_worker(ui)

    assert ui.chart_worker_thread.is_alive() is False


def test_stale_chart_result_is_ignored():
    ui = chart_ui()
    ui.active_chart_job_id = 2
    ui.chart_worker_busy = True
    stale = {
        "job_id": 1,
        "symbol": "BTCUSDT",
        "timeframe": "60",
        "exchange_id": "bybit",
        "display_symbol": "BTCUSDT",
        "platform_market_name": "BTCUSDT",
        "exchange_name": "Bybit Futures",
        "asset_class": "crypto",
        "frame": sample_frame(),
        "error": None,
    }

    assert ui.apply_chart_result(stale) is False
    assert ui.active_chart_job_id == 2
    assert ui.chart_worker_busy is True
    assert ui.chart.calls == []


def test_chart_result_can_only_be_applied_on_ui_thread():
    ui = chart_ui()
    result = {"job_id": 1}
    errors = []

    def apply_from_worker():
        try:
            ui.apply_chart_result(result)
        except Exception as error:
            errors.append(error)

    worker = threading.Thread(target=apply_from_worker)
    worker.start()
    worker.join()

    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)


def test_chart_worker_is_single_daemon_and_stops_while_idle():
    ui = chart_ui(start_worker=True)
    worker = ui.chart_worker_thread
    stop_worker(ui)

    assert worker.daemon is True
    assert worker.name == "SmartTradeChartLoader"
    assert worker.is_alive() is False
