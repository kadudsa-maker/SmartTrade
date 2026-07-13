import threading

from config import SCAN_INTERVAL_MS
from ui import SmartTradeUI


class FakeApp:

    def __init__(self):

        self.scheduled = []

    def after(self, delay_ms, callback):

        self.scheduled.append((delay_ms, callback))
        return len(self.scheduled)


def build_scan_ui(symbol_count=100, batch_size=2):

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.app = FakeApp()
    ui.refresh_index = 0
    ui.scan_batch_position = 0
    ui.scan_cycle_started_at = None
    ui.ui_thread_id = threading.get_ident()
    ui.shutdown_requested = False
    ui.current_scan_id = 1
    ui.current_scan_symbols = [f"COIN{index}" for index in range(symbol_count)]
    ui.current_scan_results = {}
    ui.current_scan_rendered = 0
    ui.active_scan_job_id = None
    ui.scan_worker_busy = False
    ui.scan_mode = "top100"
    ui.top_bybit_limit = symbol_count
    ui.last_scan_batch_time = None
    ui.get_scan_batch_size = lambda: batch_size
    ui.perf_log = lambda *args, **kwargs: None
    ui.is_top_bybit_mode = lambda: True
    ui.top50_results = {}
    ui.update_top50_result_card = lambda symbol: True
    ui.process_alert_candidate = lambda *args, **kwargs: False
    ui.sort_top50_cards_if_needed = lambda: None
    ui.mark_scan_cycle_completed = lambda count: None
    return ui


def test_top100_worker_results_do_not_add_scan_intervals():

    ui = build_scan_ui()

    for index in range(100):
        job_id = index + 1
        ui.active_scan_job_id = job_id
        ui.scan_worker_busy = True
        result = ui.create_scan_result_record(
            1,
            f"COIN{index}",
            index,
            "no_signal",
            interval="60",
            total_symbols=100,
            job_id=job_id,
            scan_range="top100"
        )
        ui.apply_scan_result(result)

    delays = [delay for delay, _callback in ui.app.scheduled]

    assert len(ui.current_scan_results) == 100
    assert delays.count(0) == 50
    assert delays.count(SCAN_INTERVAL_MS) == 50
    assert ui.refresh_index == 0
