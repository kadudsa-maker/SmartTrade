import pandas as pd

from config import PIVOT_RIGHT, RSI_PIVOT_MATCH_TOLERANCE
from chart import SmartTradeChart
from divergence import enrich_divergence_confirmation, find_regular_divergences


def _pivot(index, price):

    return {
        "index": index,
        "time": index,
        "price": price
    }


def _df():

    df = pd.DataFrame({
        "high": [100 + index for index in range(100)],
        "low": [100 - index for index in range(100)],
        "close": list(range(100))
    })
    df.attrs["symbol"] = "TESTUSDT"

    return df


def _assert_quality(divergence):

    assert set(divergence["quality"]) == {"pivot", "rsi", "distance", "volume"}
    assert divergence["strength"] == 0


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
    assert divergences[0]["start_index_delta"] == 0
    assert divergences[0]["end_index_delta"] == 0
    _assert_quality(divergences[0])


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
    assert divergences[0]["start_index_delta"] == 0
    assert divergences[0]["end_index_delta"] == 0
    _assert_quality(divergences[0])


def test_divergence_is_detected_when_rsi_pivots_are_within_tolerance():

    divergences = find_regular_divergences(
        _df(),
        pd.Series(range(100)),
        [],
        [_pivot(10, 100), _pivot(30, 90)],
        [],
        [
            _pivot(10 + RSI_PIVOT_MATCH_TOLERANCE, 30),
            _pivot(30 - RSI_PIVOT_MATCH_TOLERANCE, 40)
        ]
    )

    assert len(divergences) == 1
    assert divergences[0]["start_index_delta"] == RSI_PIVOT_MATCH_TOLERANCE
    assert divergences[0]["end_index_delta"] == RSI_PIVOT_MATCH_TOLERANCE


def test_no_divergence_when_rsi_pivot_is_outside_tolerance():

    divergences = find_regular_divergences(
        _df(),
        pd.Series(range(100)),
        [],
        [_pivot(10, 100), _pivot(30, 90)],
        [],
        [
            _pivot(10 + RSI_PIVOT_MATCH_TOLERANCE + 1, 30),
            _pivot(30, 40)
        ]
    )

    assert divergences == []


def test_divergence_index_deltas_do_not_exceed_tolerance():

    divergences = find_regular_divergences(
        _df(),
        pd.Series(range(100)),
        [_pivot(10, 100), _pivot(30, 120)],
        [],
        [
            _pivot(10 - RSI_PIVOT_MATCH_TOLERANCE, 70),
            _pivot(30 + RSI_PIVOT_MATCH_TOLERANCE, 60)
        ],
        []
    )

    divergence = divergences[0]

    assert divergence["start_index_delta"] <= RSI_PIVOT_MATCH_TOLERANCE
    assert divergence["end_index_delta"] <= RSI_PIVOT_MATCH_TOLERANCE


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


def test_divergence_age_is_counted_from_confirmation_index():

    divergence = {
        "price_end": {"index": 50, "time": 50, "price": 100}
    }

    enrich_divergence_confirmation(
        divergence,
        candle_count=56,
        times=pd.Series(range(56)),
        right=PIVOT_RIGHT
    )

    assert divergence["pivot_index"] == 50
    assert divergence["confirmed_index"] == 52
    assert divergence["pivot_time"] == 50
    assert divergence["confirmed_time"] == 52
    assert divergence["age_candles"] == 3


def test_chart_draws_divergence_lines_from_divergence_points():

    chart = SmartTradeChart.__new__(SmartTradeChart)
    chart.canvas = FakeCanvas()
    chart._is_line_visible = lambda *_args: True
    chart._pivot_x = lambda pivot, *_args: pivot["index"]
    chart._price_to_y = lambda price, *_args: price
    chart._rsi_to_y = lambda price, *_args: price

    divergence = {
        "type": "bullish",
        "price_start": {"index": 10, "time": 10, "price": 100},
        "price_end": {"index": 30, "time": 30, "price": 90},
        "rsi_start": {"index": 11, "time": 11, "price": 30},
        "rsi_end": {"index": 29, "time": 29, "price": 40}
    }

    chart._draw_divergence_pair(
        divergence,
        "#26a69a",
        "Bull Div",
        first_visible_index=0,
        visible_count=100,
        step=1,
        padding=0,
        high=120,
        low=80,
        price_top=0,
        price_height=100,
        rsi_top=0,
        rsi_bottom=100
    )

    assert chart.canvas.lines[0][:4] == (10, 100, 30, 90)
    assert chart.canvas.lines[1][:4] == (11, 30, 29, 40)


class FakeCanvas:

    def __init__(self):

        self.lines = []
        self.texts = []

    def create_line(self, *args, **_kwargs):

        self.lines.append(args)

    def create_text(self, *args, **_kwargs):

        self.texts.append(args)
