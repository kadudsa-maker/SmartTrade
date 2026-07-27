from collections.abc import Iterable, Mapping
import math
from typing import Any

from .config import get_market_structure_pivot_window
from .models import PivotType, PricePivot


def merge_price_pivots(
    high_pivots: Iterable[Mapping[str, Any]],
    low_pivots: Iterable[Mapping[str, Any]],
    timeframe: str | None = None,
) -> list[PricePivot]:
    """Adapt existing price-pivot dictionaries into one ordered sequence."""

    pivots = [
        PricePivot(
            index=int(pivot["index"]),
            price=float(pivot["price"]),
            type=PivotType.HIGH,
        )
        for pivot in high_pivots
    ]
    pivots.extend(
        PricePivot(
            index=int(pivot["index"]),
            price=float(pivot["price"]),
            type=PivotType.LOW,
        )
        for pivot in low_pivots
    )

    return normalize_price_pivots(pivots, timeframe=timeframe)


def normalize_price_pivots(
    pivots: Iterable[PricePivot],
    timeframe: str | None = None,
) -> list[PricePivot]:
    """Return recent, valid, chronological and alternating price pivots."""

    unique_pivots = {}

    for pivot in pivots:
        if not _is_valid_pivot(pivot):
            continue

        identity = (pivot.index, pivot.type)
        current = unique_pivots.get(identity)
        if current is None or _is_more_extreme(pivot, current):
            unique_pivots[identity] = pivot

    chronological = sorted(
        unique_pivots.values(),
        key=lambda pivot: (pivot.index, pivot.type.value),
    )
    alternating = []

    for pivot in chronological:
        if alternating and alternating[-1].type is pivot.type:
            if _is_more_extreme(pivot, alternating[-1]):
                alternating[-1] = pivot
            continue
        alternating.append(pivot)

    window = get_market_structure_pivot_window(timeframe)
    return alternating[-window:]


def _is_valid_pivot(pivot):
    if not isinstance(pivot, PricePivot):
        return False
    if not isinstance(pivot.type, PivotType):
        return False
    if isinstance(pivot.index, bool) or not isinstance(pivot.index, int):
        return False
    if pivot.index < 0:
        return False
    if isinstance(pivot.price, bool) or not isinstance(pivot.price, (int, float)):
        return False
    return math.isfinite(pivot.price)


def _is_more_extreme(candidate, current):
    if candidate.type is PivotType.HIGH:
        return candidate.price > current.price
    return candidate.price < current.price
