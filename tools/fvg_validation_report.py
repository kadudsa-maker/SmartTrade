"""Generate a text summary from SmartTrade FVG diagnostics JSONL."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean, median
import sys


def load_records(path, warning_stream=None):
    warning_stream = sys.stderr if warning_stream is None else warning_stream
    records = []
    invalid_lines = 0
    with Path(path).open("r", encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("record is not a JSON object")
            except (json.JSONDecodeError, ValueError) as error:
                invalid_lines += 1
                print(f"Warning: skipped invalid line {number}: {error}", file=warning_stream)
                continue
            records.append(record)
    return records, invalid_lines


def _counter(records, field):
    return Counter(str(item.get(field) or "<missing>") for item in records)


def _gaps(records):
    for record in records:
        for gap in record.get("gaps") or ():
            if isinstance(gap, dict):
                yield record, gap


def count_overlapping_same_direction_pairs(records):
    total = 0
    for record in records:
        groups = {}
        for gap in record.get("gaps") or ():
            if not isinstance(gap, dict):
                continue
            groups.setdefault(gap.get("direction"), []).append(gap)
        for direction, gaps in groups.items():
            if direction not in ("bullish", "bearish"):
                continue
            for index, left in enumerate(gaps):
                for right in gaps[index + 1:]:
                    try:
                        overlaps = max(float(left["lower_price"]), float(right["lower_price"])) <= min(
                            float(left["upper_price"]), float(right["upper_price"])
                        )
                    except (KeyError, TypeError, ValueError):
                        overlaps = False
                    total += int(overlaps)
    return total


def build_summary(records, invalid_lines=0):
    gap_rows = list(_gaps(records))
    gap_counts = [len(record.get("gaps") or ()) for record in records]
    pending_distances = []
    active_symbols = Counter()
    pending_symbols = Counter()
    for record, gap in gap_rows:
        status = gap.get("status")
        symbol = str(record.get("symbol") or "<missing>")
        if status == "ACTIVE":
            active_symbols[symbol] += 1
        elif status == "PENDING":
            pending_symbols[symbol] += 1
            value = gap.get("distance_percent")
            if isinstance(value, (int, float)) and math.isfinite(value):
                pending_distances.append(float(value))
    status_counts = Counter(gap.get("status") for _record, gap in gap_rows)
    direction_counts = Counter(gap.get("direction") for _record, gap in gap_rows)
    return {
        "valid_records": len(records),
        "invalid_lines": invalid_lines,
        "unique_symbols": len({item.get("symbol") for item in records if item.get("symbol")}),
        "by_exchange": _counter(records, "exchange_id"),
        "by_market": _counter(records, "market"),
        "by_timeframe": _counter(records, "timeframe"),
        "total_gaps": len(gap_rows),
        "bullish": direction_counts["bullish"],
        "bearish": direction_counts["bearish"],
        "active": status_counts["ACTIVE"],
        "pending": status_counts["PENDING"],
        "none": status_counts[""] + status_counts["NONE"],
        "average_gaps": mean(gap_counts) if gap_counts else 0.0,
        "median_gaps": median(gap_counts) if gap_counts else 0.0,
        "maximum_gaps": max(gap_counts, default=0),
        "pending_distances": pending_distances,
        "records_without_fvg": gap_counts.count(0),
        "top_active_symbols": active_symbols,
        "top_pending_symbols": pending_symbols,
        "overlapping_same_direction_pairs": count_overlapping_same_direction_pairs(records),
    }


def _format_counter(counter):
    return ", ".join(f"{key}={value}" for key, value in counter.most_common()) or "none"


def _distance_summary(values):
    if not values:
        return "count=0"
    buckets = Counter()
    for value in values:
        if value <= 0.10:
            buckets["0-0.10"] += 1
        elif value <= 0.20:
            buckets["0.10-0.20"] += 1
        elif value <= 0.30:
            buckets["0.20-0.30"] += 1
        else:
            buckets[">0.30"] += 1
    return (
        f"count={len(values)}, mean={mean(values):.6f}, median={median(values):.6f}, "
        f"min={min(values):.6f}, max={max(values):.6f}; buckets: {_format_counter(buckets)}"
    )


def format_report(summary):
    lines = [
        "FVG VALIDATION REPORT",
        f"Valid records: {summary['valid_records']}",
        f"Invalid lines: {summary['invalid_lines']}",
        f"Unique symbols: {summary['unique_symbols']}",
        f"By exchange: {_format_counter(summary['by_exchange'])}",
        f"By market: {_format_counter(summary['by_market'])}",
        f"By timeframe: {_format_counter(summary['by_timeframe'])}",
        f"All gaps: {summary['total_gaps']}",
        f"Directions: bullish={summary['bullish']}, bearish={summary['bearish']}",
        f"Statuses: ACTIVE={summary['active']}, PENDING={summary['pending']}, NONE={summary['none']}",
        f"Gaps per record: mean={summary['average_gaps']:.3f}, median={summary['median_gaps']:.3f}, max={summary['maximum_gaps']}",
        f"PENDING distance_percent: {_distance_summary(summary['pending_distances'])}",
        f"Records without FVG: {summary['records_without_fvg']}",
        f"Top ACTIVE symbols: {_format_counter(summary['top_active_symbols'])}",
        f"Top PENDING symbols: {_format_counter(summary['top_pending_symbols'])}",
        f"Overlapping same-direction pairs: {summary['overlapping_same_direction_pairs']}",
    ]
    return "\n".join(lines)


def generate_report(path, warning_stream=None):
    records, invalid_lines = load_records(path, warning_stream)
    return format_report(build_summary(records, invalid_lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jsonl", type=Path)
    args = parser.parse_args(argv)
    print(generate_report(args.jsonl))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
