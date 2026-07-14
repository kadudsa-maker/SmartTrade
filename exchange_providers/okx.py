import logging
import time

import requests

from config import (
    ALL_BYBIT_SYMBOLS_CACHE_TTL,
    KLINE_CACHE_TTL,
    OKX_EEA_BASE_URL,
    TOP_BYBIT_CACHE_TTL,
)
from exchange_providers.base import ExchangeProvider, ExchangeProviderError, ExchangeSymbol


logger = logging.getLogger(__name__)


class OKXPerpetualProvider(ExchangeProvider):
    exchange_id = "okx"
    display_name = "OKX Perpetual"
    interval_map = {
        "1": "1m", "5": "5m", "15": "15m", "30": "30m",
        "60": "1H", "240": "4H", "D": "1Dutc"
    }

    def __init__(self, session=None, base_url=OKX_EEA_BASE_URL):
        super().__init__()
        self.session = session or requests.Session()
        self.base_url = base_url.rstrip("/")
        self._instruments = []
        self._instruments_at = 0
        self._top_cache = {}
        self.last_public_futures_count = 0
        self.last_public_swap_count = 0
        self.last_identified_xperps_count = 0
        self.last_asset_class_counts = {}

    def _get(self, path, params):
        try:
            response = self.session.get(
                f"{self.base_url}{path}", params=params, timeout=(5, 15)
            )
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as error:
            raise ExchangeProviderError("OKX EEA public request timed out.") from error
        except requests.RequestException as error:
            raise ExchangeProviderError(f"OKX EEA HTTP request failed: {error}") from error
        except ValueError as error:
            raise ExchangeProviderError("OKX EEA returned invalid JSON.") from error
        if payload.get("code") != "0":
            code = payload.get("code") or "unknown"
            raise ExchangeProviderError(f"OKX EEA public API error {code}.")
        return payload.get("data", [])

    def get_instruments(self, force=False):
        if (
            not force and self._instruments
            and time.time() - self._instruments_at < ALL_BYBIT_SYMBOLS_CACHE_TTL
        ):
            self._instruments = [
                item for item in self._instruments if self._instrument_contract_valid(item)
            ]
            return list(self._instruments)

        futures = self._get("/api/v5/public/instruments", {"instType": "FUTURES"})
        swaps = self._get("/api/v5/public/instruments", {"instType": "SWAP"})
        identified_xperps = [item for item in futures if self._is_xperp(item)]

        validated = []
        for item in identified_xperps:
            display_symbol = self._display_symbol(item)
            asset_class = self._asset_class(item)
            instrument = ExchangeSymbol(
                self.exchange_id,
                item["instId"],
                display_symbol,
                (item.get("uly") or item["instId"]).split("-")[0],
                "USD",
                "futures",
                item.get("state", ""),
                {
                    **item,
                    "instrument_scope": "public_eea",
                    "platform_market": "UM",
                    "market_validation": "OKX EEA public crypto X-Perp",
                },
                platform_market_name=f"{display_symbol} UM",
                asset_class=asset_class,
            )
            self._log_instrument_boundary(item, accepted=True, instrument=instrument)
            validated.append(instrument)

        self._instruments = sorted(validated, key=lambda item: item.exchange_symbol)
        self.last_public_futures_count = len(futures)
        self.last_public_swap_count = len(swaps)
        self.last_identified_xperps_count = len(identified_xperps)
        self.last_asset_class_counts = {
            asset_class: sum(item.asset_class == asset_class for item in self._instruments)
            for asset_class in ("crypto", "stock", "etf", "commodity", "index", "other")
        }
        if not self._instruments:
            raise ExchangeProviderError(
                "OKX EEA public API returned no live crypto X-Perps."
            )
        self._instruments_at = time.time()
        self.last_error = None
        return list(self._instruments)

    def get_top_symbols(self, limit):
        cached = self._top_cache.get(limit)
        if cached and cached["symbols"] and time.time() - cached["time"] < TOP_BYBIT_CACHE_TTL:
            return list(cached["symbols"])
        instruments = {item.exchange_symbol: item for item in self.get_instruments()}
        tickers = self._get("/api/v5/market/tickers", {"instType": "FUTURES"})
        ranked = sorted(
            (item for item in tickers if item.get("instId") in instruments),
            key=self._ticker_turnover,
            reverse=True,
        )
        effective_scan_limit = min(limit, len(instruments))
        symbols = [instruments[item["instId"]] for item in ranked[:effective_scan_limit]]
        if not symbols:
            raise ExchangeProviderError(f"OKX EEA returned no Top {limit} X-Perps.")
        logger.info(
            "OKX EEA X-PERPS: public_futures_count=%s public_swap_count=%s "
            "total_xperps=%s crypto_count=%s stock_count=%s etf_count=%s "
            "commodity_count=%s index_count=%s other_count=%s "
            "selected_top_limit=%s effective_scan_limit=%s",
            self.last_public_futures_count,
            self.last_public_swap_count,
            self.last_identified_xperps_count,
            self.last_asset_class_counts["crypto"],
            self.last_asset_class_counts["stock"],
            self.last_asset_class_counts["etf"],
            self.last_asset_class_counts["commodity"],
            self.last_asset_class_counts["index"],
            self.last_asset_class_counts["other"],
            limit,
            effective_scan_limit,
        )
        self._top_cache[limit] = {"time": time.time(), "symbols": symbols}
        return list(symbols)

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
        # OKX FUTURES: volCcy is underlying volume and volCcyQuote is USD turnover.
        rows = [row[:5] + [row[6], row[7]] for row in data]
        frame = self.normalize_candles(rows)
        frame.attrs.update(
            exchange_id=self.exchange_id,
            exchange_symbol=instrument.exchange_symbol,
            display_symbol=instrument.display_symbol,
            platform_market_name=instrument.platform_market_name,
            asset_class=instrument.asset_class,
        )
        self._candle_cache[key] = {"time": time.time(), "data": frame}
        return frame

    @staticmethod
    def _display_symbol(item):
        if isinstance(item, str):
            parts = item.split("-")
            return "".join(parts[:2]) if len(parts) >= 2 else item
        underlying = item.get("uly", "")
        parts = underlying.split("-")
        return "".join(parts[:2]) if len(parts) >= 2 else underlying or item.get("instId", "")

    @staticmethod
    def _is_xperp(item):
        inst_id = item.get("instId", "")
        family = item.get("instFamily", "")
        return (
            item.get("instType") == "FUTURES"
            and item.get("ruleType") == "xperp"
            and item.get("alias") == "this_five_years"
            and item.get("ctType") == "linear"
            and item.get("settleCcy") == "USD"
            and item.get("state") == "live"
            and OKXPerpetualProvider._has_five_year_expiry(item)
            and family.endswith("_UM_XPERP")
            and inst_id.startswith(f"{family}-")
        )

    @staticmethod
    def _has_five_year_expiry(item):
        try:
            duration_ms = int(item.get("expTime")) - int(item.get("listTime"))
        except (TypeError, ValueError):
            return False
        year_ms = 365 * 24 * 60 * 60 * 1000
        return int(4.5 * year_ms) <= duration_ms <= int(5.5 * year_ms)

    @staticmethod
    def _asset_class(item):
        explicit = str(item.get("assetClass") or item.get("asset_class") or "").lower()
        aliases = {
            "crypto": "crypto", "cryptocurrency": "crypto",
            "stock": "stock", "stocks": "stock", "equity": "stock",
            "etf": "etf", "commodity": "commodity", "commodities": "commodity",
            "index": "index",
        }
        if explicit:
            return aliases.get(explicit, "other")
        return {
            "1": "crypto",
            "3": "stock",
            "4": "commodity",
        }.get(str(item.get("instCategory") or ""), "other")

    @staticmethod
    def _ticker_turnover(item):
        try:
            return float(item.get("volCcy24h") or 0) * float(item.get("last") or 0)
        except (TypeError, ValueError):
            return 0.0

    def _log_instrument_boundary(
        self, item, *, accepted, instrument=None, hard_failure=False
    ):
        log = logger.warning if hard_failure else logger.debug
        log(
            "OKX EEA X-Perp boundary accepted=%s exchange_symbol=%s "
            "display_symbol=%s instType=%s ruleType=%s alias=%s category=%s "
            "ctType=%s settleCcy=%s state=%s expTime=%s",
            accepted,
            item.get("instId", ""),
            instrument.display_symbol if instrument is not None else "",
            item.get("instType", ""),
            item.get("ruleType", ""),
            item.get("alias", ""),
            item.get("instCategory", ""),
            item.get("ctType", ""),
            item.get("settleCcy", ""),
            item.get("state", ""),
            item.get("expTime", ""),
        )

    def _instrument_contract_valid(self, instrument):
        return (
            instrument.exchange_id == self.exchange_id
            and instrument.instrument_type == "futures"
            and instrument.metadata.get("instrument_scope") == "public_eea"
            and self._is_xperp(instrument.metadata)
            and instrument.exchange_symbol == instrument.metadata.get("instId")
            and instrument.asset_class == self._asset_class(instrument.metadata)
        )


OKXProvider = OKXPerpetualProvider
