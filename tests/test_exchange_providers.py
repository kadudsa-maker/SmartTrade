import json
import logging

import pandas as pd
import pytest

import market
from exchange_providers import (
    BybitProvider,
    ExchangeProviderError,
    ExchangeSymbol,
    OKXSpotProvider,
    OKXProvider,
    REQUIRED_CANDLE_COLUMNS,
    SMARTTRADE_INTERVALS,
)


BYBIT_CANDLES = [
    ["3000", "3", "4", "2", "3.5", "12", "42"],
    ["2000", "2", "3", "1", "2.5", "11", "27.5"],
    ["1000", "1", "2", "0.5", "1.5", "10", "15"],
]

OKX_CANDLES = [
    ["3000", "3", "4", "2", "3.5", "120", "12", "42", "0"],
    ["2000", "2", "3", "1", "2.5", "110", "11", "27.5", "1"],
    ["1000", "1", "2", "0.5", "1.5", "100", "10", "15", "1"],
]


class FakeBybitSession:
    def get_instruments_info(self, **params):
        return {"result": {"list": [
            {
                "symbol": "BTCUSDT", "baseCoin": "BTC", "quoteCoin": "USDT",
                "status": "Trading", "contractType": "LinearPerpetual"
            },
            {
                "symbol": "BTCUSD", "baseCoin": "BTC", "quoteCoin": "USD",
                "status": "Trading", "contractType": "InversePerpetual"
            },
        ], "nextPageCursor": ""}}

    def get_tickers(self, **params):
        return {"result": {"list": [
            {"symbol": "ETHUSDT", "turnover24h": "20"},
            {"symbol": "BTCUSDT", "turnover24h": "30"},
        ]}}

    def get_kline(self, **params):
        return {"result": {"list": list(BYBIT_CANDLES)}}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeOKXSession:
    def __init__(self, invalid_json=False):
        self.invalid_json = invalid_json
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        if self.invalid_json:
            return InvalidJSONResponse(None)
        if url.endswith("/public/instruments"):
            if params["instType"] == "SPOT":
                data = [
                    {
                        "instId": "BTC-USDT", "instType": "SPOT", "baseCcy": "BTC",
                        "quoteCcy": "USDT", "state": "live", "ruleType": "normal",
                        "instCategory": "1"
                    },
                    {
                        "instId": "UNI-USDT", "instType": "SPOT", "baseCcy": "UNI",
                        "quoteCcy": "USDT", "state": "live", "ruleType": "normal",
                        "instCategory": "1"
                    },
                    {
                        "instId": "BTC-USDT-SWAP", "instType": "SWAP", "baseCcy": "BTC",
                        "quoteCcy": "USDT", "state": "live", "ruleType": "normal",
                        "instCategory": "1"
                    },
                ]
            elif params["instType"] == "FUTURES":
                data = [
                    self.xperp("BTC"),
                    self.xperp("UNI"),
                    self.xperp("AAPL", category="3"),
                    self.xperp("SPY", category="3", asset_class="ETF"),
                    self.xperp("XAU", category="4"),
                    self.xperp("MYSTERY", category="99"),
                    self.xperp("INACTIVE", state="suspend"),
                    {
                        "instId": "BTC-USD-260925", "instType": "FUTURES",
                        "instFamily": "BTC-USD", "uly": "BTC-USD", "ctType": "inverse",
                        "settleCcy": "BTC", "state": "live", "ruleType": "normal",
                        "alias": "quarter", "expTime": "1790323200000", "instCategory": "1",
                    },
                ]
            else:
                data = [{"instId": "GLOBAL-ONLY-USDT-SWAP", "instType": "SWAP"}]
        elif url.endswith("/market/tickers"):
            inst_id = "BTC-USDT" if params["instType"] == "SPOT" else self.xperp("BTC")["instId"]
            data = [
                {"instId": inst_id, "volCcy24h": "2", "last": "30000"},
                {"instId": "GLOBAL-ONLY-USDT-SWAP", "volCcy24h": "999", "last": "1"},
            ]
        else:
            data = list(OKX_CANDLES)
        return FakeResponse({"code": "0", "msg": "", "data": data})

    @staticmethod
    def xperp(base, category="1", asset_class=None, state="live"):
        family = f"{base}-USD_UM_XPERP"
        item = {
            "instId": f"{family}-310404", "instType": "FUTURES",
            "instFamily": family, "uly": f"{base}-USD", "ctType": "linear",
            "settleCcy": "USD", "ctValCcy": base, "state": state,
            "ruleType": "xperp", "alias": "this_five_years",
            "listTime": "1774845000428", "expTime": "1933056000000",
            "instCategory": category,
        }
        if asset_class is not None:
            item["assetClass"] = asset_class
        return item


