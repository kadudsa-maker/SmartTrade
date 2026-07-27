import pandas as pd

import ui as ui_module
from analysis_modes import MARKET_STRUCTURE, RSI_VIEW_ON
from market_structure import (
    DivergenceDirection,
    MarketStructureResult,
    MarketStructureState,
    PivotType,
    PricePivot,
    evaluate_market_structure,
    merge_price_pivots,
)
from ui import SmartTradeUI
from trend_health import (
    TrendHealthResult,
    TrendHealthState,
    evaluate_trend_health,
)


class ModeValue:

    def get(self):

        return RSI_VIEW_ON


class PivotAwareDivergences(list):

    def __init__(self, divergences, price_pivots, rsi_value=None):

        super().__init__(divergences)
        self.price_pivots = price_pivots
        self.rsi_value = rsi_value


def _frame():

    return pd.DataFrame({
        "time": [1_000, 2_000, 3_000, 4_000],
        "open": [10.0, 11.0, 12.0, 13.0],
        "high": [11.0, 12.0, 13.0, 14.0],
        "low": [9.0, 10.0, 11.0, 12.0],
        "close": [10.5, 11.5, 12.5, 13.5],
        "volume": [1.0, 1.0, 1.0, 1.0],
        "turnover": [1.0, 1.0, 1.0, 1.0],
    })


def _price_pivots():

    return [
        PricePivot(1, 100, PivotType.HIGH),
        PricePivot(2, 90, PivotType.LOW),
        PricePivot(3, 110, PivotType.HIGH),
        PricePivot(4, 95, PivotType.LOW),
    ]


def _health_price_pivots():

    return [
        PricePivot(1, 11, PivotType.HIGH),
        PricePivot(2, 9, PivotType.LOW),
        PricePivot(3, 13, PivotType.HIGH),
        PricePivot(4, 10, PivotType.LOW),
    ]


def _worker_ui(divergences):

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.rsi_view_option = ModeValue()
    ui.selected_interval = "1"
    ui.active_exchange_id = "bybit"
    ui.instrument_by_symbol = {}
    ui.buttons = []
    ui.fetch_klines = lambda *_args, **_kwargs: _frame().copy()
    ui.perf_log = lambda *_args, **_kwargs: None
    ui.find_coin_divergences_from_candles = lambda _candles: divergences
    ui.select_freshest_best_signal = (
        lambda items, _count: items[0] if items else None
    )
    return ui


def _run_worker(ui):

    return ui.update_watchlist_coin(
        {"symbol": "BTCUSDT"},
        0,
        scan_id=1,
        interval="1",
        total_symbols=1,
        exchange_id="bybit",
        analysis_mode=RSI_VIEW_ON,
    )


def test_adapter_merges_high_and_low_pivots():

    merged = merge_price_pivots(
        [{"index": 3, "time": 3, "price": 110}],
        [{"index": 2, "time": 2, "price": 90}],
    )

    assert merged == [
        PricePivot(2, 90, PivotType.LOW),
        PricePivot(3, 110, PivotType.HIGH),
    ]


def test_adapter_orders_pivots_and_preserves_same_candle_types():

    merged = merge_price_pivots(
        [
            {"index": 5, "time": 5, "price": 120},
            {"index": 3, "time": 3, "price": 110},
        ],
        [
            {"index": 5, "time": 5, "price": 95},
            {"index": 2, "time": 2, "price": 90},
        ],
    )

    assert [(pivot.index, pivot.type) for pivot in merged] == [
        (2, PivotType.LOW),
        (5, PivotType.HIGH),
        (5, PivotType.LOW),
    ]


def test_divergence_analysis_reuses_pivots_for_adapter(monkeypatch):

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.calculate_rsi_series = lambda _close: pd.Series([40, 45, 50, 55])
    calls = {"price": 0, "rsi": 0}
    highs = [{"index": 3, "time": 4_000, "price": 14}]
    lows = [{"index": 1, "time": 2_000, "price": 10}]

    def fake_price_pivots(*_args, **_kwargs):
        calls["price"] += 1
        return highs, lows

    def fake_rsi_pivots(*_args, **_kwargs):
        calls["rsi"] += 1
        return [], []

    monkeypatch.setattr(ui_module, "find_pivots", fake_price_pivots)
    monkeypatch.setattr(ui_module, "find_rsi_pivots", fake_rsi_pivots)
    monkeypatch.setattr(
        ui_module,
        "find_regular_divergences",
        lambda *_args: [],
    )

    divergences = ui.find_coin_divergences_from_candles(_frame())

    assert calls == {"price": 1, "rsi": 1}
    assert divergences.price_pivots == [
        PricePivot(1, 10, PivotType.LOW),
        PricePivot(3, 14, PivotType.HIGH),
    ]
    assert divergences.rsi_value == 55.0


