import customtkinter as ctk
import time
from tkinter import BooleanVar, StringVar, messagebox

from alerts import AlertManager
from chart import SmartTradeChart
from config import (
    ACTIVE_MAX_CANDLES,
    AGING_MAX_CANDLES,
    MIN_VISIBLE_QUALITY,
    PIVOT_LEFT,
    PIVOT_RIGHT,
    SCAN_BATCH_SIZE,
    SCAN_INTERVAL_MS,
    SHOW_EXPIRED_SIGNALS,
    TOP_SCAN_BATCH_SIZES,
    TOP_SORT_INTERVAL_MS
)
from divergence import find_regular_divergences
from market import (
    calculate_rsi,
    filter_symbols,
    get_all_bybit_symbols,
    get_klines,
    get_top_bybit_symbols,
    get_watchlist,
    reset_watchlist,
    save_watchlist
)
from pivots import find_pivots, find_rsi_pivots
from rsi import calculate_rsi_series
from scanner_state import run_scan_batch, scan_mode_label
from signal_quality import calculate_quality_score
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
RSI_SORT_LABELS = {
    RSI_SORT_MODE_QUALITY: "Sort: Quality",
    RSI_SORT_MODE_RSI: "Sort: RSI",
    RSI_SORT_MODE_RSI_QUALITY: "Sort: RSI + Quality"
}


