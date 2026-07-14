import time

from pybit.unified_trading import HTTP

from config import ALL_BYBIT_SYMBOLS_CACHE_TTL, KLINE_CACHE_TTL, TOP_BYBIT_CACHE_TTL
from exchange_providers.base import ExchangeProvider, ExchangeProviderError, ExchangeSymbol


class BybitProvider(ExchangeProvider):
    exchange_id = "bybit"
    display_name = "Bybit Futures"
    interval_map = {
        "1": "1", "5": "5", "15": "15", "30": "30",
        "60": "60", "240": "240", "D": "D"
    }

    def __init__(self, session=None):
        super().__init__()
        self.session = session or HTTP(testnet=False)
        self._instruments = []
        self._instruments_at = 0
        self._top_cache = {}

    def get_instruments(self, force=False):
        if (
            not force and self._instruments
            and time.time() - self._instruments_at < ALL_BYBIT_SYMBOLS_CACHE_TTL
        ):
            return self._instruments

        instruments = []
        cursor = None
        try:
            while True:
                params = {"category": "linear", "limit": 1000}
                if cursor:
                    params["cursor"] = cursor
                result = self.session.get_instruments_info(**params).get("result", {})
                instruments.extend(result.get("list", []))
                cursor = result.get("nextPageCursor")
                if not cursor:
                    break
        except Exception as error:
            self.last_error = error
            raise ExchangeProviderError(f"Could not fetch Bybit instruments: {error}") from error

        self._instruments = sorted({
            ExchangeSymbol(
                exchange_id=self.exchange_id,
                exchange_symbol=item["symbol"],
                display_symbol=item["symbol"],
                base_currency=item.get("baseCoin", ""),
                quote_currency=item.get("quoteCoin", ""),
                instrument_type="linear_perpetual",
                status=item.get("status", ""),
                metadata=item,
            )
            for item in instruments
            if item.get("quoteCoin") == "USDT"
            and item.get("status") == "Trading"
            and item.get("contractType") == "LinearPerpetual"
        }, key=lambda item: item.exchange_symbol)
        self._instruments_at = time.time()
        self.last_error = None
        if not self._instruments:
            raise ExchangeProviderError("Bybit returned no tradable USDT perpetual instruments.")
        return self._instruments

    def get_top_symbols(self, limit):
        cached = self._top_cache.get(limit)
        if cached and cached["symbols"] and time.time() - cached["time"] < TOP_BYBIT_CACHE_TTL:
            return cached["symbols"]
        try:
            tickers = self.session.get_tickers(category="linear")["result"]["list"]
            ranked = sorted(
                (item for item in tickers if item.get("symbol", "").endswith("USDT")),
                key=lambda item: float(item.get("turnover24h", 0)),
                reverse=True,
            )
            symbols = [
                ExchangeSymbol(
                    self.exchange_id, item["symbol"], item["symbol"],
                    item["symbol"][:-4], "USDT", "linear_perpetual", "Trading", item
                )
                for item in ranked[:limit]
            ]
        except Exception as error:
            self.last_error = error
            raise ExchangeProviderError(f"Could not fetch Top {limit} Bybit: {error}") from error
        self.last_error = None
        self._top_cache[limit] = {"time": time.time(), "symbols": symbols}
        return symbols

    def get_klines(self, symbol, interval, limit):
        instrument = symbol if isinstance(symbol, ExchangeSymbol) else ExchangeSymbol(
            self.exchange_id, str(symbol), str(symbol), str(symbol)[:-4], "USDT",
            "linear_perpetual", "Trading"
        )
        mapped_interval = self.map_interval(interval)
        key = self.cache_key(instrument, interval, limit)
        cached = self._candle_cache.get(key)
        if cached and time.time() - cached["time"] < KLINE_CACHE_TTL:
            return cached["data"]
        try:
            candles = self.session.get_kline(
                category="linear", symbol=instrument.exchange_symbol,
                interval=mapped_interval, limit=limit
            )["result"]["list"]
            frame = self.normalize_candles(candles)
        except ExchangeProviderError:
            raise
        except Exception as error:
            raise ExchangeProviderError(
                f"Could not fetch Bybit candles for {instrument.exchange_symbol}: {error}"
            ) from error
        frame.attrs.update(exchange_id=self.exchange_id, exchange_symbol=instrument.exchange_symbol,
                           display_symbol=instrument.display_symbol)
        self._candle_cache[key] = {"time": time.time(), "data": frame}
        return frame
