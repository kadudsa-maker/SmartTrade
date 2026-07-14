from exchange_providers.base import (
    ExchangeProvider, ExchangeProviderError, ExchangeSymbol,
    REQUIRED_CANDLE_COLUMNS, SMARTTRADE_INTERVALS, UnsupportedIntervalError,
)
from exchange_providers.bybit import BybitProvider
from exchange_providers.okx import OKXPerpetualProvider, OKXProvider
from exchange_providers.okx_spot import OKXSpotProvider


_PROVIDERS = {
    "bybit": BybitProvider(),
    "okx": OKXProvider(),
    "okx_spot": OKXSpotProvider(),
}


def get_provider(exchange_id):
    try:
        return _PROVIDERS[exchange_id]
    except KeyError as error:
        raise ValueError(f"Unknown exchange provider: {exchange_id}") from error


def get_providers():
    return dict(_PROVIDERS)


__all__ = [
    "BybitProvider", "ExchangeProvider", "ExchangeProviderError", "ExchangeSymbol",
    "OKXPerpetualProvider", "OKXProvider", "OKXSpotProvider",
    "REQUIRED_CANDLE_COLUMNS", "SMARTTRADE_INTERVALS",
    "UnsupportedIntervalError", "get_provider", "get_providers",
]
