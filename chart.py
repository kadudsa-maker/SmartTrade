import tkinter as tk

import customtkinter as ctk
import pandas as pd
import plotly.graph_objects as go
from pivots import find_pivots


class SmartTradeChart:

    def __init__(self, parent):

        self.frame = ctk.CTkFrame(parent)

        self.figure = go.Figure()
        self.candles = pd.DataFrame()
        self.rsi_period = 14
        self.rsi_series = pd.Series(dtype=float)
        self.pivot_highs = []
        self.pivot_lows = []
        self.divergence_lines = []
        self.rsi_divergence_lines = []

        self.canvas = tk.Canvas(
            self.frame,
            bg="#111111",
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)

        self.crosshair_x = None
        self.crosshair_y = None

        self.canvas.bind("<Configure>", self._draw)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Leave>", self._on_mouse_leave)

        self._configure_figure()

    def pack(self, **kwargs):

        self.frame.pack(**kwargs)

    def grid(self, **kwargs):

        self.frame.grid(**kwargs)

    def set_candles(self, df):

        self.candles = self._prepare_candles(df)
        self.rsi_series = self._calculate_rsi(self.candles["close"])
        self.pivot_highs, self.pivot_lows = find_pivots(self.candles)

        if self.candles.empty:
            return

        self._update_figure()
        self._draw()

    def set_rsi(self, rsi_data):

        self.rsi_series = rsi_data
        self._update_figure()
        self._draw()

    def set_divergences(self, divergence_lines):

        self.divergence_lines = divergence_lines
        self._update_figure()
        self._draw()

    def set_rsi_divergences(self, divergence_lines):

        self.rsi_divergence_lines = divergence_lines
        self._draw()

    def _configure_figure(self):

        self.figure.update_layout(
            template="plotly_dark",
            margin=dict(l=0, r=0, t=0, b=0),
            xaxis_rangeslider_visible=False,
            yaxis=dict(domain=[0.32, 1.0]),
            yaxis2=dict(domain=[0.0, 0.24], range=[0, 100], title="RSI")
        )

    def _update_figure(self):

        self.figure = go.Figure()
        self._configure_figure()

        if self.candles.empty:
            return

        self.figure.add_trace(
            go.Candlestick(
                x=pd.to_datetime(self.candles["time"], unit="s"),
                open=self.candles["open"],
                high=self.candles["high"],
                low=self.candles["low"],
                close=self.candles["close"],
                name="Price"
            )
        )

        self._add_rsi_trace()
        self._add_pivot_markers()
        self._add_divergence_traces()
        self._add_rsi_levels()

    def _add_rsi_trace(self):

        if self.rsi_series is None:
            return

        self.figure.add_trace(
            go.Scatter(
                x=pd.to_datetime(self.candles["time"], unit="s"),
                y=self.rsi_series,
                name="RSI 14",
                yaxis="y2"
            )
        )

    def _add_divergence_traces(self):

        for divergence in self.divergence_lines:
            self.figure.add_trace(divergence)

    def _add_pivot_markers(self):

        if self.pivot_highs:
            self.figure.add_trace(
                go.Scatter(
                    x=[pd.to_datetime(pivot["time"], unit="s") for pivot in self.pivot_highs],
                    y=[pivot["price"] for pivot in self.pivot_highs],
                    mode="markers",
                    marker=dict(color="#ef5350", size=7),
                    name="Pivot High"
                )
            )

        if self.pivot_lows:
            self.figure.add_trace(
                go.Scatter(
                    x=[pd.to_datetime(pivot["time"], unit="s") for pivot in self.pivot_lows],
                    y=[pivot["price"] for pivot in self.pivot_lows],
                    mode="markers",
                    marker=dict(color="#26a69a", size=7),
                    name="Pivot Low"
                )
            )

    def _add_rsi_levels(self):

        for level in [30, 50, 70]:
            self.figure.add_shape(
                type="line",
                xref="paper",
                yref="y2",
                x0=0,
                x1=1,
                y0=level,
                y1=level,
                line=dict(color="#777777", dash="dash")
            )

    def _calculate_rsi(self, close):

        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(self.rsi_period).mean()
        avg_loss = loss.rolling(self.rsi_period).mean()

        rs = avg_gain / avg_loss

        return 100 - (100 / (1 + rs))

    def _prepare_candles(self, df):

        candles = df[["time", "open", "high", "low", "close"]].copy()

        candles["time"] = pd.to_numeric(candles["time"])
        candles["time"] = (candles["time"] / 1000).astype(int)

        for column in ["open", "high", "low", "close"]:
            candles[column] = candles[column].astype(float)

        return candles

    def _on_mouse_move(self, event):

        self.crosshair_x = event.x
        self.crosshair_y = event.y
        self._draw()

    def _on_mouse_leave(self, _event):

        self.crosshair_x = None
        self.crosshair_y = None
        self._draw()

    def _draw(self, _event=None):

        self.canvas.delete("all")

        if self.candles.empty:
            self._draw_empty_state()
            return

        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()

        if width <= 2 or height <= 2:
            return

        padding = 28
        panel_gap = 18
        rsi_panel_height = max(90, int(height * 0.24))
        price_top = padding
        price_bottom = height - padding - panel_gap - rsi_panel_height
        rsi_top = price_bottom + panel_gap
        rsi_bottom = height - padding

        if price_bottom <= price_top or rsi_bottom <= rsi_top:
            return

        visible_candles = self.candles.tail(80).reset_index(drop=True)
        visible_rsi = self.rsi_series.tail(80).reset_index(drop=True)

        high = visible_candles["high"].max()
        low = visible_candles["low"].min()

        if high == low:
            return

        candle_area_width = width - (padding * 2)
        candle_area_height = price_bottom - price_top
        step = candle_area_width / max(len(visible_candles), 1)
        candle_width = max(3, step * 0.55)

        self._draw_price_grid(width, price_top, price_bottom, padding)
        self._draw_rsi_grid(width, rsi_top, rsi_bottom, padding)

        for index, candle in visible_candles.iterrows():
            x = padding + (index * step) + (step / 2)
            open_y = self._price_to_y(candle["open"], high, low, price_top, candle_area_height)
            high_y = self._price_to_y(candle["high"], high, low, price_top, candle_area_height)
            low_y = self._price_to_y(candle["low"], high, low, price_top, candle_area_height)
            close_y = self._price_to_y(candle["close"], high, low, price_top, candle_area_height)

            color = "#26a69a" if candle["close"] >= candle["open"] else "#ef5350"

            self.canvas.create_line(x, high_y, x, low_y, fill=color, width=1)
            self.canvas.create_rectangle(
                x - (candle_width / 2),
                min(open_y, close_y),
                x + (candle_width / 2),
                max(open_y, close_y),
                fill=color,
                outline=color
            )

        self._draw_rsi_line(visible_rsi, step, padding, rsi_top, rsi_bottom)
        self._draw_pivot_markers(visible_candles, high, low, step, padding, price_top, candle_area_height)
        self._draw_rsi_divergences(step, padding, rsi_top, rsi_bottom)
        self._draw_crosshair(width, price_top, rsi_bottom, padding)

    def _draw_empty_state(self):

        self.canvas.create_text(
            self.canvas.winfo_width() / 2,
            self.canvas.winfo_height() / 2,
            text="Brak danych wykresu",
            fill="#dddddd",
            font=("Arial", 16, "bold")
        )

    def _draw_price_grid(self, width, top, bottom, padding):

        grid_color = "#2b2b2b"

        for index in range(5):
            y = top + index * ((bottom - top) / 4)
            self.canvas.create_line(padding, y, width - padding, y, fill=grid_color)

        for index in range(6):
            x = padding + index * ((width - padding * 2) / 5)
            self.canvas.create_line(x, top, x, bottom, fill=grid_color)

    def _draw_rsi_grid(self, width, top, bottom, padding):

        self.canvas.create_rectangle(
            padding,
            top,
            width - padding,
            bottom,
            outline="#2b2b2b"
        )

        for level in [30, 50, 70]:
            y = self._rsi_to_y(level, top, bottom)
            color = "#555555" if level == 50 else "#666666"

            self.canvas.create_line(
                padding,
                y,
                width - padding,
                y,
                fill=color,
                dash=(4, 4)
            )
            self.canvas.create_text(
                padding - 8,
                y,
                text=str(level),
                fill="#aaaaaa",
                anchor="e",
                font=("Arial", 9)
            )

        self.canvas.create_text(
            padding,
            top - 8,
            text=f"RSI {self.rsi_period}",
            fill="#dddddd",
            anchor="w",
            font=("Arial", 10, "bold")
        )

    def _draw_rsi_line(self, visible_rsi, step, padding, top, bottom):

        points = []

        for index, value in visible_rsi.items():

            if pd.isna(value):
                continue

            x = padding + (index * step) + (step / 2)
            y = self._rsi_to_y(value, top, bottom)
            points.extend([x, y])

        if len(points) >= 4:
            self.canvas.create_line(
                *points,
                fill="#f6c85f",
                width=2,
                smooth=True
            )

    def _draw_pivot_markers(self, visible_candles, high, low, step, padding, top, chart_height):

        first_visible_index = len(self.candles) - len(visible_candles)

        for pivot in self.pivot_highs:
            visible_index = pivot["index"] - first_visible_index

            if not 0 <= visible_index < len(visible_candles):
                continue

            x = padding + (visible_index * step) + (step / 2)
            y = self._price_to_y(pivot["price"], high, low, top, chart_height) - 8

            self.canvas.create_oval(
                x - 4,
                y - 4,
                x + 4,
                y + 4,
                fill="#ef5350",
                outline="#ef5350"
            )

        for pivot in self.pivot_lows:
            visible_index = pivot["index"] - first_visible_index

            if not 0 <= visible_index < len(visible_candles):
                continue

            x = padding + (visible_index * step) + (step / 2)
            y = self._price_to_y(pivot["price"], high, low, top, chart_height) + 8

            self.canvas.create_oval(
                x - 4,
                y - 4,
                x + 4,
                y + 4,
                fill="#26a69a",
                outline="#26a69a"
            )

    def _draw_rsi_divergences(self, step, padding, top, bottom):

        for line in self.rsi_divergence_lines:
            start_index, start_value, end_index, end_value = line
            start_x = padding + (start_index * step) + (step / 2)
            end_x = padding + (end_index * step) + (step / 2)

            self.canvas.create_line(
                start_x,
                self._rsi_to_y(start_value, top, bottom),
                end_x,
                self._rsi_to_y(end_value, top, bottom),
                fill="#42a5f5",
                width=2
            )

    def _draw_crosshair(self, width, top, bottom, padding):

        if self.crosshair_x is None or self.crosshair_y is None:
            return

        if not padding <= self.crosshair_x <= width - padding:
            return

        if not top <= self.crosshair_y <= bottom:
            return

        self.canvas.create_line(
            self.crosshair_x,
            top,
            self.crosshair_x,
            bottom,
            fill="#666666",
            dash=(4, 4)
        )
        self.canvas.create_line(
            padding,
            self.crosshair_y,
            width - padding,
            self.crosshair_y,
            fill="#666666",
            dash=(4, 4)
        )

    def _price_to_y(self, price, high, low, padding, chart_height):

        return padding + ((high - price) / (high - low)) * chart_height

    def _rsi_to_y(self, value, top, bottom):

        clamped_value = max(0, min(100, value))

        return bottom - ((clamped_value / 100) * (bottom - top))