class InvalidJSONResponse(FakeResponse):
    def json(self):
        raise ValueError("bad json")


@pytest.mark.parametrize("provider", [
    BybitProvider(session=FakeBybitSession()),
    OKXProvider(session=FakeOKXSession()),
    OKXSpotProvider(session=FakeOKXSession()),
])
def test_provider_contract_instruments_intervals_and_candles(provider):
    instruments = provider.get_instruments()
    assert instruments
    assert all(isinstance(item, ExchangeSymbol) for item in instruments)
    assert all(item.exchange_symbol and item.display_symbol for item in instruments)
    assert all(provider.map_interval(value) for value in SMARTTRADE_INTERVALS)

    frame = provider.get_klines(instruments[0], "60", 300)
    assert list(frame.columns) == REQUIRED_CANDLE_COLUMNS
    assert frame["time"].is_monotonic_increasing
    assert frame["time"].is_unique
    assert all(pd.api.types.is_numeric_dtype(frame[column]) for column in frame.columns)
    assert provider.cache_key(instruments[0], "60", 300).startswith(provider.exchange_id + "|")


def test_provider_ids_are_unique_and_top_rankings_return_records():
    bybit = BybitProvider(session=FakeBybitSession())
    okx = OKXProvider(session=FakeOKXSession())
    spot = OKXSpotProvider(session=FakeOKXSession())
    assert len({bybit.exchange_id, okx.exchange_id, spot.exchange_id}) == 3
    assert [item.exchange_symbol for item in bybit.get_top_symbols(2)] == [
        "BTCUSDT", "ETHUSDT"
    ]
    assert [item.exchange_symbol for item in okx.get_top_symbols(1)] == [
        "BTC-USD_UM_XPERP-310404"
    ]
    assert [item.exchange_symbol for item in spot.get_top_symbols(1)] == ["BTC-USDT"]


def test_okx_normalizes_documented_base_volume_and_quote_turnover():
    provider = OKXProvider(session=FakeOKXSession())
    frame = provider.get_klines(provider.get_instruments()[0], "60", 300)
    assert frame["volume"].tolist() == [10.0, 11.0, 12.0]
    assert frame["turnover"].tolist() == [15.0, 27.5, 42.0]


def test_okx_spot_and_perpetual_instruments_never_mix():
    perpetual = OKXProvider(session=FakeOKXSession()).get_instruments()
    spot = OKXSpotProvider(session=FakeOKXSession()).get_instruments()
    assert all(
        item.instrument_type == "futures" and "_UM_XPERP-" in item.exchange_symbol
        for item in perpetual
    )
    assert all(item.instrument_type == "spot" and not item.exchange_symbol.endswith("-SWAP") for item in spot)


def test_provider_boundary_logs_and_skips_wrong_instrument_type(caplog):
    caplog.set_level(logging.DEBUG, logger="exchange_providers.okx")
    perpetual = OKXProvider(session=FakeOKXSession()).get_instruments()
    assert all(item.metadata["instType"] == "FUTURES" for item in perpetual)
    assert all(item.metadata["ruleType"] == "xperp" for item in perpetual)
    assert {item.asset_class for item in perpetual} == {
        "crypto", "stock", "etf", "commodity", "other"
    }
    assert "accepted=True" in caplog.text


