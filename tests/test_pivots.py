import pandas as pd

from pivots import find_pivots, find_rsi_pivots
from config import PIVOT_LEFT, PIVOT_RIGHT


def test_find_pivots_detects_pivot_high_and_pivot_low():

    df = pd.DataFrame({
        "time": list(range(9)),
        "high": [1, 2, 3, 9, 4, 3, 2, 1, 2],
        "low": [9, 8, 7, 6, 1, 6, 7, 8, 9]
    })

    pivot_highs, pivot_lows = find_pivots(df, left=PIVOT_LEFT, right=PIVOT_RIGHT)

    assert pivot_highs == [{"index": 3, "time": 3, "price": 9.0}]
    assert pivot_lows == [{"index": 4, "time": 4, "price": 1.0}]


def test_configured_pivot_is_confirmed_after_exactly_one_right_candle():

    assert PIVOT_RIGHT == 1

    df = pd.DataFrame({
        "time": list(range(5)),
        "high": [1, 2, 3, 9, 4],
        "low": [9, 8, 7, 1, 6]
    })

    pivot_highs, pivot_lows = find_pivots(
        df,
        left=PIVOT_LEFT,
        right=PIVOT_RIGHT
    )

    assert pivot_highs == [{"index": 3, "time": 3, "price": 9.0}]
    assert pivot_lows == [{"index": 3, "time": 3, "price": 1.0}]


def test_last_candle_without_right_neighbor_cannot_become_pivot():

    df = pd.DataFrame({
        "time": list(range(5)),
        "high": [1, 2, 3, 4, 10],
        "low": [9, 8, 7, 6, 0]
    })

    pivot_highs, pivot_lows = find_pivots(
        df,
        left=PIVOT_LEFT,
        right=PIVOT_RIGHT
    )

    assert all(pivot["index"] != 4 for pivot in pivot_highs)
    assert all(pivot["index"] != 4 for pivot in pivot_lows)


def test_price_and_rsi_pivots_use_the_same_configured_right_window():

    times = pd.Series(range(5))
    values = pd.Series([1, 2, 3, 9, 4], dtype=float)
    price_df = pd.DataFrame({
        "time": times,
        "high": values,
        "low": values
    })

    price_highs, _price_lows = find_pivots(
        price_df,
        left=PIVOT_LEFT,
        right=PIVOT_RIGHT
    )
    rsi_highs, _rsi_lows = find_rsi_pivots(
        values,
        times,
        left=PIVOT_LEFT,
        right=PIVOT_RIGHT
    )

    assert price_highs[0]["index"] == 3
    assert rsi_highs[0]["index"] == 3
