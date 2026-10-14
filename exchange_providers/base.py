from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
import threading
import time
from typing import Any

import pandas as pd

from config import KLINE_CACHE_MAX_ENTRIES, KLINE_CACHE_TTL


REQUIRED_CANDLE_COLUMNS = [
    "time", "open", "high", "low", "close", "volume", "turnover"
]
SMARTTRADE_INTERVALS = ("1", "5", "15", "30", "60", "240", "D")


@dataclass(frozen=True)
class ExchangeSymbol:
    exchange_id: str
    exchange_symbol: str
    display_symbol: str
    base_currency: str
    quote_currency: str
    instrument_type: str
    status: str
    metadata: dict[str, Any] = field(default_factory=dict, compare=False)
    platform_market_name: str = ""
    asset_class: str = "other"


class ExchangeProviderError(RuntimeError):
    """A public exchange-data request failed or returned unusable data."""


class UnsupportedIntervalError(ExchangeProviderError):
    pass


class ExchangeProvider(ABC):
    exchange_id: str
    display_name: str
    interval_map: dict[str, str]

    def __init__(self):
        self._candle_cache = OrderedDict()
        self._candle_cache_lock = threading.RLock()
        self.candle_cache_max_entries = KLINE_CACHE_MAX_ENTRIES
        self.last_error = None

    @abstractmethod
    def get_instruments(self, force=False):
        raise NotImplementedError

    @abstractmethod
    def get_top_symbols(self, limit):
        raise NotImplementedError

    def search_symbols(self, query, limit=100):
        normalized = query.strip().upper()
        return [
            item for item in self.get_instruments()
            if normalized in item.display_symbol.upper()
            or normalized in item.exchange_symbol.upper()
            or normalized in item.platform_market_name.upper()
        ][:limit]

    @abstractmethod
    def get_klines(self, symbol, interval, limit):
        raise NotImplementedError

    def map_interval(self, interval):
        try:
            return self.interval_map[interval]
        except KeyError as error:
            raise UnsupportedIntervalError(
                f"{self.display_name} does not support interval {interval!r}."
            ) from error

    def cache_key(self, symbol, interval, limit):
        exchange_symbol = (
            symbol.exchange_symbol if isinstance(symbol, ExchangeSymbol) else str(symbol)
        )
        return f"{self.exchange_id}|{exchange_symbol}|{interval}|{limit}"

    def clear_cache(self):
        with self._candle_cache_lock:
            self._candle_cache.clear()

    def get_cached_candles(self, key, now=None):
        now = time.time() if now is None else float(now)
        with self._candle_cache_lock:
            cached = self._candle_cache.get(key)
            if cached is None:
                return None
            if now - cached["time"] >= KLINE_CACHE_TTL:
                self._candle_cache.pop(key, None)
                return None
            self._candle_cache.move_to_end(key)
            return cached["data"]

    def store_cached_candles(self, key, frame, now=None):
        now = time.time() if now is None else float(now)
        with self._candle_cache_lock:
            self._candle_cache[key] = {"time": now, "data": frame}
            self._candle_cache.move_to_end(key)
            while len(self._candle_cache) > self.candle_cache_max_entries:
                self._candle_cache.popitem(last=False)

    def candle_cache_size(self):
        with self._candle_cache_lock:
            return len(self._candle_cache)

    def resolve_symbol(self, symbol):
        if isinstance(symbol, ExchangeSymbol):
            if symbol.exchange_id != self.exchange_id:
                raise ExchangeProviderError(
                    f"Instrument {symbol.exchange_symbol} belongs to {symbol.exchange_id}, "
                    f"not {self.exchange_id}."
                )
            return symbol

        for item in self.get_instruments():
            if item.exchange_symbol == symbol or item.display_symbol == symbol:
                return item
        raise ExchangeProviderError(f"Instrument {symbol!r} is unavailable on {self.display_name}.")

    @staticmethod
    def normalize_candles(rows):
        frame = pd.DataFrame(rows, columns=REQUIRED_CANDLE_COLUMNS)
        if frame.empty:
            raise ExchangeProviderError("Exchange returned no candles.")
        frame["time"] = pd.to_numeric(frame["time"])
        for column in REQUIRED_CANDLE_COLUMNS[1:]:
            frame[column] = pd.to_numeric(frame[column]).astype(float)
        return (
            frame.drop_duplicates(subset="time", keep="last")
            .sort_values("time")
            .reset_index(drop=True)
        )
