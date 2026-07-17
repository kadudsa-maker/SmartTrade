"""Opt-in JSONL diagnostics for manual FVG market validation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any, Sequence

from app_paths import runtime_path

from .models import Candle, EvaluatedFVG, FVGScanResult


FVG_DIAGNOSTICS_ENABLED = False
FVG_DIAGNOSTICS_FILENAME = "fvg_diagnostics.jsonl"


def diagnostics_path() -> Path:
    return runtime_path("logs", FVG_DIAGNOSTICS_FILENAME)


def normalize_enum(value: Any) -> Any:
    return getattr(value, "value", value)


def _finite_or_none(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _sanitize(value: Any) -> Any:
    value = normalize_enum(value)
    if isinstance(value, dict):
        return {str(key): _sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return _finite_or_none(value)


def serialize_gap(evaluated: EvaluatedFVG | None) -> dict[str, Any] | None:
    if evaluated is None:
        return None
    gap = evaluated.gap
    return {
        "direction": normalize_enum(gap.direction),
        "candle1_time": gap.candle1_time,
        "candle3_time": gap.candle3_time,
        "lower_price": gap.lower_price,
        "upper_price": gap.upper_price,
        "status": normalize_enum(evaluated.status),
        "distance_percent": evaluated.distance_percent,
    }


def result_signature(result: FVGScanResult) -> dict[str, Any]:
    """Return the production fields that scanner/chart parity tests compare."""
    return {
        "gaps": [serialize_gap(item) for item in result.gaps],
        "selected_fvg": serialize_gap(result.selected_fvg),
    }


def results_match(left: FVGScanResult, right: FVGScanResult) -> bool:
    return result_signature(left) == result_signature(right)


def build_record(
    *,
    source: str,
    exchange_id: str,
    market: str,
    symbol: str,
    timeframe: str,
    scan_id: int | None,
    input_candles_count: int,
    closed_candles: Sequence[Candle],
    latest_candle: Candle,
    latest_candle_was_open: bool,
    current_candle: Candle,
    previous_candle: Candle,
    result: FVGScanResult,
) -> dict[str, Any]:
    gaps = [serialize_gap(item) for item in result.gaps]
    statuses = [item["status"] for item in gaps]
    directions = [item["direction"] for item in gaps]
    return _sanitize(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "exchange_id": exchange_id,
            "market": market,
            "symbol": symbol,
            "timeframe": timeframe,
            "scan_id": scan_id,
            "input_candles_count": input_candles_count,
            "closed_candles_count": len(closed_candles),
            "latest_candle_time": latest_candle.time,
            "latest_candle_was_open": bool(latest_candle_was_open),
            "current_candle_time": current_candle.time,
            "current_candle_close": current_candle.close,
            "previous_candle_time": previous_candle.time,
            "previous_candle_close": previous_candle.close,
            "gaps_count": len(gaps),
            "bullish_count": directions.count("bullish"),
            "bearish_count": directions.count("bearish"),
            "active_count": statuses.count("ACTIVE"),
            "pending_count": statuses.count("PENDING"),
            "none_count": statuses.count(""),
            "selected_fvg": serialize_gap(result.selected_fvg),
            "gaps": gaps,
        }
    )


def record_analysis(*, enabled: bool | None = None, path: Path | None = None, **fields):
    """Append one record when enabled; a write failure is isolated and reported."""
    if enabled is None:
        enabled = FVG_DIAGNOSTICS_ENABLED
    if not enabled:
        return None

    try:
        record = build_record(**fields)
        target = diagnostics_path() if path is None else Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(record, ensure_ascii=False, allow_nan=False)
        with target.open("a", encoding="utf-8") as stream:
            stream.write(payload + "\n")
    except Exception as error:
        print(
            "FVG diagnostics write error: "
            f"symbol={fields.get('symbol')} "
            f"timeframe={fields.get('timeframe')} "
            f"error_type={type(error).__name__} "
            f"error_message={error}"
        )
        return None
    return record
