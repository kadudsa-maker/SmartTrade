import customtkinter as ctk
from queue import Empty, Queue
import threading
import time
from tkinter import BooleanVar, StringVar, TclError, messagebox

from alerts import AlertManager
from app_paths import configure_windows_window_icon
from chart import SmartTradeChart
from config import (
    ACTIVE_MAX_CANDLES,
    AGING_MAX_CANDLES,
    MIN_VISIBLE_QUALITY,
    PERF_DEBUG,
    PIVOT_LEFT,
    PIVOT_RIGHT,
    SCAN_BATCH_SIZE,
    SCAN_INTERVAL_MS,
    SHOW_EXPIRED_SIGNALS,
    TOP_SCAN_BATCH_SIZES,
    TOP_SORT_INTERVAL_MS
)
from divergence import find_regular_divergences
from fvg import Candle, FVGDirection, FVGOpportunityStatus, FVGService
from market import (
    calculate_rsi,
    filter_symbols,
    get_all_bybit_symbols,
    get_exchange_provider,
    get_instruments,
    get_klines,
    get_top_symbols,
    get_top_bybit_symbols,
    get_top_bybit_last_error,
    get_watchlist,
    reset_watchlist,
    save_watchlist
)
from pivots import find_pivots, find_rsi_pivots
from rsi import calculate_rsi_series
from scanner_state import next_scan_index, scan_mode_label
from signal_quality import calculate_quality_score
from strings import (
    ALERTS_BUTTON,
    APP_TITLE,
    BYBIT_FETCH_TOP_EMPTY,
    BYBIT_FETCH_TOP_ERROR,
    BYBIT_TOP_WARNING,
    CANCEL_BUTTON,
    CLOSE_BUTTON,
    COIN_LIST_EMPTY,
    COIN_LIST_ERROR,
    COIN_NO_RESULTS,
    COIN_SEARCH_LABEL,
    COIN_SELECTOR_HEADER,
    COIN_SELECTOR_TITLE,
    GUIDE_BUTTON,
    GUIDE_CONTENT,
    GUIDE_NOTE,
    GUIDE_TITLE,
    MINIMUM_QUALITY_ERROR,
    OPEN_CHART,
    OPEN_CHART_EMPTY,
    PL_TIME,
    PL_TIME_LABEL,
    RESET_TOP20_BUTTON,
    SAVE_BUTTON,
    SCAN_LOADING_BYBIT,
    SCAN_READY,
    SCAN_START,
    WATCHLIST_EMPTY,
    WATCHLIST_RESET_CONFIRM,
    WATCHLIST_RESET_ERROR,
    WATCHLIST_SAVE_ERROR
)
from time_utils import current_polish_time, format_polish_time


def clamp_alert_quality(value):

    return max(0, min(100, int(value)))


BG_COLOR = "#111315"
PANEL_COLOR = "#181A1F"
BORDER_COLOR = "#2A2E36"
TEXT_COLOR = "#EAEAEA"
MUTED_TEXT_COLOR = "#8D96A0"
GREEN = "#2ECC71"
RED = "#E74C3C"
ORANGE = "#E67E22"
BLUE = "#3498DB"
GRAY = "#6E7681"
CARD_HEIGHT = 62
STATUS_FILTERED_COLOR = "#4B525C"
RSI_QUALITY_PRIORITY_THRESHOLD = 65

SCAN_MODE_WATCHLIST = "watchlist"
SCAN_MODE_TOP_BYBIT = "top_bybit"
SCAN_MODE_TOP50 = "top50"
SCAN_MODE_TOP100 = "top100"
SCAN_MODE_TOP200 = "top200"
TOP_BYBIT_LIMITS = {
    SCAN_MODE_TOP50: 50,
    SCAN_MODE_TOP100: 100,
    SCAN_MODE_TOP200: 200
}
TOP_BYBIT_MODES_BY_LIMIT = {
    50: SCAN_MODE_TOP50,
    100: SCAN_MODE_TOP100,
    200: SCAN_MODE_TOP200
}
SCAN_RESULT_POLL_MS = 15
ALERT_SCAN_RANGES = [
    (SCAN_MODE_WATCHLIST, "Watchlist"),
    (SCAN_MODE_TOP50, "Top 50"),
    (SCAN_MODE_TOP100, "Top 100"),
    (SCAN_MODE_TOP200, "Top 200")
]
RSI_VIEW_OFF = "RSI OFF"
RSI_VIEW_ON = "RSI ON"
RSI_VIEW_SORT = "RSI Sort"
RSI_VIEW_QUALITY_SORT = "RSI + Quality Sort"
RSI_SORT_MODE_QUALITY = "quality"
RSI_SORT_MODE_RSI = "rsi"
RSI_SORT_MODE_RSI_QUALITY = "rsi_quality"
DEFAULT_SCAN_MODE = SCAN_MODE_TOP100
DEFAULT_TOP_BYBIT_LIMIT = 100
DEFAULT_TIMEFRAME = "60"
DEFAULT_RSI_VIEW_OPTION = RSI_VIEW_ON
DEFAULT_RSI_SORT_MODE = RSI_SORT_MODE_QUALITY
DEFAULT_EXCHANGE_ID = "bybit"
FVG_INTERVAL_SECONDS = {
    "1": 60,
    "5": 5 * 60,
    "15": 15 * 60,
    "30": 30 * 60,
    "60": 60 * 60,
    "240": 4 * 60 * 60,
    "D": 24 * 60 * 60,
}
EXCHANGE_OPTIONS = {
    "Bybit Futures": "bybit",
    "OKX Perpetual": "okx",
    "OKX Spot": "okx_spot",
}