def test_cached_provider_boundary_cannot_return_injected_wrong_market():
    perpetual = OKXProvider(session=FakeOKXSession())
    perpetual.get_instruments()
    perpetual._instruments.append(ExchangeSymbol(
        "okx", "UNI-USDT", "UNIUSDT", "UNI", "USDT", "spot", "live",
        {"instId": "UNI-USDT", "instType": "SPOT"},
    ))
    assert all(item.metadata["ruleType"] == "xperp" for item in perpetual.get_instruments())

    spot = OKXSpotProvider(session=FakeOKXSession())
    spot.get_instruments()
    spot._instruments.append(ExchangeSymbol(
        "okx_spot", "UNI-USDT-SWAP", "UNIUSDT", "UNI", "USDT", "swap", "live",
        {"instId": "UNI-USDT-SWAP", "instType": "SWAP"},
    ))
    assert all(item.metadata["instType"] == "SPOT" for item in spot.get_instruments())


def test_perpetual_search_cannot_return_spot_with_same_display_symbol():
    perpetual_provider = OKXProvider(session=FakeOKXSession())
    spot_provider = OKXSpotProvider(session=FakeOKXSession())
    perpetual = perpetual_provider.search_symbols("BTC")
    spot = spot_provider.search_symbols("BTC")
    assert {item.display_symbol for item in perpetual} == {"BTCUSD"}
    assert {item.display_symbol for item in spot} == {"BTCUSDT"}
    assert all(item.exchange_id == "okx" and "_UM_XPERP-" in item.exchange_symbol for item in perpetual)
    assert all(item.exchange_id == "okx_spot" and not item.exchange_symbol.endswith("-SWAP") for item in spot)


def test_okx_perpetual_matches_public_eea_xperp_market_validation():
    instrument = next(
        item for item in OKXProvider(session=FakeOKXSession()).get_instruments()
        if item.display_symbol == "BTCUSD"
    )
    assert instrument.metadata["platform_market"] == "UM"
    assert instrument.metadata["instFamily"] == "BTC-USD_UM_XPERP"
    assert instrument.metadata["settleCcy"] == "USD"
    assert instrument.metadata["ctType"] == "linear"
    assert instrument.metadata["ruleType"] == "xperp"
    assert instrument.metadata["alias"] == "this_five_years"


@pytest.mark.parametrize(
    ("display_symbol", "expected_asset_class"),
    [
        ("BTCUSD", "crypto"),
        ("AAPLUSD", "stock"),
        ("SPYUSD", "etf"),
        ("XAUUSD", "commodity"),
        ("MYSTERYUSD", "other"),
    ],
)
def test_xperp_asset_class_is_preserved(display_symbol, expected_asset_class):
    instruments = OKXProvider(session=FakeOKXSession()).get_instruments()
    instrument = next(item for item in instruments if item.display_symbol == display_symbol)
    assert instrument.asset_class == expected_asset_class


def test_non_xperp_and_inactive_records_are_rejected():
    instruments = OKXProvider(session=FakeOKXSession()).get_instruments()
    symbols = {item.exchange_symbol for item in instruments}
    assert "BTC-USD-260925" not in symbols
    assert "INACTIVE-USD_UM_XPERP-310404" not in symbols
    assert all(item.metadata["instType"] != "SPOT" for item in instruments)
    assert all(item.metadata["instType"] != "SWAP" for item in instruments)


def test_uni_xperp_builds_required_platform_market_name():
    provider = OKXProvider(session=FakeOKXSession())
    instrument = next(
        item for item in provider.get_instruments()
        if item.exchange_symbol == "UNI-USD_UM_XPERP-310404"
    )
    assert instrument.display_symbol == "UNIUSD"
    assert instrument.platform_market_name == "UNIUSD UM"


def test_final_market_name_filter_separates_perpetual_and_spot():
    perpetual = OKXProvider(session=FakeOKXSession()).get_instruments()
    spot = OKXSpotProvider(session=FakeOKXSession()).get_instruments()
    assert perpetual and all(item.platform_market_name.endswith(" UM") for item in perpetual)
    assert spot and all(not item.platform_market_name.endswith(" UM") for item in spot)


