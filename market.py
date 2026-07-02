import json
from pathlib import Path
from pybit.unified_trading import HTTP
import pandas as pd
import time
from rsi import calculate_latest_rsi

session = HTTP(testnet=False)

WATCHLIST_PATH = Path("data/watchlist.json")
TOP_BYBIT_CACHE_TTL = 300
ALL_BYBIT_SYMBOLS_CACHE_TTL = 600
SYMBOL_SEARCH_LIMIT = 100

# CACHE
cache = {}
top_bybit_cache = {}
all_bybit_symbols_cache = {
    "time": 0,
    "symbols": []
}


def get_top20():

    response = session.get_tickers(category="linear")

    coins = sorted(
        response["result"]["list"],
        key=lambda x: float(x["turnover24h"]),
        reverse=True
    )

    return coins[:20]


def get_top_bybit_symbols(limit=50):

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
        print(f"Nie udało się pobrać Top {limit} Bybit: {error}")
        return []

    top_bybit_cache[limit] = {
        "time": time.time(),
        "symbols": symbols
    }

    return symbols


def get_top20_usdt_perpetual_symbols(limit=20):

    return get_top_bybit_symbols(limit)


def get_available_usdt_perpetual_symbols():

    return get_all_bybit_symbols()


def get_all_bybit_symbols():

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


def get_klines(symbol="BTCUSDT", interval="15", limit=300):

    limit = max(limit, 300)
    key = f"{symbol}_{interval}_{limit}"

    # jeżeli dane są młodsze niż 30 sekund
    if key in cache:

        age = time.time() - cache[key]["time"]

        if age < 30:

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
