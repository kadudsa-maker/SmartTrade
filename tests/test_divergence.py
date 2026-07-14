import pandas as pd

from config import (
    ACTIVE_MAX_CANDLES,
    AGING_MAX_CANDLES,
    PIVOT_LEFT,
    PIVOT_RIGHT,
    RSI_PIVOT_MATCH_TOLERANCE
)
from chart import SmartTradeChart
from divergence import enrich_divergence_confirmation, find_regular_divergences
from pivots import find_pivots, find_rsi_pivots
from ui import SmartTradeUI


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
    assert divergence["confirmed_index"] == 51
    assert divergence["pivot_time"] == 50
    assert divergence["confirmed_time"] == 51
    assert divergence["age_candles"] == 4


def test_bullish_divergence_is_detected_one_candle_earlier_with_right_one():

    right_one = _diagnostic_divergences("bullish", right=1, candle_count=10)
    right_two_too_early = _diagnostic_divergences("bullish", right=2, candle_count=10)
    right_two_confirmed = _diagnostic_divergences("bullish", right=2, candle_count=11)

    assert len(right_one) == 1
    assert right_two_too_early == []
    assert len(right_two_confirmed) == 1
    assert _confirmation_snapshot(right_one[0], 10, right=1) == {
        "type": "bullish",
        "price_pivot_index": 8,
        "rsi_pivot_index": 8,
        "confirmed_index": 9,
        "age_candles": 0
    }
    assert _confirmation_snapshot(right_two_confirmed[0], 11, right=2) == {
        "type": "bullish",
        "price_pivot_index": 8,
        "rsi_pivot_index": 8,
        "confirmed_index": 10,
        "age_candles": 0
    }


def test_bearish_divergence_is_detected_one_candle_earlier_with_right_one():

    right_one = _diagnostic_divergences("bearish", right=1, candle_count=10)
    right_two_too_early = _diagnostic_divergences("bearish", right=2, candle_count=10)
    right_two_confirmed = _diagnostic_divergences("bearish", right=2, candle_count=11)

    assert len(right_one) == 1
    assert right_two_too_early == []
    assert len(right_two_confirmed) == 1
    assert _confirmation_snapshot(right_one[0], 10, right=1)["confirmed_index"] == 9
    assert _confirmation_snapshot(right_two_confirmed[0], 11, right=2)["confirmed_index"] == 10


def test_signal_status_boundaries_are_unchanged():

    assert ACTIVE_MAX_CANDLES == 2
    assert AGING_MAX_CANDLES == 6

    ui = SmartTradeUI.__new__(SmartTradeUI)

    for age in (0, 1, 2):
        assert ui.signal_status({"age_candles": age}, 0)[0] == "ACTIVE"

    assert ui.signal_status({"age_candles": 3}, 0)[0] == "AGING"
    assert ui.signal_status({"age_candles": 7}, 0)[0] == "EXPIRED"


def _diagnostic_divergences(kind, right, candle_count):

    data = _diagnostic_candles(kind).iloc[:candle_count].copy()
    rsi = pd.Series(data.pop("rsi").to_list(), dtype=float)
    price_highs, price_lows = find_pivots(data, left=PIVOT_LEFT, right=right)
    rsi_highs, rsi_lows = find_rsi_pivots(
        rsi,
        data["time"],
        left=PIVOT_LEFT,
        right=right
    )

    return find_regular_divergences(
        data,
        rsi,
        price_highs,
        price_lows,
        rsi_highs,
        rsi_lows
    )


def _diagnostic_candles(kind):

    if kind == "bullish":
        highs = [20] * 11
        lows = [12, 11, 10, 5, 9, 10, 11, 8, 4, 9, 10]
        rsi = [60, 55, 50, 30, 50, 55, 60, 50, 40, 55, 60]
    else:
        highs = [50, 55, 60, 70, 55, 50, 45, 65, 80, 70, 60]
        lows = [20] * 11
        rsi = [40, 45, 50, 70, 50, 45, 40, 50, 60, 50, 40]

    return pd.DataFrame({
        "time": list(range(11)),
        "open": [15] * 11,
        "high": highs,
        "low": lows,
        "close": [15] * 11,
        "volume": [100] * 11,
        "rsi": rsi
    })


def _confirmation_snapshot(divergence, candle_count, right):

    enrich_divergence_confirmation(
        divergence,
        candle_count=candle_count,
        times=pd.Series(range(candle_count)),
        right=right
    )

    return {
        "type": divergence["type"],
        "price_pivot_index": divergence["price_end"]["index"],
        "rsi_pivot_index": divergence["rsi_end"]["index"],
        "confirmed_index": divergence["confirmed_index"],
        "age_candles": divergence["age_candles"]
    }


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
