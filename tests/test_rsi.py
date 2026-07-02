import pandas as pd

from rsi import calculate_rma_series, calculate_rsi_series


def test_calculate_rma_series_uses_sma_seed_and_wilder_updates():

    values = pd.Series([1, 2, 3, 4, 5], dtype=float)

    rma = calculate_rma_series(values, period=3)

    assert pd.isna(rma.iloc[0])
    assert pd.isna(rma.iloc[1])
    assert rma.iloc[2] == 2.0
    assert round(rma.iloc[3], 4) == 2.6667
    assert round(rma.iloc[4], 4) == 3.4444


def test_calculate_rsi_series_uses_wilder_rma():

    close = pd.Series([
        100, 102, 101, 103, 104, 102, 105, 106,
        104, 107, 108, 109, 107, 110, 112, 111
    ], dtype=float)

    rsi = calculate_rsi_series(close, period=14)

    assert rsi.iloc[:14].isna().all()
    assert round(rsi.iloc[14], 4) == 73.0769
    assert round(rsi.iloc[15], 4) == 70.1705
