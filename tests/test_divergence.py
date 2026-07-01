import pandas as pd

from divergence import find_regular_divergences


def _pivot(index, price):

    return {
        "index": index,
        "time": index,
        "price": price
    }


def _df():

    df = pd.DataFrame({"close": list(range(100))})
    df.attrs["symbol"] = "TESTUSDT"

    return df


def test_find_regular_bullish_divergence():

    divergences = find_regular_divergences(
        _df(),
        pd.Series(range(100)),
        [],
        [_pivot(10, 100), _pivot(30, 90)],
        [],
        [_pivot(10, 30), _pivot(30, 40)]
    )

    assert len(divergences) == 1
    assert divergences[0]["type"] == "bullish"
    assert divergences[0]["strength"] == 0
    assert divergences[0]["quality"] is None


def test_find_regular_bearish_divergence():

    divergences = find_regular_divergences(
        _df(),
        pd.Series(range(100)),
        [_pivot(10, 100), _pivot(30, 120)],
        [],
        [_pivot(10, 70), _pivot(30, 60)],
        []
    )

    assert len(divergences) == 1
    assert divergences[0]["type"] == "bearish"


def test_no_divergence_when_price_pivots_are_too_far_apart():

    divergences = find_regular_divergences(
        _df(),
        pd.Series(range(100)),
        [],
        [_pivot(10, 100), _pivot(71, 90)],
        [],
        [_pivot(10, 30), _pivot(71, 40)]
    )

    assert divergences == []
