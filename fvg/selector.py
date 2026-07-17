from math import isfinite
from numbers import Real
from typing import Sequence

from .models import Candle, EvaluatedFVG, FVGOpportunityStatus


class FVGSelector:
    @staticmethod
    def select(
        evaluated_gaps: Sequence[EvaluatedFVG],
        current_candle: Candle,
    ) -> EvaluatedFVG | None:
        current_price = FVGSelector._validated_current_price(current_candle)
        candidates = tuple(evaluated_gaps)

        active = tuple(
            item
            for item in candidates
            if item.status is FVGOpportunityStatus.ACTIVE
        )
        if active:
            return min(
                active,
                key=lambda item: FVGSelector._active_key(
                    item, current_price
                ),
            )

        pending = tuple(
            item
            for item in candidates
            if item.status is FVGOpportunityStatus.PENDING
        )
        if pending:
            for item in pending:
                FVGSelector._validate_pending_distance(item)
            return min(pending, key=FVGSelector._pending_key)

        return None

    @staticmethod
    def _active_key(
        evaluated: EvaluatedFVG,
        current_price: float,
    ) -> tuple[float, int, int, float, float, str]:
        gap = evaluated.gap
        midpoint = (gap.lower_price + gap.upper_price) / 2.0
        return (
            abs(midpoint - current_price),
            -gap.candle3_time,
            -gap.candle1_time,
            gap.lower_price,
            gap.upper_price,
            gap.direction.value,
        )

    @staticmethod
    def _pending_key(
        evaluated: EvaluatedFVG,
    ) -> tuple[float, int, int, float, float, str]:
        gap = evaluated.gap
        return (
            float(evaluated.distance_percent),
            -gap.candle3_time,
            -gap.candle1_time,
            gap.lower_price,
            gap.upper_price,
            gap.direction.value,
        )

    @staticmethod
    def _validated_current_price(candle: Candle) -> float:
        if not isinstance(candle, Candle):
            raise ValueError("The current candle has an invalid type.")

        price = candle.close
        if (
            not isinstance(price, Real)
            or isinstance(price, bool)
            or not isfinite(float(price))
            or price <= 0
        ):
            raise ValueError(
                "The current candle close must be positive and finite."
            )
        return float(price)

    @staticmethod
    def _validate_pending_distance(evaluated: EvaluatedFVG) -> None:
        distance = evaluated.distance_percent
        if (
            not isinstance(distance, Real)
            or isinstance(distance, bool)
            or not isfinite(float(distance))
            or distance < 0
        ):
            raise ValueError(
                "A pending FVG requires a non-negative finite distance."
            )