def test_top_and_search_use_final_platform_market_names():
    perpetual = OKXProvider(session=FakeOKXSession())
    spot = OKXSpotProvider(session=FakeOKXSession())
    for limit in (50, 100, 200):
        assert all(
            item.platform_market_name.endswith(" UM")
            for item in perpetual.get_top_symbols(limit)
        )
    assert [item.platform_market_name for item in perpetual.search_symbols("UNI")] == [
        "UNIUSD UM"
    ]
    assert [item.platform_market_name for item in spot.search_symbols("UNI")] == [
        "UNIUSDT"
    ]
    assert [item.asset_class for item in perpetual.search_symbols("AAPL")] == ["stock"]


def test_okx_spot_volume_and_turnover_use_documented_spot_fields():
    provider = OKXSpotProvider(session=FakeOKXSession())
    frame = provider.get_klines(provider.get_instruments()[0], "60", 300)
    assert frame["volume"].tolist() == [100.0, 110.0, 120.0]
    assert frame["turnover"].tolist() == [15.0, 27.5, 42.0]


def test_okx_spot_and_perpetual_cache_and_top_ranges_are_independent():
    perpetual = OKXProvider(session=FakeOKXSession())
    spot = OKXSpotProvider(session=FakeOKXSession())
    perp_symbol = perpetual.get_instruments()[0]
    spot_symbol = spot.get_instruments()[0]
    assert perpetual.cache_key(perp_symbol, "60", 300) != spot.cache_key(spot_symbol, "60", 300)
    for limit in (50, 100, 200):
        assert all(item.exchange_id == "okx" for item in perpetual.get_top_symbols(limit))
        assert all(item.exchange_id == "okx_spot" for item in spot.get_top_symbols(limit))


def test_provider_errors_are_consistent_for_invalid_json():
    provider = OKXProvider(session=FakeOKXSession(invalid_json=True))
    with pytest.raises(ExchangeProviderError, match="invalid JSON"):
        provider.get_instruments()


def test_synthetic_um_label_does_not_qualify_public_instrument():
    provider = OKXProvider(session=FakeOKXSession())
    synthetic = ExchangeSymbol(
        "okx", "FAKE-USDT-SWAP", "FAKEUSDT", "FAKE", "USDT", "swap", "live",
        {"instType": "SWAP", "instrument_scope": "public"},
        platform_market_name="FAKEUSDT UM",
    )
    assert provider._instrument_contract_valid(synthetic) is False


def test_perpetual_uses_public_eea_futures_and_never_global_swap_as_um():
    session = FakeOKXSession()
    symbols = OKXProvider(session=session).get_instruments()
    assert {item.exchange_symbol for item in symbols} == {
        "AAPL-USD_UM_XPERP-310404", "BTC-USD_UM_XPERP-310404",
        "MYSTERY-USD_UM_XPERP-310404", "SPY-USD_UM_XPERP-310404",
        "UNI-USD_UM_XPERP-310404", "XAU-USD_UM_XPERP-310404",
    }
    assert all(url.startswith("https://eea.okx.com/") for url, *_rest in session.calls)
    assert not any("/account/" in url for url, *_rest in session.calls)
    instrument_calls = [
        params["instType"] for url, params, *_rest in session.calls
        if url.endswith("/public/instruments")
    ]
    assert instrument_calls == ["FUTURES", "SWAP"]
    assert all(item.exchange_symbol != "GLOBAL-ONLY-USDT-SWAP" for item in symbols)


class FakeManyEEASession(FakeOKXSession):
    def get(self, url, params, timeout):
        self.calls.append((url, params, timeout))
        if url.endswith("/public/instruments") and params["instType"] == "FUTURES":
            data = [self.xperp(f"COIN{index:03d}") for index in range(7)]
            data.append(self.xperp("AAPL", category="3"))
        elif url.endswith("/public/instruments"):
            data = [{"instId": "GLOBAL-ONLY-USDT-SWAP", "instType": "SWAP"}]
        elif url.endswith("/market/tickers"):
            data = [
                {"instId": self.xperp(f"COIN{index:03d}")["instId"],
                 "volCcy24h": str(1000-index), "last": "1"}
                for index in range(7)
            ] + [
                {"instId": self.xperp("AAPL", category="3")["instId"],
                 "volCcy24h": "500", "last": "1"},
                {"instId": "OUTSIDE-USD_UM_XPERP-310404", "volCcy24h": "999999", "last": "1"},
            ]
        else:
            data = list(OKX_CANDLES)
        return FakeResponse({"code": "0", "msg": "", "data": data})


