import customtkinter as ctk
from chart import SmartTradeChart
from market import get_watchlist, get_klines, calculate_rsi


class SmartTradeUI:

    def __init__(self):

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.app = ctk.CTk()
        self.app.geometry("1400x800")
        self.app.title("SmartTrade")

        self.selected_symbol = None
        self.selected_interval = "15"

        self.coins = [{"symbol": coin} for coin in get_watchlist()]
        self.buttons = []
        self.timeframe_buttons = {}

        self.refresh_index = 0

        self.build_ui()

    def select_timeframe(self, interval):

        self.selected_interval = interval

        self.update_timeframe_buttons()
        self.refresh_selected()

    def update_timeframe_buttons(self):

        for interval, button in self.timeframe_buttons.items():

            if interval == self.selected_interval:
                button.configure(fg_color="#1f6aa5")

            else:
                button.configure(fg_color="#3a3a3a")

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

        rsi = calculate_rsi(df)

        price = round(df["close"].iloc[-1], 2)

        self.chart.set_candles(df)

        self.center_label.configure(
            text=f"{self.selected_symbol}\n\nCena: {price}\n\nRSI: {rsi}"
        )

    def refresh_one_coin(self):

        coin = self.coins[self.refresh_index]

        try:

            df = get_klines(
                coin["symbol"],
                interval=self.selected_interval
            )

            rsi = calculate_rsi(df)

            icon = ""

            if rsi <= 30:
                icon = " 🔥"

            elif rsi >= 70:
                icon = " ⚠"

            self.buttons[self.refresh_index].configure(
                text=f"{coin['symbol']}\nRSI {rsi}{icon}"
            )

        except Exception as e:
            print(e)

        self.refresh_index += 1

        if self.refresh_index >= len(self.coins):
            self.refresh_index = 0

        if self.selected_symbol:
            self.refresh_selected()

        self.app.after(1000, self.refresh_one_coin)

    def build_ui(self):

        self.app.grid_columnconfigure(0, weight=1)
        self.app.grid_columnconfigure(1, weight=3)
        self.app.grid_columnconfigure(2, weight=1)

        self.app.grid_rowconfigure(0, weight=1)

        self.left = ctk.CTkFrame(self.app)
        self.left.grid(row=0,column=0,sticky="nsew",padx=10,pady=10)

        self.center = ctk.CTkFrame(self.app)
        self.center.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.center.grid_rowconfigure(1, weight=1)
        self.center.grid_columnconfigure(0, weight=1)
        

        self.right = ctk.CTkFrame(self.app)
        self.right.grid(row=0,column=2,sticky="nsew",padx=10,pady=10)

        scroll = ctk.CTkScrollableFrame(self.left)
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(
            scroll,
            text="WATCHLIST",
            font=("Arial",20,"bold")
        ).pack(pady=10)

        for coin in self.coins:

            button = ctk.CTkButton(
                scroll,
                text=coin["symbol"],
                height=50,
                command=lambda s=coin["symbol"]: self.select_coin(s)
            )

            button.pack(fill="x", padx=5, pady=3)

            self.buttons.append(button)

        self.build_timeframe_bar()

        self.chart = SmartTradeChart(self.center)
        self.chart.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.status_bar = ctk.CTkFrame(
            self.center,
            height=45
        )

        self.center_label = ctk.CTkLabel(
            self.center,
            text="Kliknij coina",
            font=("Arial",28,"bold")
        )

        self.center_label.pack(expand=True)

        ctk.CTkLabel(
            self.right,
            text="AI",
            font=("Arial",20,"bold")
        ).pack(pady=10)

        self.refresh_one_coin()

    def build_timeframe_bar(self):

        timeframe_bar = ctk.CTkFrame(self.center)
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
                command=lambda value=interval: self.select_timeframe(value)
            )

            button.pack(side="left", padx=4, pady=6)

            self.timeframe_buttons[interval] = button

        self.update_timeframe_buttons()

    def run(self):

        self.app.mainloop()
