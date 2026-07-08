import json
import time
from pathlib import Path

import pandas as pd
from pybit.unified_trading import HTTP

from config import (
    ALL_BYBIT_SYMBOLS_CACHE_TTL,
    DEFAULT_KLINE_LIMIT,
    DEFAULT_WATCHLIST_LIMIT,
    KLINE_CACHE_TTL,
    SYMBOL_SEARCH_LIMIT,
    TOP_BYBIT_CACHE_TTL
)
from rsi import calculate_latest_rsi

session = HTTP(testnet=False)

WATCHLIST_PATH = Path("data/watchlist.json")

# CACHE
cache = {}
top_bybit_cache = {}
top_bybit_last_error = None
all_bybit_symbols_cache = {
    "time": 0,
    "symbols": []
}


def get_top_bybit_symbols(limit=50):
    """Return top Bybit USDT linear symbols by 24h turnover, cached per limit."""

    global top_bybit_last_error

    cached = top_bybit_cache.get(limit)

    if (
        cached
        and cached["symbols"]
        and time.time() - cached["time"] < TOP_BYBIT_CACHE_TTL
    ):
        return cached["symbols"]

    try:
        response = session.get_tickers(category="linear")
        tickers = response["result"]["list"]

        usdt_tickers = [
            ticker
            for ticker in tickers
            if ticker.get("symbol", "").endswith("USDT")
        ]

        sorted_tickers = sorted(
            usdt_tickers,
            key=lambda ticker: float(ticker.get("turnover24h", 0)),
            reverse=True
        )

        symbols = [ticker["symbol"] for ticker in sorted_tickers[:limit]]

    except Exception as error:
        top_bybit_last_error = error
        print(f"Nie udało się pobrać Top {limit} Bybit: {error}")
        return []

    top_bybit_last_error = None
    top_bybit_cache[limit] = {
        "time": time.time(),
        "symbols": symbols
    }

    return symbols


def get_top_bybit_last_error():

    return top_bybit_last_error


def get_top20_usdt_perpetual_symbols(limit=DEFAULT_WATCHLIST_LIMIT):

    return get_top_bybit_symbols(limit)


def get_all_bybit_symbols():
    """Return every tradable Bybit linear USDT perpetual symbol with a 10 minute cache."""

    age = time.time() - all_bybit_symbols_cache["time"]

    if all_bybit_symbols_cache["symbols"] and age < ALL_BYBIT_SYMBOLS_CACHE_TTL:
        return all_bybit_symbols_cache["symbols"]

    try:
        symbols = _fetch_all_bybit_symbols()
    except Exception as error:
        print(f"Nie udalo sie pobrac pelnej listy symboli Bybit: {error}")
        return all_bybit_symbols_cache["symbols"]

    all_bybit_symbols_cache["time"] = time.time()
    all_bybit_symbols_cache["symbols"] = symbols

    print(f"Pobrano symbole Bybit USDT Perpetual: {len(symbols)}")

    return symbols


def filter_symbols(symbols, query, limit=SYMBOL_SEARCH_LIMIT):
    """Filter symbols case-insensitively by partial text and cap UI results."""

    normalized_query = query.strip().upper()

    matching_symbols = [
        symbol
        for symbol in symbols
        if normalized_query in symbol.upper()
    ]

    return matching_symbols[:limit]


def _fetch_all_bybit_symbols():

    instruments = []
    cursor = None

    while True:
        params = {
            "category": "linear",
            "limit": 1000
        }

        if cursor:
            params["cursor"] = cursor

        response = session.get_instruments_info(**params)
        result = response.get("result", {})
        instruments.extend(result.get("list", []))

        cursor = result.get("nextPageCursor")

        if not cursor:
            break

    symbols = [
        instrument["symbol"]
        for instrument in instruments
        if instrument.get("quoteCoin") == "USDT"
        and instrument.get("status") == "Trading"
        and instrument.get("contractType") == "LinearPerpetual"
    ]

    return sorted(set(symbols))


def load_default_watchlist():

    try:
        coins = get_top20_usdt_perpetual_symbols()
    except Exception as error:
        print(f"Nie udało się pobrać domyślnej watchlisty: {error}")
        coins = []

    if coins:
        save_watchlist(coins)

    return coins


def save_watchlist(coins):

    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)

    with WATCHLIST_PATH.open("w", encoding="utf-8") as file:
        json.dump({"coins": coins}, file, indent=4)


def reset_watchlist():

    coins = get_top20_usdt_perpetual_symbols()

    if not coins:
        raise RuntimeError("Bybit nie zwrócił listy Top20.")

    save_watchlist(coins)

    return coins


def get_klines(symbol="BTCUSDT", interval="15", limit=DEFAULT_KLINE_LIMIT):
    """Fetch ascending Bybit kline data with enough history for stable RSI."""

    limit = max(limit, DEFAULT_KLINE_LIMIT)
    key = f"{symbol}_{interval}_{limit}"

    # jeżeli dane są młodsze niż 30 sekund
    if key in cache:

        age = time.time() - cache[key]["time"]

        if age < KLINE_CACHE_TTL:

            return cache[key]["data"]

    response = session.get_kline(
        category="linear",
        symbol=symbol,
        interval=interval,
        limit=limit
    )

    candles = response["result"]["list"]

    candles.reverse()

    df = pd.DataFrame(
        candles,
        columns=[
            "time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover"
        ]
    )

    df["time"] = pd.to_numeric(df["time"])
    df = df.sort_values("time").reset_index(drop=True)

    for column in ["open", "high", "low", "close", "volume", "turnover"]:
        df[column] = df[column].astype(float)

    cache[key] = {
        "time": time.time(),
        "data": df
    }

    return df


def calculate_rsi(df, period=14):

    return calculate_latest_rsi(df["close"], period=period)


def get_watchlist():
    """Load the saved watchlist or rebuild the default Top20 list."""

    if not WATCHLIST_PATH.exists():
        return load_default_watchlist()

    try:
        with WATCHLIST_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)

    except (json.JSONDecodeError, OSError) as error:
        print(f"Nie udało się odczytać watchlisty: {error}")
        return load_default_watchlist()

    coins = data.get("coins", [])

    if not coins:
        return load_default_watchlist()

    return coins