def test_public_catalog_size_caps_top200_and_rejects_external_ticker(caplog):
    caplog.set_level(logging.INFO, logger="exchange_providers.okx")
    provider = OKXProvider(session=FakeManyEEASession())
    symbols = provider.get_top_symbols(200)
    assert provider.last_public_futures_count == 8
    assert provider.last_public_swap_count == 1
    assert provider.last_identified_xperps_count == 8
    assert provider.last_asset_class_counts["crypto"] == 7
    assert provider.last_asset_class_counts["stock"] == 1
    assert len(symbols) == 8
    assert all(item.exchange_symbol != "OUTSIDE-USD_UM_XPERP-310404" for item in symbols)
    assert "public_futures_count=8" in caplog.text
    assert "effective_scan_limit=8" in caplog.text


def test_xperp_ranking_missing_or_invalid_volume_has_zero_turnover_fallback():
    assert OKXProvider._ticker_turnover({"last": "10"}) == 0
    assert OKXProvider._ticker_turnover({"volCcy24h": "bad", "last": "10"}) == 0


def test_no_provider_calls_account_instruments_or_sends_private_headers():
    session = FakeOKXSession()
    OKXProvider(session=session).get_instruments()
    assert session.calls
    assert all("account/instruments" not in call[0] for call in session.calls)
    assert all(len(call) == 3 for call in session.calls)


def test_public_eea_cache_is_independent_from_spot_cache():
    provider = OKXProvider(session=FakeOKXSession())
    spot = OKXSpotProvider(session=FakeOKXSession())
    xperps = provider.get_instruments()
    spot_symbols = spot.get_instruments()
    provider._instruments.clear()
    assert xperps
    assert spot.get_instruments() == spot_symbols


def test_tickers_and_candles_stay_in_public_eea_provider_context():
    session = FakeOKXSession()
    provider = OKXProvider(session=session)
    symbol = provider.get_top_symbols(1)[0]
    provider.get_klines(symbol, "60", 300)
    assert all(url.startswith("https://eea.okx.com/") for url, *_rest in session.calls)
    assert any(
        url.endswith("/market/tickers") and params["instType"] == "FUTURES"
        for url, params, *_rest in session.calls
    )
    assert any(
        url.endswith("/market/candles") and params["instId"] == symbol.exchange_symbol
        for url, params, *_rest in session.calls
    )


def test_watchlist_migrates_legacy_symbols_to_bybit_without_data_loss(tmp_path, monkeypatch):
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps({"coins": ["BTCUSDT", "ETHUSDT"]}), encoding="utf-8")
    monkeypatch.setattr(market, "WATCHLIST_PATH", path)

    assert market.get_watchlist("bybit") == ["BTCUSDT", "ETHUSDT"]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["instruments"][0] == {
        "exchange_id": "bybit",
        "exchange_symbol": "BTCUSDT",
        "display_symbol": "BTCUSDT",
    }


def test_watchlist_preserves_xperp_presentation_and_asset_class(tmp_path, monkeypatch):
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps({"instruments": [{
        "exchange_id": "bybit", "exchange_symbol": "BTCUSDT",
        "display_symbol": "BTCUSDT",
    }]}), encoding="utf-8")
    monkeypatch.setattr(market, "WATCHLIST_PATH", path)
    instrument = OKXProvider(session=FakeOKXSession()).search_symbols("AAPL")[0]
    market.save_watchlist([instrument], exchange_id="okx")
    saved = json.loads(path.read_text(encoding="utf-8"))["instruments"]
    assert saved[0]["exchange_id"] == "bybit"
    assert saved[1] == {
        "exchange_id": "okx",
        "exchange_symbol": "AAPL-USD_UM_XPERP-310404",
        "display_symbol": "AAPLUSD",
        "platform_market_name": "AAPLUSD UM",
        "asset_class": "stock",
    }
