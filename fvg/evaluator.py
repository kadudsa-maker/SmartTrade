from math import isfinite
from numbers import Real
from typing import Sequence

from .models import (
    Candle,
    EvaluatedFVG,
    FairValueGap,
    FVGOpportunityStatus,
)


class FVGEvaluator:
    @staticmethod
    def evaluate(
        gaps: Sequence[FairValueGap],
        current_candle: Candle,
        previous_candle: Candle,
        pending_distance_percent: float = 0.30,
    ) -> list[EvaluatedFVG]:
        current_price = FVGEvaluator._validated_price(
            current_candle, "current"
        )
        previous_price = FVGEvaluator._validated_price(
            previous_candle, "previous"
        )
        threshold = FVGEvaluator._validated_threshold(
            pending_distance_percent
        )
        evaluated: list[EvaluatedFVG] = []

        for gap in tuple(gaps):
            FVGEvaluator._validate_gap(gap)

            distance_now = FVGEvaluator._distance_to_gap(current_price, gap)
            if distance_now == 0.0:
                evaluated.append(
                    EvaluatedFVG(
                        gap=gap,
                        status=FVGOpportunityStatus.ACTIVE,
                        distance_percent=0.0,
                    )
                )
                continue

            distance_percent = distance_now / current_price * 100.0
            distance_previous = FVGEvaluator._distance_to_gap(
                previous_price, gap
            )
            status = FVGOpportunityStatus.NONE
            if (
                distance_percent <= threshold
                and distance_now < distance_previous
            ):
                status = FVGOpportunityStatus.PENDING

            evaluated.append(
                EvaluatedFVG(
                    gap=gap,
                    status=status,
                    distance_percent=distance_percent,
                )
            )

        return evaluated

    @staticmethod
    def _distance_to_gap(price: float, gap: FairValueGap) -> float:
        if price < gap.lower_price:
            return gap.lower_price - price
        if price > gap.upper_price:
            return price - gap.upper_price
        return 0.0

    @staticmethod
    def _validated_price(candle: Candle, label: str) -> float:
        if not isinstance(candle, Candle):
            raise ValueError(f"The {label} candle has an invalid type.")

        price = candle.close
        if (
            not isinstance(price, Real)
            or isinstance(price, bool)
            or not isfinite(float(price))
            or price <= 0
        ):
            raise ValueError(
                f"The {label} candle close must be positive and finite."
            )
        return float(price)

    @staticmethod
    def _validated_threshold(value: float) -> float:
        if (
            not isinstance(value, Real)
            or isinstance(value, bool)
            or not isfinite(float(value))
            or value < 0
        ):
            raise ValueError(
                "The pending distance percent must be non-negative and finite."
            )
        return float(value)

    @staticmethod
    def _validate_gap(gap: FairValueGap) -> None:
        if not isinstance(gap, FairValueGap):
            raise ValueError("The evaluated gap has an invalid type.")

        boundaries = (gap.lower_price, gap.upper_price)
        if any(
            not isinstance(boundary, Real)
            or isinstance(boundary, bool)
            or not isfinite(float(boundary))
            for boundary in boundaries
        ):
            raise ValueError("FVG boundaries must be finite numbers.")

        if gap.lower_price >= gap.upper_price:
            raise ValueError(
                "FVG lower price must be below its upper price."
            )
