from math import isfinite
from numbers import Real
from typing import Sequence

from .models import Candle, FairValueGap, FVGDirection


class FVGDetector:
    """Detect current three-candle FVGs in closed, ordered candles."""

    @staticmethod
    def detect(candles: Sequence[Candle]) -> list[FairValueGap]:
        closed_candles = tuple(candles)
        FVGDetector._validate(closed_candles)

        suffix_low, suffix_high = FVGDetector._build_suffix_extremes(
            closed_candles
        )
        gaps: list[FairValueGap] = []

        for candle3_index in range(2, len(closed_candles)):
            candle1 = closed_candles[candle3_index - 2]
            candle3 = closed_candles[candle3_index]
            later_index = candle3_index + 1

            if candle3.low > candle1.high:
                lower_price = candle1.high
                if suffix_low[later_index] > lower_price:
                    gaps.append(
                        FairValueGap(
                            direction=FVGDirection.BULLISH,
                            candle1_time=candle1.time,
                            candle3_time=candle3.time,
                            lower_price=lower_price,
                            upper_price=candle3.low,
                        )
                    )
                continue

            if candle3.high < candle1.low:
                upper_price = candle1.low
                if suffix_high[later_index] < upper_price:
                    gaps.append(
                        FairValueGap(
                            direction=FVGDirection.BEARISH,
                            candle1_time=candle1.time,
                            candle3_time=candle3.time,
                            lower_price=candle3.high,
                            upper_price=upper_price,
                        )
                    )

        return gaps

    @staticmethod
    def _build_suffix_extremes(
        candles: tuple[Candle, ...],
    ) -> tuple[list[float], list[float]]:
        candle_count = len(candles)
        suffix_low = [float("inf")] * (candle_count + 1)
        suffix_high = [float("-inf")] * (candle_count + 1)

        for index in range(candle_count - 1, -1, -1):
            suffix_low[index] = min(candles[index].low, suffix_low[index + 1])
            suffix_high[index] = max(
                candles[index].high, suffix_high[index + 1]
            )

        return suffix_low, suffix_high

    @staticmethod
    def _validate(candles: tuple[Candle, ...]) -> None:
        if len(candles) < 3:
            raise ValueError("FVG detection requires at least three candles.")

        previous_time: int | None = None
        for index, candle in enumerate(candles):
            if not isinstance(candle, Candle):
                raise ValueError(f"Candle at index {index} has an invalid type.")

            if not isinstance(candle.time, int) or isinstance(candle.time, bool):
                raise ValueError(f"Candle at index {index} has an invalid time.")

            if previous_time is not None and candle.time <= previous_time:
                raise ValueError("Candle times must be unique and strictly increasing.")

            prices = (candle.open, candle.high, candle.low, candle.close)
            if any(
                not isinstance(price, Real)
                or isinstance(price, bool)
                or not isfinite(float(price))
                for price in prices
            ):
                raise ValueError(
                    f"Candle at index {index} contains a non-finite price."
                )

            if candle.high < candle.low:
                raise ValueError(f"Candle at index {index} has high below low.")

            if not candle.low <= candle.open <= candle.high:
                raise ValueError(
                    f"Candle at index {index} has open outside its range."
                )

            if not candle.low <= candle.close <= candle.high:
                raise ValueError(
                    f"Candle at index {index} has close outside its range."
                )

            previous_time = candle.time
