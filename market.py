import json

from app_paths import configure_https_certificates, runtime_path

configure_https_certificates()

from config import DEFAULT_KLINE_LIMIT, DEFAULT_WATCHLIST_LIMIT, SYMBOL_SEARCH_LIMIT
from exchange_providers import ExchangeProviderError, ExchangeSymbol, get_provider
from rsi import calculate_latest_rsi


DEFAULT_EXCHANGE_ID = "bybit"
WATCHLIST_PATH = runtime_path("data", "watchlist.json")

# Kept as compatibility hooks for existing callers/tests. API details live in providers.
bybit_provider = get_provider("bybit")
session = bybit_provider.session
top_bybit_last_error = None


def get_exchange_provider(exchange_id=DEFAULT_EXCHANGE_ID):
    return get_provider(exchange_id)


def get_instruments(exchange_id=DEFAULT_EXCHANGE_ID, force=False):
    return get_provider(exchange_id).get_instruments(force=force)


def get_top_symbols(exchange_id=DEFAULT_EXCHANGE_ID, limit=50):
    return get_provider(exchange_id).get_top_symbols(limit)


def get_top_bybit_symbols(limit=50):
    """Compatibility API: identical string list and 24h-turnover ranking."""
    global top_bybit_last_error
    try:
        symbols = bybit_provider.get_top_symbols(limit)
    except Exception as error:
        top_bybit_last_error = error
        print(f"Nie udalo sie pobrac Top {limit} Bybit: {error}")
        return []
    top_bybit_last_error = None
    return [item.exchange_symbol for item in symbols]


def get_top_bybit_last_error():
    return top_bybit_last_error


def get_top20_usdt_perpetual_symbols(limit=DEFAULT_WATCHLIST_LIMIT):
    return get_top_bybit_symbols(limit)


def get_all_bybit_symbols():
    try:
        return [item.exchange_symbol for item in bybit_provider.get_instruments()]
    except ExchangeProviderError as error:
        print(f"Nie udalo sie pobrac pelnej listy symboli Bybit: {error}")
        return [item.exchange_symbol for item in bybit_provider._instruments]


def filter_symbols(symbols, query, limit=SYMBOL_SEARCH_LIMIT):
    normalized_query = query.strip().upper()
    matches = []
    for symbol in symbols:
        text = symbol.display_symbol if isinstance(symbol, ExchangeSymbol) else str(symbol)
        exchange_text = symbol.exchange_symbol if isinstance(symbol, ExchangeSymbol) else text
        if normalized_query in text.upper() or normalized_query in exchange_text.upper():
            matches.append(symbol)
    return matches[:limit]


def get_klines(
    symbol="BTCUSDT", interval="15", limit=DEFAULT_KLINE_LIMIT,
    exchange_id=DEFAULT_EXCHANGE_ID
):
    limit = max(limit, DEFAULT_KLINE_LIMIT)
    return get_provider(exchange_id).get_klines(symbol, interval, limit)


def calculate_rsi(df, period=14):
    return calculate_latest_rsi(df["close"], period=period)


def _watchlist_record(value):
    if isinstance(value, ExchangeSymbol):
        return {
            "exchange_id": value.exchange_id,
            "exchange_symbol": value.exchange_symbol,
            "display_symbol": value.display_symbol,
            "platform_market_name": value.platform_market_name,
            "asset_class": value.asset_class,
        }
    if isinstance(value, str):
        return {
            "exchange_id": "bybit", "exchange_symbol": value, "display_symbol": value
        }
    if isinstance(value, dict):
        exchange_id = value.get("exchange_id") or "bybit"
        exchange_symbol = value.get("exchange_symbol") or value.get("symbol")
        display_symbol = value.get("display_symbol") or exchange_symbol
        if exchange_symbol:
            record = {
                "exchange_id": exchange_id,
                "exchange_symbol": exchange_symbol,
                "display_symbol": display_symbol,
            }
            if value.get("platform_market_name"):
                record["platform_market_name"] = value["platform_market_name"]
            if value.get("asset_class"):
                record["asset_class"] = value["asset_class"]
            return record
    return None


def load_default_watchlist(exchange_id=DEFAULT_EXCHANGE_ID):
    try:
        coins = get_provider(exchange_id).get_top_symbols(DEFAULT_WATCHLIST_LIMIT)
    except Exception as error:
        print(f"Nie udalo sie pobrac domyslnej watchlisty: {error}")
        return []
    save_watchlist(coins, exchange_id=exchange_id)
    return [item.exchange_symbol for item in coins]


def save_watchlist(coins, exchange_id=DEFAULT_EXCHANGE_ID):
    existing = _load_watchlist_records()
    retained = [item for item in existing if item["exchange_id"] != exchange_id]
    records = []
    for coin in coins:
        record = _watchlist_record(coin)
        if record is None:
            continue
        if isinstance(coin, str):
            record["exchange_id"] = exchange_id
        records.append(record)

    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with WATCHLIST_PATH.open("w", encoding="utf-8") as file:
        json.dump({"instruments": retained + records}, file, indent=4)


def reset_watchlist(exchange_id=DEFAULT_EXCHANGE_ID):
    coins = get_provider(exchange_id).get_top_symbols(DEFAULT_WATCHLIST_LIMIT)
    if not coins:
        raise RuntimeError(f"{get_provider(exchange_id).display_name} returned no Top20 list.")
    save_watchlist(coins, exchange_id=exchange_id)
    return [item.exchange_symbol for item in coins]


def _load_watchlist_records():
    if not WATCHLIST_PATH.exists():
        return []
    try:
        with WATCHLIST_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError) as error:
        print(f"Nie udalo sie odczytac watchlisty: {error}")
        return []

    raw_items = data.get("instruments")
    migrated = raw_items is None
    if raw_items is None:
        raw_items = data.get("coins", [])
    records = [record for item in raw_items if (record := _watchlist_record(item))]
    if migrated and records:
        WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with WATCHLIST_PATH.open("w", encoding="utf-8") as file:
            json.dump({"instruments": records}, file, indent=4)
    return records


def get_watchlist(exchange_id=DEFAULT_EXCHANGE_ID):
    records = _load_watchlist_records()
    if not records:
        return load_default_watchlist(exchange_id)
    return [
        item["exchange_symbol"] for item in records if item["exchange_id"] == exchange_id
    ]