def test_pipeline_passes_pivots_divergence_and_rsi_but_not_quality_to_evaluator(
    monkeypatch,
):

    divergence = {"type": "bearish", "quality": {"score": 80}}
    divergences = PivotAwareDivergences([divergence], _price_pivots())
    ui = _worker_ui(divergences)
    ui.signal_age = lambda *_args: 1
    ui.signal_status = lambda *_args: ("ACTIVE", "green")
    ui.is_visible_signal = lambda *_args: True
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 57.5)
    monkeypatch.setattr(ui_module, "calculate_quality_score", lambda _quality: 80)
    calls = []

    def evaluator_spy(
        pivots,
        divergence_direction=None,
        rsi_value=None,
        timeframe=None,
    ):
        calls.append((pivots, divergence_direction, rsi_value, timeframe))
        return evaluate_market_structure(
            pivots,
            divergence_direction=divergence_direction,
            rsi_value=rsi_value,
            timeframe=timeframe,
        )

    monkeypatch.setattr(ui_module, "evaluate_market_structure", evaluator_spy)

    result = _run_worker(ui)

    assert calls == [
        (_price_pivots(), DivergenceDirection.BEARISH, 57.5, "1")
    ]
    assert isinstance(result["market_structure"], MarketStructureResult)
    assert result["market_structure"].rsi_value == 57.5
    assert result["quality"] == 80


def test_pipeline_passes_only_the_latest_normalized_pivot_window(monkeypatch):

    high_pivots = [
        {"index": index, "time": index, "price": 100 + index}
        for index in range(1, 25, 2)
    ]
    low_pivots = [
        {"index": index, "time": index, "price": 80 + index}
        for index in range(2, 25, 2)
    ]
    limited_pivots = merge_price_pivots(
        high_pivots,
        low_pivots,
        timeframe="1",
    )
    ui = _worker_ui(PivotAwareDivergences([], limited_pivots))
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 50)
    calls = []

    def evaluator_spy(
        pivots,
        divergence_direction=None,
        rsi_value=None,
        timeframe=None,
    ):
        calls.append((pivots, timeframe))
        return evaluate_market_structure(
            pivots,
            divergence_direction=divergence_direction,
            rsi_value=rsi_value,
            timeframe=timeframe,
        )

    monkeypatch.setattr(ui_module, "evaluate_market_structure", evaluator_spy)

    _run_worker(ui)

    assert len(limited_pivots) == 16
    assert [pivot.index for pivot in limited_pivots] == list(range(9, 25))
    assert calls == [(limited_pivots, "1")]


def test_pipeline_calculates_trend_health_once_from_reused_analysis(monkeypatch):

    divergence = {
        "type": "bearish",
        "quality": {"score": 80},
        "age_candles": 0,
        "confirmed_index": 3,
    }
    divergences = PivotAwareDivergences(
        [divergence],
        _health_price_pivots(),
        rsi_value=57.5,
    )
    ui = _worker_ui(divergences)
    ui.rsi_view_option = type(
        "MarketStructureMode",
        (),
        {"get": lambda self: MARKET_STRUCTURE},
    )()
    calls = {"analysis": 0, "structure": 0, "health": 0}

    def analysis_spy(_candles):
        calls["analysis"] += 1
        return divergences

    def structure_spy(*args, **kwargs):
        calls["structure"] += 1
        return evaluate_market_structure(*args, **kwargs)

    def health_spy(*args, **kwargs):
        calls["health"] += 1
        return evaluate_trend_health(*args, **kwargs)

    ui.find_coin_divergences_from_candles = analysis_spy
    monkeypatch.setattr(ui_module, "calculate_quality_score", lambda _value: 80)
    monkeypatch.setattr(ui_module, "evaluate_market_structure", structure_spy)
    monkeypatch.setattr(ui_module, "evaluate_trend_health", health_spy)

    result = ui.update_watchlist_coin(
        {"symbol": "BTCUSDT"},
        0,
        scan_id=1,
        interval="1",
        total_symbols=1,
        exchange_id="bybit",
        analysis_mode=MARKET_STRUCTURE,
    )

    assert calls == {"analysis": 1, "structure": 1, "health": 1}
    assert isinstance(result["trend_health"], TrendHealthResult)
    assert result["trend_health"].state is TrendHealthState.WEAKENING
    assert result["rsi"] == 57.5
    assert result["quality"] == 80


def test_expired_divergence_is_not_an_active_trend_health_warning():

    ui = SmartTradeUI.__new__(SmartTradeUI)
    ui.signal_status = lambda *_args: ("EXPIRED", "gray")
    divergence = {"type": "bearish"}

    assert (
        ui.active_trend_health_divergence_direction(divergence, 20)
        is None
    )


def test_trend_health_failure_returns_undefined_without_failing_scan(
    monkeypatch,
    capsys,
):

    ui = _worker_ui(
        PivotAwareDivergences([], _health_price_pivots(), rsi_value=50)
    )
    monkeypatch.setattr(
        ui_module,
        "evaluate_trend_health",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("isolated")
        ),
    )

    result = _run_worker(ui)

    assert result["status"] == "no_signal"
    assert result["trend_health"].state is TrendHealthState.UNDEFINED
    assert "Trend Health evaluation failed: RuntimeError: isolated" in (
        capsys.readouterr().out
    )


