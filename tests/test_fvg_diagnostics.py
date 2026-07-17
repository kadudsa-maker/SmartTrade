import json
import math

import pytest

from fvg import (
    Candle,
    EvaluatedFVG,
    FairValueGap,
    FVGDirection,
    FVGOpportunityStatus,
    FVGScanResult,
    FVGService,
)
from fvg import diagnostics


def candles():
    return (
        Candle(100, 95, 100, 90, 95),
        Candle(160, 98, 102, 95, 98),
        Candle(220, 103, 105, 101, 103),
    )


def result(status=FVGOpportunityStatus.ACTIVE, distance=None):
    gap = FairValueGap(FVGDirection.BULLISH, 100, 220, 100.0, 101.0)
    evaluated = EvaluatedFVG(gap, status, distance)
    selected = evaluated if status is not FVGOpportunityStatus.NONE else None
    return FVGScanResult(100.5, (evaluated,), selected, status)


def fields(scan_result=None):
    items = candles()
    return {
        "source": "scanner",
        "exchange_id": "bybit",
        "market": "Bybit Futures",
        "symbol": "BTCUSDT",
        "timeframe": "15",
        "scan_id": 7,
        "input_candles_count": 4,
        "closed_candles": items,
        "latest_candle": items[-1],
        "latest_candle_was_open": False,
        "current_candle": items[-1],
        "previous_candle": items[-2],
        "result": scan_result or result(),
    }


def test_diagnostics_are_disabled_by_default():
    assert diagnostics.FVG_DIAGNOSTICS_ENABLED is False


def test_disabled_diagnostics_do_not_create_file(tmp_path):
    path = tmp_path / "diagnostics.jsonl"
    assert diagnostics.record_analysis(path=path, **fields()) is None
    assert not path.exists()


def test_disabled_diagnostics_do_not_resolve_default_path(monkeypatch):
    monkeypatch.setattr(diagnostics, "diagnostics_path", lambda: (_ for _ in ()).throw(AssertionError))
    diagnostics.record_analysis(**fields())


def test_disabled_diagnostics_do_not_change_service_result(tmp_path):
    items = candles()
    before = FVGService().analyze(items, items[-1], items[-2])
    diagnostics.record_analysis(path=tmp_path / "x.jsonl", **fields(before))
    after = FVGService().analyze(items, items[-1], items[-2])
    assert diagnostics.results_match(before, after)


def test_enabled_diagnostics_create_one_valid_json_line(tmp_path):
    path = tmp_path / "diagnostics.jsonl"
    diagnostics.record_analysis(enabled=True, path=path, **fields())
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["symbol"] == "BTCUSDT"


@pytest.mark.parametrize(
    "field",
    [
        "timestamp", "source", "exchange_id", "market", "symbol", "timeframe",
        "scan_id", "input_candles_count", "closed_candles_count",
        "latest_candle_time", "latest_candle_was_open", "current_candle_time",
        "current_candle_close", "previous_candle_time", "previous_candle_close",
        "gaps_count", "bullish_count", "bearish_count", "active_count",
        "pending_count", "none_count", "selected_fvg", "gaps",
    ],
)
def test_record_contains_required_field(field):
    assert field in diagnostics.build_record(**fields())


def test_record_contains_every_current_gap():
    first = result().gaps[0]
    bearish_gap = FairValueGap(FVGDirection.BEARISH, 160, 280, 98, 99)
    second = EvaluatedFVG(bearish_gap, FVGOpportunityStatus.PENDING, 0.2)
    scan_result = FVGScanResult(100.5, (first, second), first, FVGOpportunityStatus.ACTIVE)
    assert len(diagnostics.build_record(**fields(scan_result))["gaps"]) == 2


def test_selected_fvg_is_fully_serialized():
    selected = diagnostics.build_record(**fields())["selected_fvg"]
    assert selected == {
        "direction": "bullish", "candle1_time": 100, "candle3_time": 220,
        "lower_price": 100.0, "upper_price": 101.0, "status": "ACTIVE",
        "distance_percent": None,
    }


def test_missing_selected_fvg_is_null():
    scan_result = FVGScanResult(100.5, (), None, FVGOpportunityStatus.NONE)
    assert diagnostics.build_record(**fields(scan_result))["selected_fvg"] is None


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_nonfinite_values_are_serialized_as_null(tmp_path, invalid):
    scan_result = result(FVGOpportunityStatus.PENDING, invalid)
    path = tmp_path / "diagnostics.jsonl"
    diagnostics.record_analysis(enabled=True, path=path, **fields(scan_result))
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["gaps"][0]["distance_percent"] is None


def test_multiple_analyses_append_separate_lines(tmp_path):
    path = tmp_path / "diagnostics.jsonl"
    for _ in range(3):
        diagnostics.record_analysis(enabled=True, path=path, **fields())
    assert len(path.read_text(encoding="utf-8").splitlines()) == 3


def test_write_error_is_reported_and_does_not_escape(tmp_path, capsys):
    result_value = diagnostics.record_analysis(enabled=True, path=tmp_path, **fields())
    output = capsys.readouterr().out
    assert result_value is None
    assert "symbol=BTCUSDT" in output
    assert "timeframe=15" in output
    assert "error_type=" in output


def test_result_comparator_covers_selected_fvg():
    assert diagnostics.results_match(result(), result())
    assert not diagnostics.results_match(result(), result(FVGOpportunityStatus.NONE))


def test_scanner_and_chart_service_paths_match_for_identical_candles():
    items = candles()
    scanner = FVGService().analyze(items, items[-1], items[-2])
    chart = FVGService().analyze(items, items[-1], items[-2])
    assert diagnostics.result_signature(scanner) == diagnostics.result_signature(chart)
