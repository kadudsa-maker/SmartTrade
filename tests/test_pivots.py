import pandas as pd

from pivots import find_pivots


def test_find_pivots_detects_pivot_high_and_pivot_low():

    df = pd.DataFrame({
        "time": list(range(9)),
        "high": [1, 2, 3, 9, 4, 3, 2, 1, 2],
        "low": [9, 8, 7, 6, 1, 6, 7, 8, 9]
    })

    pivot_highs, pivot_lows = find_pivots(df, left=3, right=3)

    assert pivot_highs == [{"index": 3, "time": 3, "price": 9.0}]
    assert pivot_lows == [{"index": 4, "time": 4, "price": 1.0}]
