import customtkinter as ctk
import time
from tkinter import StringVar, messagebox
from chart import SmartTradeChart
from config import MIN_VISIBLE_QUALITY, SHOW_EXPIRED_SIGNALS
from divergence import find_regular_divergences
from market import (
    calculate_rsi,
    get_available_usdt_perpetual_symbols,
    get_klines,
    get_top_bybit_symbols,
    get_watchlist,
    reset_watchlist,
    save_watchlist
)
from pivots import find_pivots, find_rsi_pivots
from signal_quality import calculate_quality_score
from time_utils import current_polish_time, format_polish_time


BG_COLOR = "#111315"
PANEL_COLOR = "#181A1F"
BORDER_COLOR = "#2A2E36"
TEXT_COLOR = "#EAEAEA"
MUTED_TEXT_COLOR = "#8D96A0"
GREEN = "#2ECC71"
RED = "#E74C3C"
YELLOW = "#F1C40F"
BLUE = "#3498DB"
GRAY = "#6E7681"

ACTIVE_MAX_AGE = 3
AGING_MAX_AGE = 10
SCAN_INTERVAL_SECONDS = 1
SCAN_BATCH_SIZE = 3
SCAN_INTERVAL_MS = 1000
TOP50_SORT_INTERVAL_MS = 5000
SCAN_MODE_WATCHLIST = "watchlist"
SCAN_MODE_TOP50 = "top50"


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

        self.watchlist_symbols = get_watchlist()
        self.top50_symbols = []
        self.top50_results = {}
        self.coins = [{"symbol": coin} for coin in self.watchlist_symbols]
        self.buttons = []
        self.timeframe_buttons = {}
        self.scan_mode_buttons = {}
        self.top_time_label = None
        self.top_timeframe_label = None
        self.last_scan_label = None
        self.next_scan_label = None
        self.scan_progress_label = None
        self.watchlist_scroll = None
        self.watchlist_title_label = None
        self.reset_watchlist_button = None

        self.refresh_index = 0
        self.next_scan_seconds = SCAN_INTERVAL_SECONDS
        self.last_top50_sort_at = 0

        self.build_ui()

    def select_timeframe(self, interval):

        self.selected_interval = interval
        self.refresh_index = 0
        self.top50_results = {}
        self.reset_scan_countdown()

        if self.scan_mode == SCAN_MODE_TOP50:
            self.coins = [{"symbol": symbol} for symbol in self.top50_symbols]
            self.build_watchlist_cards()

        self.update_timeframe_buttons()
        self.update_scan_progress()
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

        self.refresh_selected()

    def refresh_selected(self):

        if self.selected_symbol is None:
            return

        df = get_klines(
            self.selected_symbol,
            interval=self.selected_interval
        )
        df.attrs["symbol"] = self.selected_symbol

        rsi = calculate_rsi(df)

        price = round(df["close"].iloc[-1], 2)

        self.chart.set_candles(df)

    def refresh_one_coin(self):

        self.scan_one_coin()

    def scan_one_coin(self):

        scan_symbols = self.get_scan_symbols()

        if not scan_symbols:
            self.reset_scan_countdown()
            self.app.after(SCAN_INTERVAL_MS, self.scan_one_coin)
            return

        scanned_count = 0

        while scanned_count < SCAN_BATCH_SIZE and scan_symbols:
            if self.refresh_index >= len(scan_symbols):
                self.refresh_index = 0

            symbol = scan_symbols[self.refresh_index]

            try:
                self.update_watchlist_coin({"symbol": symbol}, self.refresh_index)
            except Exception as e:
                print(e)

            self.refresh_index += 1
            scanned_count += 1

            if self.refresh_index >= len(scan_symbols):
                self.refresh_index = 0
                break

        if self.scan_mode == SCAN_MODE_TOP50:
            self.sort_top50_cards_if_needed()

        self.mark_scan_finished()

        self.app.after(SCAN_INTERVAL_MS, self.scan_one_coin)

    def mark_scan_finished(self):

        if self.last_scan_label is not None:
            self.configure_label_if_changed(
                self.last_scan_label,
                text=f"Ostatni skan: {current_polish_time()}"
            )

        self.reset_scan_countdown()
        self.update_scan_progress()

    def reset_scan_countdown(self):

        self.next_scan_seconds = SCAN_INTERVAL_SECONDS

    def update_scan_progress(self):

        if self.scan_progress_label is None:
            return

        total = len(self.get_scan_symbols())
        scanned = len(self.top50_results) if self.scan_mode == SCAN_MODE_TOP50 else self.refresh_index

        if self.scan_mode == SCAN_MODE_WATCHLIST and scanned == 0 and total:
            scanned = total

        self.configure_label_if_changed(
            self.scan_progress_label,
            text=f"Skan: {min(scanned, total)}/{total}"
        )

    def get_scan_symbols(self):

        # Watchlist scans exactly in the user's saved order.
        if self.scan_mode == SCAN_MODE_WATCHLIST:
            return self.watchlist_symbols

        # Top 50 scans the fixed Bybit list, while cards are ranked separately.
        return self.top50_symbols

    def set_scan_mode(self, mode):

        if mode == self.scan_mode:
            return

        self.scan_mode = mode
        self.refresh_index = 0
        self.reset_scan_countdown()

        if mode == SCAN_MODE_TOP50:
            self.top50_results = {}
            self.load_top50_scan_symbols()
        else:
            self.watchlist_symbols = get_watchlist()
            self.coins = [{"symbol": coin} for coin in self.watchlist_symbols]

        self.update_scan_mode_buttons()
        self.build_watchlist_cards()
        self.update_scan_progress()

    def load_top50_scan_symbols(self):

        symbols = get_top_bybit_symbols(50)

        if not symbols:
            messagebox.showwarning(
                "SmartTrade",
                "Nie udało się pobrać Top 50 Bybit. Spróbuj ponownie za chwilę."
            )

        self.top50_symbols = symbols
        self.coins = [{"symbol": symbol} for symbol in self.top50_symbols]

    def update_scan_mode_buttons(self):

        for mode, button in self.scan_mode_buttons.items():
            if mode == self.scan_mode:
                button.configure(fg_color=BLUE, text_color="#FFFFFF", border_color=BLUE)
            else:
                button.configure(
                    fg_color=PANEL_COLOR,
                    text_color=MUTED_TEXT_COLOR,
                    border_color=BORDER_COLOR
                )

        if self.watchlist_title_label is not None:
            title = "WATCHLIST" if self.scan_mode == SCAN_MODE_WATCHLIST else "TOP 50 BYBIT"
            self.watchlist_title_label.configure(text=title)

        if self.reset_watchlist_button is not None:
            if self.scan_mode == SCAN_MODE_WATCHLIST:
                self.reset_watchlist_button.configure(state="normal", text_color=TEXT_COLOR)
            else:
                self.reset_watchlist_button.configure(state="disabled", text_color=GRAY)

    def update_watchlist_coin(self, coin, index):

        symbol = coin["symbol"]
        df = get_klines(
            symbol,
            interval=self.selected_interval
        )
        df.attrs["symbol"] = symbol

        rsi = calculate_rsi(df)
        candles = self.prepare_engine_candles(df)
        divergences = self.find_coin_divergences_from_candles(candles)
        best_divergence = self.select_freshest_best_signal(divergences, len(candles))

        if self.scan_mode == SCAN_MODE_TOP50:
            self.top50_results[symbol] = {
                "symbol": symbol,
                "rsi": rsi,
                "divergence": best_divergence,
                "candle_count": len(candles)
            }
            self.update_top50_result_card(symbol)
            return

        self.update_watchlist_card(index, symbol, rsi, best_divergence, len(candles))

    def find_coin_divergences(self, df):

        candles = self.prepare_engine_candles(df)
        return self.find_coin_divergences_from_candles(candles)

    def find_coin_divergences_from_candles(self, candles):

        rsi_series = self.calculate_rsi_series(candles["close"])
        price_pivot_highs, price_pivot_lows = find_pivots(candles)
        rsi_pivot_highs, rsi_pivot_lows = find_rsi_pivots(
            rsi_series,
            candles["time"]
        )

        return find_regular_divergences(
            candles,
            rsi_series,
            price_pivot_highs,
            price_pivot_lows,
            rsi_pivot_highs,
            rsi_pivot_lows
        )

    def select_best_divergence(self, divergences, candle_count=None):

        if candle_count is not None:
            return self.select_freshest_best_signal(
                divergences,
                candle_count,
                visible_only=True
            )

        return self.select_freshest_best_signal(divergences)

    def select_best_signal(self, divergences, candle_count=None, visible_only=False):

        return self.select_freshest_best_signal(
            divergences,
            candle_count,
            visible_only
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
        freshness = divergence["price_end"]["index"]

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
        freshness = divergence["price_end"]["index"]
        quality_score = calculate_quality_score(divergence.get("quality"))

        return priorities.get(status, 0), freshness, quality_score, rsi

    def is_visible_signal(self, divergence, candle_count):

        quality_score = calculate_quality_score(divergence.get("quality"))

        if quality_score < MIN_VISIBLE_QUALITY:
            return False

        status, _status_color = self.signal_status(divergence, candle_count)

        if status == "EXPIRED" and not SHOW_EXPIRED_SIGNALS:
            return False

        return True

    def is_visible_divergence(self, divergence, candle_count):

        return self.is_visible_signal(divergence, candle_count)

    def update_watchlist_card(self, index, symbol, rsi, divergence, candle_count):

        card = self.buttons[index]

        if divergence is None:
            status = ""
            status_color = GRAY
            setup_text = "—"
            setup_color = MUTED_TEXT_COLOR
            signal_time = ""
            age_text = ""
        elif self.is_visible_signal(divergence, candle_count):
            status, status_color = self.signal_status(divergence, candle_count)
            status = self.format_status_label(status)
            setup_text, setup_color = self.signal_setup_text(divergence)
            signal_time = self.signal_time_text(divergence)
            age_text = self.signal_age_text(divergence, candle_count)
        else:
            status, status_color, setup_text, setup_color, signal_time, age_text = (
                self.format_filtered_signal(divergence, candle_count)
            )

        self.configure_label_if_changed(card["symbol"], text=symbol)
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
        self.configure_label_if_changed(card["time"], text=signal_time)
        self.configure_label_if_changed(card["age"], text=age_text)
        self.configure_label_if_changed(card["rsi"], text=f"RSI {rsi}")

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

        if status == "EXPIRED":
            filter_status = "⚪ Expired"
        else:
            filter_status = "⚪ Filtered"

        return filter_status, GRAY, setup_text, setup_color, signal_time, age_text

    def format_status_label(self, status):

        icons = {
            "ACTIVE": "🟢",
            "AGING": "🟡",
            "EXPIRED": "⚪"
        }

        icon = icons.get(status)

        if icon is None:
            return status

        return f"{icon} {status}"

    def format_watchlist_button(self, symbol, rsi, divergence):

        if divergence is None:
            return f"{symbol}\n—\nRSI {rsi}"

        quality_score = calculate_quality_score(divergence.get("quality"))
        signal_time = format_polish_time(divergence["price_end"]["time"])

        if divergence["type"] == "bullish":
            return f"{symbol}\n🟢 Bull Q:{quality_score}\n{signal_time} PL\nRSI {rsi}"

        return f"{symbol}\n🔴 Bear Q:{quality_score}\n{signal_time} PL\nRSI {rsi}"

    def signal_setup_text(self, divergence):

        if divergence is None:
            return "—", MUTED_TEXT_COLOR

        quality_score = calculate_quality_score(divergence.get("quality"))

        if divergence["type"] == "bullish":
            return f"Bull Q:{quality_score}", GREEN

        return f"Bear Q:{quality_score}", RED

    def signal_status(self, divergence, candle_count):

        if divergence is None:
            return "", GRAY

        age = self.signal_age(divergence, candle_count)

        if age <= ACTIVE_MAX_AGE:
            return "ACTIVE", GREEN

        if age <= AGING_MAX_AGE:
            return "AGING", YELLOW

        return "EXPIRED", GRAY

    def signal_time_text(self, divergence):

        if divergence is None:
            return ""

        return f"{format_polish_time(divergence['price_end']['time'])} PL"

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

        return max(0, candle_count - 1 - divergence["price_end"]["index"])

    def prepare_engine_candles(self, df):

        candles = df[["time", "open", "high", "low", "close"]].copy()
        candles.attrs["symbol"] = df.attrs.get("symbol", "UNKNOWN")

        candles["time"] = candles["time"].astype(float).astype(int) // 1000

        for column in ["open", "high", "low", "close"]:
            candles[column] = candles[column].astype(float)

        return candles

    def calculate_rsi_series(self, close):

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()

        rs = avg_gain / avg_loss

        return 100 - (100 / (1 + rs))

    def create_watchlist_card(self, parent, symbol, index, editable=True):

        frame = ctk.CTkFrame(
            parent,
            fg_color=BG_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=8
        )

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 0))

        symbol_label = self.create_card_label(header, symbol, 14, TEXT_COLOR, True)
        symbol_label.pack(side="left", fill="x", expand=True)

        if editable:
            edit_button = ctk.CTkButton(
                header,
                text="✎",
                width=28,
                height=24,
                fg_color=PANEL_COLOR,
                hover_color=BORDER_COLOR,
                border_color=BORDER_COLOR,
                border_width=1,
                text_color=MUTED_TEXT_COLOR,
                corner_radius=6,
                command=lambda card_index=index: self.open_coin_selector(card_index)
            )
            edit_button.pack(side="right")

        labels = {
            "symbol": symbol_label,
            "status": self.create_card_label(frame, "", 11, GRAY, True),
            "setup": self.create_card_label(frame, "—", 13, MUTED_TEXT_COLOR, True),
            "time": self.create_card_label(frame, "", 11, MUTED_TEXT_COLOR, False),
            "age": self.create_card_label(frame, "", 11, MUTED_TEXT_COLOR, False),
            "rsi": self.create_card_label(frame, "RSI —", 12, TEXT_COLOR, False)
        }

        labels["status"].pack(fill="x", padx=10, pady=(1, 0))
        labels["setup"].pack(fill="x", padx=10, pady=(1, 0))
        labels["time"].pack(fill="x", padx=10)
        labels["age"].pack(fill="x", padx=10)
        labels["rsi"].pack(fill="x", padx=10, pady=(0, 8))

        self.bind_card_click(frame, symbol)

        labels["frame"] = frame
        labels["symbol_value"] = symbol

        return labels

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
            symbols = get_available_usdt_perpetual_symbols()
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
            query = search_var.get().strip().upper()
            filtered_symbols = [
                symbol
                for symbol in symbols
                if query in symbol.upper()
            ]

            for child in scroll.winfo_children():
                child.destroy()

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

        editable = self.scan_mode == SCAN_MODE_WATCHLIST

        for index, coin in enumerate(self.coins):
            card = self.create_watchlist_card(
                self.watchlist_scroll,
                coin["symbol"],
                index,
                editable=editable
            )

            card["frame"].pack(fill="x", padx=8, pady=5)
            self.buttons.append(card)

            if self.scan_mode == SCAN_MODE_TOP50:
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

        if self.scan_mode != SCAN_MODE_TOP50:
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

        if elapsed_ms >= TOP50_SORT_INTERVAL_MS:
            self.sort_top50_cards()

    def update_top50_result_card(self, symbol):

        for index, card in enumerate(self.buttons):
            if card["symbol_value"] != symbol:
                continue

            result = self.top50_results[symbol]
            self.update_watchlist_card(
                index,
                result["symbol"],
                result["rsi"],
                result["divergence"],
                result["candle_count"]
            )
            return

    def reorder_top50_cards(self, sorted_results):

        cards_by_symbol = {
            card["symbol_value"]: card
            for card in self.buttons
        }

        if any(result["symbol"] not in cards_by_symbol for result in sorted_results):
            self.build_watchlist_cards()
            return

        for card in self.buttons:
            card["frame"].pack_forget()

        self.buttons = []

        for index, result in enumerate(sorted_results):
            symbol = result["symbol"]
            card = cards_by_symbol[symbol]

            card["frame"].pack(fill="x", padx=8, pady=5)
            self.buttons.append(card)

            if symbol in self.top50_results:
                self.update_watchlist_card(
                    index,
                    symbol,
                    result["rsi"],
                    result["divergence"],
                    result["candle_count"]
                )

    def build_scan_mode_controls(self):

        container = ctk.CTkFrame(self.watchlist_scroll, fg_color="transparent")
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
            (SCAN_MODE_TOP50, "Top 50")
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

        self.update_scan_mode_buttons()

    def build_top_bar(self):

        top_bar = ctk.CTkFrame(
            self.center,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=10,
            height=54
        )
        top_bar.pack(fill="x", padx=10, pady=(0, 10))

        self.top_time_label = ctk.CTkLabel(
            top_bar,
            text="Czas PL: --:--:--",
            font=("Arial", 13, "bold"),
            text_color=MUTED_TEXT_COLOR
        )
        self.top_time_label.pack(side="left", padx=14)

        self.top_timeframe_label = ctk.CTkLabel(
            top_bar,
            text=f"TimeFrame: {self.interval_label(self.selected_interval)}",
            font=("Arial", 13, "bold"),
            text_color=BLUE
        )
        self.top_timeframe_label.pack(side="right", padx=14)

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
        self.watchlist_scroll = ctk.CTkScrollableFrame(
            self.left,
            fg_color=PANEL_COLOR,
            scrollbar_button_color=BORDER_COLOR,
            scrollbar_button_hover_color=GRAY
        )
        self.watchlist_scroll.pack(fill="both", expand=True)

        self.watchlist_title_label = ctk.CTkLabel(
            self.watchlist_scroll,
            text="WATCHLIST",
            font=("Arial",18,"bold"),
            text_color=TEXT_COLOR
        )
        self.watchlist_title_label.pack(pady=(14, 10))

        self.build_scan_mode_controls()

        self.reset_watchlist_button = ctk.CTkButton(
            self.watchlist_scroll,
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
        self.scan_one_coin()

    def update_polish_time(self):

        current_time = current_polish_time()

        if self.top_time_label is not None:
            self.configure_label_if_changed(
                self.top_time_label,
                text=f"Czas PL: {current_time}"
            )

        self.app.after(1000, self.update_polish_time)

    def update_scan_countdown(self):

        if self.next_scan_label is not None:
            self.configure_label_if_changed(
                self.next_scan_label,
                text=f"Następny skan za: {self.next_scan_seconds} s"
            )

        if self.next_scan_seconds > 0:
            self.next_scan_seconds -= 1

        self.app.after(1000, self.update_scan_countdown)

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
