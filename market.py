from pybit.unified_trading import HTTP
import pandas as pd
import time

session = HTTP(testnet=False)

# CACHE
cache = {}


def get_top20():

    response = session.get_tickers(category="linear")

    coins = sorted(
        response["result"]["list"],
        key=lambda x: float(x["turnover24h"]),
        reverse=True
    )

    return coins[:20]


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