import json
from pathlib import Path
from pybit.unified_trading import HTTP
import pandas as pd
import time

session = HTTP(testnet=False)

WATCHLIST_PATH = Path("data/watchlist.json")
TOP_BYBIT_CACHE_TTL = 300

# CACHE
cache = {}
top_bybit_cache = {
    "time": 0,
    "limit": None,
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

    age = time.time() - top_bybit_cache["time"]

    if (
        top_bybit_cache["symbols"]
        and top_bybit_cache["limit"] == limit
        and age < TOP_BYBIT_CACHE_TTL
    ):
        return top_bybit_cache["symbols"]

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

    top_bybit_cache["time"] = time.time()
    top_bybit_cache["limit"] = limit
    top_bybit_cache["symbols"] = symbols

    return symbols


def get_top20_usdt_perpetual_symbols(limit=20):

    return get_top_bybit_symbols(limit)


def get_available_usdt_perpetual_symbols():

    response = session.get_instruments_info(category="linear")
    instruments = response["result"]["list"]

    symbols = [
        instrument["symbol"]
        for instrument in instruments
        if instrument.get("quoteCoin") == "USDT"
        and instrument.get("status") == "Trading"
        and instrument.get("contractType") == "LinearPerpetual"
    ]

    return sorted(symbols)


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


def get_klines(symbol="BTCUSDT", interval="15", limit=200):

    key = f"{symbol}_{interval}"

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

    df["close"] = df["close"].astype(float)

    cache[key] = {
        "time": time.time(),
        "data": df
    }

    return df


def calculate_rsi(df, period=14):

    delta = df["close"].diff()

    gain = delta.clip(lower=0)

    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()

    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    return round((100 - (100 / (1 + rs))).iloc[-1], 2)
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
