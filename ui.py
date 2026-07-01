import customtkinter as ctk
from chart import SmartTradeChart
from divergence import find_regular_divergences
from market import get_watchlist, get_klines, calculate_rsi
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

        self.coins = [{"symbol": coin} for coin in get_watchlist()]
        self.buttons = []
        self.timeframe_buttons = {}
        self.best_divergence_label = None
        self.top_time_label = None
        self.bottom_time_label = None
        self.top_timeframe_label = None

        self.refresh_index = 0

        self.build_ui()

    def select_timeframe(self, interval):

        self.selected_interval = interval

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
        self.update_best_divergence_panel(
            self.select_best_divergence(self.chart.regular_divergences),
            len(self.chart.candles)
        )

        self.center_label.configure(
            text=f"{self.selected_symbol}\n\nCena: {price}\n\nRSI: {rsi}"
        )

    def refresh_one_coin(self):

        coin = self.coins[self.refresh_index]

        try:

            self.update_watchlist_coin(coin, self.refresh_index)

        except Exception as e:
            print(e)

        self.refresh_index += 1

        if self.refresh_index >= len(self.coins):
            self.refresh_index = 0

        if self.selected_symbol:
            self.refresh_selected()

        self.app.after(1000, self.refresh_one_coin)

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
        best_divergence = self.select_best_divergence(divergences)

        self.update_watchlist_card(
            index,
            symbol,
            rsi,
            best_divergence,
            len(candles)
        )

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

    def select_best_divergence(self, divergences):

        if not divergences:
            return None

        return max(
            divergences,
            key=lambda divergence: calculate_quality_score(divergence.get("quality"))
        )

    def update_watchlist_card(self, index, symbol, rsi, divergence, candle_count):

        card = self.buttons[index]
        status, status_color = self.signal_status(divergence, candle_count)
        setup_text, setup_color = self.signal_setup_text(divergence)
        signal_time = self.signal_time_text(divergence)
        age_text = self.signal_age_text(divergence, candle_count)

        card["symbol"].configure(text=symbol)
        card["status"].configure(text=status, text_color=status_color)
        card["setup"].configure(text=setup_text, text_color=setup_color)
        card["time"].configure(text=signal_time)
        card["age"].configure(text=age_text)
        card["rsi"].configure(text=f"RSI {rsi}")

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

    def create_watchlist_card(self, parent, symbol):

        frame = ctk.CTkFrame(
            parent,
            fg_color=BG_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=8
        )

        labels = {
            "symbol": self.create_card_label(frame, symbol, 14, TEXT_COLOR, True),
            "status": self.create_card_label(frame, "", 11, GRAY, True),
            "setup": self.create_card_label(frame, "—", 13, MUTED_TEXT_COLOR, True),
            "time": self.create_card_label(frame, "", 11, MUTED_TEXT_COLOR, False),
            "age": self.create_card_label(frame, "", 11, MUTED_TEXT_COLOR, False),
            "rsi": self.create_card_label(frame, "RSI —", 12, TEXT_COLOR, False)
        }

        labels["symbol"].pack(fill="x", padx=10, pady=(8, 0))
        labels["status"].pack(fill="x", padx=10, pady=(1, 0))
        labels["setup"].pack(fill="x", padx=10, pady=(1, 0))
        labels["time"].pack(fill="x", padx=10)
        labels["age"].pack(fill="x", padx=10)
        labels["rsi"].pack(fill="x", padx=10, pady=(0, 8))

        self.bind_card_click(frame, symbol)

        labels["frame"] = frame

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

        widget.bind("<Button-1>", lambda _event, s=symbol: self.select_coin(s))

        for child in widget.winfo_children():
            self.bind_card_click(child, symbol)

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

        ctk.CTkLabel(
            top_bar,
            text="SmartTrade",
            font=("Arial", 20, "bold"),
            text_color=TEXT_COLOR
        ).pack(side="left", padx=14)

        self.top_time_label = ctk.CTkLabel(
            top_bar,
            text="Czas PL: --:--:--",
            font=("Arial", 13, "bold"),
            text_color=MUTED_TEXT_COLOR
        )
        self.top_time_label.pack(side="left", padx=18)

        self.top_timeframe_label = ctk.CTkLabel(
            top_bar,
            text=f"TimeFrame: {self.interval_label(self.selected_interval)}",
            font=("Arial", 13, "bold"),
            text_color=BLUE
        )
        self.top_timeframe_label.pack(side="right", padx=14)

    def build_bottom_panel(self):

        self.status_bar.grid_columnconfigure(0, weight=1)
        self.status_bar.grid_columnconfigure(1, weight=1)
        self.status_bar.grid_columnconfigure(2, weight=2)

        time_section = self.create_bottom_section(self.status_bar, "Czas PL", 0)
        self.bottom_time_label = ctk.CTkLabel(
            time_section,
            text="--:--:--",
            font=("Arial", 16, "bold"),
            text_color=TEXT_COLOR
        )
        self.bottom_time_label.pack(anchor="w")

        legend_section = self.create_bottom_section(self.status_bar, "Legenda statusów", 1)
        ctk.CTkLabel(
            legend_section,
            text="ACTIVE   AGING   EXPIRED",
            font=("Arial", 12, "bold"),
            text_color=TEXT_COLOR
        ).pack(anchor="w")
        ctk.CTkLabel(
            legend_section,
            text="zielony   żółty   szary",
            font=("Arial", 11),
            text_color=MUTED_TEXT_COLOR
        ).pack(anchor="w")

        best_section = self.create_bottom_section(self.status_bar, "Najlepsza dywergencja", 2)
        self.best_divergence_label = ctk.CTkLabel(
            best_section,
            text="—",
            font=("Arial", 12, "bold"),
            text_color=MUTED_TEXT_COLOR,
            anchor="w",
            justify="left"
        )
        self.best_divergence_label.pack(fill="x")

    def create_bottom_section(self, parent, title, column):

        section = ctk.CTkFrame(
            parent,
            fg_color=PANEL_COLOR,
            corner_radius=8
        )
        section.grid(row=0, column=column, sticky="nsew", padx=10, pady=8)

        ctk.CTkLabel(
            section,
            text=title,
            font=("Arial", 11, "bold"),
            text_color=MUTED_TEXT_COLOR
        ).pack(anchor="w")

        return section

    def update_best_divergence_panel(self, divergence, candle_count):

        if self.best_divergence_label is None:
            return

        if divergence is None:
            self.best_divergence_label.configure(text="—", text_color=MUTED_TEXT_COLOR)
            return

        setup_text, setup_color = self.signal_setup_text(divergence)
        signal_time = self.signal_time_text(divergence)
        age_text = self.signal_age_text(divergence, candle_count)
        status, _status_color = self.signal_status(divergence, candle_count)

        self.best_divergence_label.configure(
            text=f"{status}  {setup_text}  {signal_time}  {age_text}",
            text_color=setup_color
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

    def build_ui(self):

        self.app.grid_columnconfigure(0, weight=1)
        self.app.grid_columnconfigure(1, weight=3)
        self.app.grid_columnconfigure(2, weight=1)

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
        

        self.right = ctk.CTkFrame(
            self.app,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=10
        )
        self.right.grid(row=0,column=2,sticky="nsew",padx=12,pady=12)

        scroll = ctk.CTkScrollableFrame(
            self.left,
            fg_color=PANEL_COLOR,
            scrollbar_button_color=BORDER_COLOR,
            scrollbar_button_hover_color=GRAY
        )
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(
            scroll,
            text="WATCHLIST",
            font=("Arial",18,"bold"),
            text_color=TEXT_COLOR
        ).pack(pady=(14, 10))

        for coin in self.coins:

            card = self.create_watchlist_card(
                scroll,
                coin["symbol"]
            )

            card["frame"].pack(fill="x", padx=8, pady=5)

            self.buttons.append(card)

        self.build_top_bar()
        self.build_timeframe_bar()

        self.chart = SmartTradeChart(self.center)
        self.chart.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.status_bar = ctk.CTkFrame(
            self.center,
            height=70,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=10
        )
        self.status_bar.pack(fill="x", padx=10, pady=(0, 10))

        self.build_bottom_panel()

        self.center_label = ctk.CTkLabel(
            self.center,
            text="Kliknij coina",
            font=("Arial",24,"bold"),
            text_color=TEXT_COLOR
        )

        self.center_label.pack(expand=True)

        ctk.CTkLabel(
            self.right,
            text="AI",
            font=("Arial",18,"bold"),
            text_color=TEXT_COLOR
        ).pack(pady=10)

        self.update_polish_time()
        self.refresh_one_coin()

    def update_polish_time(self):

        current_time = current_polish_time()

        if self.top_time_label is not None:
            self.top_time_label.configure(text=f"Czas PL: {current_time}")

        if self.bottom_time_label is not None:
            self.bottom_time_label.configure(text=current_time)

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
