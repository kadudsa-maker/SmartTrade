from market import filter_symbols


def test_filter_symbols_is_case_insensitive_and_partial():

    symbols = ["BTCUSDT", "ETHUSDT", "VETUSDT", "AAVEUSDT", "SOLUSDT"]

    assert filter_symbols(symbols, "v") == ["VETUSDT", "AAVEUSDT"]
    assert filter_symbols(symbols, "vet") == ["VETUSDT"]
    assert filter_symbols(symbols, "btc") == ["BTCUSDT"]


def test_filter_symbols_limits_results():

    symbols = [f"COIN{index}USDT" for index in range(150)]

    assert len(filter_symbols(symbols, "coin", limit=100)) == 100
