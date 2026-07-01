import customtkinter as ctk
from market import get_top20, get_klines, calculate_rsi


class SmartTradeUI:

    def __init__(self):

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.app = ctk.CTk()
        self.app.geometry("1400x800")
        self.app.title("SmartTrade")

        self.selected_symbol = None

        self.coins = get_top20()
        self.buttons = []

        self.refresh_index = 0

        self.build_ui()

    def select_coin(self, symbol):

        self.selected_symbol = symbol

        self.refresh_selected()

    def refresh_selected(self):

        if self.selected_symbol is None:
            return

        df = get_klines(self.selected_symbol)

        rsi = calculate_rsi(df)

        price = round(df["close"].iloc[-1], 2)

        self.center_label.configure(
            text=f"{self.selected_symbol}\n\nCena: {price}\n\nRSI: {rsi}"
        )

    def refresh_one_coin(self):

        coin = self.coins[self.refresh_index]

        try:

            df = get_klines(coin["symbol"])

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
        self.center.grid(row=0,column=1,sticky="nsew",padx=10,pady=10)

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

    def run(self):

        self.app.mainloop()