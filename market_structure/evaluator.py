import math
from collections.abc import Sequence
from types import MappingProxyType

from .adapter import normalize_price_pivots
from .models import (
    DivergenceDirection,
    MarketStructureResult,
    MarketStructureState,
    PivotType,
    PricePivot,
    PriceStructure,
    SemanticColor,
    Strength,
    TrendDirection,
)


STATE_COLOR_KEYS = MappingProxyType({
    MarketStructureState.UPTREND: SemanticColor.POSITIVE,
    MarketStructureState.POTENTIAL_DISTRIBUTION: SemanticColor.WARNING,
    MarketStructureState.DOWNTREND_CONFIRMED: SemanticColor.NEGATIVE,
    MarketStructureState.DOWNTREND: SemanticColor.NEGATIVE,
    MarketStructureState.POTENTIAL_ACCUMULATION: SemanticColor.ACCUMULATION,
    MarketStructureState.UPTREND_CONFIRMED: SemanticColor.POSITIVE,
    MarketStructureState.UNDEFINED: SemanticColor.NEUTRAL,
})


def evaluate_market_structure(
    pivots: Sequence[PricePivot],
    divergence_direction: DivergenceDirection | None = None,
    rsi_value: float | None = None,
    timeframe: str | None = None,
) -> MarketStructureResult:
    """Classify a short, ordered sequence of confirmed price pivots.

    The function does not mutate or retain ``pivots``. Transition states are
    deliberately conservative: they require a previously confirmed trend and
    both latest price relations to reverse.
    """

    pivot_snapshot = tuple(
        normalize_price_pivots(pivots, timeframe=timeframe)
    )

    if not _valid_pivots(pivot_snapshot):
        return _result(
            MarketStructureState.UNDEFINED,
            TrendDirection.NONE,
            Strength.LOW,
            "Invalid pivot sequence",
            PriceStructure.INSUFFICIENT_DATA,
            divergence_direction,
            rsi_value,
        )

    highs = tuple(pivot for pivot in pivot_snapshot if pivot.type is PivotType.HIGH)
    lows = tuple(pivot for pivot in pivot_snapshot if pivot.type is PivotType.LOW)

    if len(highs) < 2 or len(lows) < 2:
        return _result(
            MarketStructureState.UNDEFINED,
            TrendDirection.NONE,
            Strength.LOW,
            "Insufficient pivots",
            PriceStructure.INSUFFICIENT_DATA,
            divergence_direction,
            rsi_value,
        )

    latest_high = _relation(highs[-2].price, highs[-1].price)
    latest_low = _relation(lows[-2].price, lows[-1].price)
    prior_high = _prior_relation(highs)
    prior_low = _prior_relation(lows)

    previous_uptrend = prior_high == 1 and prior_low == 1
    previous_downtrend = prior_high == -1 and prior_low == -1

    if (
        previous_uptrend
        and latest_high == -1
        and latest_low == -1
        and highs[-1].index < lows[-1].index
    ):
        return _result(
            MarketStructureState.DOWNTREND_CONFIRMED,
            TrendDirection.UP,
            Strength.HIGH,
            "Recent bearish structure break confirmed",
            PriceStructure.BREAKDOWN_CONFIRMED,
            divergence_direction,
            rsi_value,
            protected_pivot=lows[-2],
        )

    if (
        previous_downtrend
        and latest_high == 1
        and latest_low == 1
        and lows[-1].index < highs[-1].index
    ):
        return _result(
            MarketStructureState.UPTREND_CONFIRMED,
            TrendDirection.DOWN,
            Strength.HIGH,
            "Recent bullish structure break confirmed",
            PriceStructure.BREAKOUT_CONFIRMED,
            divergence_direction,
            rsi_value,
            protected_pivot=highs[-2],
        )

    if (
        divergence_direction is DivergenceDirection.BEARISH
        and prior_high == 1
        and latest_high <= 0
        and latest_low == 1
    ):
        return _result(
            MarketStructureState.POTENTIAL_DISTRIBUTION,
            TrendDirection.UP,
            Strength.MEDIUM,
            "Bearish divergence after uptrend",
            PriceStructure.FIRST_LOWER_HIGH,
            divergence_direction,
            rsi_value,
            protected_pivot=lows[-1],
        )

    if (
        divergence_direction is DivergenceDirection.BULLISH
        and prior_low == -1
        and latest_low >= 0
        and latest_high == -1
    ):
        return _result(
            MarketStructureState.POTENTIAL_ACCUMULATION,
            TrendDirection.DOWN,
            Strength.MEDIUM,
            "Bullish divergence after downtrend",
            PriceStructure.FIRST_HIGHER_LOW,
            divergence_direction,
            rsi_value,
            protected_pivot=highs[-1],
        )

    if latest_high == 1 and latest_low == 1:
        return _result(
            MarketStructureState.UPTREND,
            TrendDirection.UP,
            Strength.MEDIUM,
            "HH + HL active sequence",
            PriceStructure.HIGHER_HIGH_HIGHER_LOW,
            divergence_direction,
            rsi_value,
            protected_pivot=lows[-1],
        )

    if latest_high == -1 and latest_low == -1:
        return _result(
            MarketStructureState.DOWNTREND,
            TrendDirection.DOWN,
            Strength.MEDIUM,
            "LH + LL active sequence",
            PriceStructure.LOWER_HIGH_LOWER_LOW,
            divergence_direction,
            rsi_value,
            protected_pivot=highs[-1],
        )

    return _result(
        MarketStructureState.UNDEFINED,
        TrendDirection.NONE,
        Strength.LOW,
        "Mixed recent pivot sequence",
        PriceStructure.MIXED,
        divergence_direction,
        rsi_value,
    )


def _valid_pivots(pivots: tuple[PricePivot, ...]) -> bool:
    previous_index = None
    seen_pivots = set()

    for pivot in pivots:
        if not isinstance(pivot, PricePivot):
            return False
        if not isinstance(pivot.type, PivotType):
            return False
        if isinstance(pivot.index, bool) or not isinstance(pivot.index, int):
            return False
        if previous_index is not None and pivot.index < previous_index:
            return False
        identity = (pivot.index, pivot.type)
        if identity in seen_pivots:
            return False
        if isinstance(pivot.price, bool) or not isinstance(pivot.price, (int, float)):
            return False
        if not math.isfinite(pivot.price):
            return False
        seen_pivots.add(identity)
        previous_index = pivot.index

    return True


def _relation(previous: float, current: float) -> int:
    if current > previous:
        return 1
    if current < previous:
        return -1
    return 0


def _prior_relation(pivots: tuple[PricePivot, ...]) -> int | None:
    if len(pivots) < 3:
        return None
    return _relation(pivots[-3].price, pivots[-2].price)


def _result(
    state: MarketStructureState,
    previous_trend: TrendDirection,
    strength: Strength,
    reason: str,
    price_structure: PriceStructure,
    divergence_direction: DivergenceDirection | None,
    rsi_value: float | None,
    protected_pivot: PricePivot | None = None,
) -> MarketStructureResult:
    return MarketStructureResult(
        state=state,
        previous_trend=previous_trend,
        strength=strength,
        reason=reason,
        price_structure=price_structure,
        divergence_direction=divergence_direction,
        rsi_value=rsi_value,
        color_key=STATE_COLOR_KEYS[state],
        protected_level=(
            protected_pivot.price
            if protected_pivot is not None
            else None
        ),
        protected_pivot_index=(
            protected_pivot.index
            if protected_pivot is not None
            else None
        ),
    )
