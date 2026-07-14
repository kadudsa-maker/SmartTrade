import time

from config import ALL_BYBIT_SYMBOLS_CACHE_TTL, KLINE_CACHE_TTL, OKX_BASE_URL, TOP_BYBIT_CACHE_TTL
from exchange_providers.base import ExchangeProviderError, ExchangeSymbol
from exchange_providers.okx import OKXPerpetualProvider


class OKXSpotProvider(OKXPerpetualProvider):
    exchange_id = "okx_spot"
    display_name = "OKX Spot"

    def __init__(self, session=None, base_url=OKX_BASE_URL):
        super().__init__(session=session, base_url=base_url)

    def get_instruments(self, force=False):
        if (
            not force and self._instruments
            and time.time() - self._instruments_at < ALL_BYBIT_SYMBOLS_CACHE_TTL
        ):
            self._instruments = [
                item for item in self._instruments
                if self._instrument_contract_valid(item)
            ]
            return list(self._instruments)
        data = self._get("/api/v5/public/instruments", {"instType": "SPOT"})
        validated = []
        for item in data:
            if not self._is_active_usdt_spot(item):
                self._log_instrument_boundary(item, accepted=False)
                continue
            instrument = ExchangeSymbol(
                self.exchange_id,
                item["instId"],
                self._display_symbol(item["instId"]),
                item.get("baseCcy") or item["instId"].split("-")[0],
                item.get("quoteCcy", ""),
                "spot",
                item.get("state", ""),
                item,
                platform_market_name=self._display_symbol(item["instId"]),
            )
            if (
                item.get("instType") != "SPOT"
                or instrument.exchange_symbol.endswith("-SWAP")
                or instrument.platform_market_name.endswith(" UM")
            ):
                self._log_instrument_boundary(item, accepted=False, hard_failure=True)
                continue
            self._log_instrument_boundary(
                item, accepted=True, instrument=instrument
            )
            validated.append(instrument)
        self._instruments = sorted(validated, key=lambda item: item.exchange_symbol)
        if not self._instruments:
            raise ExchangeProviderError("OKX returned no live USDT spot instruments.")
        self._instruments_at = time.time()
        self.last_error = None
        return list(self._instruments)

    def get_top_symbols(self, limit):
        cached = self._top_cache.get(limit)
        if cached and cached["symbols"] and time.time() - cached["time"] < TOP_BYBIT_CACHE_TTL:
            return cached["symbols"]
        instruments = {item.exchange_symbol: item for item in self.get_instruments()}
        tickers = self._get("/api/v5/market/tickers", {"instType": "SPOT"})
        ranked = sorted(
            (item for item in tickers if item.get("instId") in instruments),
            # For SPOT, OKX documents volCcy24h in quote currency. All retained
            # instruments quote in USDT, so this is a directly comparable turnover.
            key=lambda item: float(item.get("volCcy24h") or 0),
            reverse=True,
        )
        symbols = [instruments[item["instId"]] for item in ranked[:limit]]
        if not symbols:
            raise ExchangeProviderError(f"OKX Spot returned no Top {limit} symbols.")
        self._top_cache[limit] = {"time": time.time(), "symbols": symbols}
        return symbols

    def get_klines(self, symbol, interval, limit):
        instrument = self.resolve_symbol(symbol)
        mapped_interval = self.map_interval(interval)
        key = self.cache_key(instrument, interval, limit)
        cached = self._candle_cache.get(key)
        if cached and time.time() - cached["time"] < KLINE_CACHE_TTL:
            return cached["data"]
        data = self._get("/api/v5/market/candles", {
            "instId": instrument.exchange_symbol,
            "bar": mapped_interval,
            "limit": str(limit),
        })
        # SPOT: vol is base currency; volCcyQuote is quote currency turnover.
        rows = [row[:5] + [row[5], row[7]] for row in data]
        frame = self.normalize_candles(rows)
        frame.attrs.update(
            exchange_id=self.exchange_id,
            exchange_symbol=instrument.exchange_symbol,
            display_symbol=instrument.display_symbol,
        )
        self._candle_cache[key] = {"time": time.time(), "data": frame}
        return frame

    @staticmethod
    def _is_active_usdt_spot(item):
        inst_id = item.get("instId", "")
        return (
            item.get("instType") == "SPOT"
            and item.get("quoteCcy") == "USDT"
            and item.get("state") == "live"
            and item.get("ruleType", "normal") == "normal"
            and item.get("instCategory", "1") in ("", "1")
            and inst_id.endswith("-USDT")
            and not inst_id.endswith("-SWAP")
        )

    def _instrument_contract_valid(self, instrument):
        valid = (
            instrument.exchange_id == self.exchange_id
            and instrument.instrument_type == "spot"
            and instrument.metadata.get("instType") == "SPOT"
            and not instrument.exchange_symbol.endswith("-SWAP")
            and not instrument.platform_market_name.endswith(" UM")
        )
        if not valid:
            self._log_instrument_boundary(
                instrument.metadata,
                accepted=False,
                instrument=instrument,
                hard_failure=True,
            )
        return valid