def test_last_closed_close_ignores_current_open_candle_and_its_wick():

    candles = pd.DataFrame({
        "time": [60, 120],
        "open": [100.0, 102.0],
        "high": [103.0, 110.0],
        "low": [97.0, 90.0],
        "close": [102.0, 91.0],
    })

    close = SmartTradeUI.last_closed_candle_close(
        candles,
        "1",
        now_seconds=150,
    )

    assert close == 102.0


def test_market_structure_is_passive_and_does_not_change_scanner_fields(monkeypatch):

    divergence = {"type": "bullish", "quality": {"score": 88}}
    ui = _worker_ui(PivotAwareDivergences([divergence], _price_pivots()))
    ui.signal_age = lambda *_args: 2
    ui.signal_status = lambda *_args: ("ACTIVE", "green")
    ui.is_visible_signal = lambda *_args: True
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 51)
    monkeypatch.setattr(ui_module, "calculate_quality_score", lambda _quality: 88)

    result = _run_worker(ui)

    assert result["status"] == "signal_found"
    assert result["rsi"] == 51
    assert result["divergence"] is divergence
    assert result["quality"] == 88
    assert result["signal_status"] == "ACTIVE"
    assert result["ui_visible"] is True
    assert isinstance(result["market_structure"], MarketStructureResult)


def test_market_structure_result_is_available_but_not_used_without_divergence(
    monkeypatch,
):

    ui = _worker_ui(PivotAwareDivergences([], _price_pivots()))
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 50)

    result = _run_worker(ui)

    assert result["status"] == "no_signal"
    assert result["quality"] is None
    assert result["ui_visible"] is False
    assert result["market_structure"].state is MarketStructureState.UPTREND
    assert result["market_structure"].divergence_direction is None


def test_pipeline_supports_missing_rsi(monkeypatch):

    ui = _worker_ui(PivotAwareDivergences([], _price_pivots()))
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: None)

    result = _run_worker(ui)

    assert result["status"] == "no_signal"
    assert result["market_structure"].rsi_value is None


def test_market_structure_failure_does_not_change_scanner_result(monkeypatch):

    ui = _worker_ui(PivotAwareDivergences([], _price_pivots()))
    monkeypatch.setattr(ui_module, "calculate_rsi", lambda _frame: 50)
    monkeypatch.setattr(
        ui_module,
        "evaluate_market_structure",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("isolated")),
    )

    result = _run_worker(ui)

    assert result["status"] == "no_signal"
    assert result["rsi"] == 50
    assert result["divergence"] is None
    assert result["quality"] is None
    assert result["market_structure"] is None


def test_market_structure_mode_keeps_internal_divergence_out_of_scanner_fields(
    monkeypatch,
):

    divergence = {"type": "bearish"}
    ui = _worker_ui(PivotAwareDivergences([divergence], _price_pivots()))
    ui.rsi_view_option = type(
        "MarketStructureMode",
        (),
        {"get": lambda self: MARKET_STRUCTURE},
    )()
    monkeypatch.setattr(
        ui_module,
        "calculate_rsi",
        lambda _frame: (_ for _ in ()).throw(
            AssertionError("standalone RSI must stay disabled")
        ),
    )

    result = ui.update_watchlist_coin(
        {"symbol": "BTCUSDT"},
        0,
        scan_id=1,
        interval="1",
        total_symbols=1,
        exchange_id="bybit",
        analysis_mode=MARKET_STRUCTURE,
    )

    assert result["status"] == "no_signal"
    assert result["rsi"] is None
    assert result["divergence"] is None
    assert result["quality"] is None
    assert result["alert_candidate"] is None
    assert result["market_structure"].state is MarketStructureState.UPTREND


def test_market_structure_mode_reuses_existing_rsi_and_quality_context(
    monkeypatch,
):

    divergence = {
        "type": "bearish",
        "quality": {
            "pivot": 100,
            "rsi": 100,
            "distance": 100,
            "volume": 100,
        },
    }
    ui = _worker_ui(
        PivotAwareDivergences(
            [divergence],
            _price_pivots(),
            rsi_value=67.44,
        )
    )
    ui.rsi_view_option = type(
        "MarketStructureMode",
        (),
        {"get": lambda self: MARKET_STRUCTURE},
    )()
    monkeypatch.setattr(
        ui_module,
        "calculate_rsi",
        lambda _frame: (_ for _ in ()).throw(
            AssertionError("RSI must be reused, not recalculated")
        ),
    )

    result = ui.update_watchlist_coin(
        {"symbol": "BTCUSDT"},
        0,
        scan_id=1,
        interval="1",
        total_symbols=1,
        exchange_id="bybit",
        analysis_mode=MARKET_STRUCTURE,
    )

    assert result["rsi"] == 67.44
    assert result["quality"] == 100
    assert result["divergence"] is None
