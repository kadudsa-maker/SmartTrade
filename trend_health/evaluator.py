import math

from market_structure import (
    DivergenceDirection,
    MarketStructureResult,
    MarketStructureState,
)

from .models import TrendHealthResult, TrendHealthState


_UP_STATES = {
    MarketStructureState.UPTREND,
    MarketStructureState.POTENTIAL_DISTRIBUTION,
    MarketStructureState.DOWNTREND_CONFIRMED,
}
_DOWN_STATES = {
    MarketStructureState.DOWNTREND,
    MarketStructureState.POTENTIAL_ACCUMULATION,
    MarketStructureState.UPTREND_CONFIRMED,
}
_CONFIRMED_STATES = {
    MarketStructureState.DOWNTREND_CONFIRMED,
    MarketStructureState.UPTREND_CONFIRMED,
}


def evaluate_trend_health(
    market_structure: MarketStructureResult,
    last_closed_close: float | None,
    divergence_direction: DivergenceDirection | None = None,
    rsi_value: float | None = None,
) -> TrendHealthResult:
    """Describe the health of the active formal price structure.

    ``rsi_value`` is accepted as passive context only. Version 1 deliberately
    applies no RSI thresholds or scoring.
    """

    if not isinstance(market_structure, MarketStructureResult):
        return undefined_trend_health("No active structure")

    state = market_structure.state
    if state is MarketStructureState.UNDEFINED:
        return undefined_trend_health("No active structure")
    if state not in _UP_STATES and state not in _DOWN_STATES:
        return undefined_trend_health("No active structure")

    protected_level = market_structure.protected_level
    protected_index = market_structure.protected_pivot_index
    if not _is_finite_number(protected_level) or not _is_valid_index(
        protected_index
    ):
        return undefined_trend_health("Protected level unavailable")
    if not _is_finite_number(last_closed_close):
        return undefined_trend_health("Closed candle unavailable")

    if state in _UP_STATES and last_closed_close < protected_level:
        return _result(
            TrendHealthState.BREAKING,
            "Close below protected HL",
            market_structure,
        )
    if state in _DOWN_STATES and last_closed_close > protected_level:
        return _result(
            TrendHealthState.BREAKING,
            "Close above protected LH",
            market_structure,
        )

    if state in _CONFIRMED_STATES:
        reason = (
            "Confirmed bearish structure transition"
            if state is MarketStructureState.DOWNTREND_CONFIRMED
            else "Confirmed bullish structure transition"
        )
        return _result(TrendHealthState.BREAKING, reason, market_structure)

    if state is MarketStructureState.POTENTIAL_DISTRIBUTION:
        return _result(
            TrendHealthState.WEAKENING,
            "Potential distribution, structure intact",
            market_structure,
        )
    if state is MarketStructureState.POTENTIAL_ACCUMULATION:
        return _result(
            TrendHealthState.WEAKENING,
            "Potential accumulation, structure intact",
            market_structure,
        )

    if (
        state is MarketStructureState.UPTREND
        and divergence_direction is DivergenceDirection.BEARISH
    ):
        return _result(
            TrendHealthState.WEAKENING,
            "Bearish divergence, protected HL intact",
            market_structure,
        )
    if (
        state is MarketStructureState.DOWNTREND
        and divergence_direction is DivergenceDirection.BULLISH
    ):
        return _result(
            TrendHealthState.WEAKENING,
            "Bullish divergence, protected LH intact",
            market_structure,
        )

    return _result(
        TrendHealthState.HEALTHY,
        "Structure intact, no active warning",
        market_structure,
    )


def undefined_trend_health(reason="No active structure"):
    return TrendHealthResult(
        state=TrendHealthState.UNDEFINED,
        reason=reason,
    )


def _result(state, reason, market_structure):
    return TrendHealthResult(
        state=state,
        reason=reason,
        protected_level=market_structure.protected_level,
        protected_pivot_index=market_structure.protected_pivot_index,
    )


def _is_finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return math.isfinite(value)


def _is_valid_index(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