class SmartTradeUI:

    def __init__(self):

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.app = ctk.CTk()
        self.set_window_icon()
        self.app.after(250, self.set_window_icon)
        self.app.geometry("1400x800")
        self.app.title(APP_TITLE)
        self.app.configure(fg_color=BG_COLOR)

        self.selected_symbol = None
        self.active_exchange_id = DEFAULT_EXCHANGE_ID
        self.instrument_by_symbol = {}
        self.selected_interval = DEFAULT_TIMEFRAME
        self.scan_mode = DEFAULT_SCAN_MODE
        self.top_bybit_limit = DEFAULT_TOP_BYBIT_LIMIT

        self.watchlist_symbols = get_watchlist(self.active_exchange_id)
        self.top50_symbols = []
        self.top50_results = {}
        self.coins = [{"symbol": coin} for coin in self.watchlist_symbols]
        self.buttons = []
        self.cards_by_symbol = {}
        self.last_card_texts = {}
        self.timeframe_buttons = {}
        self.scan_mode_buttons = {}
        self.top_limit_buttons = {}
        self.top_limit_container = None
        self.top_time_label = None
        self.top_timeframe_label = None
        self.open_chart_label = None
        self.watchlist_scroll = None
        self.watchlist_title_label = None
        self.reset_watchlist_button = None
        self.alert_notification_status_label = None
        self.alert_sound_status_label = None
        self.scan_button = None
        self.scan_status_label = None
        self.scan_progress_label = None
        self.rsi_view_option = StringVar(value=DEFAULT_RSI_VIEW_OPTION)
        self.rsi_view_menu = None
        self.rsi_sort_mode = DEFAULT_RSI_SORT_MODE
        self.rsi_sort_mode_label = None

        self.refresh_index = 0
        self.last_top50_sort_at = 0
        self.last_top50_order = []
        self.scan_cycle_started_at = None
        self.scan_cycle_number = 0
        self.last_scan_batch_time = None
        self.last_full_scan_time = None
        self.scan_after_id = None
        self.scan_result_after_id = None
        self.scan_batch_position = 0
        self.scan_generation = 0
        self.current_scan_id = 0
        self.current_scan_symbols = []
        self.current_scan_results = {}
        self.current_scan_rendered = 0
        self.scan_cycle_alert_sent_count = 0
        self.scan_job_sequence = 0
        self.active_scan_job_id = None
        self.scan_worker_busy = False
        self.ui_thread_id = threading.get_ident()
        self.max_scan_ui_callback_ms = 0
        self.initialize_scan_worker()
        self.app.protocol("WM_DELETE_WINDOW", self.shutdown_app)
        self.alert_manager = AlertManager(
            default_timeframe=self.selected_interval,
            default_scan_range=self.get_alert_scan_range()
        )
        self.alert_settings_window = None

        if self.is_top_bybit_mode():
            self.load_top50_scan_symbols()

        self.build_ui()

    def set_window_icon(self):

        configure_windows_window_icon(self.app)

    def get_active_exchange_id(self):

        return getattr(self, "active_exchange_id", DEFAULT_EXCHANGE_ID)

    def active_provider(self):

        return get_exchange_provider(self.get_active_exchange_id())

    def active_exchange_option(self):

        exchange_id = self.get_active_exchange_id()
        return next(
            label for label, value in EXCHANGE_OPTIONS.items() if value == exchange_id
        )

    def select_exchange(self, option):

        target_exchange_id = EXCHANGE_OPTIONS.get(option, option)
        if target_exchange_id == self.get_active_exchange_id():
            return True

        target_provider = get_exchange_provider(target_exchange_id)
        if not hasattr(self, "app"):
            return self.switch_exchange_now(target_exchange_id, target_provider)

        if self.exchange_menu is not None:
            self.exchange_menu.configure(state="disabled")
        self.update_scan_status(f"Loading {target_provider.display_name}...", MUTED_TEXT_COLOR)
        threading.Thread(
            target=self.prepare_exchange_switch,
            args=(target_exchange_id, target_provider),
            name="SmartTradeExchangeLoader",
            daemon=True
        ).start()
        return True

    def prepare_exchange_switch(self, target_exchange_id, target_provider):

        try:
            prepared = self.load_exchange_symbols(target_exchange_id, target_provider)
        except Exception as error:
            self.app.after(
                0, lambda: self.finish_exchange_switch_error(target_provider, error)
            )
            return
        self.app.after(
            0,
            lambda: self.apply_exchange_switch(
                target_exchange_id, target_provider, *prepared
            )
        )

    def load_exchange_symbols(self, target_exchange_id, target_provider):

        instruments = [
            item for item in target_provider.get_instruments(force=True)
            if self.instrument_matches_exchange(item, target_exchange_id)
        ]
        instrument_by_symbol = {item.exchange_symbol: item for item in instruments}
        if self.scan_mode == SCAN_MODE_WATCHLIST:
            symbols = self.filter_provider_symbols(
                get_watchlist(target_exchange_id),
                exchange_id=target_exchange_id,
                instrument_by_symbol=instrument_by_symbol,
            )
            if not symbols:
                defaults = target_provider.get_top_symbols(20)
                save_watchlist(defaults, exchange_id=target_exchange_id)
                symbols = [item.exchange_symbol for item in defaults]
        else:
            symbols = [
                item.exchange_symbol
                for item in target_provider.get_top_symbols(self.top_bybit_limit)
            ]
        if not symbols:
            raise RuntimeError("The exchange returned an empty scan list.")
        return instrument_by_symbol, symbols

    def switch_exchange_now(self, target_exchange_id, target_provider):

        try:
            prepared = self.load_exchange_symbols(target_exchange_id, target_provider)
        except Exception as error:
            self.finish_exchange_switch_error(target_provider, error)
            return False
        self.apply_exchange_switch(target_exchange_id, target_provider, *prepared)
        return True

    def finish_exchange_switch_error(self, target_provider, error):

        if self.exchange_menu is not None:
            self.exchange_menu.configure(state="normal")
            self.exchange_menu.set(self.active_exchange_option())
        message = f"Could not switch to {target_provider.display_name}.\n\n{error}"
        self.update_scan_status(f"{target_provider.display_name} connection error", RED)
        messagebox.showerror(APP_TITLE, message)

    def apply_exchange_switch(
        self, target_exchange_id, target_provider, instrument_by_symbol, symbols
    ):

        self.cancel_scan_loop()
        self.active_exchange_id = target_exchange_id
        self.instrument_by_symbol = instrument_by_symbol
        self.selected_symbol = None
        self.clear_chart_fvg()
        if self.scan_mode == SCAN_MODE_WATCHLIST:
            self.watchlist_symbols = symbols
        else:
            self.top50_symbols = symbols
        self.coins = [{"symbol": symbol} for symbol in symbols]
        self.reset_scan_state_for_new_run()
        self.begin_scan_generation(symbols)
        self.clear_watchlist_cards()
        self.build_watchlist_cards()
        self.update_scan_mode_buttons()
        self.update_open_chart_status(current_polish_time())
        self.update_scan_status(f"SCAN: {target_provider.display_name}", GREEN)
        self.update_scan_progress(None, 0, len(symbols))
        if self.exchange_menu is not None:
            self.exchange_menu.configure(state="normal")
            self.exchange_menu.set(self.active_exchange_option())
        self.schedule_scan_loop(0)

    def display_symbol(self, exchange_symbol):

        instrument = getattr(self, "instrument_by_symbol", {}).get(exchange_symbol)
        return instrument.display_symbol if instrument is not None else exchange_symbol

    def platform_market_name(self, exchange_symbol):

        instrument = getattr(self, "instrument_by_symbol", {}).get(exchange_symbol)
        if instrument is not None and instrument.platform_market_name:
            return instrument.platform_market_name
        return self.display_symbol(exchange_symbol)

    def asset_class(self, exchange_symbol):

        instrument = getattr(self, "instrument_by_symbol", {}).get(exchange_symbol)
        return instrument.asset_class if instrument is not None else "other"

    def asset_class_label(self, exchange_symbol):

        return self.asset_class(exchange_symbol).upper()

    def market_badge(self, exchange_symbol=None):

        badge = {
            "bybit": "BYBIT",
            "okx": "OKX PERP",
            "okx_spot": "SPOT",
        }.get(self.get_active_exchange_id(), self.active_provider().display_name.upper())
        if exchange_symbol and self.get_active_exchange_id() == "okx":
            return f"{badge} · {self.asset_class_label(exchange_symbol)}"
        return badge

    def market_label(self, exchange_id=None):

        return {
            "bybit": "Bybit Futures",
            "okx": "OKX Perpetual",
            "okx_spot": "OKX SPOT",
        }.get(exchange_id or self.get_active_exchange_id(), self.active_provider().display_name)

    def instrument_matches_exchange(self, instrument, exchange_id=None):

        exchange_id = exchange_id or self.get_active_exchange_id()
        if instrument.exchange_id != exchange_id:
            return False
        if exchange_id == "okx":
            return (
                instrument.instrument_type == "futures"
                and instrument.metadata.get("instrument_scope") == "public_eea"
                and instrument.metadata.get("ruleType") == "xperp"
            )
        if exchange_id == "okx_spot":
            return (
                instrument.instrument_type == "spot"
                and not instrument.exchange_symbol.endswith("-SWAP")
                and not instrument.platform_market_name.endswith(" UM")
            )
        return True

    def filter_provider_symbols(
        self, symbols, *, exchange_id=None, instrument_by_symbol=None
    ):

        exchange_id = exchange_id or self.get_active_exchange_id()
        instrument_by_symbol = (
            instrument_by_symbol
            if instrument_by_symbol is not None
            else getattr(self, "instrument_by_symbol", {})
        )
        if exchange_id not in ("okx", "okx_spot") or not instrument_by_symbol:
            return list(symbols)
        return [
            symbol for symbol in symbols
            if symbol in instrument_by_symbol
            and self.instrument_matches_exchange(
                instrument_by_symbol[symbol], exchange_id
            )
        ]

    def fetch_klines(self, symbol, interval, exchange_id=None):

        exchange_id = exchange_id or self.get_active_exchange_id()
        try:
            return get_klines(symbol, interval=interval, exchange_id=exchange_id)
        except TypeError as error:
            # Compatibility for tests/extensions still providing the legacy 2-argument hook.
            if exchange_id == "bybit" and "exchange_id" in str(error):
                return get_klines(symbol, interval=interval)
            raise

    def perf_log(self, label, started_at, **fields):

        if not PERF_DEBUG:
            return

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        details = " ".join(
            f"{key}={value}"
            for key, value in fields.items()
        )

        if details:
            print(f"PERF {label}: {elapsed_ms:.1f}ms {details}")
        else:
            print(f"PERF {label}: {elapsed_ms:.1f}ms")

    def select_timeframe(self, interval):

        self.cancel_scan_loop()
        self.clear_fvg_card_sections()
        self.clear_chart_fvg()
        self.selected_interval = interval
        self.refresh_index = 0
        self.top50_results = {}
        self.last_top50_sort_at = time.monotonic()
        self.reset_scan_cycle_state()
        if self.is_top_bybit_mode():
            self.coins = [{"symbol": symbol} for symbol in self.top50_symbols]
            self.build_watchlist_cards()

        self.update_timeframe_buttons()
        self.refresh_selected()
        self.begin_scan_generation()
        self.schedule_scan_loop(0)

    def update_timeframe_buttons(self):

        for interval, button in self.timeframe_buttons.items():

            if interval == self.selected_interval:
                button.configure(fg_color=BLUE, text_color="#FFFFFF", border_color=BLUE)

            else:
                button.configure(fg_color=PANEL_COLOR, text_color=MUTED_TEXT_COLOR, border_color=BORDER_COLOR)

        if self.top_timeframe_label is not None:
            self.top_timeframe_label.configure(
                text=f"TimeFrame: {self.interval_label(self.selected_interval)}"
            )

    def select_coin(self, symbol):

        self.clear_chart_fvg()
        self.selected_symbol = symbol
        self.alert_manager.mark_opened_for_symbol(symbol, self.get_active_exchange_id())

        self.refresh_selected()

    def refresh_selected(self):

        if self.selected_symbol is None:
            return

        fetch_started_at = time.perf_counter()
        df = self.fetch_klines(self.selected_symbol, self.selected_interval)
        self.perf_log(
            "chart_fetch",
            fetch_started_at,
            symbol=self.selected_symbol,
            timeframe=self.selected_interval
        )
        df.attrs["symbol"] = self.selected_symbol
        df.attrs["timeframe"] = self.selected_interval
        df.attrs["display_symbol"] = self.display_symbol(self.selected_symbol)
        df.attrs["platform_market_name"] = self.platform_market_name(
            self.selected_symbol
        )
        df.attrs["exchange_id"] = self.get_active_exchange_id()
        df.attrs["exchange_name"] = self.market_label()
        df.attrs["asset_class"] = self.asset_class(self.selected_symbol)

        chart_fvg_gaps = self.resolve_chart_fvg_gaps(
            df,
            self.selected_symbol,
            self.selected_interval,
        )
        chart_started_at = time.perf_counter()
        self.chart.set_candles(df, fvg_gaps=chart_fvg_gaps)
        self.perf_log(
            "chart_set_candles",
            chart_started_at,
            symbol=self.selected_symbol,
            timeframe=self.selected_interval
        )
        self.update_open_chart_status(current_polish_time())

    def matching_chart_scan_record(self, symbol, interval):

        record = getattr(self, "current_scan_results", {}).get(symbol)
        if record is None:
            return None

        exchange_symbol = record.get("exchange_symbol", record.get("symbol"))
        if (
            record.get("scan_id") != getattr(self, "current_scan_id", None)
            or record.get("exchange_id") != self.get_active_exchange_id()
            or exchange_symbol != symbol
            or record.get("interval") != interval
            or record.get("market_label") != self.market_label()
        ):
            return None
        return record

    def resolve_chart_fvg_gaps(self, df, symbol, interval):

        record = self.matching_chart_scan_record(symbol, interval)
        if record is not None:
            fvg_result = record.get("fvg_result")
            return () if fvg_result is None else tuple(fvg_result.gaps)

        try:
            candles = self.prepare_engine_candles(df, interval=interval)
            closed, current, previous = self.prepare_fvg_candles(candles, interval)
            return tuple(FVGService().analyze(closed, current, previous).gaps)
        except Exception as error:
            print(
                "FVG chart analysis error: "
                f"symbol={symbol} "
                f"exchange_id={self.get_active_exchange_id()} "
                f"timeframe={interval} "
                f"error_type={type(error).__name__} "
                f"error_message={error}"
            )
            return ()

    def clear_chart_fvg(self):

        chart = getattr(self, "chart", None)
        if chart is not None and hasattr(chart, "set_fvg_gaps"):
            chart.set_fvg_gaps(())

    def update_selected_chart_fvg(self, result):

        symbol = result.get("exchange_symbol", result.get("symbol"))
        if symbol != getattr(self, "selected_symbol", None):
            return False
        if self.matching_chart_scan_record(symbol, self.selected_interval) is not result:
            return False

        chart = getattr(self, "chart", None)
        if chart is None or not hasattr(chart, "set_fvg_gaps"):
            return False
        fvg_result = result.get("fvg_result")
        chart.set_fvg_gaps(() if fvg_result is None else fvg_result.gaps)
        return True

    def initialize_scan_worker(self):

        self.shutdown_requested = False
        self.scan_result_queue = Queue()
        self.scan_job_lock = threading.Lock()
        self.scan_job_event = threading.Event()
        self.scan_shutdown_event = threading.Event()
        self.pending_scan_job = None
        self.scan_worker_thread = threading.Thread(
            target=self.scan_worker_loop,
            name="SmartTradeScanner",
            daemon=True
        )
        self.scan_worker_thread.start()

    def scan_worker_loop(self):

        while not self.scan_shutdown_event.is_set():
            self.scan_job_event.wait()

            if self.scan_shutdown_event.is_set():
                break

            with self.scan_job_lock:
                job = self.pending_scan_job
                self.pending_scan_job = None
                self.scan_job_event.clear()

            if job is None:
                continue

            try:
                result = self.update_watchlist_coin(
                    {"symbol": job["symbol"]},
                    job["index"],
                    scan_id=job["scan_id"],
                    interval=job["interval"],
                    total_symbols=job["total_symbols"],
                    job_id=job["job_id"],
                    scan_range=job["scan_range"],
                    exchange_id=job["exchange_id"],
                    display_symbol=job["display_symbol"],
                    market_label=job["market_label"],
                    platform_market_name=job["platform_market_name"],
                    asset_class=job["asset_class"]
                )
            except Exception as error:
                result = self.create_scan_result_record(
                    job["scan_id"],
                    job["symbol"],
                    job["index"],
                    "error",
                    interval=job["interval"],
                    total_symbols=job["total_symbols"],
                    job_id=job["job_id"],
                    scan_range=job["scan_range"],
                    exchange_id=job["exchange_id"],
                    display_symbol=job["display_symbol"],
                    market_label=job["market_label"],
                    platform_market_name=job["platform_market_name"],
                    asset_class=job["asset_class"]
                )
                result["error"] = f"{type(error).__name__}: {error}"

            if not self.scan_shutdown_event.is_set():
                self.scan_result_queue.put(result)

    def begin_scan_generation(self, symbols=None):

        self.scan_generation += 1
        self.current_scan_id = self.scan_generation
        self.current_scan_symbols = list(
            self.get_scan_symbols() if symbols is None else symbols
        )
        self.current_scan_results = {}
        self.current_scan_rendered = 0
        self.scan_cycle_alert_sent_count = 0
        self.clear_scan_result_queue()
        return self.current_scan_id

    def clear_scan_result_queue(self):

        while True:
            try:
                result = self.scan_result_queue.get_nowait()
            except Empty:
                return

            if result.get("job_id") == self.active_scan_job_id:
                self.active_scan_job_id = None
                self.scan_worker_busy = False

    def create_scan_result_record(
        self,
        scan_id,
        symbol,
        index,
        status,
        *,
        interval=None,
        total_symbols=0,
        job_id=None,
        scan_range=None,
        exchange_id=None,
        display_symbol=None,
        market_label=None,
        platform_market_name=None,
        asset_class=None
    ):

        exchange_id = exchange_id or self.get_active_exchange_id()
        return {
            "scan_id": scan_id,
            "exchange_id": exchange_id,
            "job_id": job_id,
            "symbol": symbol,
            "exchange_symbol": symbol,
            "display_symbol": display_symbol or self.display_symbol(symbol),
            "platform_market_name": (
                platform_market_name or self.platform_market_name(symbol)
            ),
            "market_label": market_label or self.market_label(exchange_id),
            "asset_class": asset_class or self.asset_class(symbol),
            "interval": interval,
            "index": index,
            "total_symbols": total_symbols,
            "status": status,
            "rsi": None,
            "divergence": None,
            "candle_count": 0,
            "quality": None,
            "candles_ago": None,
            "signal_status": "",
            "alert_candidate": None,
            "scan_range": scan_range,
            "ui_visible": False,
            "fvg_result": None,
            "fvg_status": "",
            "selected_fvg": None,
            "error": None,
            "worker_duration_ms": 0
        }

    def scan_one_coin(self):

        self.scan_after_id = None

        if self.shutdown_requested or self.scan_worker_busy:
            return

        if not self.current_scan_symbols:
            self.begin_scan_generation()

        if not self.current_scan_symbols:
            return

        if self.refresh_index >= len(self.current_scan_symbols):
            self.refresh_index = 0

        if self.scan_cycle_started_at is None:
            self.scan_cycle_started_at = time.perf_counter()

        symbol = self.current_scan_symbols[self.refresh_index]
        self.scan_symbol_with_progress(
            symbol,
            self.refresh_index,
            len(self.current_scan_symbols)
        )

    def scan_symbol_with_progress(self, symbol, index, total_symbols):

        if self.shutdown_requested or self.scan_worker_busy:
            return False

        self.update_scan_progress(symbol, index, total_symbols)
        self.scan_job_sequence += 1
        job = {
            "scan_id": self.current_scan_id,
            "job_id": self.scan_job_sequence,
            "symbol": symbol,
            "interval": self.selected_interval,
            "index": index,
            "total_symbols": total_symbols,
            "scan_range": self.get_alert_scan_range(),
            "exchange_id": self.get_active_exchange_id(),
            "display_symbol": self.display_symbol(symbol),
            "market_label": self.market_label(),
            "platform_market_name": self.platform_market_name(symbol),
            "asset_class": self.asset_class(symbol)
        }

        with self.scan_job_lock:
            if self.pending_scan_job is not None:
                return False
            self.pending_scan_job = job
            self.active_scan_job_id = job["job_id"]
            self.scan_worker_busy = True
            self.scan_job_event.set()

        return True

    def process_scan_results(self):

        self.scan_result_after_id = None

        if self.shutdown_requested:
            return

        callback_started_at = time.perf_counter()
        try:
            while True:
                try:
                    result = self.scan_result_queue.get_nowait()
                except Empty:
                    break
                self.apply_scan_result(result)
        finally:
            callback_ms = (time.perf_counter() - callback_started_at) * 1000
            self.max_scan_ui_callback_ms = max(self.max_scan_ui_callback_ms, callback_ms)
            self.schedule_scan_result_poll()

    def apply_scan_result(self, result):

        if threading.get_ident() != self.ui_thread_id:
            raise RuntimeError("Scan results must be applied on the Tk main thread.")

        if self.shutdown_requested:
            return False

        is_active_job = result.get("job_id") == self.active_scan_job_id
        if is_active_job:
            self.active_scan_job_id = None
            self.scan_worker_busy = False

        exchange_symbol = result.get("exchange_symbol", result.get("symbol"))
        active_symbols = getattr(self, "current_scan_symbols", [])
        active_instruments = getattr(self, "instrument_by_symbol", {})
        if (
            result.get("scan_id") != self.current_scan_id
            or result.get("exchange_id", DEFAULT_EXCHANGE_ID) != self.get_active_exchange_id()
            or (active_symbols and exchange_symbol not in active_symbols)
            or (active_instruments and exchange_symbol not in active_instruments)
        ):
            if is_active_job:
                self.schedule_scan_loop(0)
            return False

        callback_started_at = time.perf_counter()
        symbol = result["symbol"]
        index = result["index"]
        if not hasattr(self, "current_scan_results"):
            self.current_scan_results = {}
        if not hasattr(self, "current_scan_rendered"):
            self.current_scan_rendered = 0
        self.current_scan_results[symbol] = result
        self.current_scan_rendered += 1
        self.update_selected_chart_fvg(result)

        if result["status"] == "error":
            print(f"Scan symbol error: {symbol}: {result['error']}")
        else:
            ui_ready = False
            if self.is_top_bybit_mode():
                self.top50_results[symbol] = {
                    "symbol": symbol,
                    "exchange_id": result["exchange_id"],
                    "exchange_symbol": result["exchange_symbol"],
                    "display_symbol": result["display_symbol"],
                    "platform_market_name": result["platform_market_name"],
                    "market_label": result["market_label"],
                    "asset_class": result["asset_class"],
                    "rsi": result["rsi"],
                    "divergence": result["divergence"],
                    "candle_count": result["candle_count"],
                    "fvg_result": result["fvg_result"],
                    "fvg_status": result["fvg_status"],
                    "selected_fvg": result["selected_fvg"]
                }
                ui_ready = self.update_top50_result_card(symbol)
            elif index < len(self.buttons):
                ui_ready = self.update_watchlist_card(
                    index,
                    symbol,
                    result["rsi"],
                    result["divergence"],
                    result["candle_count"],
                    fvg_result=result["fvg_result"],
                    fvg_status=result["fvg_status"],
                    selected_fvg=result["selected_fvg"]
                )

            self.process_alert_candidate(
                symbol,
                result["alert_candidate"],
                result["candle_count"],
                ui_ready=ui_ready,
                interval=result["interval"],
                scan_range=result["scan_range"],
                exchange_id=result["exchange_id"]
            )

        self.refresh_index, completed_cycle = next_scan_index(
            index,
            len(self.current_scan_symbols)
        )
        self.scan_batch_position += 1
        continue_current_batch = (
            not completed_cycle
            and self.scan_batch_position < self.get_scan_batch_size()
        )

        if not continue_current_batch:
            self.scan_batch_position = 0

        self.last_scan_batch_time = current_polish_time()

        if self.is_top_bybit_mode() and not continue_current_batch:
            self.sort_top50_cards_if_needed()

        if completed_cycle:
            self.mark_scan_cycle_completed(len(self.current_scan_symbols))

        self.perf_log(
            "scan_result_ui",
            callback_started_at,
            mode=scan_mode_label(self.scan_mode, self.top_bybit_limit),
            symbol=symbol
        )
        delay_ms = 0 if continue_current_batch else SCAN_INTERVAL_MS
        self.schedule_scan_loop(delay_ms)
        return True

    def schedule_scan_loop(self, delay_ms=SCAN_INTERVAL_MS):

        if self.shutdown_requested:
            return

        self.scan_after_id = self.app.after(delay_ms, self.scan_one_coin)

    def schedule_scan_result_poll(self):

        if self.shutdown_requested or self.scan_result_after_id is not None:
            return

        self.scan_result_after_id = self.app.after(
            SCAN_RESULT_POLL_MS,
            self.process_scan_results
        )

    def cancel_scan_result_poll(self):

        if self.scan_result_after_id is None:
            return

        try:
            self.app.after_cancel(self.scan_result_after_id)
        except Exception:
            pass
        self.scan_result_after_id = None

    def cancel_scan_loop(self):

        scan_after_id = getattr(self, "scan_after_id", None)

        if scan_after_id is None:
            return

        try:
            self.app.after_cancel(scan_after_id)
        except Exception:
            pass

        self.scan_after_id = None

    def restart_scan(self):

        self.scan_now()

    def scan_now(self):

        self.update_scan_status(
            f"SCAN: loading {self.active_provider().display_name}...",
            MUTED_TEXT_COLOR
        )
        prepared = self.prepare_scan_queue_for_restart()

        if not prepared:
            return

        self.cancel_scan_loop()
        self.reset_scan_state_for_new_run()
        self.begin_scan_generation()
        self.clear_watchlist_cards()
        self.build_watchlist_cards()
        self.update_scan_status(SCAN_START, GREEN)
        self.update_scan_progress(None, 0, len(self.get_scan_symbols()))
        self.schedule_scan_loop(0)

    def reset_scan_state_for_new_run(self):

        self.refresh_index = 0
        self.top50_results = {}
        self.last_top50_sort_at = time.monotonic()
        self.last_top50_order = []
        self.reset_scan_cycle_state()
        self.last_card_texts = {}

    def reload_scan_queue(self):

        if self.scan_mode == SCAN_MODE_WATCHLIST:
            self.watchlist_symbols = self.filter_provider_symbols(
                get_watchlist(self.get_active_exchange_id())
            )
            self.coins = [{"symbol": symbol} for symbol in self.watchlist_symbols]
            return

        self.load_top50_scan_symbols()

    def prepare_scan_queue_for_restart(self):

        try:
            if self.scan_mode == SCAN_MODE_WATCHLIST:
                symbols = self.filter_provider_symbols(
                    get_watchlist(self.get_active_exchange_id())
                )

                if not symbols:
                    self.show_scan_connection_error(WATCHLIST_EMPTY)
                    return False

                self.watchlist_symbols = symbols
                self.coins = [{"symbol": symbol} for symbol in symbols]
                return True

            if self.get_active_exchange_id() == "bybit":
                symbols = get_top_bybit_symbols(self.top_bybit_limit)
            else:
                symbols = [
                    item.exchange_symbol
                    for item in get_top_symbols(
                        self.get_active_exchange_id(), self.top_bybit_limit
                    )
                ]

        except Exception as error:
            self.show_scan_connection_error(
                f"Could not fetch Top {self.top_bybit_limit} "
                f"{self.active_provider().display_name}: {error}"
            )
            return False

        if not symbols:
            last_error = (
                get_top_bybit_last_error()
                if self.get_active_exchange_id() == "bybit" else None
            )
            if last_error is not None:
                self.show_scan_connection_error(
                    f"Could not fetch Top {self.top_bybit_limit} "
                    f"{self.active_provider().display_name}: {last_error}"
                )
            else:
                self.show_scan_connection_error(
                    f"{self.active_provider().display_name} returned no Top "
                    f"{self.top_bybit_limit} symbols."
                )
            return False

        self.top50_symbols = symbols
        self.coins = [{"symbol": symbol} for symbol in symbols]
        return True

    def show_scan_connection_error(self, message):

        exchange_label = (
            "Bybit" if self.get_active_exchange_id() == "bybit"
            else self.active_provider().display_name
        )
        print(f"{exchange_label} connection error: {message}")
        self.update_scan_status(f"{exchange_label} connection error", RED)
        messagebox.showerror(APP_TITLE, message)

    def update_scan_status(self, text, color=MUTED_TEXT_COLOR):

        if self.scan_status_label is None:
            return

        self.configure_label_if_changed(
            self.scan_status_label,
            text=text,
            text_color=color
        )

    def update_scan_progress(self, symbol, index, total_symbols):

        if getattr(self, "scan_progress_label", None) is None:
            return

        if not symbol or total_symbols <= 0:
            text = "0/0"
        else:
            text = f"{index + 1}/{total_symbols}"

        self.configure_label_if_changed(
            self.scan_progress_label,
            text=text,
            text_color=GREEN
        )

    def clear_watchlist_cards(self):

        for card in getattr(self, "buttons", []):
            card["frame"].destroy()

        self.buttons = []
        self.cards_by_symbol = {}
        self.last_card_texts = {}

    def mark_scan_cycle_completed(self, symbol_count):

        cycle_started_at = self.scan_cycle_started_at
        self.scan_cycle_number += 1
        self.last_full_scan_time = current_polish_time()

        print(
            "Scan cycle completed: "
            f"mode={scan_mode_label(self.scan_mode, self.top_bybit_limit)} "
            f"symbols={symbol_count} "
            f"cycle={self.scan_cycle_number} "
            f"time={self.last_full_scan_time}"
        )
        if cycle_started_at is not None:
            self.perf_log(
                "scan_cycle",
                cycle_started_at,
                mode=scan_mode_label(self.scan_mode, self.top_bybit_limit),
                symbols=symbol_count,
                cycle=self.scan_cycle_number
            )
        self.scan_cycle_started_at = None

    def reset_scan_cycle_state(self):

        self.scan_cycle_number = 0
        self.scan_batch_position = 0
        self.scan_cycle_started_at = None
        self.last_scan_batch_time = None
        self.last_full_scan_time = None

    def get_scan_symbols(self):

        # Watchlist scans exactly in the user's saved order.
        if self.scan_mode == SCAN_MODE_WATCHLIST:
            return self.watchlist_symbols

        # Top Bybit scans the fixed Bybit list, while cards are ranked separately.
        return self.top50_symbols

    def get_scan_batch_size(self):

        if not self.is_top_bybit_mode():
            return SCAN_BATCH_SIZE

        return TOP_SCAN_BATCH_SIZES.get(self.top_bybit_limit, 1)

    def set_scan_mode(self, mode):

        if mode == SCAN_MODE_TOP_BYBIT:
            if self.is_top_bybit_mode():
                return

            mode = self.get_top_bybit_mode()

        if mode == self.scan_mode:
            return

        self.cancel_scan_loop()
        self.scan_mode = mode
        self.refresh_index = 0
        self.top50_results = {}
        self.last_top50_sort_at = time.monotonic()
        self.reset_scan_cycle_state()

        if self.is_top_bybit_mode():
            self.top_bybit_limit = self.get_top_bybit_limit()
            self.load_top50_scan_symbols()
        else:
            self.watchlist_symbols = self.filter_provider_symbols(
                get_watchlist(self.get_active_exchange_id())
            )
            self.coins = [{"symbol": coin} for coin in self.watchlist_symbols]

        self.update_scan_mode_buttons()
        self.build_watchlist_cards()
        self.begin_scan_generation()
        self.schedule_scan_loop(0)

    def load_top50_scan_symbols(self):

        if self.get_active_exchange_id() == "bybit":
            symbols = get_top_bybit_symbols(self.top_bybit_limit)
        else:
            try:
                symbols = [
                    item.exchange_symbol
                    for item in get_top_symbols(
                        self.get_active_exchange_id(), self.top_bybit_limit
                    )
                ]
            except Exception:
                symbols = []

        if not symbols:
            messagebox.showwarning(
                APP_TITLE,
                f"Could not fetch Top {self.top_bybit_limit} "
                f"{self.active_provider().display_name}. Try again in a moment."
            )

        self.top50_symbols = symbols
        self.coins = [{"symbol": symbol} for symbol in self.top50_symbols]

    def is_top_bybit_mode(self):

        return self.scan_mode in TOP_BYBIT_LIMITS

    def get_top_bybit_limit(self):

        return TOP_BYBIT_LIMITS.get(self.scan_mode, 50)

    def get_top_bybit_mode(self):

        return TOP_BYBIT_MODES_BY_LIMIT.get(self.top_bybit_limit, SCAN_MODE_TOP50)

    def set_top_bybit_limit(self, limit):

        mode = TOP_BYBIT_MODES_BY_LIMIT[limit]

        if self.scan_mode == mode:
            return

        self.top_bybit_limit = limit
        self.set_scan_mode(mode)

    def update_scan_mode_buttons(self):

        for mode, button in self.scan_mode_buttons.items():
            is_active = (
                mode == self.scan_mode
                or mode == SCAN_MODE_TOP_BYBIT and self.is_top_bybit_mode()
            )

            if is_active:
                button.configure(fg_color=BLUE, text_color="#FFFFFF", border_color=BLUE)
            else:
                button.configure(
                    fg_color=PANEL_COLOR,
                    text_color=MUTED_TEXT_COLOR,
                    border_color=BORDER_COLOR
                )

        if self.watchlist_title_label is not None:
            title = (
                "WATCHLIST"
                if self.scan_mode == SCAN_MODE_WATCHLIST
                else f"TOP {self.top_bybit_limit} {self.active_provider().display_name.upper()}"
            )
            self.watchlist_title_label.configure(text=title)

        if self.reset_watchlist_button is not None:
            if self.scan_mode == SCAN_MODE_WATCHLIST:
                self.reset_watchlist_button.configure(
                    state="normal",
                    text=f"Reset to Top20 {self.active_provider().display_name}",
                    text_color=TEXT_COLOR
                )
            else:
                self.reset_watchlist_button.configure(state="disabled", text_color=GRAY)

        self.update_top_limit_buttons()

    def update_top_limit_buttons(self):

        if self.top_limit_container is None:
            return

        if self.is_top_bybit_mode():
            if not self.top_limit_container.winfo_ismapped():
                self.top_limit_container.pack(fill="x", pady=(8, 0))
        else:
            if self.top_limit_container.winfo_ismapped():
                self.top_limit_container.pack_forget()

        for limit, button in self.top_limit_buttons.items():
            if limit == self.top_bybit_limit and self.is_top_bybit_mode():
                button.configure(fg_color=BLUE, text_color="#FFFFFF", border_color=BLUE)
            else:
                button.configure(
                    fg_color=PANEL_COLOR,
                    text_color=MUTED_TEXT_COLOR,
                    border_color=BORDER_COLOR
                )

    def update_watchlist_coin(
        self,
        coin,
        index,
        *,
        scan_id=None,
        interval=None,
        total_symbols=0,
        job_id=None,
        scan_range=None,
        exchange_id=None,
        display_symbol=None,
        market_label=None,
        platform_market_name=None,
        asset_class=None
    ):

        symbol = coin["symbol"]
        interval = interval or self.selected_interval
        symbol_started_at = time.perf_counter()
        result = self.create_scan_result_record(
            scan_id,
            symbol,
            index,
            "running",
            interval=interval,
            total_symbols=total_symbols,
            job_id=job_id,
            scan_range=scan_range,
            exchange_id=exchange_id,
            display_symbol=display_symbol,
            market_label=market_label,
            platform_market_name=platform_market_name,
            asset_class=asset_class
        )

        try:
            fetch_started_at = time.perf_counter()
            df = self.fetch_klines(symbol, interval, exchange_id=exchange_id)
            self.perf_log("fetch_klines", fetch_started_at, symbol=symbol)
            df.attrs["symbol"] = symbol
            df.attrs["timeframe"] = interval
            df.attrs["exchange_id"] = exchange_id or self.get_active_exchange_id()

            rsi_started_at = time.perf_counter()
            rsi = calculate_rsi(df)
            self.perf_log("calculate_rsi", rsi_started_at, symbol=symbol)

            candles_started_at = time.perf_counter()
            candles = self.prepare_engine_candles(df, interval=interval)
            self.perf_log("prepare_candles", candles_started_at, symbol=symbol)

            fvg_result = None
            try:
                fvg_closed, fvg_current, fvg_previous = self.prepare_fvg_candles(
                    candles,
                    interval,
                )
                fvg_result = FVGService().analyze(
                    fvg_closed,
                    fvg_current,
                    fvg_previous,
                )
            except Exception as fvg_error:
                print(
                    "FVG analysis error: "
                    f"symbol={symbol} "
                    f"exchange_id={exchange_id or self.get_active_exchange_id()} "
                    f"timeframe={interval} "
                    f"error_type={type(fvg_error).__name__} "
                    f"error_message={fvg_error}"
                )

            divergence_started_at = time.perf_counter()
            divergences = self.find_coin_divergences_from_candles(candles)
            self.perf_log("find_divergences", divergence_started_at, symbol=symbol)

            select_started_at = time.perf_counter()
            best_divergence = self.select_freshest_best_signal(divergences, len(candles))
            self.perf_log("select_signal", select_started_at, symbol=symbol)

            quality_score = None
            candles_ago = None
            signal_status = ""
            ui_visible = False
            if best_divergence is not None:
                quality_score = calculate_quality_score(best_divergence.get("quality"))
                candles_ago = self.signal_age(best_divergence, len(candles))
                signal_status, _status_color = self.signal_status(best_divergence, len(candles))
                ui_visible = self.is_visible_signal(best_divergence, len(candles))

            result.update(
                {
                    "status": "signal_found" if best_divergence is not None else "no_signal",
                    "rsi": rsi,
                    "divergence": best_divergence,
                    "candle_count": len(candles),
                    "quality": quality_score,
                    "candles_ago": candles_ago,
                    "signal_status": signal_status,
                    "alert_candidate": best_divergence,
                    "ui_visible": ui_visible,
                    "fvg_result": fvg_result,
                    "fvg_status": (
                        fvg_result.status.value if fvg_result else ""
                    ),
                    "selected_fvg": (
                        fvg_result.selected_fvg if fvg_result else None
                    )
                }
            )
        except Exception as error:
            result["status"] = "error"
            result["error"] = f"{type(error).__name__}: {error}"
        finally:
            result["worker_duration_ms"] = (
                time.perf_counter() - symbol_started_at
            ) * 1000

        return result

    def find_coin_divergences_from_candles(self, candles):

        rsi_series = self.calculate_rsi_series(candles["close"])
        price_pivot_highs, price_pivot_lows = find_pivots(
            candles,
            left=PIVOT_LEFT,
            right=PIVOT_RIGHT
        )
        rsi_pivot_highs, rsi_pivot_lows = find_rsi_pivots(
            rsi_series,
            candles["time"],
            left=PIVOT_LEFT,
            right=PIVOT_RIGHT
        )

        return find_regular_divergences(
            candles,
            rsi_series,
            price_pivot_highs,
            price_pivot_lows,
            rsi_pivot_highs,
            rsi_pivot_lows
        )

    def select_freshest_best_signal(self, divergences, candle_count=None, visible_only=False):

        if not divergences:
            return None

        candidates = divergences

        if visible_only:
            candidates = [
                divergence
                for divergence in divergences
                if self.is_visible_signal(divergence, candle_count)
            ]

        if not candidates:
            return None

        return max(
            candidates,
            key=lambda divergence: self.signal_sort_key(divergence, candle_count)
        )

    def signal_sort_key(self, divergence, candle_count=None):

        status = self.signal_filter_status(divergence, candle_count)
        quality_score = calculate_quality_score(divergence.get("quality"))
        freshness = divergence.get("confirmed_index", divergence["price_end"]["index"])

        return self.get_signal_priority(status), freshness, quality_score

    def signal_filter_status(self, divergence, candle_count=None):

        if divergence is None:
            return None

        if candle_count is None:
            return "FILTERED"

        status, _status_color = self.signal_status(divergence, candle_count)
        quality_score = calculate_quality_score(divergence.get("quality"))

        if status == "EXPIRED":
            return "EXPIRED"

        if quality_score < MIN_VISIBLE_QUALITY:
            return "FILTERED"

        return status

    def get_signal_priority(self, status):

        priorities = {
            "ACTIVE": 3,
            "AGING": 2,
            "FILTERED": 1,
            "EXPIRED": 1
        }

        return priorities.get(status, 0)

    def get_signal_sort_key(self, result):

        divergence = result.get("divergence")
        rsi = result.get("rsi") or 0

        if self.sorts_by_rsi_view():
            return self.rsi_view_sort_key(result)

        if divergence is None:
            return 0, -1, 0, rsi

        status = self.signal_filter_status(
            divergence,
            result.get("candle_count")
        )
        priorities = {
            "ACTIVE": 5,
            "AGING": 4,
            "FILTERED": 3,
            "EXPIRED": 2
        }
        freshness = divergence.get("confirmed_index", divergence["price_end"]["index"])
        quality_score = calculate_quality_score(divergence.get("quality"))

        return priorities.get(status, 0), freshness, quality_score, rsi

    def rsi_view_sort_key(self, result):

        divergence = result.get("divergence")
        rsi = result.get("rsi") or 0

        if divergence is None:
            return 0, 0, -999999, 0, 0

        status = self.signal_filter_status(
            divergence,
            result.get("candle_count")
        )
        candle_count = result.get("candle_count")
        age = 999999 if candle_count is None else self.signal_age(divergence, candle_count)
        quality_score = calculate_quality_score(divergence.get("quality"))
        rsi_extreme = self.rsi_extreme_score(rsi)

        if getattr(self, "rsi_sort_mode", RSI_SORT_MODE_QUALITY) == RSI_SORT_MODE_RSI_QUALITY:
            return self.rsi_quality_sort_key(status, age, rsi_extreme, quality_score)

        return self.rsi_sort_key(age, rsi_extreme, quality_score)

    def rsi_sort_key(self, age, rsi_extreme, quality_score):

        return rsi_extreme, quality_score, -age

    def rsi_quality_sort_key(self, status, age, rsi_extreme, quality_score):

        rsi_quality_average = (rsi_extreme + quality_score) / 2

        return (
            self.rsi_status_priority(status),
            -age,
            1 if quality_score > RSI_QUALITY_PRIORITY_THRESHOLD else 0,
            rsi_extreme,
            quality_score,
            rsi_quality_average
        )

    def is_fresh_rsi_setup(self, age):

        return 0 <= age <= 3

    def rsi_extreme_score(self, rsi):

        try:
            return abs(float(rsi) - 50) * 2
        except (TypeError, ValueError):
            return 0

    def rsi_status_priority(self, status):

        priorities = {
            "ACTIVE": 3,
            "AGING": 2,
            "FILTERED": 1,
            "EXPIRED": 1
        }

        return priorities.get(status, 0)

    def sorts_by_rsi_view(self):

        return getattr(self, "rsi_sort_mode", RSI_SORT_MODE_QUALITY) in (
            RSI_SORT_MODE_RSI,
            RSI_SORT_MODE_RSI_QUALITY
        )

    def is_rsi_view_enabled(self):

        return (
            self.current_rsi_view_option() != RSI_VIEW_OFF
            or self.sorts_by_rsi_view()
        )

    def current_rsi_view_option(self):

        option = getattr(self, "rsi_view_option", None)

        if option is None:
            return RSI_VIEW_OFF

        return option.get()

    def apply_rsi_view_option(self, option):

        rsi_view_option = getattr(self, "rsi_view_option", None)

        if rsi_view_option is not None:
            rsi_view_option.set(option)

        if option == RSI_VIEW_OFF:
            self.rsi_sort_mode = RSI_SORT_MODE_QUALITY
        elif option == RSI_VIEW_SORT:
            self.rsi_sort_mode = RSI_SORT_MODE_RSI
        elif option == RSI_VIEW_QUALITY_SORT:
            self.rsi_sort_mode = RSI_SORT_MODE_RSI_QUALITY

        self.update_rsi_sort_mode_label()
        self.refresh_rsi_view()

    def update_rsi_sort_mode_label(self):

        if getattr(self, "rsi_sort_mode_label", None) is None:
            return

        self.configure_label_if_changed(
            self.rsi_sort_mode_label,
            text="RSI Sort"
        )

    def refresh_rsi_view(self):

        self.last_card_texts = {}

        for card in getattr(self, "buttons", []):
            self.update_rsi_card_visibility(card)

        if self.is_top_bybit_mode():
            self.sort_top50_cards()

    def is_visible_signal(self, divergence, candle_count):

        quality_score = calculate_quality_score(divergence.get("quality"))

        if quality_score < MIN_VISIBLE_QUALITY:
            return False

        status, _status_color = self.signal_status(divergence, candle_count)

        if status == "EXPIRED" and not SHOW_EXPIRED_SIGNALS:
            return False

        return True

    @staticmethod
    def format_fvg_price(value):

        price = float(value)
        magnitude = abs(price)

        if magnitude >= 1000:
            decimals = 2
        elif magnitude >= 1:
            decimals = 4
        elif magnitude >= 0.01:
            decimals = 6
        else:
            decimals = 8

        formatted = f"{price:,.{decimals}f}"
        integer, dot, fraction = formatted.partition(".")
        fraction = fraction.rstrip("0")
        formatted = integer if not fraction else f"{integer}{dot}{fraction}"
        return formatted.replace(",", " ")

    def format_fvg_card_content(self, fvg_result, fvg_status, selected_fvg):

        if fvg_result is None or selected_fvg is None:
            return None

        status = getattr(fvg_status, "value", fvg_status)
        if status not in (
            FVGOpportunityStatus.ACTIVE.value,
            FVGOpportunityStatus.PENDING.value,
        ):
            return None

        try:
            direction = selected_fvg.gap.direction
            direction_value = getattr(direction, "value", direction)
            if direction_value == FVGDirection.BULLISH.value:
                direction_text = "Bullish"
                direction_color = GREEN
            elif direction_value == FVGDirection.BEARISH.value:
                direction_text = "Bearish"
                direction_color = RED
            else:
                return None

            if status == FVGOpportunityStatus.ACTIVE.value:
                detail = (
                    f"{self.format_fvg_price(selected_fvg.gap.lower_price)} – "
                    f"{self.format_fvg_price(selected_fvg.gap.upper_price)}"
                )
                detail_color = TEXT_COLOR
            else:
                distance = selected_fvg.distance_percent
                detail = "" if distance is None else f"Distance: {distance:.2f}%"
                detail_color = MUTED_TEXT_COLOR
        except (AttributeError, TypeError, ValueError, OverflowError):
            return None

        return {
            "header": f"FVG {status} · {direction_text}",
            "header_color": direction_color,
            "detail": detail,
            "detail_color": detail_color,
        }

    def update_fvg_card_section(
        self, card, fvg_result=None, fvg_status="", selected_fvg=None
    ):

        cell = card.get("fvg_cell")
        header = card.get("fvg_header")
        detail = card.get("fvg_detail")
        if cell is None or header is None or detail is None:
            return False

        try:
            if hasattr(cell, "winfo_exists") and not cell.winfo_exists():
                return False

            content = self.format_fvg_card_content(
                fvg_result, fvg_status, selected_fvg
            )
            if content is None:
                self.configure_label_if_changed(header, text="")
                self.configure_label_if_changed(detail, text="")
                if cell.winfo_ismapped():
                    cell.grid_remove()
                return True

            self.configure_label_if_changed(
                header,
                text=content["header"],
                text_color=content["header_color"],
            )
            self.configure_label_if_changed(
                detail,
                text=content["detail"],
                text_color=content["detail_color"],
            )
            if not cell.winfo_ismapped():
                cell.grid()
            return True
        except (AttributeError, TclError) as error:
            print(
                "FVG card section update skipped: "
                f"{type(error).__name__}: {error}"
            )
            return False

    def clear_fvg_card_sections(self):

        for card in getattr(self, "buttons", []):
            self.update_fvg_card_section(card)

    def update_watchlist_card(
        self,
        index,
        symbol,
        rsi,
        divergence,
        candle_count,
        *,
        fvg_result=None,
        fvg_status="",
        selected_fvg=None,
    ):

        if index < 0 or index >= len(self.buttons):
            return False

        card = self.buttons[index]
        frame = card.get("frame")
        if frame is None:
            return False

        try:
            if not frame.winfo_exists():
                return False
        except AttributeError:
            pass

        self.bind_card_click(frame, symbol)
        self.update_fvg_card_section(
            card,
            fvg_result=fvg_result,
            fvg_status=fvg_status,
            selected_fvg=selected_fvg,
        )

        if divergence is None:
            status = ""
            status_color = GRAY
            setup_text = "—"
            setup_color = MUTED_TEXT_COLOR
            quality_text = "Q:—"
            signal_time = ""
            age_text = ""
        elif self.is_visible_signal(divergence, candle_count):
            status, status_color = self.signal_status(divergence, candle_count)
            status = self.format_status_label(status)
            setup_text, setup_color = self.signal_setup_text(divergence)
            quality_text = self.signal_quality_text(divergence)
            signal_time = self.signal_time_text(divergence)
            age_text = self.signal_age_text(divergence, candle_count)
        else:
            status, status_color, setup_text, setup_color, quality_text, signal_time, age_text = (
                self.format_filtered_signal(divergence, candle_count)
            )

        rsi_text = self.format_rsi_text(rsi)
        rsi_color = self.rsi_value_color(rsi)
        shown_symbol = self.platform_market_name(symbol)
        card_text = {
            "symbol": shown_symbol,
            "market": self.market_badge(symbol),
            "status": status,
            "status_color": status_color,
            "setup": setup_text,
            "setup_color": setup_color,
            "quality": quality_text,
            "quality_color": self.signal_quality_color(divergence),
            "time": signal_time,
            "age": age_text,
            "rsi": rsi_text,
            "rsi_color": rsi_color
        }
        cache_key = card["symbol_value"]

        if self.last_card_texts.get(cache_key) == card_text:
            return True

        self.last_card_texts[cache_key] = card_text

        self.configure_label_if_changed(card["symbol"], text=shown_symbol)
        self.configure_card_label_if_present(card, "market", text=card_text["market"])
        self.configure_label_if_changed(
            card["status"],
            text=status,
            text_color=status_color
        )
        self.configure_label_if_changed(
            card["setup"],
            text=setup_text,
            text_color=setup_color
        )
        self.configure_card_label_if_present(
            card,
            "quality",
            text=quality_text,
            text_color=card_text["quality_color"]
        )
        self.configure_card_label_if_present(card, "time", text=signal_time)
        self.configure_label_if_changed(card["age"], text=age_text)
        self.update_rsi_card_visibility(card)
        self.configure_label_if_changed(
            card["rsi"],
            text=card_text["rsi"],
            text_color=rsi_color
        )
        return True

    def update_rsi_card_visibility(self, card):

        rsi_cell = card.get("rsi_cell")

        if rsi_cell is None:
            return

        if self.is_rsi_view_enabled():
            if not rsi_cell.winfo_ismapped():
                rsi_cell.grid()
        else:
            if rsi_cell.winfo_ismapped():
                rsi_cell.grid_remove()

    def configure_card_label_if_present(self, card, key, **options):

        widget = card.get(key)

        if widget is None:
            return

        self.configure_label_if_changed(widget, **options)

    def configure_label_if_changed(self, widget, **options):

        changed_options = {}

        for option, value in options.items():
            if widget.cget(option) != value:
                changed_options[option] = value

        if changed_options:
            widget.configure(**changed_options)

    def format_filtered_signal(self, divergence, candle_count):

        status, _status_color = self.signal_status(divergence, candle_count)
        setup_text, setup_color = self.signal_setup_text(divergence)
        signal_time = self.signal_time_text(divergence)
        age_text = self.signal_age_text(divergence, candle_count)

        quality_text = self.signal_quality_text(divergence)

        if status == "EXPIRED":
            filter_status = "EXPIRED"
            filter_color = GRAY
        else:
            filter_status = "FILTERED"
            filter_color = STATUS_FILTERED_COLOR

        return (
            filter_status,
            filter_color,
            setup_text,
            setup_color,
            quality_text,
            signal_time,
            age_text
        )

    def format_status_label(self, status):

        return status

    def signal_setup_text(self, divergence):

        if divergence is None:
            return "—", MUTED_TEXT_COLOR

        if divergence["type"] == "bullish":
            return "Bull", GREEN

        return "Bear", RED

    def signal_quality_text(self, divergence):

        if divergence is None:
            return "Q:—"

        quality_score = calculate_quality_score(divergence.get("quality"))

        return f"Q:{quality_score}"

    def signal_quality_color(self, divergence):

        if divergence is None:
            return TEXT_COLOR

        quality_score = calculate_quality_score(divergence.get("quality"))

        if quality_score < 60:
            return TEXT_COLOR

        if divergence.get("type") == "bullish":
            return GREEN

        if divergence.get("type") == "bearish":
            return RED

        return TEXT_COLOR

    def format_rsi_text(self, rsi):

        try:
            value = float(rsi)
        except (TypeError, ValueError):
            return "—"

        return f"{value:.1f}".rstrip("0").rstrip(".")

    def rsi_value_color(self, rsi):

        try:
            value = float(rsi)
        except (TypeError, ValueError):
            return TEXT_COLOR

        if value >= 60:
            return RED

        if value <= 30:
            return GREEN

        return TEXT_COLOR

    def signal_status(self, divergence, candle_count):

        if divergence is None:
            return "", GRAY

        age = self.signal_age(divergence, candle_count)

        if age <= ACTIVE_MAX_CANDLES:
            return "ACTIVE", GREEN

        if age <= AGING_MAX_CANDLES:
            return "AGING", ORANGE

        return "EXPIRED", GRAY

    def signal_time_text(self, divergence):

        if divergence is None:
            return ""

        return f"{format_polish_time(divergence.get('confirmed_time', divergence['price_end']['time']))} PL"

    def signal_age_text(self, divergence, candle_count):

        if divergence is None:
            return ""

        age = self.signal_age(divergence, candle_count)

        if age == 0:
            return "0 candles ago"

        if age == 1:
            return "1 candle ago"

        return f"{age} candles ago"

    def signal_age(self, divergence, candle_count):

        if divergence.get("age_candles") is not None:
            return divergence["age_candles"]

        return max(0, candle_count - 1 - divergence.get("confirmed_index", divergence["price_end"]["index"]))

    def prepare_engine_candles(self, df, interval=None):

        candles = df[["time", "open", "high", "low", "close"]].copy()
        candles.attrs["symbol"] = df.attrs.get("symbol", "UNKNOWN")
        candles.attrs["timeframe"] = interval or self.selected_interval

        candles["time"] = candles["time"].astype(float).astype(int) // 1000

        for column in ["open", "high", "low", "close"]:
            candles[column] = candles[column].astype(float)

        return candles.sort_values("time").reset_index(drop=True)

    def prepare_fvg_candles(self, candles, interval, now_seconds=None):

        fvg_candles = tuple(
            Candle(
                time=int(row.time),
                open=float(row.open),
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
            )
            for row in candles.itertuples(index=False)
        )
        if len(fvg_candles) < 2:
            raise ValueError("FVG analysis requires at least two observations.")

        try:
            interval_seconds = FVG_INTERVAL_SECONDS[interval]
        except KeyError as error:
            raise ValueError(f"Unsupported FVG timeframe: {interval!r}.") from error

        current_time = time.time() if now_seconds is None else float(now_seconds)
        closed_candles = tuple(
            candle
            for candle in fvg_candles
            if candle.time + interval_seconds <= current_time
        )
        return closed_candles, fvg_candles[-1], fvg_candles[-2]

    def calculate_rsi_series(self, close):

        return calculate_rsi_series(close, period=14)

    def create_watchlist_card(self, parent, symbol, index, editable=True):

        frame = ctk.CTkFrame(
            parent,
            fg_color=BG_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=6,
            height=CARD_HEIGHT
        )
        frame.pack_propagate(False)
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, weight=1, minsize=88)
        frame.grid_columnconfigure(1, weight=0, minsize=42)
        frame.grid_columnconfigure(2, weight=0, minsize=46)
        frame.grid_columnconfigure(3, weight=0, minsize=48)
        frame.grid_columnconfigure(4, weight=0, minsize=74)
        frame.grid_columnconfigure(5, weight=0, minsize=62)
        frame.grid_columnconfigure(6, weight=0)

        identity = ctk.CTkFrame(frame, fg_color="transparent")
        identity.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(10, 4), pady=6)
        identity.grid_columnconfigure(1, weight=1)

        identity_font_size = 14
        position_label = self.create_card_label(
            identity, str(index + 1), identity_font_size, MUTED_TEXT_COLOR, True
        )
        position_label.configure(width=30, anchor="e")
        position_label.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(0, 5))

        symbol_label = self.create_card_label(
            identity,
            self.platform_market_name(symbol),
            identity_font_size,
            TEXT_COLOR,
            True
        )
        symbol_label.grid(row=0, column=1, sticky="ew")

        market_label = self.create_card_label(
            identity, self.market_badge(symbol), 10, MUTED_TEXT_COLOR, False
        )
        market_label.grid(row=1, column=1, sticky="ew", pady=(0, 1))

        if editable:
            edit_button = ctk.CTkButton(
                identity,
                text="✎",
                width=28,
                height=22,
                fg_color=PANEL_COLOR,
                hover_color=BORDER_COLOR,
                border_color=BORDER_COLOR,
                border_width=1,
                text_color=MUTED_TEXT_COLOR,
                corner_radius=6,
                command=lambda card_index=index: self.open_coin_selector(card_index)
            )
            edit_button.grid(row=0, column=2, rowspan=2, sticky="e", padx=(4, 0))

        labels = {
            "position": position_label,
            "symbol": symbol_label,
            "market": market_label,
            "setup": self.create_card_value(frame, 1, "SETUP", "—", MUTED_TEXT_COLOR),
            "quality": self.create_card_value(frame, 2, "QUALITY", "Q:—", TEXT_COLOR),
            "age": self.create_card_value(frame, 4, "SIGNAL", "", MUTED_TEXT_COLOR),
            "status": self.create_card_value(frame, 5, "STATUS", "", GRAY),
            "time": None
        }
        labels["rsi"] = self.create_card_value(frame, 3, "RSI", "—", TEXT_COLOR)
        labels["rsi_cell"] = labels["rsi"].master
        fvg_cell, fvg_header, fvg_detail = self.create_fvg_card_section(frame)
        labels["fvg_cell"] = fvg_cell
        labels["fvg_header"] = fvg_header
        labels["fvg_detail"] = fvg_detail
        self.update_rsi_card_visibility(labels)

        self.bind_card_click(frame, symbol)

        labels["frame"] = frame
        labels["symbol_value"] = symbol
        labels["exchange_id"] = self.get_active_exchange_id()
        labels["exchange_symbol"] = symbol
        labels["display_symbol"] = self.display_symbol(symbol)
        labels["platform_market_name"] = self.platform_market_name(symbol)
        labels["market_label"] = self.market_label()
        labels["asset_class"] = self.asset_class(symbol)
        return labels

    def create_fvg_card_section(self, parent):

        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(
            row=0,
            column=6,
            rowspan=2,
            sticky="nsew",
            padx=(4, 8),
            pady=6,
        )
        cell.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(
            cell,
            text="",
            font=("Arial", 9, "bold"),
            text_color=MUTED_TEXT_COLOR,
            anchor="w",
        )
        header.grid(row=0, column=0, sticky="ew")

        detail = ctk.CTkLabel(
            cell,
            text="",
            font=("Arial", 9, "normal"),
            text_color=MUTED_TEXT_COLOR,
            anchor="w",
        )
        detail.grid(row=1, column=0, sticky="ew", pady=(1, 0))
        cell.grid_remove()
        return cell, header, detail

    def create_card_value(self, parent, column, title, value, color):

        cell = ctk.CTkFrame(parent, fg_color="transparent")
        cell.grid(row=0, column=column, rowspan=2, sticky="nsew", padx=2, pady=6)
        cell.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            cell,
            text=title,
            font=("Arial", 8, "bold"),
            text_color=GRAY,
            anchor="w"
        ).grid(row=0, column=0, sticky="ew")

        value_label = ctk.CTkLabel(
            cell,
            text=value,
            font=("Arial", 11, "bold"),
            text_color=color,
            anchor="w"
        )
        value_label.grid(row=1, column=0, sticky="ew", pady=(1, 0))

        return value_label

    def create_card_label(self, parent, text, size, color, bold):

        weight = "bold" if bold else "normal"

        return ctk.CTkLabel(
            parent,
            text=text,
            font=("Arial", size, weight),
            text_color=color,
            anchor="w"
        )

    def bind_card_click(self, widget, symbol):

        if isinstance(widget, ctk.CTkButton):
            return

        widget.bind("<Button-1>", lambda _event, s=symbol: self.select_coin(s))

        for child in widget.winfo_children():
            self.bind_card_click(child, symbol)

    def open_coin_selector(self, index):

        current_symbol = self.coins[index]["symbol"]

        try:
            instruments = get_instruments(self.get_active_exchange_id())
            self.instrument_by_symbol = {
                item.exchange_symbol: item for item in instruments
            }
            symbols = instruments
        except Exception as error:
            messagebox.showerror(
                APP_TITLE,
                COIN_LIST_ERROR.format(error=error)
            )
            return

        if not symbols:
            messagebox.showwarning(
                APP_TITLE,
                COIN_LIST_EMPTY
            )
            return

        window = ctk.CTkToplevel(self.app)
        window.title(COIN_SELECTOR_TITLE)
        window.geometry("360x520")
        window.configure(fg_color=BG_COLOR)
        window.transient(self.app)
        window.grab_set()

        ctk.CTkLabel(
            window,
            text=COIN_SELECTOR_HEADER.format(symbol=current_symbol),
            font=("Arial", 18, "bold"),
            text_color=TEXT_COLOR
        ).pack(pady=(14, 10))

        search_frame = ctk.CTkFrame(window, fg_color="transparent")
        search_frame.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(
            search_frame,
            text=COIN_SEARCH_LABEL,
            font=("Arial", 12, "bold"),
            text_color=MUTED_TEXT_COLOR
        ).pack(anchor="w")

        search_var = StringVar()
        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=search_var,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_COLOR,
            placeholder_text="BTC, SOL, SUI..."
        )
        search_entry.pack(fill="x", pady=(4, 0))

        scroll = ctk.CTkScrollableFrame(
            window,
            fg_color=PANEL_COLOR,
            scrollbar_button_color=BORDER_COLOR,
            scrollbar_button_hover_color=GRAY
        )
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        def render_symbols(*_args):
            query = search_var.get().strip()
            filtered_symbols = [
                item for item in filter_symbols(symbols, query)
                if self.instrument_matches_exchange(item)
            ]

            for child in scroll.winfo_children():
                child.destroy()

            if not filtered_symbols:
                ctk.CTkLabel(
                    scroll,
                    text=COIN_NO_RESULTS,
                    font=("Arial", 13, "bold"),
                    text_color=MUTED_TEXT_COLOR
                ).pack(fill="x", padx=6, pady=10)
                return

            for instrument in filtered_symbols:
                button = ctk.CTkButton(
                    scroll,
                    text=(
                        f"{instrument.platform_market_name or instrument.display_symbol}"
                        f" · {instrument.asset_class.upper()}"
                        if instrument.exchange_id == "okx"
                        else instrument.platform_market_name or instrument.display_symbol
                    ),
                    height=34,
                    fg_color=BG_COLOR,
                    hover_color=BORDER_COLOR,
                    border_color=BORDER_COLOR,
                    border_width=1,
                    text_color=TEXT_COLOR,
                    corner_radius=6,
                    command=lambda value=instrument.exchange_symbol, dialog=window: self.replace_watchlist_coin(
                        index,
                        value,
                        dialog
                    )
                )
                button.pack(fill="x", padx=6, pady=3)

        search_var.trace_add("write", render_symbols)
        render_symbols()
        search_entry.focus()

    def replace_watchlist_coin(self, index, new_symbol, dialog):

        current_symbol = self.coins[index]["symbol"]
        updated_symbols = [coin["symbol"] for coin in self.coins]
        updated_symbols[index] = new_symbol

        try:
            save_watchlist(
                [self.instrument_by_symbol.get(symbol, symbol) for symbol in updated_symbols],
                exchange_id=self.get_active_exchange_id(),
            )
        except Exception as error:
            messagebox.showerror(
                APP_TITLE,
                WATCHLIST_SAVE_ERROR.format(error=error)
            )
            return

        if self.selected_symbol == current_symbol:
            self.selected_symbol = new_symbol

        dialog.destroy()
        self.reload_watchlist()

        if self.selected_symbol:
            self.refresh_selected()

    def reset_watchlist_to_top20(self):

        confirmed = messagebox.askyesno(
            APP_TITLE,
            f"Replace the {self.active_provider().display_name} watchlist with "
            "the current Top20 by 24h turnover?"
        )

        if not confirmed:
            return

        try:
            reset_watchlist(self.get_active_exchange_id())
        except Exception as error:
            messagebox.showerror(
                APP_TITLE,
                WATCHLIST_RESET_ERROR.format(error=error)
            )
            return

        self.selected_symbol = None
        self.reload_watchlist()

    def reload_watchlist(self):

        self.cancel_scan_loop()
        self.watchlist_symbols = self.filter_provider_symbols(
            get_watchlist(self.active_exchange_id)
        )

        if self.scan_mode == SCAN_MODE_WATCHLIST:
            self.coins = [{"symbol": coin} for coin in self.watchlist_symbols]

        self.refresh_index = 0

        self.build_watchlist_cards()
        self.reset_scan_cycle_state()
        self.begin_scan_generation()
        self.schedule_scan_loop(0)

    def build_watchlist_cards(self):

        if self.watchlist_scroll is None:
            return

        for card in self.buttons:
            card["frame"].destroy()

        self.buttons = []
        self.last_card_texts = {}
        self.cards_by_symbol = {}

        editable = self.scan_mode == SCAN_MODE_WATCHLIST

        for index, coin in enumerate(self.coins):
            card = self.create_watchlist_card(
                self.watchlist_scroll,
                coin["symbol"],
                index,
                editable=editable
            )

            card["frame"].pack(fill="x", padx=8, pady=5)
            card["index"] = index
            self.buttons.append(card)
            self.cards_by_symbol[coin["symbol"]] = card

            if self.is_top_bybit_mode():
                result = self.top50_results.get(coin["symbol"])

                if result is not None:
                    self.update_watchlist_card(
                        index,
                        result["symbol"],
                        result["rsi"],
                        result["divergence"],
                        result["candle_count"],
                        fvg_result=result.get("fvg_result"),
                        fvg_status=result.get("fvg_status", ""),
                        selected_fvg=result.get("selected_fvg")
                    )

        self.refresh_card_positions()

    def refresh_card_positions(self):

        position = 0
        for card in getattr(self, "buttons", []):
            frame = card.get("frame")
            if frame is None:
                continue

            try:
                if not frame.winfo_manager():
                    continue
            except AttributeError:
                pass

            position += 1
            self.configure_card_label_if_present(
                card, "position", text=str(position)
            )

    def sort_top50_cards(self):

        if not self.is_top_bybit_mode():
            return

        sort_started_at = time.perf_counter()
        results = []

        for position, symbol in enumerate(self.top50_symbols):
            result = self.top50_results.get(symbol)

            if result is None:
                result = {
                    "symbol": symbol,
                    "rsi": 0,
                    "divergence": None,
                    "candle_count": 0
                }

            result["position"] = position
            results.append(result)

        sorted_results = sorted(
            results,
            key=lambda result: (
                self.get_signal_sort_key(result),
                -result["position"]
            ),
            reverse=True
        )

        sorted_symbols = [result["symbol"] for result in sorted_results]

        current_order = [card["symbol_value"] for card in self.buttons]

        if sorted_symbols != current_order:
            self.coins = [{"symbol": symbol} for symbol in sorted_symbols]
            self.reorder_top50_cards(sorted_results)

        self.last_top50_order = sorted_symbols

        self.last_top50_sort_at = time.monotonic()
        self.perf_log(
            "sort_top_list",
            sort_started_at,
            mode=scan_mode_label(self.scan_mode, self.top_bybit_limit),
            symbols=len(sorted_results)
        )

    def sort_top50_cards_if_needed(self):

        elapsed_ms = (time.monotonic() - self.last_top50_sort_at) * 1000

        if elapsed_ms >= TOP_SORT_INTERVAL_MS:
            self.sort_top50_cards()

    def update_top50_result_card(self, symbol):

        card = self.cards_by_symbol.get(symbol)

        if card is None:
            return False

        result = self.top50_results[symbol]
        return self.update_watchlist_card(
            card["index"],
            result["symbol"],
            result["rsi"],
            result["divergence"],
            result["candle_count"],
            fvg_result=result.get("fvg_result"),
            fvg_status=result.get("fvg_status", ""),
            selected_fvg=result.get("selected_fvg")
        )

    def build_top_scan_ranking(self):

        results = []
        for position, symbol in enumerate(self.current_scan_symbols):
            result = self.current_scan_results.get(symbol)
            if result is None:
                result = self.create_scan_result_record(
                    self.current_scan_id,
                    symbol,
                    position,
                    "pending"
                )
            result["position"] = position
            results.append(result)

        return sorted(
            results,
            key=lambda result: (
                1 if result.get("divergence") is not None else 0,
                result.get("quality") or 0,
                self.get_signal_sort_key(result),
                -result["position"]
            ),
            reverse=True
        )

    def process_visible_top_alerts(self, results):

        for result in results:
            if not result.get("ui_visible"):
                continue
            if (result.get("quality") or 0) < MIN_VISIBLE_QUALITY:
                continue

            sent = self.process_alert_candidate(
                result["symbol"],
                result.get("alert_candidate") or result.get("divergence"),
                result.get("candle_count", 0),
                ui_ready=True,
                interval=result.get("interval"),
                scan_range=result.get("scan_range")
            )
            if sent:
                self.scan_cycle_alert_sent_count += 1

    def reorder_top50_cards(self, sorted_results):

        cards_by_symbol = {
            card["symbol_value"]: card
            for card in self.buttons
        }

        if any(result["symbol"] not in cards_by_symbol for result in sorted_results):
            return

        for card in self.buttons:
            card["frame"].pack_forget()

        self.buttons = []
        self.cards_by_symbol = {}

        for index, result in enumerate(sorted_results):
            symbol = result["symbol"]
            card = cards_by_symbol[symbol]

            card["frame"].pack(fill="x", padx=8, pady=5)
            card["index"] = index
            self.buttons.append(card)
            self.cards_by_symbol[symbol] = card

            if symbol in self.top50_results:
                self.update_watchlist_card(
                    index,
                    symbol,
                    result["rsi"],
                    result["divergence"],
                    result["candle_count"],
                    fvg_result=result.get("fvg_result"),
                    fvg_status=result.get("fvg_status", ""),
                    selected_fvg=result.get("selected_fvg")
                )

        self.refresh_card_positions()

    def build_scan_mode_controls(self, parent):

        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(
            container,
            text="SCAN MODE",
            font=("Arial", 11, "bold"),
            text_color=MUTED_TEXT_COLOR
        ).pack(anchor="w", pady=(0, 4))

        button_row = ctk.CTkFrame(container, fg_color="transparent")
        button_row.pack(fill="x")

        modes = [
            (SCAN_MODE_WATCHLIST, "Watchlist"),
            (SCAN_MODE_TOP_BYBIT, "Top Market")
        ]

        for mode, label in modes:
            button = ctk.CTkButton(
                button_row,
                text=label,
                height=30,
                fg_color=PANEL_COLOR,
                hover_color=BORDER_COLOR,
                border_color=BORDER_COLOR,
                border_width=1,
                text_color=MUTED_TEXT_COLOR,
                corner_radius=8,
                command=lambda value=mode: self.set_scan_mode(value)
            )
            button.pack(side="left", fill="x", expand=True, padx=2)
            self.scan_mode_buttons[mode] = button

        self.top_limit_container = ctk.CTkFrame(container, fg_color="transparent")

        ctk.CTkLabel(
            self.top_limit_container,
            text="TOP RANGE",
            font=("Arial", 11, "bold"),
            text_color=MUTED_TEXT_COLOR
        ).pack(anchor="w", pady=(0, 4))

        limit_row = ctk.CTkFrame(self.top_limit_container, fg_color="transparent")
        limit_row.pack(fill="x")

        for limit in (50, 100, 200):
            button = ctk.CTkButton(
                limit_row,
                text=f"Top {limit}",
                height=30,
                fg_color=PANEL_COLOR,
                hover_color=BORDER_COLOR,
                border_color=BORDER_COLOR,
                border_width=1,
                text_color=MUTED_TEXT_COLOR,
                corner_radius=8,
                command=lambda value=limit: self.set_top_bybit_limit(value)
            )
            button.pack(side="left", fill="x", expand=True, padx=2)
            self.top_limit_buttons[limit] = button

        self.update_scan_mode_buttons()

    def build_exchange_controls(self, parent):

        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x", padx=8, pady=(10, 8))

        ctk.CTkLabel(
            container,
            text="EXCHANGE",
            font=("Arial", 11, "bold"),
            text_color=MUTED_TEXT_COLOR
        ).pack(anchor="w", pady=(0, 4))

        self.exchange_menu = ctk.CTkOptionMenu(
            container,
            values=list(EXCHANGE_OPTIONS),
            command=self.select_exchange,
            height=30,
            fg_color=BORDER_COLOR,
            button_color=PANEL_COLOR,
            button_hover_color=BORDER_COLOR,
            dropdown_fg_color=PANEL_COLOR,
            dropdown_hover_color=BORDER_COLOR,
            dropdown_text_color=TEXT_COLOR,
            text_color=TEXT_COLOR
        )
        self.exchange_menu.set(self.active_exchange_option())
        self.exchange_menu.pack(fill="x")

    def open_guide_dialog(self):

        window = ctk.CTkToplevel(self.app)
        window.title(GUIDE_TITLE)
        window.geometry("560x680")
        window.minsize(480, 520)
        window.configure(fg_color=BG_COLOR)
        window.transient(self.app)
        window.grab_set()

        ctk.CTkLabel(
            window,
            text=GUIDE_TITLE,
            font=("Arial", 18, "bold"),
            text_color=TEXT_COLOR
        ).pack(fill="x", padx=18, pady=(16, 10))

        guide_text = ctk.CTkTextbox(
            window,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_COLOR,
            wrap="word"
        )
        guide_text.pack(fill="both", expand=True, padx=18, pady=(0, 10))
        guide_text.insert("1.0", GUIDE_CONTENT)
        guide_text.configure(state="disabled")

        ctk.CTkLabel(
            window,
            text=GUIDE_NOTE,
            font=("Arial", 11, "bold"),
            text_color=MUTED_TEXT_COLOR,
            wraplength=500,
            justify="center"
        ).pack(fill="x", padx=18, pady=(0, 12))

        ctk.CTkButton(
            window,
            text=CLOSE_BUTTON,
            width=120,
            height=34,
            fg_color=BLUE,
            hover_color="#2D83C4",
            text_color="#FFFFFF",
            corner_radius=8,
            command=window.destroy
        ).pack(pady=(0, 16))

    def build_top_bar(self):

        top_bar = ctk.CTkFrame(
            self.center,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=10,
            height=44
        )
        top_bar.pack(fill="x", padx=10, pady=(0, 10))
        top_bar.pack_propagate(False)

        self.top_time_label = ctk.CTkLabel(
            top_bar,
            text=PL_TIME_LABEL,
            font=("Arial", 13, "bold"),
            text_color=MUTED_TEXT_COLOR
        )
        self.top_time_label.pack(side="left", padx=(14, 10))

        ctk.CTkLabel(
            top_bar,
            text="|",
            font=("Arial", 13, "bold"),
            text_color=GRAY
        ).pack(side="left", padx=(0, 10))

        self.open_chart_label = ctk.CTkLabel(
            top_bar,
            text=OPEN_CHART_EMPTY,
            font=("Arial", 13, "bold"),
            text_color=TEXT_COLOR
        )
        self.open_chart_label.pack(side="left", padx=(0, 10))

        guide_button = ctk.CTkButton(
            top_bar,
            text=GUIDE_BUTTON,
            width=82,
            height=28,
            fg_color=PANEL_COLOR,
            hover_color=BORDER_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=BLUE,
            corner_radius=8,
            command=self.open_guide_dialog
        )
        guide_button.pack(side="left", padx=(0, 10))

        self.alerts_button = ctk.CTkButton(
            top_bar,
            text=ALERTS_BUTTON,
            width=96,
            height=28,
            fg_color=PANEL_COLOR,
            hover_color=BORDER_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_COLOR,
            corner_radius=8,
            command=self.open_alert_settings
        )
        self.alerts_button.pack(side="right", padx=(0, 14))

        self.scan_button = ctk.CTkButton(
            top_bar,
            text="SCAN",
            width=78,
            height=28,
            fg_color=PANEL_COLOR,
            hover_color=BORDER_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_COLOR,
            corner_radius=8,
            command=self.scan_now
        )
        self.scan_button.pack(side="right", padx=(0, 8))

        self.scan_progress_label = ctk.CTkLabel(
            top_bar,
            text="0/0",
            font=("Arial", 12, "bold"),
            text_color=GREEN
        )
        self.scan_progress_label.pack(side="right", padx=(0, 8))

        self.scan_status_label = ctk.CTkLabel(
            top_bar,
            text=SCAN_READY,
            font=("Arial", 12, "bold"),
            text_color=MUTED_TEXT_COLOR
        )
        self.scan_status_label.pack(side="right", padx=(0, 10))

        self.rsi_view_menu = ctk.CTkOptionMenu(
            top_bar,
            values=[
                RSI_VIEW_ON,
                RSI_VIEW_OFF,
                RSI_VIEW_SORT,
                RSI_VIEW_QUALITY_SORT
            ],
            variable=self.rsi_view_option,
            command=self.apply_rsi_view_option,
            width=136,
            height=28,
            fg_color=BORDER_COLOR,
            button_color=PANEL_COLOR,
            button_hover_color=BORDER_COLOR,
            dropdown_fg_color=PANEL_COLOR,
            dropdown_hover_color=BORDER_COLOR,
            dropdown_text_color=TEXT_COLOR,
            text_color=TEXT_COLOR
        )
        self.rsi_view_menu.pack(side="right", padx=(0, 10))

        self.rsi_sort_mode_label = ctk.CTkLabel(
            top_bar,
            text="RSI Sort",
            font=("Arial", 12, "bold"),
            text_color=MUTED_TEXT_COLOR
        )
        self.rsi_sort_mode_label.pack(side="right", padx=(0, 8))

    def update_open_chart_status(self, refreshed_at):

        if self.open_chart_label is not None:
            self.configure_label_if_changed(
                self.open_chart_label,
                text=(
                    f"Open: {self.platform_market_name(self.selected_symbol)} · "
                    f"{self.market_label()}"
                    f" · {self.asset_class_label(self.selected_symbol)}"
                    if self.selected_symbol and self.get_active_exchange_id() == "okx"
                    else f"Open: {self.platform_market_name(self.selected_symbol)} · "
                    f"{self.market_label()}"
                    if self.selected_symbol else OPEN_CHART_EMPTY
                )
            )

    def interval_label(self, interval):

        labels = {
            "1": "1m",
            "5": "5m",
            "15": "15m",
            "30": "30m",
            "60": "1H",
            "240": "4H",
            "D": "1D"
        }

        return labels.get(interval, interval)

    def get_alert_scan_range(self):

        if self.scan_mode == SCAN_MODE_WATCHLIST:
            return SCAN_MODE_WATCHLIST

        return self.scan_mode

    def process_alert_candidate(
        self,
        symbol,
        divergence,
        candle_count,
        *,
        ui_ready=True,
        interval=None,
        scan_range=None,
        exchange_id=None
    ):

        if divergence is None or not ui_ready:
            return False

        status, _status_color = self.signal_status(divergence, candle_count)
        age_text = self.signal_age_text(divergence, candle_count)
        quality_score = calculate_quality_score(divergence.get("quality"))

        sent = self.alert_manager.process_signal(
            symbol,
            interval or self.selected_interval,
            scan_range or self.get_alert_scan_range(),
            divergence,
            status,
            age_text,
            quality_score=quality_score,
            exchange_id=exchange_id or self.get_active_exchange_id()
        )
        self.update_alert_status_labels()
        return sent

    def process_due_alerts(self):

        if self.shutdown_requested:
            return

        self.alert_manager.process_due_alerts()
        self.update_alert_status_labels()
        self.app.after(1000, self.process_due_alerts)

    def open_alert_settings(self):

        if self.alert_settings_window is not None and self.alert_settings_window.winfo_exists():
            self.alert_settings_window.focus()
            return

        settings = self.alert_manager.settings

        if not self.alert_manager.has_saved_settings:
            settings.scan_range = self.get_alert_scan_range()

        window = ctk.CTkToplevel(self.app)
        window.title("Alerts")
        window.geometry("460x720")
        window.minsize(420, 560)
        window.configure(fg_color=BG_COLOR)
        window.transient(self.app)
        window.grab_set()
        self.alert_settings_window = window

        window.grid_columnconfigure(0, weight=1)
        window.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            window,
            text="Alerts",
            font=("Arial", 18, "bold"),
            text_color=TEXT_COLOR
        ).grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))

        content = ctk.CTkScrollableFrame(
            window,
            fg_color=PANEL_COLOR,
            scrollbar_button_color=BORDER_COLOR,
            scrollbar_button_hover_color=GRAY
        )
        content.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 10))
        content.grid_columnconfigure(0, weight=1)

        alerts_enabled_var = BooleanVar(value=settings.alerts_enabled)
        sound_enabled_var = BooleanVar(value=settings.sound_enabled)
        notification_enabled_var = BooleanVar(value=settings.windows_notification_enabled)
        minimum_quality_var = StringVar(value=str(settings.minimum_quality))
        scan_range_var = StringVar(value=settings.scan_range or self.get_alert_scan_range())
        type_vars = {
            "bullish": BooleanVar(value=settings.bullish),
            "bearish": BooleanVar(value=settings.bearish)
        }
        status_vars = {
            "active": BooleanVar(value=settings.active),
            "aging": BooleanVar(value=settings.aging),
            "expired": BooleanVar(value=settings.expired)
        }

        self.create_alert_checkbox(content, "Enable Alerts", alerts_enabled_var)
        self.create_alert_section_label(content, "Minimum Quality")

        quality_entry = ctk.CTkEntry(
            content,
            textvariable=minimum_quality_var,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_COLOR
        )
        quality_entry.pack(fill="x", padx=14, pady=(0, 10))

        self.create_alert_section_label(content, "Scan Range")

        for value, label in ALERT_SCAN_RANGES:
            ctk.CTkRadioButton(
                content,
                text=label,
                variable=scan_range_var,
                value=value,
                fg_color=BLUE,
                border_color=BORDER_COLOR,
                hover_color=BORDER_COLOR,
                text_color=TEXT_COLOR
            ).pack(anchor="w", padx=14, pady=2)

        self.create_alert_section_label(content, "Signal Type")
        self.create_alert_checkbox(content, "Bullish", type_vars["bullish"])
        self.create_alert_checkbox(content, "Bearish", type_vars["bearish"])

        self.create_alert_section_label(content, "Status")
        self.create_alert_checkbox(content, "ACTIVE", status_vars["active"])
        self.create_alert_checkbox(content, "AGING", status_vars["aging"])
        self.create_alert_checkbox(content, "EXPIRED", status_vars["expired"])

        self.create_alert_section_label(content, "Sound")
        self.create_alert_checkbox(content, "Enable Sound", sound_enabled_var)

        self.create_alert_section_label(content, "Windows Notification")
        self.create_alert_checkbox(
            content,
            "Enable Windows Notification",
            notification_enabled_var
        )

        self.create_alert_section_label(content, "Notification status")
        self.alert_notification_status_label = self.create_card_label(
            content,
            "",
            12,
            MUTED_TEXT_COLOR,
            True
        )
        self.alert_notification_status_label.pack(anchor="w", padx=14, pady=2)
        self.alert_sound_status_label = self.create_card_label(
            content,
            "",
            12,
            MUTED_TEXT_COLOR,
            True
        )
        self.alert_sound_status_label.pack(anchor="w", padx=14, pady=(2, 10))
        self.update_alert_status_labels()

        def save_alert_settings():
            try:
                minimum_quality = clamp_alert_quality(minimum_quality_var.get())
            except (TypeError, ValueError):
                messagebox.showerror(
                    APP_TITLE,
                    MINIMUM_QUALITY_ERROR
                )
                return

            self.alert_manager.update_settings(
                alerts_enabled=alerts_enabled_var.get(),
                minimum_quality=minimum_quality,
                scan_range=scan_range_var.get(),
                bullish=type_vars["bullish"].get(),
                bearish=type_vars["bearish"].get(),
                active=status_vars["active"].get(),
                aging=status_vars["aging"].get(),
                expired=status_vars["expired"].get(),
                sound_enabled=sound_enabled_var.get(),
                windows_notification_enabled=notification_enabled_var.get()
            )
            window.destroy()

        button_bar = ctk.CTkFrame(window, fg_color=BG_COLOR)
        button_bar.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        button_bar.grid_columnconfigure(0, weight=1)
        button_bar.grid_columnconfigure(1, weight=1)
        button_bar.grid_columnconfigure(2, weight=1)
        button_bar.grid_columnconfigure(3, weight=1)

        ctk.CTkButton(
            button_bar,
            text=CANCEL_BUTTON,
            height=36,
            fg_color=PANEL_COLOR,
            hover_color=BORDER_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_COLOR,
            corner_radius=8,
            command=window.destroy
        ).grid(row=0, column=0, sticky="ew", padx=(0, 5))

        ctk.CTkButton(
            button_bar,
            text="Test Alert",
            height=36,
            fg_color=PANEL_COLOR,
            hover_color=BORDER_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_COLOR,
            corner_radius=8,
            command=self.run_test_alert
        ).grid(row=0, column=1, sticky="ew", padx=5)

        ctk.CTkButton(
            button_bar,
            text="Force Test",
            height=36,
            fg_color=PANEL_COLOR,
            hover_color=BORDER_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_COLOR,
            corner_radius=8,
            command=self.run_force_test_alert
        ).grid(row=0, column=2, sticky="ew", padx=5)

        ctk.CTkButton(
            button_bar,
            text=SAVE_BUTTON,
            height=36,
            fg_color=BLUE,
            hover_color="#2D83C4",
            text_color="#FFFFFF",
            corner_radius=8,
            command=save_alert_settings
        ).grid(row=0, column=3, sticky="ew", padx=(5, 0))

    def run_test_alert(self):

        self.alert_manager.send_test_alert()
        self.update_alert_status_labels()

    def run_force_test_alert(self):

        self.alert_manager.send_force_test_alert(self.selected_interval)
        self.update_alert_status_labels()

    def update_alert_status_labels(self):

        if (
            self.alert_notification_status_label is None
            or self.alert_sound_status_label is None
        ):
            return

        status = self.alert_manager.notifier.diagnostic_status()

        if status["notification_ok"]:
            notification_text = "🟢 Windows Notification: OK"
            notification_color = GREEN
        else:
            notification_text = "🔴 Windows Notification: FAILED"
            notification_color = RED

        if status["sound_ok"]:
            sound_text = "🟢 Sound: OK"
            sound_color = GREEN
        else:
            sound_text = "🔴 Sound: FAILED"
            sound_color = RED

        self.configure_label_if_changed(
            self.alert_notification_status_label,
            text=notification_text,
            text_color=notification_color
        )
        self.configure_label_if_changed(
            self.alert_sound_status_label,
            text=sound_text,
            text_color=sound_color
        )

    def create_alert_section_label(self, parent, text):

        ctk.CTkLabel(
            parent,
            text=text,
            font=("Arial", 11, "bold"),
            text_color=MUTED_TEXT_COLOR
        ).pack(anchor="w", padx=14, pady=(8, 4))

    def create_alert_checkbox(self, parent, text, variable, compact=False, packed=True):

        checkbox = ctk.CTkCheckBox(
            parent,
            text=text,
            variable=variable,
            fg_color=BLUE,
            border_color=BORDER_COLOR,
            hover_color=BORDER_COLOR,
            text_color=TEXT_COLOR
        )

        if packed:
            if compact:
                checkbox.pack(side="left", padx=(0, 10), pady=2)
            else:
                checkbox.pack(anchor="w", padx=14, pady=2)

        return checkbox

    def build_ui(self):

        self.app.grid_columnconfigure(0, weight=1)
        self.app.grid_columnconfigure(1, weight=5)

        self.app.grid_rowconfigure(0, weight=1)

        self.left = ctk.CTkFrame(
            self.app,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=10
        )
        self.left.grid(row=0,column=0,sticky="nsew",padx=12,pady=12)

        self.center = ctk.CTkFrame(
            self.app,
            fg_color=BG_COLOR,
            corner_radius=0
        )
        self.center.grid(row=0, column=1, sticky="nsew", padx=0, pady=12)

        self.center.grid_rowconfigure(1, weight=1)
        self.center.grid_columnconfigure(0, weight=1)

        left_controls = ctk.CTkFrame(self.left, fg_color="transparent")
        left_controls.pack(fill="x")

        self.build_exchange_controls(left_controls)

        self.watchlist_title_label = ctk.CTkLabel(
            left_controls,
            text="WATCHLIST",
            font=("Arial",18,"bold"),
            text_color=TEXT_COLOR
        )
        self.watchlist_title_label.pack(pady=(14, 10))

        self.build_scan_mode_controls(left_controls)

        self.watchlist_scroll = ctk.CTkScrollableFrame(
            self.left,
            fg_color=PANEL_COLOR,
            scrollbar_button_color=BORDER_COLOR,
            scrollbar_button_hover_color=GRAY
        )
        self.watchlist_scroll.pack(fill="both", expand=True)

        self.reset_watchlist_button = ctk.CTkButton(
            left_controls,
            text=RESET_TOP20_BUTTON,
            height=34,
            fg_color=PANEL_COLOR,
            hover_color=BORDER_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            text_color=TEXT_COLOR,
            corner_radius=8,
            command=self.reset_watchlist_to_top20
        )
        self.reset_watchlist_button.pack(fill="x", padx=8, pady=(0, 8))

        self.build_watchlist_cards()
        self.update_scan_mode_buttons()

        self.build_top_bar()
        self.build_timeframe_bar()

        self.chart = SmartTradeChart(self.center)
        self.chart.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.update_polish_time()
        self.process_due_alerts()
        self.begin_scan_generation()
        self.schedule_scan_result_poll()
        self.schedule_scan_loop(0)

    def update_polish_time(self):

        if self.shutdown_requested:
            return

        current_time = current_polish_time()

        if self.top_time_label is not None:
            self.configure_label_if_changed(
                self.top_time_label,
                text=PL_TIME.format(time=current_time)
            )

        self.app.after(1000, self.update_polish_time)

    def build_timeframe_bar(self):

        timeframe_bar = ctk.CTkFrame(
            self.center,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=10
        )
        timeframe_bar.pack(fill="x", padx=10, pady=10)

        timeframes = [
            ("1m", "1"),
            ("5m", "5"),
            ("15m", "15"),
            ("30m", "30"),
            ("1H", "60"),
            ("4H", "240"),
            ("1D", "D")
        ]

        for label, interval in timeframes:

            button = ctk.CTkButton(
                timeframe_bar,
                text=label,
                width=70,
                height=32,
                fg_color=PANEL_COLOR,
                hover_color=BORDER_COLOR,
                border_color=BORDER_COLOR,
                border_width=1,
                text_color=MUTED_TEXT_COLOR,
                corner_radius=8,
                command=lambda value=interval: self.select_timeframe(value)
            )

            button.pack(side="left", padx=4, pady=6)

            self.timeframe_buttons[interval] = button

        self.update_timeframe_buttons()

    def run(self):

        self.app.mainloop()

    def shutdown_app(self):

        if getattr(self, "shutdown_requested", False):
            return

        self.shutdown_requested = True
        self.scan_generation = getattr(self, "scan_generation", 0) + 1
        self.current_scan_id = self.scan_generation
        self.cancel_scan_loop()
        self.cancel_scan_result_poll()
        self.clear_scan_result_queue()
        self.scan_shutdown_event.set()
        self.scan_job_event.set()

        try:
            self.app.destroy()
        except Exception:
            pass
