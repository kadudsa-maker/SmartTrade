import tkinter as tk

import customtkinter as ctk
import pandas as pd
import plotly.graph_objects as go
from config import ACTIVE_MAX_CANDLES, AGING_MAX_CANDLES, PIVOT_LEFT, PIVOT_RIGHT
from divergence import find_regular_divergences
from pivots import find_pivots, find_rsi_pivots
from rsi import calculate_rsi_series
from signal_quality import calculate_quality_score
from strings import CHART_NO_DATA
from time_utils import format_polish_time


BG_COLOR = "#111315"
PANEL_COLOR = "#181A1F"
BORDER_COLOR = "#2A2E36"
TEXT_COLOR = "#EAEAEA"
MUTED_TEXT_COLOR = "#8D96A0"
GREEN = "#2ECC71"
RED = "#E74C3C"
YELLOW = "#F1C40F"
GRAY = "#6E7681"

class SmartTradeChart:

    def __init__(self, parent):

        self.frame = ctk.CTkFrame(
            parent,
            fg_color=PANEL_COLOR,
            border_color=BORDER_COLOR,
            border_width=1,
            corner_radius=10
        )

        self.figure = go.Figure()
        self.candles = pd.DataFrame()
        self.rsi_period = 14
        self.rsi_series = pd.Series(dtype=float)
        self.pivot_highs = []
        self.pivot_lows = []
        self.rsi_pivot_highs = []
        self.rsi_pivot_lows = []
        self.regular_divergences = []
        self._last_source_key = None

        self.canvas = tk.Canvas(
            self.frame,
            bg=BG_COLOR,
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

        source_key = (
            id(df),
            df.attrs.get("exchange_id"),
            df.attrs.get("exchange_symbol"),
            df.attrs.get("symbol"),
            df.attrs.get("platform_market_name"),
            df.attrs.get("asset_class"),
            df.attrs.get("timeframe")
        )

        if source_key == self._last_source_key:
            return

        self.candles = self._prepare_candles(df)
        self.rsi_series = self._calculate_rsi(self.candles["close"])
        self.pivot_highs, self.pivot_lows = find_pivots(
            self.candles,
            left=PIVOT_LEFT,
            right=PIVOT_RIGHT
        )
        self.rsi_pivot_highs, self.rsi_pivot_lows = find_rsi_pivots(
            self.rsi_series,
            self.candles["time"],
            left=PIVOT_LEFT,
            right=PIVOT_RIGHT
        )
        self.regular_divergences = find_regular_divergences(
            self.candles,
            self.rsi_series,
            self.pivot_highs,
            self.pivot_lows,
            self.rsi_pivot_highs,
            self.rsi_pivot_lows
        )

        if self.candles.empty:
            self._last_source_key = source_key
            return

        self._update_figure()
        self._draw()
        self._last_source_key = source_key

    def _configure_figure(self):

        self.figure.update_layout(
            template="plotly_dark",
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=False,
            hovermode=False,
            xaxis_rangeslider_visible=False,
            paper_bgcolor=BG_COLOR,
            plot_bgcolor=BG_COLOR,
            font=dict(color=TEXT_COLOR),
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
                name="Price",
                hoverinfo="skip",
                showlegend=False
            )
        )

        self._add_rsi_trace()
        self._add_pivot_markers()
        self._add_rsi_pivot_markers()
        self._add_regular_divergence_traces()
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

    def _add_rsi_pivot_markers(self):

        if self.rsi_pivot_highs:
            self.figure.add_trace(
                go.Scatter(
                    x=[pd.to_datetime(pivot["time"], unit="s") for pivot in self.rsi_pivot_highs],
                    y=[pivot["price"] for pivot in self.rsi_pivot_highs],
                    mode="markers",
                    marker=dict(color="#ef5350", size=7),
                    name="RSI Pivot High",
                    yaxis="y2"
                )
            )

        if self.rsi_pivot_lows:
            self.figure.add_trace(
                go.Scatter(
                    x=[pd.to_datetime(pivot["time"], unit="s") for pivot in self.rsi_pivot_lows],
                    y=[pivot["price"] for pivot in self.rsi_pivot_lows],
                    mode="markers",
                    marker=dict(color="#26a69a", size=7),
                    name="RSI Pivot Low",
                    yaxis="y2"
                )
            )

    def _add_regular_divergence_traces(self):

        for divergence in self.regular_divergences:
            color, label, name = self._divergence_style(divergence["type"])
            quality_label = self._divergence_label_with_quality(label, divergence)
            self._add_divergence_trace_pair(divergence, color, name, quality_label)

    def _add_divergence_trace_pair(self, divergence, color, name, label):

        price_start = divergence["price_start"]
        price_end = divergence["price_end"]
        rsi_start = divergence["rsi_start"]
        rsi_end = divergence["rsi_end"]
        price_mid_time = self._mid_time(price_start, price_end)
        price_mid_value = (price_start["price"] + price_end["price"]) / 2
        rsi_mid_time = self._mid_time(rsi_start, rsi_end)
        rsi_mid_value = (rsi_start["price"] + rsi_end["price"]) / 2

        self.figure.add_trace(
            go.Scatter(
                x=[
                    pd.to_datetime(price_start["time"], unit="s"),
                    pd.to_datetime(price_mid_time, unit="s"),
                    pd.to_datetime(price_end["time"], unit="s")
                ],
                y=[price_start["price"], price_mid_value, price_end["price"]],
                mode="lines+text",
                line=dict(color=color, width=2),
                text=["", label, ""],
                textfont=dict(color=TEXT_COLOR),
                textposition="middle center",
                name=f"{name} Price"
            )
        )

        self.figure.add_trace(
            go.Scatter(
                x=[
                    pd.to_datetime(rsi_start["time"], unit="s"),
                    pd.to_datetime(rsi_mid_time, unit="s"),
                    pd.to_datetime(rsi_end["time"], unit="s")
                ],
                y=[rsi_start["price"], rsi_mid_value, rsi_end["price"]],
                mode="lines+text",
                line=dict(color=color, width=2),
                text=["", label, ""],
                textfont=dict(color=TEXT_COLOR),
                textposition="middle center",
                name=f"{name} RSI",
                yaxis="y2"
            )
        )

    def _divergence_style(self, divergence_type):

        if divergence_type == "bullish":
            return "#26a69a", "Bull Div", "Regular Bullish"

        return "#ef5350", "Bear Div", "Regular Bearish"

    def _divergence_label_with_quality(self, label, divergence):

        quality_score = self._quality_score(divergence)
        signal_time = format_polish_time(
            divergence.get("confirmed_time", divergence["price_end"]["time"])
        )
        status = self._signal_status(divergence)

        return f"{label}\n{status}\nQ: {quality_score}\n{signal_time} PL"

    def _quality_score(self, divergence):

        return calculate_quality_score(divergence.get("quality"))

    def _signal_status(self, divergence):

        age = self._signal_age(divergence)

        if age <= ACTIVE_MAX_CANDLES:
            return "ACTIVE"

        if age <= AGING_MAX_CANDLES:
            return "AGING"

        return "EXPIRED"

    def _signal_age(self, divergence):

        if divergence.get("age_candles") is not None:
            return divergence["age_candles"]

        return max(0, len(self.candles) - 1 - divergence.get("confirmed_index", divergence["price_end"]["index"]))

    def _mid_time(self, start, end):

        return (float(start["time"]) + float(end["time"])) / 2

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

        return calculate_rsi_series(close, period=self.rsi_period)

    def _prepare_candles(self, df):

        columns = ["time", "open", "high", "low", "close"]

        if "volume" in df.columns:
            columns.append("volume")

        candles = df[columns].copy()
        candles.attrs["symbol"] = df.attrs.get("symbol", "UNKNOWN")
        candles.attrs["timeframe"] = df.attrs.get("timeframe")
        candles.attrs["exchange_id"] = df.attrs.get("exchange_id")
        candles.attrs["exchange_name"] = df.attrs.get("exchange_name")
        candles.attrs["platform_market_name"] = df.attrs.get("platform_market_name")
        candles.attrs["asset_class"] = df.attrs.get("asset_class", "other")

        candles["time"] = pd.to_numeric(candles["time"])
        candles["time"] = (candles["time"] / 1000).astype(int)

        if "volume" not in candles.columns:
            candles["volume"] = 0

        for column in ["open", "high", "low", "close", "volume"]:
            candles[column] = candles[column].astype(float)

        return candles.sort_values("time").reset_index(drop=True)

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
        self._draw_rsi_pivot_markers(visible_candles, step, padding, rsi_top, rsi_bottom)
        self._draw_regular_divergences(
            visible_candles,
            high,
            low,
            step,
            padding,
            price_top,
            candle_area_height,
            rsi_top,
            rsi_bottom
        )
        self._draw_crosshair(
            width,
            price_top,
            rsi_bottom,
            padding,
            high,
            low,
            price_top,
            candle_area_height
        )

    def _draw_empty_state(self):

        self.canvas.create_text(
            self.canvas.winfo_width() / 2,
            self.canvas.winfo_height() / 2,
            text=CHART_NO_DATA,
            fill="#dddddd",
            font=("Arial", 16, "bold")
        )

    def _draw_price_grid(self, width, top, bottom, padding):

        grid_color = BORDER_COLOR

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
                x - 3,
                y - 3,
                x + 3,
                y + 3,
                fill=RED,
                outline=RED
            )

        for pivot in self.pivot_lows:
            visible_index = pivot["index"] - first_visible_index

            if not 0 <= visible_index < len(visible_candles):
                continue

            x = padding + (visible_index * step) + (step / 2)
            y = self._price_to_y(pivot["price"], high, low, top, chart_height) + 8

            self.canvas.create_oval(
                x - 3,
                y - 3,
                x + 3,
                y + 3,
                fill=GREEN,
                outline=GREEN
            )

    def _draw_rsi_pivot_markers(self, visible_candles, step, padding, top, bottom):

        first_visible_index = len(self.candles) - len(visible_candles)

        for pivot in self.rsi_pivot_highs:
            visible_index = pivot["index"] - first_visible_index

            if not 0 <= visible_index < len(visible_candles):
                continue

            x = padding + (visible_index * step) + (step / 2)
            y = self._rsi_to_y(pivot["price"], top, bottom) - 6

            self.canvas.create_oval(
                x - 3,
                y - 3,
                x + 3,
                y + 3,
                fill=RED,
                outline=RED
            )

        for pivot in self.rsi_pivot_lows:
            visible_index = pivot["index"] - first_visible_index

            if not 0 <= visible_index < len(visible_candles):
                continue

            x = padding + (visible_index * step) + (step / 2)
            y = self._rsi_to_y(pivot["price"], top, bottom) + 6

            self.canvas.create_oval(
                x - 3,
                y - 3,
                x + 3,
                y + 3,
                fill=GREEN,
                outline=GREEN
            )

    def _draw_regular_divergences(
        self,
        visible_candles,
        high,
        low,
        step,
        padding,
        price_top,
        price_height,
        rsi_top,
        rsi_bottom
    ):

        first_visible_index = len(self.candles) - len(visible_candles)

        for divergence in self.regular_divergences:
            color, label, _name = self._divergence_style(divergence["type"])
            quality_label = self._divergence_label_with_quality(label, divergence)
            self._draw_divergence_pair(
                divergence,
                color,
                quality_label,
                first_visible_index,
                len(visible_candles),
                high,
                low,
                step,
                padding,
                price_top,
                price_height,
                rsi_top,
                rsi_bottom
            )

    def _draw_divergence_pair(
        self,
        divergence,
        color,
        label,
        first_visible_index,
        visible_count,
        high,
        low,
        step,
        padding,
        price_top,
        price_height,
        rsi_top,
        rsi_bottom
    ):

        price_start = divergence["price_start"]
        price_end = divergence["price_end"]
        rsi_start = divergence["rsi_start"]
        rsi_end = divergence["rsi_end"]

        if not self._is_line_visible(price_start, price_end, first_visible_index, visible_count):
            return

        price_start_x = self._pivot_x(price_start, first_visible_index, step, padding)
        price_end_x = self._pivot_x(price_end, first_visible_index, step, padding)
        price_start_y = self._price_to_y(price_start["price"], high, low, price_top, price_height)
        price_end_y = self._price_to_y(price_end["price"], high, low, price_top, price_height)
        rsi_start_x = self._pivot_x(rsi_start, first_visible_index, step, padding)
        rsi_end_x = self._pivot_x(rsi_end, first_visible_index, step, padding)
        rsi_start_y = self._rsi_to_y(rsi_start["price"], rsi_top, rsi_bottom)
        rsi_end_y = self._rsi_to_y(rsi_end["price"], rsi_top, rsi_bottom)

        self.canvas.create_line(
            price_start_x,
            price_start_y,
            price_end_x,
            price_end_y,
            fill=color,
            width=2
        )
        self.canvas.create_text(
            (price_start_x + price_end_x) / 2,
            ((price_start_y + price_end_y) / 2) - 14,
            text=label,
            fill=TEXT_COLOR,
            font=("Arial", 9, "bold")
        )

        self.canvas.create_line(
            rsi_start_x,
            rsi_start_y,
            rsi_end_x,
            rsi_end_y,
            fill=color,
            width=2
        )
        self.canvas.create_text(
            (rsi_start_x + rsi_end_x) / 2,
            ((rsi_start_y + rsi_end_y) / 2) - 14,
            text=label,
            fill=TEXT_COLOR,
            font=("Arial", 9, "bold")
        )

    def _is_line_visible(self, start_pivot, end_pivot, first_visible_index, visible_count):

        first = first_visible_index
        last = first_visible_index + visible_count - 1

        return first <= start_pivot["index"] <= last and first <= end_pivot["index"] <= last

    def _pivot_x(self, pivot, first_visible_index, step, padding):

        visible_index = pivot["index"] - first_visible_index

        return padding + (visible_index * step) + (step / 2)

    def _draw_crosshair(
        self,
        width,
        top,
        bottom,
        padding,
        high,
        low,
        price_top,
        price_height
    ):

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
        self._draw_cursor_price_label(
            width,
            padding,
            high,
            low,
            price_top,
            price_height
        )

    def _draw_cursor_price_label(self, width, padding, high, low, top, chart_height):

        if self.crosshair_y is None:
            return

        if chart_height <= 0:
            return

        if not top <= self.crosshair_y <= top + chart_height:
            return

        price = high - ((self.crosshair_y - top) / chart_height) * (high - low)
        self._draw_price_axis_label(
            width,
            padding,
            self.crosshair_y,
            price,
            BG_COLOR,
            TEXT_COLOR
        )

    def _draw_price_axis_label(self, width, padding, y, price, fill, text_fill):

        label_width = 72
        label_height = 20
        x1 = width - 2
        x0 = x1 - label_width
        y0 = y - (label_height / 2)
        y1 = y + (label_height / 2)

        self.canvas.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            fill=fill,
            outline=BORDER_COLOR
        )
        self.canvas.create_text(
            (x0 + x1) / 2,
            y,
            text=f"{price:.4f}",
            fill=text_fill,
            font=("Arial", 9, "bold")
        )

    def _price_to_y(self, price, high, low, padding, chart_height):

        return padding + ((high - price) / (high - low)) * chart_height

    def _rsi_to_y(self, value, top, bottom):

        clamped_value = max(0, min(100, value))

        return bottom - ((clamped_value / 100) * (bottom - top))