class SmartTradeUI:

    def __init__(self):

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.app = ctk.CTk()
        self.app.geometry("1400x800")
        self.app.title("SmartTrade")
        self.app.configure(fg_color=BG_COLOR)

        self.selected_symbol = None
        self.selected_interval = "15"
        self.scan_mode = SCAN_MODE_WATCHLIST
        self.top_bybit_limit = 50

        self.watchlist_symbols = get_watchlist()
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
        self.chart_refreshed_label = None
        self.watchlist_scroll = None
        self.watchlist_title_label = None
        self.reset_watchlist_button = None
        self.alert_notification_status_label = None
        self.alert_sound_status_label = None
        self.rsi_view_option = StringVar(value=RSI_VIEW_OFF)
        self.rsi_view_menu = None
        self.rsi_sort_mode = RSI_SORT_MODE_QUALITY
        self.rsi_sort_mode_label = None

        self.refresh_index = 0
        self.last_top50_sort_at = 0
        self.scan_cycle_number = 0
        self.last_scan_batch_time = None
        self.last_full_scan_time = None
        self.alert_manager = AlertManager(
            default_timeframe=self.selected_interval,
            default_scan_range=self.get_alert_scan_range()
        )
        self.alert_settings_window = None

        self.build_ui()

    def select_timeframe(self, interval):

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

        self.selected_symbol = symbol
        self.alert_manager.mark_opened_for_symbol(symbol)

        self.refresh_selected()

    def refresh_selected(self):

        if self.selected_symbol is None:
            return

        df = get_klines(
            self.selected_symbol,
            interval=self.selected_interval
        )
        df.attrs["symbol"] = self.selected_symbol
        df.attrs["timeframe"] = self.selected_interval

        self.chart.set_candles(df)
        self.update_open_chart_status(current_polish_time())

    def scan_one_coin(self):

        completed_cycle = False

        try:
            scan_symbols = self.get_scan_symbols()

            if not scan_symbols:
                return

            batch_result = run_scan_batch(
                scan_symbols,
                self.refresh_index,
                self.get_scan_batch_size(),
                lambda symbol, index: self.update_watchlist_coin(
                    {"symbol": symbol},
                    index
                )
            )
            self.refresh_index = batch_result["next_index"]
            completed_cycle = batch_result["completed_cycle"]

            for symbol, error in batch_result["errors"]:
                print(f"Scan symbol error: {symbol}: {error}")

            self.last_scan_batch_time = current_polish_time()

            if self.is_top_bybit_mode():
                self.sort_top50_cards_if_needed()

            if completed_cycle:
                self.mark_scan_cycle_completed(len(scan_symbols))

        except Exception as error:
            print(f"Scanner loop error: {error}")

        finally:
            self.app.after(SCAN_INTERVAL_MS, self.scan_one_coin)

    def mark_scan_cycle_completed(self, symbol_count):

        self.scan_cycle_number += 1
        self.last_full_scan_time = current_polish_time()

        print(
            "Scan cycle completed: "
            f"mode={scan_mode_label(self.scan_mode, self.top_bybit_limit)} "
            f"symbols={symbol_count} "
            f"cycle={self.scan_cycle_number} "
            f"time={self.last_full_scan_time}"
        )

    def reset_scan_cycle_state(self):

        self.scan_cycle_number = 0
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

        self.scan_mode = mode
        self.refresh_index = 0
        self.top50_results = {}
        self.last_top50_sort_at = time.monotonic()
        self.reset_scan_cycle_state()

        if self.is_top_bybit_mode():
            self.top_bybit_limit = self.get_top_bybit_limit()
            self.load_top50_scan_symbols()
        else:
            self.watchlist_symbols = get_watchlist()
            self.coins = [{"symbol": coin} for coin in self.watchlist_symbols]

        self.update_scan_mode_buttons()
        self.build_watchlist_cards()

    def load_top50_scan_symbols(self):

        symbols = get_top_bybit_symbols(self.top_bybit_limit)

        if not symbols:
            messagebox.showwarning(
                "SmartTrade",
                f"Nie udalo sie pobrac Top {self.top_bybit_limit} Bybit. Sprobuj ponownie za chwile."
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
            title = "WATCHLIST" if self.scan_mode == SCAN_MODE_WATCHLIST else f"TOP {self.top_bybit_limit} BYBIT"
            self.watchlist_title_label.configure(text=title)

        if self.reset_watchlist_button is not None:
            if self.scan_mode == SCAN_MODE_WATCHLIST:
                self.reset_watchlist_button.configure(state="normal", text_color=TEXT_COLOR)
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

    def update_watchlist_coin(self, coin, index):

        symbol = coin["symbol"]
        df = get_klines(
            symbol,
            interval=self.selected_interval
        )
        df.attrs["symbol"] = symbol
        df.attrs["timeframe"] = self.selected_interval

        rsi = calculate_rsi(df)
        candles = self.prepare_engine_candles(df)
        divergences = self.find_coin_divergences_from_candles(candles)
        best_divergence = self.select_freshest_best_signal(divergences, len(candles))
        self.process_alert_candidate(symbol, best_divergence, len(candles))

        if self.is_top_bybit_mode():
            self.top50_results[symbol] = {
                "symbol": symbol,
                "rsi": rsi,
                "divergence": best_divergence,
                "candle_count": len(candles)
            }
            self.update_top50_result_card(symbol)
            return

        self.update_watchlist_card(index, symbol, rsi, best_divergence, len(candles))

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

        return self.rsi_sort_key(status, age, rsi_extreme)

    def rsi_sort_key(self, status, age, rsi_extreme):

        is_fresh = self.is_fresh_rsi_setup(age)

        if is_fresh:
            primary = -age
            secondary = rsi_extreme
        else:
            primary = rsi_extreme
            secondary = -age

        return (
            self.rsi_status_priority(status),
            1 if is_fresh else 0,
            primary,
            secondary
        )

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
            text=RSI_SORT_LABELS.get(self.rsi_sort_mode, "Sort: Quality")
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

    def update_watchlist_card(self, index, symbol, rsi, divergence, candle_count):

        card = self.buttons[index]

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
        card_text = {
            "symbol": symbol,
            "market": "USDT Perpetual",
            "status": status,
            "status_color": status_color,
            "setup": setup_text,
            "setup_color": setup_color,
            "quality": quality_text,
            "time": signal_time,
            "age": age_text,
            "rsi": rsi_text,
            "rsi_color": rsi_color
        }
        cache_key = card["symbol_value"]

        if self.last_card_texts.get(cache_key) == card_text:
            return

        self.last_card_texts[cache_key] = card_text

        self.configure_label_if_changed(card["symbol"], text=symbol)
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
            text_color=TEXT_COLOR
        )
        self.configure_card_label_if_present(card, "time", text=signal_time)
        self.configure_label_if_changed(card["age"], text=age_text)
        self.update_rsi_card_visibility(card)
        self.configure_label_if_changed(
            card["rsi"],
            text=card_text["rsi"],
            text_color=rsi_color
        )

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

        if value > 70:
            return RED

        if value < 30:
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
            return "0 świec temu"

        if age == 1:
            return "1 świeca temu"

        return f"{age} świece temu"

    def signal_age(self, divergence, candle_count):

        if divergence.get("age_candles") is not None:
            return divergence["age_candles"]

        return max(0, candle_count - 1 - divergence.get("confirmed_index", divergence["price_end"]["index"]))

    def prepare_engine_candles(self, df):

        candles = df[["time", "open", "high", "low", "close"]].copy()
        candles.attrs["symbol"] = df.attrs.get("symbol", "UNKNOWN")
        candles.attrs["timeframe"] = self.selected_interval

        candles["time"] = candles["time"].astype(float).astype(int) // 1000

        for column in ["open", "high", "low", "close"]:
            candles[column] = candles[column].astype(float)

        return candles.sort_values("time").reset_index(drop=True)

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

        identity = ctk.CTkFrame(frame, fg_color="transparent")
        identity.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(10, 4), pady=6)
        identity.grid_columnconfigure(0, weight=1)

        symbol_label = self.create_card_label(identity, symbol, 14, TEXT_COLOR, True)
        symbol_label.grid(row=0, column=0, sticky="ew")

        market_label = self.create_card_label(identity, "USDT Perpetual", 10, MUTED_TEXT_COLOR, False)
        market_label.grid(row=1, column=0, sticky="ew", pady=(0, 1))

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
            edit_button.grid(row=0, column=1, rowspan=2, sticky="e", padx=(4, 0))

        labels = {
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
        self.update_rsi_card_visibility(labels)

        self.bind_card_click(frame, symbol)

        labels["frame"] = frame
        labels["symbol_value"] = symbol

        return labels

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
            symbols = get_all_bybit_symbols()
        except Exception as error:
            messagebox.showerror(
                "SmartTrade",
                f"Nie udało się pobrać listy coinów z Bybit.\n\n{error}"
            )
            return

        if not symbols:
            messagebox.showwarning(
                "SmartTrade",
                "Bybit nie zwrócił żadnych kontraktów USDT Perpetual."
            )
            return

        window = ctk.CTkToplevel(self.app)
        window.title("Wybierz coina")
        window.geometry("360x520")
        window.configure(fg_color=BG_COLOR)
        window.transient(self.app)
        window.grab_set()

        ctk.CTkLabel(
            window,
            text=f"Zmień {current_symbol}",
            font=("Arial", 18, "bold"),
            text_color=TEXT_COLOR
        ).pack(pady=(14, 10))

        search_frame = ctk.CTkFrame(window, fg_color="transparent")
        search_frame.pack(fill="x", padx=12, pady=(0, 10))

        ctk.CTkLabel(
            search_frame,
            text="🔍 Szukaj",
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
            filtered_symbols = filter_symbols(symbols, query)

            for child in scroll.winfo_children():
                child.destroy()

            if not filtered_symbols:
                ctk.CTkLabel(
                    scroll,
                    text="Brak wyników",
                    font=("Arial", 13, "bold"),
                    text_color=MUTED_TEXT_COLOR
                ).pack(fill="x", padx=6, pady=10)
                return

            for symbol in filtered_symbols:
                button = ctk.CTkButton(
                    scroll,
                    text=symbol,
                    height=34,
                    fg_color=BG_COLOR,
                    hover_color=BORDER_COLOR,
                    border_color=BORDER_COLOR,
                    border_width=1,
                    text_color=TEXT_COLOR,
                    corner_radius=6,
                    command=lambda value=symbol, dialog=window: self.replace_watchlist_coin(
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
            save_watchlist(updated_symbols)
        except Exception as error:
            messagebox.showerror(
                "SmartTrade",
                f"Nie udało się zapisać watchlisty.\n\n{error}"
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
            "SmartTrade",
            "Nadpisać watchlistę aktualnym Top20 Bybit według 24h Turnover?"
        )

        if not confirmed:
            return

        try:
            reset_watchlist()
        except Exception as error:
            messagebox.showerror(
                "SmartTrade",
                f"Nie udało się zresetować watchlisty.\n\n{error}"
            )
            return

        self.selected_symbol = None
        self.reload_watchlist()

    def reload_watchlist(self):

        self.watchlist_symbols = get_watchlist()

        if self.scan_mode == SCAN_MODE_WATCHLIST:
            self.coins = [{"symbol": coin} for coin in self.watchlist_symbols]

        self.refresh_index = 0

        self.build_watchlist_cards()

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
                        result["candle_count"]
                    )

    def sort_top50_cards(self):

        if not self.is_top_bybit_mode():
            return

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

        self.coins = [{"symbol": result["symbol"]} for result in sorted_results]
        self.reorder_top50_cards(sorted_results)
        self.last_top50_sort_at = time.monotonic()

    def sort_top50_cards_if_needed(self):

        elapsed_ms = (time.monotonic() - self.last_top50_sort_at) * 1000

        if elapsed_ms >= TOP_SORT_INTERVAL_MS:
            self.sort_top50_cards()

    def update_top50_result_card(self, symbol):

        card = self.cards_by_symbol.get(symbol)

        if card is None:
            return

        result = self.top50_results[symbol]
        self.update_watchlist_card(
            card["index"],
            result["symbol"],
            result["rsi"],
            result["divergence"],
            result["candle_count"]
        )

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
                    result["candle_count"]
                )

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
            (SCAN_MODE_TOP_BYBIT, "Top Bybit")
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
            text="TOP BYBIT RANGE",
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
            text="Czas PL: --:--:--",
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
            text="Otwarty: —",
            font=("Arial", 13, "bold"),
            text_color=TEXT_COLOR
        )
        self.open_chart_label.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(
            top_bar,
            text="|",
            font=("Arial", 13, "bold"),
            text_color=GRAY
        ).pack(side="left", padx=(0, 10))

        self.chart_refreshed_label = ctk.CTkLabel(
            top_bar,
            text="Wykres odświeżony: —",
            font=("Arial", 13, "bold"),
            text_color=MUTED_TEXT_COLOR
        )
        self.chart_refreshed_label.pack(side="left", padx=(0, 14))

        self.alerts_button = ctk.CTkButton(
            top_bar,
            text="🔔 Alerts",
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

        ctk.CTkLabel(
            top_bar,
            text="RSI View",
            font=("Arial", 12, "bold"),
            text_color=MUTED_TEXT_COLOR
        ).pack(side="right", padx=(0, 8))

        self.rsi_sort_mode_label = ctk.CTkLabel(
            top_bar,
            text=RSI_SORT_LABELS[RSI_SORT_MODE_QUALITY],
            font=("Arial", 12, "bold"),
            text_color=TEXT_COLOR
        )
        self.rsi_sort_mode_label.pack(side="right", padx=(0, 12))

    def update_open_chart_status(self, refreshed_at):

        if self.open_chart_label is not None:
            self.configure_label_if_changed(
                self.open_chart_label,
                text=f"Otwarty: {self.selected_symbol or '—'}"
            )

        if self.chart_refreshed_label is not None:
            self.configure_label_if_changed(
                self.chart_refreshed_label,
                text=f"Wykres odświeżony: {refreshed_at}"
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

    def process_alert_candidate(self, symbol, divergence, candle_count):

        if divergence is None:
            return

        status, _status_color = self.signal_status(divergence, candle_count)
        age_text = self.signal_age_text(divergence, candle_count)
        quality_score = calculate_quality_score(divergence.get("quality"))

        self.alert_manager.process_signal(
            symbol,
            self.selected_interval,
            self.get_alert_scan_range(),
            divergence,
            status,
            age_text,
            quality_score=quality_score
        )
        self.update_alert_status_labels()

    def process_due_alerts(self):

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
                    "SmartTrade",
                    "Minimum Quality musi być liczbą od 0 do 100."
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
            text="Anuluj",
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
            text="Zapisz",
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
            text="↻ Reset do Top20 Bybit",
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
        self.scan_one_coin()

    def update_polish_time(self):

        current_time = current_polish_time()

        if self.top_time_label is not None:
            self.configure_label_if_changed(
                self.top_time_label,
                text=f"Czas PL: {current_time}"
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
