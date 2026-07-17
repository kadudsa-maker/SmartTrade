import io
import json

from tools.fvg_validation_report import (
    build_summary,
    count_overlapping_same_direction_pairs,
    generate_report,
    load_records,
)


def gap(direction="bullish", status="ACTIVE", lower=100, upper=101, distance=None):
    return {
        "direction": direction, "candle1_time": 1, "candle3_time": 3,
        "lower_price": lower, "upper_price": upper, "status": status,
        "distance_percent": distance,
    }


def record(symbol="BTC", gaps=None, exchange="bybit", market="futures", timeframe="15"):
    return {
        "symbol": symbol, "gaps": list(gaps or ()), "exchange_id": exchange,
        "market": market, "timeframe": timeframe,
    }


def test_report_handles_empty_file(tmp_path):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    report = generate_report(path)
    assert "Valid records: 0" in report
    assert "All gaps: 0" in report


def test_report_skips_invalid_line_with_warning(tmp_path):
    path = tmp_path / "mixed.jsonl"
    path.write_text(json.dumps(record()) + "\n{broken\n", encoding="utf-8")
    warnings = io.StringIO()
    records, invalid = load_records(path, warnings)
    assert len(records) == 1
    assert invalid == 1
    assert "line 2" in warnings.getvalue()


def test_report_counts_directions_and_statuses():
    summary = build_summary([
        record(gaps=[gap(), gap("bearish", "PENDING", distance=0.2), gap(status="")])
    ])
    assert (summary["bullish"], summary["bearish"]) == (2, 1)
    assert (summary["active"], summary["pending"], summary["none"]) == (1, 1, 1)


def test_report_counts_mean_median_and_maximum():
    summary = build_summary([
        record("A", []), record("B", [gap()]), record("C", [gap(), gap()]),
    ])
    assert summary["average_gaps"] == 1
    assert summary["median_gaps"] == 1
    assert summary["maximum_gaps"] == 2


def test_report_detects_overlapping_same_direction_pairs_only():
    records = [record(gaps=[
        gap("bullish", lower=100, upper=102),
        gap("bullish", lower=101, upper=103),
        gap("bearish", lower=101, upper=103),
    ])]
    assert count_overlapping_same_direction_pairs(records) == 1


def test_report_counts_active_and_pending_symbols():
    summary = build_summary([
        record("BTC", [gap(status="ACTIVE"), gap(status="PENDING", distance=0.1)]),
        record("BTC", [gap(status="ACTIVE")]),
        record("ETH", [gap(status="PENDING", distance=0.2)]),
    ])
    assert summary["top_active_symbols"]["BTC"] == 2
    assert summary["top_pending_symbols"] == {"BTC": 1, "ETH": 1}


def test_report_groups_exchange_market_timeframe_and_no_fvg():
    summary = build_summary([
        record("A"), record("B", [gap()], "okx", "spot", "60"),
    ])
    assert summary["by_exchange"] == {"bybit": 1, "okx": 1}
    assert summary["by_market"] == {"futures": 1, "spot": 1}
    assert summary["by_timeframe"] == {"15": 1, "60": 1}
    assert summary["records_without_fvg"] == 1


def test_report_includes_pending_distance_distribution(tmp_path):
    path = tmp_path / "pending.jsonl"
    path.write_text(json.dumps(record(gaps=[gap(status="PENDING", distance=0.25)])), encoding="utf-8")
    report = generate_report(path)
    assert "PENDING distance_percent: count=1" in report
    assert "0.20-0.30=1" in report
